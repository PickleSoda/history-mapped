<?php

declare(strict_types=1);

namespace App\Http\Tiles;

use App\Services\Tiles\TileServer;
use App\Services\Tiles\UnknownTileSource;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Symfony\Component\HttpFoundation\Response as BaseResponse;

/**
 * The app as tile server (`TILES_DRIVER=app`), answering Martin's URLs with
 * Martin's semantics: `application/x-protobuf` with the function's key as
 * ETag, 304 on a matching If-None-Match, 204 for an empty tile, 404 for an
 * unknown source. Routes: routes/tiles.php; contract: docs/schemas/atlas-tiles.md.
 */
class TileController
{
    public function __construct(private readonly TileServer $tiles) {}

    public function catalog(): JsonResponse
    {
        return $this->json($this->tiles->catalog());
    }

    public function tileJson(Request $request, string $source): JsonResponse
    {
        try {
            $template = $request->getSchemeAndHttpHost().'/tiles/'.$source.'/{z}/{x}/{y}';
            $json = $this->tiles->tileJson($source, $template);
        } catch (UnknownTileSource) {
            abort(404);
        }

        return $this->json($json);
    }

    public function tile(Request $request, string $source, int $z, int $x, int $y): BaseResponse
    {
        try {
            $tile = $this->tiles->tile($source, $z, $x, $y);
        } catch (UnknownTileSource) {
            abort(404);
        }

        if ($tile->isEmpty()) {
            return (new Response('', 204))->withHeaders($this->cors());
        }

        $response = (new Response($tile->mvt, 200, [
            'Content-Type' => 'application/x-protobuf',
            ...$this->cors(),
        ]))->setEtag($tile->key)->setPublic()->setMaxAge($this->maxAge());

        // A matching If-None-Match turns this into a 304 and drops the body.
        $response->isNotModified($request);

        return $response;
    }

    /** @param  array<string, mixed>  $payload */
    private function json(array $payload): JsonResponse
    {
        return (new JsonResponse($payload, 200, $this->cors()))->setPublic()->setMaxAge($this->maxAge());
    }

    /** Tiles are public data: open to any origin, as Martin serves them. */
    private function cors(): array
    {
        return ['Access-Control-Allow-Origin' => '*'];
    }

    private function maxAge(): int
    {
        return max(0, (int) config('tiles.max_age', 300));
    }
}
