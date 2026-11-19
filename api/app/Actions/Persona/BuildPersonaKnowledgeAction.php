<?php

declare(strict_types=1);

namespace App\Actions\Persona;

use App\Models\Entity;
use App\Support\Persona\AnachronismGuard;
use App\Support\Persona\PersonaKnowledge;
use Illuminate\Support\Facades\DB;

/**
 * The surroundings a speaker would know, from atlas data only (no LLM).
 *
 * Reusable by anything that needs "what is around this person/place in this
 * era": the chat system prompt today, a city or family speaker later.
 *
 * Steps (each one small, indexed query; see docs/architecture/talk-with-people.md):
 *  1. direct relationships, both directions, dated at or before the knowledge year;
 *  2. the realm: the polities they ruled and those polities' wars, allies, vassals;
 *  3. anchor points from the places in 1, then notable cities, polities, wars,
 *     battles and treaties near them that were active in their lifetime;
 *  4. chronicle entries that mention them;
 *  5. famous contemporaries (wide-reach speakers only).
 *
 * Nothing dated after `$knowledgeYear` is returned, and free text that names
 * a later year is dropped (AnachronismGuard). How much a speaker would know
 * scales with their impact score ("reach": wide, regional, local).
 */
class BuildPersonaKnowledgeAction
{
    /** Importance of a relationship type for the briefing (higher = first). */
    private const WEIGHT = [
        'rules' => 100, 'governed_by' => 70, 'married_to' => 95, 'parent_of' => 92, 'child_of' => 92,
        'sibling_of' => 85, 'at_war_with' => 90, 'allied_with' => 80, 'vassal_of' => 78, 'suzerain_of' => 78,
        'succeeded_by' => 75, 'preceded_by' => 75, 'assassinated_by' => 88, 'commanded' => 82,
        'defeated_at' => 84, 'victorious_at' => 84, 'fought_at' => 76, 'participated_in' => 74,
        'founded' => 72, 'member_of_dynasty' => 80, 'mentor_of' => 66, 'student_of' => 66, 'patron_of' => 60,
        'commissioned' => 55, 'authored' => 50, 'born_in' => 60, 'resided_in' => 58, 'influenced_by' => 45,
        'adopted' => 70, 'signed_by' => 68, 'adheres_to' => 50,
    ];

    /** Phrase for the speaker as source of the link. */
    private const OUT = [
        'rules' => 'ruled', 'governed_by' => 'was governed by', 'married_to' => 'married', 'parent_of' => 'parent of',
        'child_of' => 'child of', 'sibling_of' => 'sibling of', 'at_war_with' => 'at war with', 'allied_with' => 'allied with',
        'vassal_of' => 'vassal of', 'suzerain_of' => 'overlord of', 'succeeded_by' => 'succeeded by', 'preceded_by' => 'preceded by',
        'assassinated_by' => 'killed by', 'commanded' => 'commanded', 'defeated_at' => 'defeated at', 'victorious_at' => 'won at',
        'fought_at' => 'fought at', 'participated_in' => 'took part in', 'founded' => 'founded', 'member_of_dynasty' => 'of the dynasty',
        'mentor_of' => 'mentor of', 'student_of' => 'student of', 'patron_of' => 'patron of', 'commissioned' => 'commissioned',
        'authored' => 'wrote', 'born_in' => 'born in', 'resided_in' => 'lived in', 'influenced_by' => 'influenced by',
        'adopted' => 'adopted', 'signed_by' => 'signed', 'adheres_to' => 'followed',
    ];

    /** Phrase when the speaker is the target of the link. */
    private const IN = [
        'rules' => 'ruled by', 'married_to' => 'married', 'parent_of' => 'child of', 'child_of' => 'parent of',
        'sibling_of' => 'sibling of', 'at_war_with' => 'at war with', 'allied_with' => 'allied with',
        'vassal_of' => 'overlord of', 'suzerain_of' => 'vassal of', 'succeeded_by' => 'succeeded', 'preceded_by' => 'followed by',
        'assassinated_by' => 'killed', 'commanded' => 'commanded by', 'mentor_of' => 'student of', 'student_of' => 'mentor of',
        'patron_of' => 'protégé of', 'member_of_dynasty' => 'head of the house of', 'influenced_by' => 'influenced',
        'adopted' => 'adopted by', 'participated_in' => 'joined by', 'founded' => 'founded by',
    ];

    /** Never part of a briefing: unknowable to the speaker or pure noise. */
    private const SKIP = ['died_in', 'located_at', 'contributed_to', 'built_by', 'recruited_from', 'stationed_at'];

    private const REALM_TYPES = [
        'at_war_with', 'allied_with', 'vassal_of', 'suzerain_of', 'part_of', 'contains', 'capital_of',
        'participated_in', 'fought_at', 'succeeded_by', 'preceded_by',
    ];

    private const NEARBY_TYPES = ['city', 'political_entity', 'event_war', 'event_battle', 'event_treaty', 'event_rebellion'];

    public function __invoke(Entity $person, ?int $knowledgeYear = null, ?int $tokenBudget = null): PersonaKnowledge
    {
        $range = DB::table('entity_temporal_ranges')->where('entity_id', $person->entity_id)->where('is_primary', true)
            ->first(['start_year', 'end_year']);
        $birth = $range?->start_year;
        $k = $knowledgeYear ?? $range?->end_year;
        if ($k === null) {
            return new PersonaKnowledge(0, $birth, 'local', []);
        }
        $k = (int) $k;
        $windowStart = $birth !== null ? max($birth + 12, $k - 70) : $k - 50;
        $seen = [$person->entity_id => true];
        [$relations, $anchorsSource, $realmIds, $degree] = $this->relations($person, $k, $seen);
        $reach = $this->reach((int) $person->impact_score, $degree);
        $domain = $this->realm($realmIds, $k, $windowStart, $seen);
        $anchors = $this->anchors($anchorsSource, $reach);
        $nearby = $this->nearby($anchors, $reach, $k, $windowStart, $seen);
        $chronicle = $this->chronicle($person, $k);
        $contemporaries = $reach === 'wide' ? $this->contemporaries($k, $windowStart, $seen, 6)
            : ($reach === 'regional' ? $this->contemporaries($k, $windowStart, $seen, 3) : []);

        $knowledge = new PersonaKnowledge($k, $birth, $reach, [
            'relations' => $relations,
            'domain' => $domain,
            'nearby' => $nearby,
            'chronicle' => $chronicle,
            'contemporaries' => $contemporaries,
        ], ['anchors' => count($anchors)]);

        return $knowledge->fit($tokenBudget ?? (int) config('persona.knowledge.token_budget', 2500));
    }

    /**
     * How far a speaker's knowledge reaches. Impact scores top out around 70
     * for many famous people, so the number of atlas links counts too.
     */
    private function reach(int $impact, int $degree): string
    {
        if ($impact >= 80 || $degree >= 40 || ($impact >= 70 && $degree >= 20)) {
            return 'wide';
        }

        return $impact >= 60 || $degree >= 8 ? 'regional' : 'local';
    }

    /**
     * @param  array<string, true>  $seen
     * @return array{0: list<string>, 1: list<object>, 2: list<string>, 3: int}
     */
    private function relations(Entity $person, int $k, array &$seen): array
    {
        $id = $person->entity_id;
        $cols = 'r.relationship_type, r.start_year AS rs, r.end_year AS re, e.entity_id, e.name, e.entity_type, e.impact_score';
        $common = "(t.start_year IS NULL OR t.start_year <= {$k}) AND (r.start_year IS NULL OR r.start_year <= {$k})";
        $skip = "'".implode("','", self::SKIP)."'";

        $rows = [];
        foreach ([['out', 'source_entity_id', 'target_entity_id'], ['in', 'target_entity_id', 'source_entity_id']] as [$dir, $me, $other]) {
            $q = DB::select(
                "SELECT {$cols}, ? AS dir FROM relationships r
                 JOIN entities e ON e.entity_id = r.{$other}
                 LEFT JOIN entity_temporal_ranges t ON t.entity_id = e.entity_id AND t.is_primary
                 WHERE r.{$me} = ? AND r.relationship_type NOT IN ({$skip}) AND {$common}
                 ORDER BY e.impact_score DESC NULLS LAST LIMIT 150",
                [$dir, $id],
            );
            array_push($rows, ...$q);
        }

        $groups = [];
        $anchorsSource = [];
        $realmIds = [];
        foreach ($rows as $row) {
            $type = $row->relationship_type;
            $phrase = $row->dir === 'out' ? (self::OUT[$type] ?? null) : (self::IN[$type] ?? null);
            if ($phrase === null) {
                continue;
            }
            $weight = self::WEIGHT[$type] ?? 40;
            $groups[$phrase]['weight'] = max($groups[$phrase]['weight'] ?? 0, $weight);
            $groups[$phrase]['items'][mb_strtolower($row->name)] ??= ['row' => $row, 'score' => $weight * 1000 + (int) $row->impact_score];
            if ($row->dir === 'out' && in_array($type, ['rules', 'governed_by'], true) && $row->entity_type === 'political_entity') {
                $realmIds[$row->entity_id] = (int) $row->impact_score;
            }
            if ($row->dir === 'out' && in_array($type, ['born_in', 'resided_in', 'rules', 'fought_at', 'victorious_at', 'defeated_at', 'participated_in', 'founded'], true)) {
                $anchorsSource[$row->entity_id] = (object) ['id' => $row->entity_id, 'weight' => $weight, 'impact' => (int) $row->impact_score];
            }
        }

        uasort($groups, fn ($a, $b) => $b['weight'] <=> $a['weight']);
        $lines = [];
        foreach ($groups as $phrase => $group) {
            $items = collect($group['items'])->sortByDesc('score')->take(6)->values();
            $total = count($group['items']);
            $parts = $items->map(function ($it) use ($k) {
                $r = $it['row'];

                return $r->name.self::yearsSuffix($r->rs, $r->re, $k);
            })->all();
            $line = $phrase.': '.implode('; ', $parts).($total > 6 ? '; and '.($total - 6).' more' : '');
            $lines[] = $line;
            foreach ($items as $it) {
                $seen[$it['row']->entity_id] = true;
            }
        }

        arsort($realmIds);

        return [array_slice($lines, 0, 22), array_values($anchorsSource), array_slice(array_keys($realmIds), 0, 3), count($rows)];
    }

    /** " (1799-1804)"; an end after the knowledge year is cut, since the speaker cannot know it. */
    private static function yearsSuffix(?int $start, ?int $end, int $k): string
    {
        if ($start === null) {
            return '';
        }
        $s = PersonaKnowledge::formatYear($start);
        if ($end !== null && $end > $k) {
            return ' (since '.$s.')';
        }

        return ' ('.($end !== null && $end !== $start ? $s.'-'.PersonaKnowledge::formatYear($end) : $s).')';
    }

    /**
     * Allies, enemies and wars of the polities the speaker ruled.
     *
     * @param  list<string>  $realmIds
     * @param  array<string, true>  $seen
     * @return list<string>
     */
    private function realm(array $realmIds, int $k, int $windowStart, array &$seen): array
    {
        if ($realmIds === []) {
            return [];
        }
        $types = "'".implode("','", self::REALM_TYPES)."'";
        $names = DB::table('entities')->whereIn('entity_id', $realmIds)->pluck('name', 'entity_id');
        $lines = [];
        foreach ($realmIds as $realmId) {
            $rows = [];
            foreach ([['out', 'source_entity_id', 'target_entity_id'], ['in', 'target_entity_id', 'source_entity_id']] as [$dir, $me, $other]) {
                $q = DB::select(
                    "SELECT r.relationship_type, r.start_year AS rs, r.end_year AS re, e.entity_id, e.name, e.impact_score, ? AS dir
                     FROM relationships r JOIN entities e ON e.entity_id = r.{$other}
                     LEFT JOIN entity_temporal_ranges t ON t.entity_id = e.entity_id AND t.is_primary
                     WHERE r.{$me} = ? AND r.relationship_type IN ({$types})
                       AND (r.start_year IS NULL OR r.start_year <= ?) AND (r.end_year IS NULL OR r.end_year >= ?)
                       AND (t.start_year IS NULL OR t.start_year <= ?)
                     ORDER BY e.impact_score DESC NULLS LAST LIMIT 40",
                    [$dir, $realmId, $k, $windowStart, $k],
                );
                array_push($rows, ...$q);
            }
            $by = [];
            foreach ($rows as $row) {
                $type = $row->relationship_type;
                $phrase = $row->dir === 'out' ? (self::OUT[$type] ?? self::REALM_OUT[$type] ?? null) : (self::IN[$type] ?? self::REALM_IN[$type] ?? null);
                if ($phrase === null || isset($seen[$row->entity_id])) {
                    continue;
                }
                $by[$phrase]['w'] = max($by[$phrase]['w'] ?? 0, self::WEIGHT[$type] ?? 40);
                $by[$phrase]['items'][mb_strtolower($row->name)] ??= $row;
            }
            uasort($by, fn ($a, $b) => $b['w'] <=> $a['w']);
            $parts = [];
            foreach ($by as $phrase => $group) {
                $take = array_slice(array_values($group['items']), 0, 5);
                $parts[] = $phrase.' '.implode('; ', array_map(fn ($r) => $r->name.self::yearsSuffix($r->rs, $r->re, $k), $take));
                foreach ($take as $r) {
                    $seen[$r->entity_id] = true;
                }
            }
            if ($parts !== []) {
                $lines[] = ($names[$realmId] ?? 'Their realm').' — '.implode(' | ', array_slice($parts, 0, 6));
            }
        }

        return $lines;
    }

    private const REALM_OUT = ['part_of' => 'part of', 'contains' => 'holds', 'capital_of' => 'capital of'];

    private const REALM_IN = ['part_of' => 'includes', 'contains' => 'part of', 'capital_of' => 'has the capital'];

    /**
     * Up to three places, clustered on a 2-degree grid, strongest first.
     *
     * @param  list<object>  $source
     * @return list<array{lon: float, lat: float}>
     */
    private function anchors(array $source, string $reach): array
    {
        if ($source === []) {
            return [];
        }
        $ids = array_map(fn ($s) => $s->id, array_slice($source, 0, 80));
        $pts = DB::table('entity_locations')->whereIn('entity_id', $ids)->whereNotNull('geom')
            ->selectRaw('entity_id, ST_X(ST_Centroid(geom)) AS lon, ST_Y(ST_Centroid(geom)) AS lat')->get()->groupBy('entity_id');
        $cells = [];
        foreach ($source as $s) {
            $p = $pts[$s->id][0] ?? null;
            if ($p === null) {
                continue;
            }
            $key = floor($p->lon / 2).':'.floor($p->lat / 2);
            $c = &$cells[$key];
            $c['score'] = ($c['score'] ?? 0) + $s->weight + $s->impact / 10;
            $c['lon'] = ($c['lon'] ?? 0) + $p->lon;
            $c['lat'] = ($c['lat'] ?? 0) + $p->lat;
            $c['n'] = ($c['n'] ?? 0) + 1;
            unset($c);
        }
        uasort($cells, fn ($a, $b) => $b['score'] <=> $a['score']);

        return collect($cells)->take($reach === 'local' ? 1 : 3)
            ->map(fn ($c) => ['lon' => $c['lon'] / $c['n'], 'lat' => $c['lat'] / $c['n']])->values()->all();
    }

    /**
     * Notable settlements, states, wars and treaties around the anchors in
     * the speaker's lifetime. The spatial candidates are materialised first
     * (the GiST index finds a few thousand points), then filtered by type and
     * date and ranked by impact: planning it the other way walks the impact
     * index hoping for early matches, which is slow for sparse eras.
     *
     * @param  list<array{lon: float, lat: float}>  $anchors
     * @param  array<string, true>  $seen
     * @return list<string>
     */
    private function nearby(array $anchors, string $reach, int $k, int $windowStart, array &$seen): array
    {
        if ($anchors === []) {
            return [];
        }
        $radius = match ($reach) {
            'wide' => (float) config('persona.knowledge.radius_degrees', 3.0),
            'regional' => 2.0,
            default => 1.0,
        };
        $types = "'".implode("','", self::NEARBY_TYPES)."'";
        $found = [];
        foreach ($anchors as $a) {
            $rows = DB::select(
                "WITH near AS MATERIALIZED (
                    SELECT entity_id FROM entity_locations
                    WHERE ST_DWithin(geom, ST_SetSRID(ST_MakePoint(?, ?), 4326), ?)
                 )
                 SELECT e.entity_id, e.name, e.entity_type, e.impact_score, t.start_year, t.end_year
                 FROM near n
                 JOIN entities e ON e.entity_id = n.entity_id AND e.entity_type IN ({$types})
                 JOIN entity_temporal_ranges t ON t.entity_id = e.entity_id AND t.is_primary
                 WHERE t.start_year <= ? AND COALESCE(t.end_year, 9999) >= ?
                 ORDER BY e.impact_score DESC NULLS LAST LIMIT 10",
                [$a['lon'], $a['lat'], $radius, $k, $windowStart],
            );
            foreach ($rows as $r) {
                if (! isset($seen[$r->entity_id])) {
                    $found[$r->entity_id] = $r;
                }
            }
        }
        $label = ['city' => 'city', 'political_entity' => 'state', 'event_war' => 'war', 'event_battle' => 'battle', 'event_treaty' => 'treaty', 'event_rebellion' => 'rebellion'];
        $items = collect($found)->sortByDesc('impact_score')->take(16);
        $lines = [];
        foreach ($items as $r) {
            $seen[$r->entity_id] = true;
            $lines[] = $r->name.' ('.($label[$r->entity_type] ?? $r->entity_type).', '.self::span($r->start_year, $r->end_year, $k).')';
        }

        return $this->pack($lines, 2);
    }

    private static function span(?int $s, ?int $e, int $k): string
    {
        $a = $s === null ? '?' : PersonaKnowledge::formatYear($s);
        if ($e === null || $e === $s) {
            return $a;
        }
        if ($e > $k) {
            return 'since '.$a;
        }

        return $a.'-'.PersonaKnowledge::formatYear($e);
    }

    /** Join short items two to a line, so the briefing stays compact. */
    private function pack(array $items, int $perLine): array
    {
        return array_map(fn ($chunk) => implode('; ', $chunk), array_chunk($items, max(1, $perLine * 3)));
    }

    /** @return list<string> */
    private function chronicle(Entity $person, int $k): array
    {
        $rows = DB::select(
            'SELECT ce.start_year, ce.end_year, ce.narrative_text
             FROM chronicle_entry_entities cee JOIN chronicle_entries ce ON ce.entry_id = cee.entry_id
             WHERE cee.entity_id = ? AND ce.start_year IS NOT NULL AND ce.start_year <= ? AND COALESCE(ce.end_year, ce.start_year) <= ?
             ORDER BY ce.impact_score DESC NULLS LAST, ce.start_year LIMIT 8',
            [$person->entity_id, $k, $k],
        );
        $lines = [];
        foreach ($rows as $r) {
            $snippet = AnachronismGuard::snippet($r->narrative_text, $k, 200);
            if ($snippet !== null) {
                $lines[] = PersonaKnowledge::formatYear((int) $r->start_year).': '.$snippet;
            }
            if (count($lines) >= 4) {
                break;
            }
        }

        return $lines;
    }

    /**
     * The best-known people alive in the speaker's adult life, at lower priority.
     *
     * @param  array<string, true>  $seen
     * @return list<string>
     */
    private function contemporaries(int $k, int $windowStart, array &$seen, int $limit): array
    {
        // Impact scores of the best-known people tie at 70, so the 60 best
        // candidates of the era are ranked again by how many atlas links they have.
        $rows = DB::select(
            "SELECT c.*, (SELECT count(*) FROM relationships r WHERE r.source_entity_id = c.entity_id)
                       + (SELECT count(*) FROM relationships r WHERE r.target_entity_id = c.entity_id) AS degree
             FROM (
               SELECT e.entity_id, e.name, e.impact_score, t.start_year, t.end_year
               FROM entities e JOIN entity_temporal_ranges t ON t.entity_id = e.entity_id AND t.is_primary
               WHERE e.entity_type = 'person' AND e.impact_score >= 70
                 AND t.start_year <= ? AND t.start_year >= ? AND COALESCE(t.end_year, 9999) >= ?
               ORDER BY e.impact_score DESC, e.name LIMIT 60
             ) c ORDER BY c.impact_score DESC, degree DESC LIMIT ?",
            [$k - 25, $k - 110, $windowStart, $limit + 6],
        );
        $names = [];
        foreach ($rows as $r) {
            if (isset($seen[$r->entity_id])) {
                continue;
            }
            $seen[$r->entity_id] = true;
            $names[] = $r->name.' (born '.PersonaKnowledge::formatYear((int) $r->start_year).')';
            if (count($names) >= $limit) {
                break;
            }
        }

        return $names === [] ? [] : [implode('; ', $names)];
    }
}
