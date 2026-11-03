<?php

declare(strict_types=1);

namespace App\Services\Tiles;

use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use RuntimeException;

/**
 * Serves the `tiles.*` MVT functions from the app, the way Martin does
 * (`TILES_DRIVER=app`; contract docs/schemas/atlas-tiles.md).
 *
 * A source (config/tiles.php) is a PostGIS function
 * `(z, x, y) RETURNS TABLE (mvt bytea, key text)`; its JSON comment carries
 * the TileJSON `vector_layers`. Rendered tiles are kept in the cache store for
 * `tiles.cache_ttl` seconds, like Martin's in-memory cache.
 */
class TileServer
{
    /** @return array<string, array{function: string, minzoom: int, maxzoom: int}> */
    public function sources(): array
    {
        $sources = [];
        foreach ((array) config('tiles.sources', []) as $name => $source) {
            $sources[(string) $name] = [
                'function' => (string) $source['function'],
                'minzoom' => (int) ($source['minzoom'] ?? 0),
                'maxzoom' => (int) ($source['maxzoom'] ?? 30),
            ];
        }

        return $sources;
    }

    public function has(string $source): bool
    {
        return array_key_exists($source, $this->sources());
    }

    /** @throws UnknownTileSource */
    public function tile(string $source, int $z, int $x, int $y): Tile
    {
        $function = $this->functionFor($source);
        $ttl = (int) config('tiles.cache_ttl', 0);

        $render = function () use ($function, $z, $x, $y): array {
            $row = DB::selectOne("SELECT mvt, key FROM {$function}(?, ?, ?)", [$z, $x, $y]);

            return [
                'mvt' => self::binary($row?->mvt),
                'key' => (string) ($row?->key ?? md5('')),
            ];
        };

        $tile = $ttl > 0
            ? Cache::remember("tiles:{$source}:{$z}/{$x}/{$y}", $ttl, $render)
            : $render();

        return new Tile($tile['mvt'], $tile['key']);
    }

    /**
     * TileJSON 3.0.0 for a source, like Martin's: `tiles` is built from the
     * caller's URL template, `vector_layers` from the function's comment.
     *
     * @return array<string, mixed>
     *
     * @throws UnknownTileSource
     */
    public function tileJson(string $source, string $tileUrlTemplate): array
    {
        $function = $this->functionFor($source);
        $meta = $this->sources()[$source];

        return [
            'tilejson' => '3.0.0',
            'name' => $source,
            'description' => $function,
            'tiles' => [$tileUrlTemplate],
            'minzoom' => $meta['minzoom'],
            'maxzoom' => $meta['maxzoom'],
            'vector_layers' => $this->vectorLayers($function),
        ];
    }

    /**
     * Martin's `/catalog` shape, for the sources served here.
     *
     * @return array{tiles: array<string, array{content_type: string, description: string}>}
     */
    public function catalog(): array
    {
        $tiles = [];
        foreach ($this->sources() as $name => $source) {
            $tiles[$name] = [
                'content_type' => 'application/x-protobuf',
                'description' => $source['function'],
            ];
        }

        return ['tiles' => $tiles];
    }

    /** @return list<array<string, mixed>> */
    private function vectorLayers(string $function): array
    {
        $row = DB::selectOne(
            "SELECT obj_description((? || '(integer,integer,integer)')::regprocedure, 'pg_proc') AS comment",
            [$function],
        );
        $comment = is_string($row?->comment) ? json_decode($row->comment, true) : null;
        $layers = is_array($comment) ? ($comment['vector_layers'] ?? null) : null;

        return is_array($layers) ? array_values($layers) : [];
    }

    /** The SQL function for a source; the name is config, but it is still interpolated, so keep it to an identifier. */
    private function functionFor(string $source): string
    {
        $function = $this->sources()[$source]['function'] ?? throw UnknownTileSource::named($source);

        if (preg_match('/^[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*$/', $function) !== 1) {
            throw new RuntimeException("Tile source '{$source}' names an invalid function '{$function}'.");
        }

        return $function;
    }

    /** `bytea` comes back from PDO pgsql as a stream; normalise to a string. */
    private static function binary(mixed $value): string
    {
        if (is_resource($value)) {
            $bytes = stream_get_contents($value);

            return $bytes === false ? '' : $bytes;
        }

        return is_string($value) ? $value : '';
    }
}
