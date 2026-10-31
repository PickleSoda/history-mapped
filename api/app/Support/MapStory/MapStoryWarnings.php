<?php

declare(strict_types=1);

namespace App\Support\MapStory;

use App\Support\MapStory\MapStoryVocabulary as V;

/**
 * The main plausibility warnings of pipeline/map_stories/validate.py, for the
 * admin editor and the AI agent: text lengths, unplaced units, a story spread
 * too wide, a unit that jumps with no arrow (distances scale with the kind),
 * a unit given an arrow or the focus before it is placed, and ships on land or troops at
 * sea. Warnings never block a save. Run it on a document that passes
 * MapStoryDocument::errors(); messages use the Python wording, so
 * "step '<id>'…" names the step.
 */
final class MapStoryWarnings
{
    /** How far (km) any point may lie from the story's centre, by kind. */
    public const SPREAD_KM = [
        'battle' => 20, 'naval_battle' => 30, 'siege' => 15,
        'campaign' => 3000, 'war' => 3000, 'expansion' => 3000,
        'diffusion' => 5000, 'event' => 5000,
        'epidemic' => 20000, 'trade_route' => 20000, 'migration' => 20000, 'exploration' => 20000,
    ];

    /** How far (m) a unit may move between frames without an arrow, by kind. */
    public const TELEPORT_M = [
        'battle' => 900, 'naval_battle' => 1500, 'siege' => 600,
        'campaign' => 150000, 'war' => 150000, 'expansion' => 150000,
        'diffusion' => 300000, 'event' => 300000,
        'epidemic' => 2000000, 'trade_route' => 2000000, 'migration' => 2000000, 'exploration' => 2000000,
    ];

    /** Text length targets [min, max] (characters), as the Python validator's. */
    public const TEXT_LIMITS = [
        'title' => [3, 120], 'date_label' => [3, 80], 'intro' => [250, 1400], 'outcome' => [20, 300],
        'uncertainty' => [40, 1500], 'step.title' => [3, 80], 'step.narrative' => [150, 1100],
    ];

    private const SHIP_UNIT_KINDS = ['warship', 'ship', 'transport', 'fleet', 'merchant_ship'];

    private const SHORE_M = 400;

    private const EARTH_R = 6371008.8;

    /** @var list<string> */
    private array $warnings = [];

    /**
     * @param  array<string, mixed>  $doc
     * @return list<string>
     */
    public static function of(array $doc): array
    {
        $check = new self;
        $check->run(MapStoryAmbient::normalise($doc));

        return $check->warnings;
    }

    /** @param  array<string, mixed>  $doc */
    private function run(array $doc): void
    {
        $kind = is_string($doc['kind'] ?? null) && isset(self::SPREAD_KM[$doc['kind']]) ? $doc['kind'] : 'battle';
        $steps = array_values(array_filter($doc['steps'] ?? [], 'is_array'));

        foreach (['title', 'date_label', 'intro', 'outcome', 'uncertainty'] as $key) {
            $this->length($key, $doc[$key] ?? null, self::TEXT_LIMITS[$key]);
        }
        [$lo, $hi] = in_array($kind, V::BATTLE_KINDS, true) ? [5, 16] : [3, 40];
        if (count($steps) < $lo || count($steps) > $hi) {
            $this->warnings[] = 'steps: '.count($steps)." (aim for {$lo}–{$hi})";
        }
        foreach ($steps as $step) {
            $where = "step '".($step['id'] ?? '?')."'";
            $this->length("{$where}.title", $step['title'] ?? null, self::TEXT_LIMITS['step.title']);
            $this->length("{$where}.narrative", $step['narrative'] ?? null, self::TEXT_LIMITS['step.narrative']);
        }

        $units = [];
        foreach ($doc['units'] ?? [] as $unit) {
            if (is_array($unit) && is_string($unit['id'] ?? null)) {
                $units[$unit['id']] = $unit;
            }
        }
        $placed = [];
        foreach ($steps as $step) {
            foreach ($this->phases($step) as $phase) {
                foreach (array_keys(is_array($phase['positions'] ?? null) ? $phase['positions'] : []) as $uid) {
                    $placed[(string) $uid] = true;
                }
            }
        }
        $never = array_values(array_diff(array_keys($units), array_keys($placed)));
        sort($never);
        if ($never !== []) {
            $this->warnings[] = 'units never placed: '.implode(', ', $never);
        }

        $frames = $this->frames($steps);
        $this->spread($doc, $steps, $frames, $kind);
        $this->transitions($steps, $frames, $kind);
        $this->landAndWater($doc, $steps, $frames, $units);
    }

    /** @param  array{0: int, 1: int}  $limits */
    private function length(string $where, mixed $text, array $limits): void
    {
        if (! is_string($text)) {
            return;
        }
        $n = mb_strlen(trim($text));
        [$lo, $hi] = $limits;
        if ($n < $lo) {
            $this->warnings[] = "{$where}: only {$n} characters (aim for {$lo}–{$hi})";
        } elseif ($n > $hi) {
            $this->warnings[] = "{$where}: {$n} characters (aim for {$lo}–{$hi})";
        }
    }

    /**
     * The step itself, then each of its beats.
     *
     * @param  array<string, mixed>  $step
     * @return list<array<string, mixed>>
     */
    private function phases(array $step): array
    {
        $beats = is_array($step['beats'] ?? null) ? array_values(array_filter($step['beats'], 'is_array')) : [];

        return [$step, ...$beats];
    }

    /**
     * Every phase's frame (validate.py `_resolve`): unit id → placement, with
     * `with` resolved to its host's point and hidden units left out.
     *
     * @param  list<array<string, mixed>>  $steps
     * @return list<list<array<string, array<string, mixed>>>>
     */
    private function frames(array $steps): array
    {
        $current = [];
        $out = [];
        foreach ($steps as $step) {
            $frames = [];
            foreach ($this->phases($step) as $phase) {
                foreach (is_array($phase['positions'] ?? null) ? $phase['positions'] : [] as $uid => $placement) {
                    if (! is_array($placement)) {
                        continue;
                    }
                    $uid = (string) $uid;
                    $merged = array_merge($current[$uid] ?? [], $placement);
                    if (array_key_exists('at', $placement) && ! array_key_exists('with', $placement)) {
                        unset($merged['with']);
                    }
                    if (array_key_exists('with', $placement) && ! array_key_exists('at', $placement)) {
                        unset($merged['at']);
                    }
                    $current[$uid] = $merged;
                }
                $frames[] = $this->snapshot($current);
                foreach ($current as $uid => $placement) {
                    unset($current[$uid]['from']);
                    if (($placement['into'] ?? null) !== null) {
                        unset($current[$uid]['into']);
                        $current[$uid]['state'] = 'hidden';
                    }
                }
            }
            $out[] = $frames;
        }

        return $out;
    }

    /**
     * @param  array<string, array<string, mixed>>  $current
     * @return array<string, array<string, mixed>>
     */
    private function snapshot(array $current): array
    {
        $snapshot = array_filter($current, fn (array $p) => ($p['state'] ?? null) !== 'hidden');
        foreach (array_keys($snapshot) as $uid) {
            $with = $snapshot[$uid]['with'] ?? null;
            if (is_string($with) && ! isset($snapshot[$uid]['at'])) {
                $host = $snapshot[$with] ?? $current[$with] ?? [];
                if (isset($host['at'])) {
                    $snapshot[$uid]['at'] = $host['at'];
                }
            }
        }
        foreach (array_keys($snapshot) as $uid) {
            $into = $snapshot[$uid]['into'] ?? null;
            if (is_string($into) && isset($snapshot[$into]['at'])) {
                $snapshot[$uid]['at'] = $snapshot[$into]['at'];
            }
        }

        return $snapshot;
    }

    /**
     * Points that lie too far from the story's centre (the median point).
     *
     * @param  array<string, mixed>  $doc
     * @param  list<array<string, mixed>>  $steps
     * @param  list<list<array<string, array<string, mixed>>>>  $frames
     */
    private function spread(array $doc, array $steps, array $frames, string $kind): void
    {
        $points = [];
        foreach ($doc['features'] ?? [] as $feature) {
            if (is_array($feature)) {
                array_push($points, ...$this->geometryPoints($feature));
            }
        }
        foreach ($steps as $step) {
            foreach (is_array($step['features'] ?? null) ? $step['features'] : [] as $state) {
                if (is_array($state)) {
                    array_push($points, ...$this->geometryPoints($state));
                }
            }
        }
        foreach ($steps as $i => $step) {
            foreach ($this->phases($step) as $k => $phase) {
                $frame = $frames[$i][$k] ?? [];
                $offstage = array_keys(array_filter($frame, fn (array $p) => ($p['frame'] ?? null) === false));
                foreach (is_array($phase['positions'] ?? null) ? $phase['positions'] : [] as $uid => $placement) {
                    if (is_array($placement) && ! in_array((string) $uid, $offstage, true) && MapStoryDocument::point($placement['at'] ?? null)) {
                        $points[] = $placement['at'];
                    }
                }
                foreach (is_array($phase['moves'] ?? null) ? $phase['moves'] : [] as $move) {
                    if (is_array($move) && ! in_array($move['unit'] ?? null, $offstage, true)) {
                        foreach (is_array($move['path'] ?? null) ? $move['path'] : [] as $p) {
                            if (MapStoryDocument::point($p)) {
                                $points[] = $p;
                            }
                        }
                    }
                }
                foreach (is_array($phase['notes'] ?? null) ? $phase['notes'] : [] as $note) {
                    if (is_array($note) && MapStoryDocument::point($note['at'] ?? null)) {
                        $points[] = $note['at'];
                    }
                }
            }
        }
        if ($points === []) {
            return;
        }
        $lons = array_column($points, 0);
        $lats = array_column($points, 1);
        sort($lons);
        sort($lats);
        $centre = [$lons[intdiv(count($lons), 2)], $lats[intdiv(count($lats), 2)]];
        $limit = self::SPREAD_KM[$kind] * 1000;
        $far = array_values(array_filter($points, fn (array $p) => self::distance($p, $centre) > $limit));
        if ($far !== []) {
            $this->warnings[] = count($far).' point(s) lie more than '.self::SPREAD_KM[$kind].' km from the story\'s centre '
                .json_encode($centre).' (e.g. '.json_encode($far[0]).')';
        }
    }

    /**
     * @param  array<string, mixed>  $object
     * @return list<array{0: float|int, 1: float|int}>
     */
    private function geometryPoints(array $object): array
    {
        $points = MapStoryDocument::point($object['at'] ?? null) ? [$object['at']] : [];
        foreach (is_array($object['line'] ?? null) ? $object['line'] : [] as $p) {
            if (MapStoryDocument::point($p)) {
                $points[] = $p;
            }
        }
        foreach (self::rings($object['area'] ?? null) as $ring) {
            foreach ($ring as $p) {
                if (MapStoryDocument::point($p)) {
                    $points[] = $p;
                }
            }
        }

        return $points;
    }

    /**
     * A unit that jumps without an arrow, and a unit given an arrow or the
     * focus before its first placement.
     *
     * @param  list<array<string, mixed>>  $steps
     * @param  list<list<array<string, array<string, mixed>>>>  $frames
     */
    private function transitions(array $steps, array $frames, string $kind): void
    {
        $previous = null;
        $placed = [];
        foreach ($steps as $i => $step) {
            foreach ($this->phases($step) as $k => $phase) {
                $where = "step '".($step['id'] ?? '?')."'".($k > 0 ? " beat {$k}" : '');
                $current = $frames[$i][$k] ?? [];
                foreach (array_keys(is_array($phase['positions'] ?? null) ? $phase['positions'] : []) as $uid) {
                    $placed[(string) $uid] = true;
                }
                $moves = array_values(array_filter(is_array($phase['moves'] ?? null) ? $phase['moves'] : [], 'is_array'));
                $moved = array_map(fn (array $m) => $m['unit'] ?? null, $moves);
                if ($previous !== null) {
                    foreach ($current as $uid => $placement) {
                        $uid = (string) $uid;
                        if (isset($placement['with']) || isset($placement['into']) || ! isset($placement['at']) || in_array($uid, $moved, true)) {
                            continue;
                        }
                        $start = ($previous[$uid] ?? $previous[$placement['from'] ?? ''] ?? [])['at'] ?? null;
                        if (MapStoryDocument::point($start) && MapStoryDocument::point($placement['at'])) {
                            $d = self::distance($start, $placement['at']);
                            if ($d > self::TELEPORT_M[$kind]) {
                                $this->warnings[] = "{$where}: {$uid} moves ".round($d).' m with no move arrow';
                            }
                        }
                    }
                }
                foreach ($moved as $uid) {
                    if (is_string($uid) && ! isset($placed[$uid])) {
                        $this->warnings[] = "{$where}: {$uid} has an arrow before it is placed (give it a position first)";
                    }
                }
                $previous = $current;
            }
            // The step's focus holds for its beats too: a unit its beats place counts.
            foreach ($this->phases($step) as $k => $phase) {
                foreach (is_array($phase['focus'] ?? null) ? $phase['focus'] : [] as $uid) {
                    if (is_string($uid) && ! isset($placed[$uid])) {
                        $this->warnings[] = "step '".($step['id'] ?? '?')."'".($k > 0 ? " beat {$k}" : '').": focus on {$uid} before it is placed";
                    }
                }
            }
        }
    }

    /**
     * Ships on water and troops on land, when the story draws any water.
     *
     * @param  array<string, mixed>  $doc
     * @param  list<array<string, mixed>>  $steps
     * @param  list<list<array<string, array<string, mixed>>>>  $frames
     * @param  array<string, array<string, mixed>>  $units
     */
    private function landAndWater(array $doc, array $steps, array $frames, array $units): void
    {
        $seas = [];
        $shores = [];
        $islands = [];
        foreach ($doc['features'] ?? [] as $feature) {
            $kind = is_array($feature) ? ($feature['kind'] ?? null) : null;
            if (in_array($kind, ['sea', 'lake'], true)) {
                array_push($seas, ...self::rings($feature['area'] ?? null));
            } elseif (in_array($kind, ['river', 'coast'], true) && is_array($feature['line'] ?? null)) {
                $shores[] = $feature['line'];
            } elseif ($kind === 'island') {
                array_push($islands, ...self::rings($feature['area'] ?? null));
            }
        }
        if ($seas === [] && $shores === []) {
            return;
        }
        $afloat = function (array $p) use ($seas, $islands): bool {
            foreach ($islands as $ring) {
                if (self::inRing($p, $ring)) {
                    return false;
                }
            }
            foreach ($seas as $ring) {
                if (self::inRing($p, $ring)) {
                    return true;
                }
            }

            return false;
        };

        $flagged = [];
        foreach ($steps as $i => $step) {
            foreach ($this->phases($step) as $k => $phase) {
                $where = "step '".($step['id'] ?? '?')."'".($k > 0 ? " beat {$k}" : '');
                $landing = [];
                foreach (is_array($phase['moves'] ?? null) ? $phase['moves'] : [] as $move) {
                    if (is_array($move) && ($move['type'] ?? null) === 'landing') {
                        $landing[] = $move['unit'] ?? null;
                    }
                }
                foreach ($frames[$i][$k] ?? [] as $uid => $placement) {
                    $uid = (string) $uid;
                    if (isset($flagged[$uid]) || isset($placement['with']) || isset($placement['into'])
                        || ! MapStoryDocument::point($placement['at'] ?? null) || ! isset($units[$uid])) {
                        continue;
                    }
                    $unitKind = (string) ($units[$uid]['kind'] ?? '');
                    $p = $placement['at'];
                    if (in_array($unitKind, self::SHIP_UNIT_KINDS, true)) {
                        $nearShore = false;
                        foreach ($shores as $line) {
                            if (self::distanceToLine($p, $line) <= self::SHORE_M) {
                                $nearShore = true;
                                break;
                            }
                        }
                        if (! $afloat($p) && ! $nearShore) {
                            $this->warnings[] = "{$where}: {$uid} ({$unitKind}) is not on water — outside every sea/lake and over ".self::SHORE_M.' m from a river or coast';
                            $flagged[$uid] = true;
                        }
                    } elseif (! in_array($uid, $landing, true) && $afloat($p)) {
                        $this->warnings[] = "{$where}: {$uid} ({$unitKind}) stands in the sea or a lake";
                        $flagged[$uid] = true;
                    }
                }
            }
        }
    }

    /** @return list<list<array{0: float|int, 1: float|int}>> one ring, or each ring of a list of rings */
    private static function rings(mixed $area): array
    {
        if (! MapStoryDocument::isArea($area)) {
            return [];
        }

        return MapStoryDocument::isMulti($area) ? array_values($area) : [$area];
    }

    /** Great-circle distance in metres. */
    public static function distance(array $a, array $b): float
    {
        $lat1 = deg2rad((float) $a[1]);
        $lat2 = deg2rad((float) $b[1]);
        $h = sin(($lat2 - $lat1) / 2) ** 2 + cos($lat1) * cos($lat2) * sin(deg2rad((float) $b[0] - (float) $a[0]) / 2) ** 2;

        return 2 * self::EARTH_R * asin(min(1.0, sqrt($h)));
    }

    /** Even-odd ray casting in lon/lat. */
    private static function inRing(array $p, array $ring): bool
    {
        $inside = false;
        $n = count($ring);
        for ($i = 0; $i < $n; $i++) {
            [$x1, $y1] = $ring[($i - 1 + $n) % $n];
            [$x2, $y2] = $ring[$i];
            if (($y1 > $p[1]) !== ($y2 > $p[1]) && $p[0] < $x1 + ($p[1] - $y1) * ($x2 - $x1) / ($y2 - $y1)) {
                $inside = ! $inside;
            }
        }

        return $inside;
    }

    /** The shortest distance (m) from `p` to a polyline, in a local flat projection. */
    private static function distanceToLine(array $p, array $line): float
    {
        $points = array_values(array_filter($line, MapStoryDocument::point(...)));
        if (count($points) === 1) {
            return self::distance($p, $points[0]);
        }
        $local = function (array $q) use ($p): array {
            $lat = deg2rad((float) $p[1]);

            return [deg2rad($q[0] - $p[0]) * self::EARTH_R * cos($lat), deg2rad($q[1] - $p[1]) * self::EARTH_R];
        };
        $best = INF;
        for ($i = 0; $i + 1 < count($points); $i++) {
            [$ax, $ay] = $local($points[$i]);
            [$bx, $by] = $local($points[$i + 1]);
            $dx = $bx - $ax;
            $dy = $by - $ay;
            $seg = $dx * $dx + $dy * $dy;
            $t = $seg == 0 ? 0.0 : max(0.0, min(1.0, -($ax * $dx + $ay * $dy) / $seg));
            $best = min($best, hypot($ax + $t * $dx, $ay + $t * $dy));
        }

        return $best;
    }
}
