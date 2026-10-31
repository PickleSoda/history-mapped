<?php

declare(strict_types=1);

namespace App\Support\MapStory;

use App\Support\MapStory\MapStoryVocabulary as V;

/**
 * Structural checks for a schema-1 map-story document: the ERROR checks of
 * pipeline/map_stories/validate.py (ids, references, vocabulary, coordinate
 * shapes). Its plausibility warnings (spread, teleports, text lengths) stay in
 * the Python authoring tool; a document that passes here renders.
 */
final class MapStoryDocument
{
    private const ID = '/^[a-z0-9][a-z0-9-]{0,63}$/';

    private const SLUG = '/^[a-z0-9][a-z0-9-]{2,120}$/';

    private const QID = '/^Q[1-9][0-9]*$/';

    private const HEX = '/^#[0-9a-fA-F]{6}$/';

    /** @var list<string> */
    private array $errors = [];

    /**
     * Every problem with the document; empty when it is valid.
     *
     * @return list<string>
     */
    public static function errors(mixed $doc): array
    {
        $check = new self;
        $check->document($doc);

        return $check->errors;
    }

    private function err(string $message): void
    {
        $this->errors[] = $message;
    }

    private function document(mixed $doc): void
    {
        if (! is_array($doc) || array_is_list($doc)) {
            $this->err('document must be an object');

            return;
        }

        if (($doc['schema'] ?? null) !== V::SCHEMA_VERSION) {
            $this->err('schema: must be '.V::SCHEMA_VERSION);
        }
        if (! is_string($doc['slug'] ?? null) || ! preg_match(self::SLUG, $doc['slug'])) {
            $this->err('slug: kebab-case, 3–120 characters');
        }
        $kind = $doc['kind'] ?? null;
        if (! in_array($kind, V::STORY_KINDS, true)) {
            $this->err('kind: one of '.implode(', ', V::STORY_KINDS));
            $kind = 'battle';
        }

        $entity = $doc['entity'] ?? null;
        if (! is_array($entity) || ! is_string($entity['name'] ?? null)) {
            $this->err('entity: {name, wikidata?} of the battle entity');
        } elseif (isset($entity['wikidata']) && ! $this->isQid($entity['wikidata'])) {
            $this->err('entity.wikidata: a Q-id like Q179591');
        }

        foreach (['title', 'date_label', 'intro', 'outcome'] as $key) {
            $this->text($key, $doc[$key] ?? null, true);
        }
        $this->text('uncertainty', $doc['uncertainty'] ?? null, false);
        if (! is_int($doc['year'] ?? null)) {
            $this->err('year: integer, negative for BCE');
        }

        $sources = $doc['sources'] ?? null;
        if (! is_array($sources) || $sources === []) {
            $this->err('sources: at least one {title, url?, kind?}');
        } else {
            foreach (array_values($sources) as $i => $source) {
                if (! is_array($source) || ! is_string($source['title'] ?? null)) {
                    $this->err("sources[{$i}]: needs a title");
                } elseif (isset($source['kind']) && ! in_array($source['kind'], V::SOURCE_KINDS, true)) {
                    $this->err("sources[{$i}].kind: one of ".implode(', ', V::SOURCE_KINDS));
                }
            }
        }

        if (array_key_exists('camera', $doc) && $doc['camera'] !== null && ! $this->isCamera($doc['camera'])) {
            $this->err('camera: {center: [lon, lat], zoom, bearing?}');
        }

        $sideIds = $this->sides($doc['sides'] ?? []);
        if (count($sideIds) < 2 && $kind !== 'campaign') {
            $this->err('sides: a battle needs at least two sides');
        }

        $units = $this->units($doc['units'] ?? [], $sideIds);
        $this->terrain($doc['terrain'] ?? []);
        $this->steps($doc['steps'] ?? [], $units, $sideIds);
    }

    /** @return list<string> side ids */
    private function sides(mixed $sides): array
    {
        $ids = [];
        foreach ($this->listOf($sides) as $i => $side) {
            $where = "sides[{$i}]";
            $id = is_array($side) ? ($side['id'] ?? null) : null;
            if (! $this->isId($id)) {
                $this->err("{$where}.id: lowercase id");

                continue;
            }
            if (in_array($id, $ids, true)) {
                $this->err("{$where}.id: duplicate '{$id}'");
            }
            $ids[] = $id;
            if (! is_string($side['name'] ?? null)) {
                $this->err("{$where}.name: missing");
            }
            if (! is_string($side['color'] ?? null) || ! preg_match(self::HEX, $side['color'])) {
                $this->err("{$where}.color: #rrggbb");
            }
            foreach ($this->listOf($side['commanders'] ?? []) as $j => $commander) {
                if (! is_array($commander) || ! is_string($commander['name'] ?? null)) {
                    $this->err("{$where}.commanders[{$j}]: {name, wikidata?, role?}");
                } elseif (isset($commander['wikidata']) && ! $this->isQid($commander['wikidata'])) {
                    $this->err("{$where}.commanders[{$j}].wikidata: Q-id");
                }
            }
            $polity = $side['polity'] ?? null;
            if ($polity !== null && ! (is_array($polity) && is_string($polity['name'] ?? null))) {
                $this->err("{$where}.polity: {name, wikidata?}");
            } elseif (is_array($polity) && isset($polity['wikidata']) && ! $this->isQid($polity['wikidata'])) {
                $this->err("{$where}.polity.wikidata: Q-id");
            }
        }

        return $ids;
    }

    /**
     * @param  list<string>  $sideIds
     * @return array<string, array<string, mixed>> units by id
     */
    private function units(mixed $units, array $sideIds): array
    {
        $byId = [];
        foreach ($this->listOf($units) as $i => $unit) {
            $where = "units[{$i}]";
            $id = is_array($unit) ? ($unit['id'] ?? null) : null;
            if (! $this->isId($id)) {
                $this->err("{$where}.id: lowercase id");

                continue;
            }
            if (isset($byId[$id])) {
                $this->err("{$where}.id: duplicate '{$id}'");
            }
            $byId[$id] = $unit;
            if (! in_array($unit['side'] ?? null, $sideIds, true)) {
                $this->err("{$where} ({$id}).side: unknown side '".$this->show($unit['side'] ?? null)."'");
            }
            if (! in_array($unit['kind'] ?? null, V::UNIT_KINDS, true)) {
                $this->err("{$where} ({$id}).kind: '".$this->show($unit['kind'] ?? null)."' is not one of ".implode(', ', V::UNIT_KINDS));
            }
            if (! is_string($unit['label'] ?? null) || trim($unit['label']) === '') {
                $this->err("{$where} ({$id}).label: missing");
            }
            if (isset($unit['wikidata']) && ! $this->isQid($unit['wikidata'])) {
                $this->err("{$where} ({$id}).wikidata: Q-id");
            }
        }
        if ($byId === []) {
            $this->err('units: none');
        }

        return $byId;
    }

    private function terrain(mixed $terrain): void
    {
        $ids = [];
        foreach ($this->listOf($terrain) as $i => $feature) {
            $where = "terrain[{$i}]";
            if (! is_array($feature)) {
                $this->err("{$where}: object");

                continue;
            }
            $id = $feature['id'] ?? null;
            if (! $this->isId($id) || in_array($id, $ids, true)) {
                $this->err("{$where}.id: unique lowercase id");
            }
            $ids[] = $id;
            $kind = $feature['kind'] ?? null;
            $geometry = is_string($kind) ? (V::TERRAIN_KINDS[$kind] ?? null) : null;
            if ($geometry === null) {
                $this->err("{$where} (".$this->show($id).").kind: '".$this->show($kind)."' is not one of ".implode(', ', array_keys(V::TERRAIN_KINDS)));

                continue;
            }
            $ok = match ($geometry) {
                'at' => $this->isPoint($feature['at'] ?? null),
                'line' => $this->isPointList($feature['line'] ?? null, 2),
                'area' => $this->isPointList($feature['area'] ?? null, 3),
            };
            if (! $ok) {
                $need = ['at' => '`at: [lon, lat]`', 'line' => '`line` with ≥2 points', 'area' => '`area` with ≥3 points'][$geometry];
                $this->err("{$where} (".$this->show($id)."): a {$kind} needs {$need}");
            }
        }
    }

    /**
     * @param  array<string, array<string, mixed>>  $units
     * @param  list<string>  $sideIds
     */
    private function steps(mixed $steps, array $units, array $sideIds): void
    {
        $ids = [];
        $placed = [];
        foreach ($this->listOf($steps) as $i => $step) {
            if (! is_array($step)) {
                $this->err("steps[{$i}]: object");

                continue;
            }
            $id = $step['id'] ?? null;
            if (! $this->isId($id) || in_array($id, $ids, true)) {
                $this->err("steps[{$i}].id: unique lowercase id");
            }
            $ids[] = $id;
            $where = "step '".$this->show($id)."'";
            $this->text("{$where}.title", $step['title'] ?? null, true);
            $this->text("{$where}.narrative", $step['narrative'] ?? null, true);
            if (isset($step['camera']) && ! $this->isCamera($step['camera'])) {
                $this->err("{$where}.camera: {center, zoom, bearing?}");
            }

            $positions = $step['positions'] ?? [];
            if (! is_array($positions)) {
                $this->err("{$where}.positions: object of unit id → placement");
                $positions = [];
            }
            foreach ($positions as $unitId => $placement) {
                $pw = "{$where}.positions.{$unitId}";
                if (! isset($units[$unitId])) {
                    $this->err("{$pw}: unknown unit");

                    continue;
                }
                if (! is_array($placement) || ($placement !== [] && array_is_list($placement))) {
                    $this->err("{$pw}: object");

                    continue;
                }
                $this->placement($pw, $placement, $units, ! isset($placed[$unitId]));
                $placed[$unitId] = true;
            }

            foreach ($this->listOf($step['moves'] ?? []) as $j => $move) {
                $this->move("{$where}.moves[{$j}]", $move, $units, $sideIds);
            }

            foreach ($this->listOf($step['notes'] ?? []) as $j => $note) {
                $nw = "{$where}.notes[{$j}]";
                if (! is_array($note) || ! $this->isPoint($note['at'] ?? null) || ! is_string($note['text'] ?? null)) {
                    $this->err("{$nw}: {at, text, kind?}");
                } elseif (isset($note['kind']) && ! in_array($note['kind'], V::NOTE_KINDS, true)) {
                    $this->err("{$nw}.kind: one of ".implode(', ', V::NOTE_KINDS));
                }
            }

            foreach ($this->listOf($step['focus'] ?? []) as $unitId) {
                if (! is_string($unitId) || ! isset($units[$unitId])) {
                    $this->err("{$where}.focus: unknown unit '".$this->show($unitId)."'");
                }
            }
        }
    }

    /**
     * @param  array<string, mixed>  $placement
     * @param  array<string, array<string, mixed>>  $units
     */
    private function placement(string $where, array $placement, array $units, bool $first): void
    {
        if (array_key_exists('at', $placement) && ! $this->isPoint($placement['at'])) {
            $this->err("{$where}.at: [lon, lat]");
        }
        if (array_key_exists('with', $placement) && ! (is_string($placement['with']) && isset($units[$placement['with']]))) {
            $this->err("{$where}.with: unknown unit '".$this->show($placement['with'])."'");
        }
        if ($first && ! array_key_exists('at', $placement) && ! array_key_exists('with', $placement)) {
            $this->err("{$where}: first placement needs `at` or `with`");
        }
        if (array_key_exists('facing', $placement) && ! ($this->isNumber($placement['facing']) && $placement['facing'] >= -360 && $placement['facing'] <= 720)) {
            $this->err("{$where}.facing: compass degrees");
        }
        foreach (['width' => [5, 12000], 'depth' => [3, 6000]] as $dim => [$lo, $hi]) {
            if (array_key_exists($dim, $placement) && ! ($this->isNumber($placement[$dim]) && $placement[$dim] >= $lo && $placement[$dim] <= $hi)) {
                $this->err("{$where}.{$dim}: metres between {$lo} and {$hi}");
            }
        }
        if (array_key_exists('shape', $placement) && ! in_array($placement['shape'], V::SHAPES, true)) {
            $this->err("{$where}.shape: one of ".implode(', ', V::SHAPES));
        }
        if (array_key_exists('state', $placement) && ! in_array($placement['state'], V::UNIT_STATES, true)) {
            $this->err("{$where}.state: one of ".implode(', ', V::UNIT_STATES));
        }
    }

    /**
     * @param  array<string, array<string, mixed>>  $units
     * @param  list<string>  $sideIds
     */
    private function move(string $where, mixed $move, array $units, array $sideIds): void
    {
        if (! is_array($move)) {
            $this->err("{$where}: object");

            return;
        }
        $unit = $move['unit'] ?? null;
        if ($unit !== null && ! (is_string($unit) && isset($units[$unit]))) {
            $this->err("{$where}.unit: unknown unit '".$this->show($unit)."'");
        }
        if ($unit === null && ! in_array($move['side'] ?? null, $sideIds, true)) {
            $this->err("{$where}: needs `unit` or `side`");
        }
        if (! in_array($move['type'] ?? null, V::MOVE_TYPES, true)) {
            $this->err("{$where}.type: one of ".implode(', ', V::MOVE_TYPES));
        }
        if (! $this->isPointList($move['path'] ?? null, 2)) {
            $this->err("{$where}.path: ≥2 [lon, lat] points");
        }
    }

    private function text(string $where, mixed $value, bool $required): void
    {
        if ($value === null) {
            if ($required) {
                $this->err("{$where}: missing");
            }

            return;
        }
        if (! is_string($value) || trim($value) === '') {
            $this->err("{$where}: must be a non-empty string");
        }
    }

    /** @return array<int, mixed> */
    private function listOf(mixed $value): array
    {
        return is_array($value) ? array_values($value) : [];
    }

    private function isId(mixed $value): bool
    {
        return is_string($value) && preg_match(self::ID, $value) === 1;
    }

    private function isQid(mixed $value): bool
    {
        return is_string($value) && preg_match(self::QID, $value) === 1;
    }

    private function isNumber(mixed $value): bool
    {
        return is_int($value) || is_float($value);
    }

    private function isPoint(mixed $value): bool
    {
        return is_array($value)
            && array_is_list($value)
            && count($value) === 2
            && $this->isNumber($value[0]) && $this->isNumber($value[1])
            && $value[0] >= -180 && $value[0] <= 180
            && $value[1] >= -90 && $value[1] <= 90;
    }

    private function isPointList(mixed $value, int $min): bool
    {
        if (! is_array($value) || ! array_is_list($value) || count($value) < $min) {
            return false;
        }
        foreach ($value as $point) {
            if (! $this->isPoint($point)) {
                return false;
            }
        }

        return true;
    }

    private function isCamera(mixed $value): bool
    {
        return is_array($value) && $this->isPoint($value['center'] ?? null) && $this->isNumber($value['zoom'] ?? null);
    }

    private function show(mixed $value): string
    {
        return is_scalar($value) ? (string) $value : json_encode($value, JSON_UNESCAPED_UNICODE);
    }
}
