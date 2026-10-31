<?php

declare(strict_types=1);

namespace App\Support\MapStory;

use App\Support\MapStory\MapStoryVocabulary as V;

/**
 * Structural checks for a schema 1–3 map-story document: the ERROR checks of
 * pipeline/map_stories/validate.py (ids, references, vocabulary, coordinate
 * shapes, dates, newer fields only under a newer `schema`). Its plausibility
 * warnings (spread, teleports, land/water, text lengths, date order) stay in
 * the Python authoring tool; a document that passes here renders.
 *
 * `features`/`terrain` and a step's `features`/`terrain_state` are the same
 * thing under the schema-3 and older names; messages use the name the
 * document uses.
 */
final class MapStoryDocument
{
    private const ID = '/^[a-z0-9][a-z0-9-]{0,63}$/';

    private const SLUG = '/^[a-z0-9][a-z0-9-]{2,120}$/';

    private const QID = '/^Q[1-9][0-9]*$/';

    private const HEX = '/^#[0-9a-fA-F]{6}$/';

    /** @var list<string> */
    private array $errors = [];

    /** The schema the document is checked as (an unknown version: the latest). */
    private int $schema = V::SCHEMA_VERSION;

    /** @var array<string, mixed> */
    private array $doc = [];

    /** @var array<string, list<string>> contingent ids by side id */
    private array $contingents = [];

    /** @var array<string, array<string, mixed>> features (terrain) by id */
    private array $featureById = [];

    /** @var array<string, string> each placed unit's current state, to know who is on the field */
    private array $states = [];

    /** @var list<int> the chronicle entries that already have a step */
    private array $entries = [];

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
        $this->doc = $doc;

        $schema = $doc['schema'] ?? null;
        if (! in_array($schema, V::SCHEMA_VERSIONS, true)) {
            $this->err('schema: must be '.implode(', ', array_slice(V::SCHEMA_VERSIONS, 0, -1)).' or '.V::SCHEMA_VERSION);
        }
        $this->schema = in_array($schema, V::SCHEMA_VERSIONS, true) ? $schema : V::SCHEMA_VERSION;
        $this->needs('document', $doc, 'document');
        if (array_key_exists('features', $doc) && array_key_exists('terrain', $doc)) {
            $this->err('features and terrain: give one (terrain is the old name of features)');
        }
        if (! is_string($doc['slug'] ?? null) || ! preg_match(self::SLUG, $doc['slug'])) {
            $this->err('slug: kebab-case, 3–120 characters');
        }
        $kind = $doc['kind'] ?? null;
        if (! in_array($kind, V::STORY_KINDS, true)) {
            $this->err('kind: one of '.implode(', ', V::STORY_KINDS));
            $kind = 'battle';
        }
        $this->added('kind', $kind, V::V3_STORY_KINDS, 3);

        $this->attachment($doc['entity'] ?? null, $doc['chronicle'] ?? null);

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

        $altSites = $doc['alt_sites'] ?? null;
        if ($altSites !== null && ! is_array($altSites)) {
            $this->err('alt_sites: a list of {at, label, note?}');
        }
        foreach ($this->listOf($altSites) as $i => $site) {
            if (! is_array($site) || ! $this->isPoint($site['at'] ?? null) || ! $this->isText($site['label'] ?? null)) {
                $this->err("alt_sites[{$i}]: {at, label, note?}");
            } elseif (isset($site['note']) && ! is_string($site['note'])) {
                $this->err("alt_sites[{$i}].note: text");
            }
        }

        $this->period($doc['period'] ?? null);
        if (array_key_exists('ambient', $doc) && $doc['ambient'] !== null && ! is_bool($doc['ambient'])) {
            $this->err('ambient: true or false');
        }
        $this->legend($doc['legend'] ?? null);

        $sideIds = $this->sides($doc['sides'] ?? []);
        if (count($sideIds) < 2 && in_array($kind, V::BATTLE_KINDS, true)) {
            $this->err('sides: a battle needs at least two sides');
        }

        $units = $this->units($doc['units'] ?? [], $sideIds, $kind);
        $featuresKey = array_key_exists('terrain', $doc) && ! array_key_exists('features', $doc) ? 'terrain' : 'features';
        $this->features($featuresKey, $doc[$featuresKey] ?? [], $sideIds);
        $this->steps($doc['steps'] ?? [], $units, $sideIds);
    }

    /** The story's entity and/or (schema 3) chronicle: at least one. */
    private function attachment(mixed $entity, mixed $chronicle): void
    {
        if ($entity === null && $chronicle === null) {
            $this->err($this->schema >= 3
                ? 'entity or chronicle: a story belongs to an entity {name, wikidata?} or a chronicle {slug}'
                : 'entity: {name, wikidata?} of the battle entity');
        }
        if ($entity !== null) {
            if (! is_array($entity) || ! is_string($entity['name'] ?? null)) {
                $this->err("entity: {name, wikidata?} of the story's entity");
            } elseif (isset($entity['wikidata']) && ! $this->isQid($entity['wikidata'])) {
                $this->err('entity.wikidata: a Q-id like Q179591');
            }
        }
        if ($chronicle !== null && ! (is_array($chronicle) && is_string($chronicle['slug'] ?? null) && preg_match(self::SLUG, $chronicle['slug']))) {
            $this->err('chronicle: {slug} of an existing chronicle');
        }
    }

    private function period(mixed $period): void
    {
        if ($period === null) {
            return;
        }
        if (! is_array($period) || ! array_key_exists('start', $period) || ! array_key_exists('end', $period)) {
            $this->err('period: {start: {year, …}, end: {year, …}}');

            return;
        }
        if ($this->date('period.start', $period['start'], false) && $this->date('period.end', $period['end'], false)
            && self::dateKey($period['end'], true) < self::dateKey($period['start'])) {
            $this->err('period.end: before the start');
        }
    }

    /**
     * A date spec {year, month?, day?} and, on a step, an optional `end`.
     * Same year numbering as `year` (negative for BCE).
     */
    private function date(string $where, mixed $value, bool $withEnd = true): bool
    {
        if (! is_array($value) || ($value !== [] && array_is_list($value)) || ! is_int($value['year'] ?? null)) {
            $this->err("{$where}: ".($withEnd ? '{year, month?, day?, end?}' : '{year, month?, day?}').' with an integer year');

            return false;
        }
        $ok = true;
        $month = $value['month'] ?? null;
        $day = $value['day'] ?? null;
        if ($month !== null && ! $this->isCount($month, 1, 12)) {
            $this->err("{$where}.month: 1–12");
            $ok = false;
        }
        if ($day !== null) {
            $last = $ok && is_int($month) ? V::MONTH_DAYS[$month - 1] : 31;
            if ($month === null) {
                $this->err("{$where}.day: needs a month");
                $ok = false;
            } elseif (! $this->isCount($day, 1, $last)) {
                $this->err("{$where}.day: 1–{$last}");
                $ok = false;
            }
        }
        if (array_key_exists('end', $value)) {
            if (! $withEnd) {
                $this->err("{$where}.end: only a step date has an end");

                return false;
            }
            if (! $this->date("{$where}.end", $value['end'], false)) {
                return false;
            }
            if ($ok && self::dateKey($value['end'], true) < self::dateKey($value)) {
                $this->err("{$where}.end: before the start");
                $ok = false;
            }
        }

        return $ok;
    }

    /**
     * A date spec as a sortable [year, month, day]: missing parts are the
     * earliest (or, with `$latest`, the last) month and day.
     *
     * @return array{0: int, 1: int, 2: int}
     */
    public static function dateKey(mixed $spec, bool $latest = false): array
    {
        if (! is_array($spec) || ! is_int($spec['year'] ?? null)) {
            return [0, 0, 0];
        }
        $month = is_int($spec['month'] ?? null) && $spec['month'] >= 1 && $spec['month'] <= 12 ? $spec['month'] : null;
        $day = is_int($spec['day'] ?? null) ? $spec['day'] : null;
        if ($latest) {
            $month ??= 12;

            return [$spec['year'], $month, $day ?? V::MONTH_DAYS[$month - 1]];
        }

        return [$spec['year'], $month ?? 1, $day ?? 1];
    }

    private function legend(mixed $legend): void
    {
        if ($legend === null) {
            return;
        }
        if (! is_array($legend) || ! array_is_list($legend)) {
            $this->err('legend: a list of {swatch, label, style?}');

            return;
        }
        foreach ($legend as $i => $item) {
            if (! is_array($item) || ! is_string($item['swatch'] ?? null) || ! preg_match(self::HEX, $item['swatch']) || ! $this->isText($item['label'] ?? null)) {
                $this->err("legend[{$i}]: {swatch: #rrggbb, label, style?}");
            } elseif (isset($item['style']) && ! in_array($item['style'], V::LEGEND_STYLES, true)) {
                $this->err("legend[{$i}].style: one of ".implode(', ', V::LEGEND_STYLES));
            }
        }
    }

    /** A linked entity reference: {name, wikidata?, entity_id?}, or (without a name) {wikidata} or {entity_id}. */
    private function linked(string $where, mixed $ref, bool $needsName = true): void
    {
        $shape = $needsName ? '{name, wikidata?}' : '{wikidata} or {entity_id}';
        if (! is_array($ref) || ($ref !== [] && array_is_list($ref))) {
            $this->err("{$where}: {$shape}");

            return;
        }
        if ($needsName && ! $this->isText($ref['name'] ?? null)) {
            $this->err("{$where}.name: missing");
        }
        if (! $needsName && empty($ref['wikidata']) && empty($ref['entity_id'])) {
            $this->err("{$where}: {$shape}");
        }
        if (isset($ref['wikidata']) && ! $this->isQid($ref['wikidata'])) {
            $this->err("{$where}.wikidata: a Q-id like Q42005");
        }
        if (isset($ref['entity_id']) && ! is_string($ref['entity_id'])) {
            $this->err("{$where}.entity_id: text");
        }
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
            $this->needs($where, $side, 'side');
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
            $this->contingents[$id] = $this->sideContingents($where, $side['contingents'] ?? null);
        }

        return $ids;
    }

    /** @return list<string> contingent ids */
    private function sideContingents(string $where, mixed $contingents): array
    {
        if ($contingents !== null && ! is_array($contingents)) {
            $this->err("{$where}.contingents: a list of {id, name, color?}");
        }
        $ids = [];
        foreach ($this->listOf($contingents) as $j => $contingent) {
            $cw = "{$where}.contingents[{$j}]";
            $id = is_array($contingent) ? ($contingent['id'] ?? null) : null;
            if (! $this->isId($id)) {
                $this->err("{$cw}.id: lowercase id");

                continue;
            }
            if (in_array($id, $ids, true)) {
                $this->err("{$cw}.id: duplicate '{$id}'");
            }
            $ids[] = $id;
            if (! $this->isText($contingent['name'] ?? null)) {
                $this->err("{$cw}.name: missing");
            }
            if (isset($contingent['color']) && ! (is_string($contingent['color']) && preg_match(self::HEX, $contingent['color']))) {
                $this->err("{$cw}.color: #rrggbb");
            }
        }

        return $ids;
    }

    /**
     * @param  list<string>  $sideIds
     * @return array<string, array<string, mixed>> units by id
     */
    private function units(mixed $units, array $sideIds, string $kind): array
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
            $uw = "{$where} ({$id})";
            $this->needs($uw, $unit, 'unit');
            // Schema 3: a story without sides (an epidemic, a trade network) has side-less units.
            $sideless = $this->schema >= 3 && $sideIds === [] && ($unit['side'] ?? null) === null;
            if (! $sideless && ! in_array($unit['side'] ?? null, $sideIds, true)) {
                $this->err("{$uw}.side: unknown side '".$this->show($unit['side'] ?? null)."'");
            }
            if (! in_array($unit['kind'] ?? null, V::UNIT_KINDS, true)) {
                $this->err("{$uw}.kind: '".$this->show($unit['kind'] ?? null)."' is not one of ".implode(', ', V::UNIT_KINDS));
            }
            $this->added("{$uw}.kind", $unit['kind'] ?? null, V::V2_UNIT_KINDS, 2);
            $this->added("{$uw}.kind", $unit['kind'] ?? null, V::V3_UNIT_KINDS, 3);
            if (! is_string($unit['label'] ?? null) || trim($unit['label']) === '') {
                $this->err("{$uw}.label: missing");
            }
            if (isset($unit['wikidata']) && ! $this->isQid($unit['wikidata'])) {
                $this->err("{$uw}.wikidata: Q-id");
            }
            if (array_key_exists('strength_n', $unit) && ! $this->isCount($unit['strength_n'])) {
                $this->err("{$uw}.strength_n: a whole number ≥ 0");
            }
            if (array_key_exists('contingent', $unit) && ! in_array($unit['contingent'], $this->contingents[$unit['side'] ?? ''] ?? [], true)) {
                $this->err("{$uw}.contingent: '".$this->show($unit['contingent'])."' is not a contingent of side '".$this->show($unit['side'] ?? null)."'");
            }
            if (array_key_exists('ranks', $unit)) {
                $this->ranks($uw, $unit['ranks']);
            }
        }
        if ($byId === [] && in_array($kind, V::MILITARY_KINDS, true)) {
            $this->err('units: none');
        }

        return $byId;
    }

    private function ranks(string $where, mixed $ranks): void
    {
        if (! is_array($ranks) || $ranks === [] || ! array_is_list($ranks)) {
            $this->err("{$where}.ranks: a list of {kind, share} bands, front to back");

            return;
        }
        foreach ($ranks as $k => $band) {
            $share = is_array($band) ? ($band['share'] ?? null) : null;
            if (! is_array($band) || ! in_array($band['kind'] ?? null, V::UNIT_KINDS, true) || ! $this->isNumber($share) || $share < 0 || $share > 1) {
                $this->err("{$where}.ranks[{$k}]: {kind: a unit kind, share: 0–1}");
            }
        }
    }

    /**
     * The document's persistent features (`features`, alias `terrain`).
     *
     * @param  list<string>  $sideIds
     */
    private function features(string $key, mixed $features, array $sideIds): void
    {
        if (! is_array($features) || ($features !== [] && ! array_is_list($features))) {
            $this->err("{$key}: a list of features");

            return;
        }
        $ids = [];
        foreach ($features as $i => $feature) {
            $where = "{$key}[{$i}]";
            if (! is_array($feature)) {
                $this->err("{$where}: object");

                continue;
            }
            $id = $feature['id'] ?? null;
            if (! $this->isId($id) || in_array($id, $ids, true)) {
                $this->err("{$where}.id: unique lowercase id");
            }
            $ids[] = $id;
            if ($this->isId($id)) {
                $this->featureById[$id] = $feature;
            }
            $fw = "{$where} (".$this->show($id).')';
            $this->needs($fw, $feature, 'feature');
            foreach (['conjectural', 'bidirectional', 'active'] as $flag) {
                if (array_key_exists($flag, $feature) && ! is_bool($feature[$flag])) {
                    $this->err("{$fw}.{$flag}: true or false");
                }
            }
            $kind = $feature['kind'] ?? null;
            $geometry = is_string($kind) ? (V::FEATURE_KINDS[$kind] ?? null) : null;
            if ($geometry === null) {
                $this->err("{$fw}.kind: '".$this->show($kind)."' is not one of ".implode(', ', array_keys(V::FEATURE_KINDS)));

                continue;
            }
            $this->added("{$fw}.kind", $kind, V::V2_FEATURE_KINDS, 2);
            $this->added("{$fw}.kind", $kind, V::V3_FEATURE_KINDS, 3);
            if ($geometry === 'at' && ! $this->isPoint($feature['at'] ?? null)) {
                $this->err("{$fw}: a {$kind} needs `at: [lon, lat]`");
            } elseif ($geometry === 'line' && ! $this->isPointList($feature['line'] ?? null, 2)) {
                $this->err("{$fw}: a {$kind} needs `line` with ≥2 points");
            } elseif ($geometry === 'area') {
                $area = $feature['area'] ?? null;
                if (! self::isArea($area)) {
                    $this->err("{$fw}: a {$kind} needs `area`: a ring of ≥3 points, or a list of such rings");
                } elseif (self::isMulti($area) && $this->schema < 3) {
                    $this->err("{$fw}.area: a list of rings needs schema 3 — bump schema to 3");
                }
            }
            $this->featureExtras($fw, $feature, $kind, $sideIds);
        }
    }

    /**
     * @param  array<string, mixed>  $feature
     * @param  list<string>  $sideIds
     */
    private function featureExtras(string $fw, array $feature, string $kind, array $sideIds): void
    {
        foreach (['route_kind' => [V::ROUTE_KINDS, 'route'], 'region_kind' => [V::REGION_KINDS, 'region']] as $sub => [$values, $owner]) {
            if ($kind === $owner && ! in_array($feature[$sub] ?? null, $values, true)) {
                $this->err("{$fw}.{$sub}: a {$owner} needs one of ".implode(', ', $values));
            } elseif ($kind !== $owner && array_key_exists($sub, $feature)) {
                $this->err("{$fw}.{$sub}: only a {$owner} has one");
            }
        }
        if (array_key_exists('entity', $feature)) {
            $this->linked("{$fw}.entity", $feature['entity']);
        }
        if (array_key_exists('side', $feature) && ! in_array($feature['side'], $sideIds, true)) {
            $this->err("{$fw}.side: unknown side '".$this->show($feature['side'])."'");
        }
        if (array_key_exists('goods', $feature)) {
            $goods = $feature['goods'];
            if (! is_array($goods) || ! array_is_list($goods) || array_filter($goods, fn (mixed $g) => ! $this->isText($g)) !== []) {
                $this->err("{$fw}.goods: a list of short names");
            }
        }
        $this->values($fw, $feature);
    }

    /**
     * `value_n` (a number ≥ 0), `value_label` (text) and `intensity` (0–1); null clears them.
     *
     * @param  array<string, mixed>  $object
     */
    private function values(string $where, array $object): void
    {
        $valueN = $object['value_n'] ?? null;
        if ($valueN !== null && ! ($this->isNumber($valueN) && $valueN >= 0)) {
            $this->err("{$where}.value_n: a number ≥ 0");
        }
        if (isset($object['value_label']) && ! $this->isText($object['value_label'])) {
            $this->err("{$where}.value_label: text");
        }
        $intensity = $object['intensity'] ?? null;
        if ($intensity !== null && ! ($this->isNumber($intensity) && $intensity >= 0 && $intensity <= 1)) {
            $this->err("{$where}.intensity: a number 0–1");
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
            // A step's `features` is schema 3's name for the schema-2 `terrain_state`.
            $old = $step;
            if (array_key_exists('features', $old)) {
                $old['terrain_state'] = $old['features'];
                unset($old['features']);
            }
            $this->needs($where, $old, 'step', 2);
            $this->needs($where, $step, 'step', 3);
            $this->text("{$where}.title", $step['title'] ?? null, true);
            $this->text("{$where}.narrative", $step['narrative'] ?? null, true);
            if (isset($step['camera']) && ! $this->isCamera($step['camera'])) {
                $this->err("{$where}.camera: {center, zoom, bearing?}");
            }

            if (array_key_exists('light', $step) && ! in_array($step['light'], V::LIGHTS, true)) {
                $this->err("{$where}.light: one of ".implode(', ', V::LIGHTS));
            }
            foreach (['wind', 'sun'] as $key) {
                if (array_key_exists($key, $step)) {
                    $this->bearingMarker("{$where}.{$key}", $step[$key], $key === 'wind');
                }
            }
            if (array_key_exists('features', $step) && array_key_exists('terrain_state', $step)) {
                $this->err("{$where}: features and terrain_state: give one (terrain_state is the old name)");
            }
            if (array_key_exists('features', $step)) {
                $this->featureState("{$where}.features", $step['features'], $sideIds, 'feature');
            } elseif (array_key_exists('terrain_state', $step)) {
                $this->featureState("{$where}.terrain_state", $step['terrain_state'], $sideIds, 'terrain');
            }
            $this->stepV3($where, $step);

            $this->phase($where, $step, $units, $sideIds, $placed);
            $this->beats($where, $step['beats'] ?? null, $units, $sideIds, $placed);
        }
    }

    /**
     * A step's date, chronicle entry and entities (schema 3).
     *
     * @param  array<string, mixed>  $step
     */
    private function stepV3(string $where, array $step): void
    {
        if (array_key_exists('date', $step)) {
            $this->date("{$where}.date", $step['date']);
        } elseif (($this->doc['ambient'] ?? null) === true) {
            $this->err("{$where}.date: an ambient story dates every step");
        }

        if (array_key_exists('entry', $step)) {
            $entry = $step['entry'];
            if (($this->doc['chronicle'] ?? null) === null) {
                $this->err("{$where}.entry: only a chronicle's story keys steps to entries");
            } elseif (! $this->isCount($entry)) {
                $this->err("{$where}.entry: the entry's sequence_order as stored, an integer ≥ 0");
            } elseif (in_array($entry, $this->entries, true)) {
                $this->err("{$where}.entry: entry {$entry} already has a step");
            } else {
                $this->entries[] = $entry;
            }
        }

        $entities = $step['entities'] ?? null;
        if ($entities === null) {
            return;
        }
        if (! is_array($entities) || ! array_is_list($entities)) {
            $this->err("{$where}.entities: a list of {name, wikidata?, role?, show?}");

            return;
        }
        foreach ($entities as $j => $entity) {
            $ew = "{$where}.entities[{$j}]";
            $this->linked($ew, $entity);
            if (! is_array($entity)) {
                continue;
            }
            if (isset($entity['role']) && ! $this->isText($entity['role'])) {
                $this->err("{$ew}.role: text");
            }
            if (array_key_exists('show', $entity) && ! is_bool($entity['show'])) {
                $this->err("{$ew}.show: true or false");
            }
        }
    }

    /**
     * @param  array<string, array<string, mixed>>  $units
     * @param  list<string>  $sideIds
     * @param  array<string, true>  $placed
     */
    private function beats(string $where, mixed $beats, array $units, array $sideIds, array &$placed): void
    {
        if ($beats === null) {
            return;
        }
        if (! is_array($beats) || ! array_is_list($beats)) {
            $this->err("{$where}.beats: a list of {label, positions?, moves?, notes?}");

            return;
        }
        if (count($beats) > V::MAX_BEATS) {
            $this->err("{$where}.beats: ".count($beats).' beats (at most '.V::MAX_BEATS.')');
        }
        foreach ($beats as $k => $beat) {
            $bw = "{$where}.beats[{$k}]";
            if (! is_array($beat) || ($beat !== [] && array_is_list($beat))) {
                $this->err("{$bw}: object");

                continue;
            }
            if (! $this->isText($beat['label'] ?? null)) {
                $this->err("{$bw}.label: missing");
            }
            if (empty($beat['positions']) && empty($beat['moves'])) {
                $this->err("{$bw}: needs `positions` or `moves`");
            }
            $this->phase($bw, $beat, $units, $sideIds, $placed);
        }
    }

    /**
     * A step's (or beat's) positions, moves, notes and focus, in order.
     *
     * @param  array<string, mixed>  $phase
     * @param  array<string, array<string, mixed>>  $units
     * @param  list<string>  $sideIds
     * @param  array<string, true>  $placed
     */
    private function phase(string $where, array $phase, array $units, array $sideIds, array &$placed): void
    {
        $positions = $phase['positions'] ?? [];
        if (! is_array($positions) || ($positions !== [] && array_is_list($positions))) {
            $this->err("{$where}.positions: object of unit id → placement");
            $positions = [];
        }
        $before = $this->onField();
        $merging = [];
        foreach ($positions as $unitId => $placement) {
            $unitId = (string) $unitId;
            $pw = "{$where}.positions.{$unitId}";
            if (! isset($units[$unitId])) {
                $this->err("{$pw}: unknown unit");

                continue;
            }
            if (! is_array($placement) || ($placement !== [] && array_is_list($placement))) {
                $this->err("{$pw}: object");

                continue;
            }
            $this->placement($pw, $unitId, $placement, $units, $sideIds, ! isset($placed[$unitId]), $before);
            $placed[$unitId] = true;
            if (array_key_exists('into', $placement)) {
                $merging[$unitId] = $placement['into'];
            }
        }
        $now = $this->onField();
        foreach ($merging as $unitId => $target) {
            if (is_string($target) && isset($units[$target]) && ! in_array($target, $now, true)) {
                $this->err("{$where}.positions.{$unitId}.into: '{$target}' is not on the field in this step");
            }
            // It slides onto the target, then leaves the field.
            $this->states[$unitId] = 'hidden';
        }

        foreach ($this->listOf($phase['moves'] ?? []) as $j => $move) {
            $this->move("{$where}.moves[{$j}]", $move, $units, $sideIds);
        }

        foreach ($this->listOf($phase['notes'] ?? []) as $j => $note) {
            $nw = "{$where}.notes[{$j}]";
            if (! is_array($note) || ! $this->isPoint($note['at'] ?? null) || ! is_string($note['text'] ?? null)) {
                $this->err("{$nw}: {at, text, kind?}");

                continue;
            }
            $this->needs($nw, $note, 'note');
            if (isset($note['kind']) && ! in_array($note['kind'], V::NOTE_KINDS, true)) {
                $this->err("{$nw}.kind: one of ".implode(', ', V::NOTE_KINDS));
            }
            if (array_key_exists('conjectural', $note) && ! is_bool($note['conjectural'])) {
                $this->err("{$nw}.conjectural: true or false");
            }
        }

        foreach ($this->listOf($phase['focus'] ?? []) as $unitId) {
            if (! is_string($unitId) || ! isset($units[$unitId])) {
                $this->err("{$where}.focus: unknown unit '".$this->show($unitId)."'");
            }
        }
    }

    /** @return list<string> the placed units that are not hidden */
    private function onField(): array
    {
        return array_keys(array_filter($this->states, fn (string $state) => $state !== 'hidden'));
    }

    private function bearingMarker(string $where, mixed $value, bool $wind): void
    {
        $from = is_array($value) ? ($value['from'] ?? null) : null;
        if (! $this->isNumber($from) || $from < -360 || $from > 720) {
            $this->err("{$where}: ".($wind ? '{from: degrees, strength?, label?}' : '{from: degrees, label?}'));

            return;
        }
        if ($wind && isset($value['strength']) && ! in_array($value['strength'], V::WIND_STRENGTHS, true)) {
            $this->err("{$where}.strength: one of ".implode(', ', V::WIND_STRENGTHS));
        }
        if (isset($value['label']) && ! is_string($value['label'])) {
            $this->err("{$where}.label: text");
        }
    }

    /**
     * A step's feature state: feature id → {held_by?, state?, label?, active?,
     * value_n?, value_label?, intensity?, at?/line?/area?/area_from_entity?}.
     *
     * @param  list<string>  $sideIds
     */
    private function featureState(string $where, mixed $value, array $sideIds, string $noun): void
    {
        if (! is_array($value) || ($value !== [] && array_is_list($value))) {
            $this->err("{$where}: object of {$noun} id → {held_by?, state?, label?, …}");

            return;
        }
        foreach ($value as $featureId => $state) {
            $tw = "{$where}.{$featureId}";
            $feature = $this->featureById[(string) $featureId] ?? null;
            if ($feature === null) {
                $this->err("{$tw}: unknown {$noun}");

                continue;
            }
            if (! is_array($state) || ($state !== [] && array_is_list($state))) {
                $this->err("{$tw}: {held_by?, state?, label?, …}");

                continue;
            }
            $this->needs($tw, $state, 'feature_state');
            if (isset($state['held_by']) && ! in_array($state['held_by'], $sideIds, true)) {
                $this->err("{$tw}.held_by: unknown side '".$this->show($state['held_by'])."'");
            }
            if (isset($state['state'])) {
                if (! in_array($state['state'], V::FEATURE_STATES, true)) {
                    $states = $this->schema >= 3 ? V::FEATURE_STATES : array_diff(V::FEATURE_STATES, V::V3_FEATURE_STATES);
                    $this->err("{$tw}.state: one of ".implode(', ', $states));
                }
                $this->added("{$tw}.state", $state['state'], V::V3_FEATURE_STATES, 3);
            }
            if (isset($state['label']) && ! is_string($state['label'])) {
                $this->err("{$tw}.label: text");
            }
            if (array_key_exists('active', $state) && ! is_bool($state['active'])) {
                $this->err("{$tw}.active: true or false");
            }
            $this->values($tw, $state);

            $geometry = V::FEATURE_KINDS[$feature['kind'] ?? ''] ?? null;
            if (array_key_exists('at', $state) && ($geometry !== 'at' || ! $this->isPoint($state['at']))) {
                $this->err("{$tw}.at: [lon, lat], on a point feature only");
            }
            if (array_key_exists('line', $state) && ($geometry !== 'line' || ! $this->isPointList($state['line'], 2))) {
                $this->err("{$tw}.line: ≥2 points, on a line feature only");
            }
            if (array_key_exists('area', $state) && ($geometry !== 'area' || ! self::isArea($state['area']))) {
                $this->err("{$tw}.area: a ring or a list of rings, on an area feature only");
            }
            if (array_key_exists('area_from_entity', $state)) {
                if ($geometry !== 'area') {
                    $this->err("{$tw}.area_from_entity: on an area feature only");
                } else {
                    $this->linked("{$tw}.area_from_entity", $state['area_from_entity'], false);
                }
                if (array_key_exists('area', $state)) {
                    $this->err("{$tw}: give `area` or `area_from_entity`, not both");
                }
            }
        }
    }

    /**
     * @param  array<string, mixed>  $placement
     * @param  array<string, array<string, mixed>>  $units
     * @param  list<string>  $sideIds
     * @param  list<string>  $before  the units on the field in the previous frame
     */
    private function placement(string $where, string $unitId, array $placement, array $units, array $sideIds, bool $first, array $before): void
    {
        $this->needs($where, $placement, 'placement');
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
        if (array_key_exists('state', $placement)) {
            if (! in_array($placement['state'], V::UNIT_STATES, true)) {
                $this->err("{$where}.state: one of ".implode(', ', V::UNIT_STATES));
            }
            $this->added("{$where}.state", $placement['state'], V::V2_UNIT_STATES, 2);
            if ($placement['state'] === 'captured' && ! array_key_exists('by', $placement)) {
                $this->err("{$where}.state: 'captured' needs `by: <side id>` (the captor)");
            }
        }
        if (array_key_exists('by', $placement) && ! in_array($placement['by'], $sideIds, true)) {
            $this->err("{$where}.by: unknown side '".$this->show($placement['by'])."'");
        }
        foreach (['frame', 'conjectural'] as $key) {
            if (array_key_exists($key, $placement) && ! is_bool($placement[$key])) {
                $this->err("{$where}.{$key}: true or false");
            }
        }
        if (array_key_exists('strength_n', $placement) && ! $this->isCount($placement['strength_n'])) {
            $this->err("{$where}.strength_n: a whole number ≥ 0");
        }
        foreach (V::FORMATION_RANGES as $key => [$lo, $hi]) {
            if (array_key_exists($key, $placement) && ! $this->isCount($placement[$key], $lo, $hi)) {
                $this->err("{$where}.{$key}: a whole number {$lo}–{$hi}");
            }
        }
        if (array_key_exists('from', $placement)) {
            $from = $placement['from'];
            if (! is_string($from) || ! isset($units[$from]) || $from === $unitId) {
                $this->err("{$where}.from: unknown unit '".$this->show($from)."'");
            } elseif (in_array($unitId, $before, true)) {
                $this->err("{$where}.from: {$unitId} is already on the field — `from` goes on its first placement");
            } elseif (! in_array($from, $before, true)) {
                $this->err("{$where}.from: '{$from}' was not on the field in the previous step");
            }
        }
        if (array_key_exists('into', $placement) && ! (is_string($placement['into']) && isset($units[$placement['into']]) && $placement['into'] !== $unitId)) {
            $this->err("{$where}.into: unknown unit '".$this->show($placement['into'])."'");
        }
        $state = $placement['state'] ?? null;
        $this->states[$unitId] = is_string($state) ? $state : ($this->states[$unitId] ?? 'ready');
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
        $this->needs($where, $move, 'move');
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
        $this->added("{$where}.type", $move['type'] ?? null, V::V2_MOVE_TYPES, 2);
        $this->added("{$where}.type", $move['type'] ?? null, V::V3_MOVE_TYPES, 3);
        if (! $this->isPointList($move['path'] ?? null, 2)) {
            $this->err("{$where}.path: ≥2 [lon, lat] points");
        }
        $continues = $move['continues'] ?? null;
        if ($continues !== null && ! (is_array($continues) && $this->isPoint($continues['toward'] ?? null) && (! isset($continues['label']) || is_string($continues['label'])))) {
            $this->err("{$where}.continues: {toward: [lon, lat], label?}");
        }
        if (array_key_exists('orient', $move) && ! in_array($move['orient'], V::MOVE_ORIENTS, true)) {
            $this->err("{$where}.orient: one of ".implode(', ', V::MOVE_ORIENTS));
        }
        if (array_key_exists('target', $move) && ! (is_string($move['target']) && isset($units[$move['target']]))) {
            $this->err("{$where}.target: unknown unit '".$this->show($move['target'])."'");
        }
        foreach (['arc', 'conjectural'] as $key) {
            if (array_key_exists($key, $move) && ! is_bool($move[$key])) {
                $this->err("{$where}.{$key}: true or false");
            }
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

    /**
     * Error on the fields a document uses that need a newer schema than it
     * declares (both newer schemas, or only `$version`).
     */
    private function needs(string $where, mixed $object, string $group, ?int $version = null): void
    {
        if (! is_array($object)) {
            return;
        }
        foreach ([2 => V::V2_FIELDS, 3 => V::V3_FIELDS] as $schema => $fields) {
            if ($this->schema >= $schema || ($version !== null && $version !== $schema)) {
                continue;
            }
            $used = array_values(array_filter($fields[$group] ?? [], fn (string $field) => array_key_exists($field, $object)));
            if ($used !== []) {
                $this->err("{$where}: ".implode(', ', $used)." need schema {$schema} — ".$this->bump($schema));
            }
        }
    }

    /**
     * Error on a vocabulary value added in a newer schema than the document's.
     *
     * @param  list<string>  $added
     */
    private function added(string $where, mixed $value, array $added, int $schema): void
    {
        if ($this->schema < $schema && in_array($value, $added, true)) {
            $this->err("{$where}: '".$this->show($value)."' needs schema {$schema} — ".$this->bump($schema));
        }
    }

    private function bump(int $schema): string
    {
        return $schema === 2 ? 'set `schema: 2`' : "bump schema to {$schema}";
    }

    /** One ring of ≥3 points, or (schema 3) a list of such rings. */
    public static function isArea(mixed $value): bool
    {
        if (self::isRing($value)) {
            return true;
        }
        if (! self::isMulti($value)) {
            return false;
        }
        foreach ($value as $ring) {
            if (! self::isRing($ring)) {
                return false;
            }
        }

        return true;
    }

    /** Whether an `area` is a list of rings rather than one ring. */
    public static function isMulti(mixed $value): bool
    {
        return is_array($value) && array_is_list($value) && $value !== []
            && is_array($value[0]) && $value[0] !== [] && is_array($value[0][0] ?? null);
    }

    private static function isRing(mixed $value): bool
    {
        if (! is_array($value) || ! array_is_list($value) || count($value) < 3) {
            return false;
        }
        foreach ($value as $point) {
            if (! self::point($point)) {
                return false;
            }
        }

        return true;
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

    private function isCount(mixed $value, int $lo = 0, ?int $hi = null): bool
    {
        return is_int($value) && $value >= $lo && ($hi === null || $value <= $hi);
    }

    private function isText(mixed $value): bool
    {
        return is_string($value) && trim($value) !== '';
    }

    private function isPoint(mixed $value): bool
    {
        return self::point($value);
    }

    /** A [lon, lat] pair in range. */
    public static function point(mixed $value): bool
    {
        return is_array($value)
            && array_is_list($value)
            && count($value) === 2
            && (is_int($value[0]) || is_float($value[0])) && (is_int($value[1]) || is_float($value[1]))
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
