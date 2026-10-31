<?php

declare(strict_types=1);

namespace App\Ai\Tools;

use App\Ai\Tools\Concerns\FindsMapStory;
use App\Support\MapStory\MapStoryFile;
use App\Support\MapStory\MapStoryWarnings;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Illuminate\Support\Str;
use Laravel\Ai\Tools\Request;
use LogicException;
use Stringable;

/**
 * Read a map story (battle map, epidemic, trade network, chronicle layer…)
 * one part at a time, with the array indices and JSON Pointers that
 * update_map_story patches need. `full` is capped; large stories answer with
 * a hint to read by part. Read-only.
 */
class GetMapStory extends AgentTool
{
    use FindsMapStory;

    /** The most `full` returns; past it, read by part. */
    public const FULL_LIMIT = 60000;

    /** Geometry lists longer than this are summarised outside `full` and `step:<id>`. */
    private const MAX_POINTS = 16;

    public static function name(): string
    {
        return 'get_map_story';
    }

    public function description(): string
    {
        return 'Read a map story (a battle map or any step-by-step map story) by `slug`, or the story of an `entity_id` / `chronicle_id`. '
            .'`part` keeps it small: overview (meta, text, sources, a step list), sides, units, terrain (the features), steps (one line each), '
            .'step:<step id> (one step in full), or full (the whole document, capped at about 60k characters). '
            .'Every item comes with its JSON Pointer (e.g. /steps/3) for update_map_story. Read before you patch.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'slug' => $schema->string()->description('The story slug, e.g. battle-of-cannae'),
            'entity_id' => $schema->string()->description('Or: the UUID (or exact name) of the entity the story belongs to'),
            'chronicle_id' => $schema->string()->description('Or: the UUID of the chronicle whose map layer it is'),
            'part' => $schema->string()->description('overview (default) | sides | units | terrain | steps | step:<id> | full'),
        ];
    }

    public function handle(Request $request): Stringable|string
    {
        try {
            $story = $this->findStory($request->all());
        } catch (ToolArgumentException $e) {
            return json_encode(['error' => $e->getMessage()], JSON_THROW_ON_ERROR);
        }

        $doc = MapStoryFile::toArray(MapStoryFile::authored($story->document));
        $part = trim((string) ($request['part'] ?? 'overview')) ?: 'overview';
        $featuresKey = array_key_exists('terrain', $doc) && ! array_key_exists('features', $doc) ? 'terrain' : 'features';

        $out = ['slug' => $story->slug, 'part' => $part, 'edited_since_file' => $story->isEdited()];
        $out += match (true) {
            $part === 'overview' => $this->overview($doc, $featuresKey),
            $part === 'sides' => ['sides' => $this->indexed($doc['sides'] ?? [], '/sides')],
            $part === 'units' => ['units' => $this->indexed($doc['units'] ?? [], '/units')],
            $part === 'terrain', $part === 'features' => [
                'features_key' => $featuresKey,
                'features' => $this->indexed(array_map($this->compactGeometry(...), $doc[$featuresKey] ?? []), "/{$featuresKey}"),
            ],
            $part === 'steps' => ['steps' => $this->stepLines($doc)],
            str_starts_with($part, 'step:') => $this->step($doc, substr($part, 5)),
            $part === 'full' => $this->full($doc),
            default => ['error' => "Unknown part '{$part}'. Use overview, sides, units, terrain, steps, step:<id> or full."],
        };

        return json_encode($out, MapStoryFile::JSON_FLAGS | JSON_THROW_ON_ERROR);
    }

    public function buildParts(array $args): array
    {
        throw new LogicException('GetMapStory is a read-only tool — it does not stage proposals.');
    }

    public function applyPart(array $payload, array $resolved): array
    {
        throw new LogicException('GetMapStory is a read-only tool — it does not apply parts.');
    }

    /** @return array<string, mixed> */
    private function overview(array $doc, string $featuresKey): array
    {
        $meta = array_intersect_key($doc, array_flip([
            'schema', 'slug', 'kind', 'entity', 'chronicle', 'title', 'date_label', 'year', 'period', 'ambient',
            'intro', 'outcome', 'uncertainty', 'sources', 'alt_sites', 'legend', 'camera',
        ]));

        return [
            'document' => $meta,
            'counts' => [
                'sides' => count($doc['sides'] ?? []),
                'units' => count($doc['units'] ?? []),
                $featuresKey => count($doc[$featuresKey] ?? []),
                'steps' => count($doc['steps'] ?? []),
            ],
            'features_key' => $featuresKey,
            'steps' => $this->stepLines($doc, false),
            'warnings' => MapStoryWarnings::of($doc),
        ];
    }

    /** @return list<array<string, mixed>> */
    private function stepLines(array $doc, bool $detail = true): array
    {
        $lines = [];
        foreach (array_values($doc['steps'] ?? []) as $i => $step) {
            $line = ['pointer' => "/steps/{$i}", 'id' => $step['id'] ?? null, 'title' => $step['title'] ?? null];
            foreach (['date', 'time', 'entry'] as $key) {
                if (isset($step[$key])) {
                    $line[$key] = $step[$key];
                }
            }
            if ($detail) {
                $line['narrative'] = Str::limit((string) ($step['narrative'] ?? ''), 160);
                $line['positions'] = array_keys($step['positions'] ?? []);
                $line['moves'] = count($step['moves'] ?? []);
                $line['notes'] = count($step['notes'] ?? []);
                $line['beats'] = count($step['beats'] ?? []);
                $line['feature_states'] = array_keys($step['features'] ?? $step['terrain_state'] ?? []);
                $line['entities'] = array_column($step['entities'] ?? [], 'name');
            }
            $lines[] = $line;
        }

        return $lines;
    }

    /** @return array<string, mixed> */
    private function step(array $doc, string $id): array
    {
        foreach (array_values($doc['steps'] ?? []) as $i => $step) {
            if (($step['id'] ?? null) === $id) {
                return ['pointer' => "/steps/{$i}", 'step' => $step];
            }
        }

        return ['error' => "No step '{$id}'. Steps: ".implode(', ', array_column($doc['steps'] ?? [], 'id'))];
    }

    /** @return array<string, mixed> */
    private function full(array $doc): array
    {
        $size = strlen((string) json_encode($doc, MapStoryFile::JSON_FLAGS));
        if ($size > self::FULL_LIMIT) {
            return ['error' => "The document is {$size} characters — too large for part=full. Use part=overview, sides, units, terrain, steps or step:<id>."];
        }

        return ['document' => $doc];
    }

    /**
     * @param  list<array<string, mixed>>  $items
     * @return list<array<string, mixed>>
     */
    private function indexed(array $items, string $prefix): array
    {
        return array_map(fn (array $item, int $i) => ['pointer' => "{$prefix}/{$i}"] + $item, array_values($items), array_keys(array_values($items)));
    }

    /** @return array<string, mixed> a feature with long lines and areas summarised */
    private function compactGeometry(array $feature): array
    {
        foreach (['line', 'area'] as $key) {
            $value = $feature[$key] ?? null;
            if (! is_array($value)) {
                continue;
            }
            $points = $key === 'line' ? $value : (is_array($value[0][0] ?? null) ? array_merge(...$value) : $value);
            if (count($points) > self::MAX_POINTS) {
                $lons = array_column($points, 0);
                $lats = array_column($points, 1);
                $feature[$key] = ['summary' => count($points).' points (replace the whole '.$key.' to change it; part=full shows them)',
                    'bbox' => [min($lons), min($lats), max($lons), max($lats)]];
            }
        }

        return $feature;
    }
}
