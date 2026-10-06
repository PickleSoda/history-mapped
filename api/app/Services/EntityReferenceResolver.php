<?php

declare(strict_types=1);

namespace App\Services;

use Illuminate\Database\Query\Builder;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

/**
 * Resolve a pipeline entity reference (relation endpoint / chronicle secondary
 * entity) to a real entities.entity_id, identity first:
 *
 *   1. entity_id    — a known DB uuid that still exists
 *   2. wikidata_id  — the QID the entity was imported with (the import dedups by
 *                     QID, so a row can carry a different name than the label).
 *                     Guarded: when a name is known, the QID row's name or one
 *                     of its aliases must be name-compatible with it (see
 *                     namesCompatible) — pipeline QIDs are sometimes wrong
 *                     ("World War I" carried World War II's QID), and a blind
 *                     QID hit would attach facts to the wrong entity.
 *   3. exact name
 *   4. case-insensitive name
 *   5. alternative name (entity_aliases), only when it names exactly one entity
 *
 * Temporal namesake guard: given a reference year span (the relation's or the
 * chronicle entry's dates), a row matched by QID, name or alias whose own
 * dates are clearly incompatible is refused, and among same-name rows the
 * date-compatible one wins ('Philip II rules Spain 1556' is Philip II of
 * Spain, never the Macedonian). None / several dated namesakes leave the end
 * unresolved ('namesake_ambiguous'). See temporalFit / pickNamesake.
 *
 * Every lookup is memoised for the lifetime of the instance (one import run).
 */
class EntityReferenceResolver
{
    private const UUID_PATTERN = '/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i';

    /** @var array<string, string|null> */
    private array $byId = [];

    /** @var array<string, string|null> */
    private array $byQid = [];

    /** @var array<string, array{0: list<array<string, mixed>>, 1: list<array<string, mixed>>}> name => [exact rows, case-insensitive rows] */
    private array $nameRows = [];

    /** @var array<string, list<array<string, mixed>>> name => rows naming it by alias */
    private array $aliasRows = [];

    /** @var array<string, array<string, mixed>|null> entity_id => row (entity_type, start_year, end_year) */
    private array $rowInfo = [];

    /** @var array<string, list<string>> entity_id => [name, ...aliases] */
    private array $namesOf = [];

    private const ORDINALS = [
        'first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth', 'tenth',
        'eleventh', 'twelfth', 'thirteenth', 'fourteenth', 'fifteenth', 'sixteenth', 'seventeenth',
        'eighteenth', 'nineteenth', 'twentieth', 'thirtieth',
    ];

    /** A token extended by one of these is the same name inflected (Ottoman→Ottomans). */
    private const PLURAL_SUFFIXES = ['s', 'es'];

    /** Demonym/adjective endings (Assyria→Assyrian, Frank→Frankish); base ≥ 4 letters. */
    private const DERIVED_SUFFIXES = ['n', 'ns', 'an', 'ans', 'ian', 'ians', 'ic', 'ics', 'ish', 'ese'];

    /** Different tokens at least this similar are a near-miss (Romagna/Romania 0.71). */
    private const NEAR_MISS_SIMILARITY = 0.7;

    /**
     * Max years between two non-overlapping spans that may still be the same
     * entity, per entity_type; types absent here are never date-checked
     * (polities, places, culture: fuzzy or open-ended spans, and one generic
     * row like 'Egypt' serves many eras). Mirrors
     * pipeline/agent/tools/disambiguation.py NAMESAKE_TOLERANCE_YEARS (keep in sync).
     */
    public const NAMESAKE_TOLERANCE_YEARS = [
        'person' => 60,
        'dynasty' => 150,
        'military_unit' => 100,
        'event_battle' => 50,
        'event_war' => 50,
        'event_treaty' => 50,
        'event_rebellion' => 50,
        'event_natural_disaster' => 50,
        'event_legal_reform' => 50,
        'event_tech_adoption' => 50,
        'migration' => 100,
        'epidemic_disease' => 100,
    ];

    /** Before this year chronologies disagree by decades: the tolerance widens. */
    public const DEEP_ANTIQUITY_YEAR = -1000;

    public const DEEP_ANTIQUITY_EXTRA_YEARS = 75;

    /**
     * A lone round-century year ('-800', '100') is usually a Wikidata
     * century-precision date stored as one year: it stands for ±100 years.
     */
    public const ROUND_CENTURY_BLUR_YEARS = 100;

    /**
     * Relation types whose date implies every dated end existed then (a ruler
     * rules while alive); influenced_by / inspired / caused / spread_to … may
     * name a long-dead person and are no temporal signal. Mirrors
     * disambiguation.CONTEMPORANEOUS_RELATION_TYPES (keep in sync).
     */
    public const CONTEMPORANEOUS_RELATION_TYPES = [
        'rules', 'governed_by', 'vassal_of', 'suzerain_of', 'allied_with', 'at_war_with',
        'succeeded_by', 'preceded_by', 'born_in', 'died_in', 'resided_in', 'commanded',
        'founded', 'authored', 'commissioned', 'married_to', 'parent_of', 'child_of',
        'sibling_of', 'mentor_of', 'student_of', 'assassinated_by', 'member_of_dynasty',
        'patron_of', 'participated_in', 'fought_at', 'defeated_at', 'victorious_at',
        'stationed_at', 'recruited_from', 'commanded_by', 'controlled_by', 'minted_by',
        'persecuted_by', 'built_by', 'destroyed_by', 'restored_by', 'invented', 'taught_at',
        'signed_by', 'violated_by', 'guaranteed_by', 'mediated_by', 'enforced_by', 'adheres_to',
    ];

    public const NAMESAKE_AMBIGUOUS = 'namesake_ambiguous';

    /** Temporal fit tiers, best first ('conflict' rows are dropped). */
    private const FIT_ORDER = ['match', 'near', 'unknown'];

    public static function isUuid(?string $value): bool
    {
        return is_string($value) && preg_match(self::UUID_PATTERN, $value) === 1;
    }

    /**
     * `via` is one of entity_id|wikidata_id|name|name_ci|alias|none; `reason`
     * explains a miss (what was tried) and is null on success.
     *
     * `$span` is the reference year span [lo, hi] — a relation's dates (only
     * for CONTEMPORANEOUS_RELATION_TYPES) or a chronicle entry's — that QID,
     * name and alias matches must be temporally compatible with (pickNamesake).
     * The entity_id path is an identity assertion and is not date-checked.
     *
     * @param  array{0: int, 1: int}|null  $span
     * @return array{id: string|null, via: string, reason: string|null}
     */
    public function resolve(?string $entityId, ?string $wikidataId, ?string $name, ?array $span = null): array
    {
        $entityId = $this->clean($entityId);
        $wikidataId = $this->clean($wikidataId);
        $name = $this->clean($name);

        $tried = [];

        if ($entityId !== null) {
            if (self::isUuid($entityId)) {
                $id = array_key_exists($entityId, $this->byId)
                    ? $this->byId[$entityId]
                    : ($this->byId[$entityId] = $this->lookupId($entityId));
                if ($id !== null) {
                    return ['id' => $id, 'via' => 'entity_id', 'reason' => null];
                }
                $tried[] = "entity_id {$entityId} not found";
            } elseif ($name === null) {
                // Legacy chronicle refs carry the label in entity_id.
                $name = $entityId;
            }
        }

        if ($wikidataId !== null) {
            $id = array_key_exists($wikidataId, $this->byQid)
                ? $this->byQid[$wikidataId]
                : ($this->byQid[$wikidataId] = $this->lookupQid($wikidataId));
            if ($id !== null && ($name === null || $this->rowMatchesName($id, $name))) {
                $row = $this->rowInfo($id);
                if ($row === null || ! self::temporallyIncompatible($row['entity_type'], $span, self::rowSpan($row))) {
                    return ['id' => $id, 'via' => 'wikidata_id', 'reason' => null];
                }
                $tried[] = "wikidata_id {$wikidataId} is '{$row['name']}' of another era (".self::describeSpan(self::rowSpan($row)).' vs '.self::describeSpan($span).')';
            } else {
                $tried[] = $id === null
                    ? "wikidata_id {$wikidataId} not in DB"
                    : "wikidata_id {$wikidataId} is '{$this->namesOf[$id][0]}' (name mismatch)";
            }
        }

        if ($name !== null) {
            [$id, $via] = $this->lookupName($name, $span);
            if ($id !== null) {
                return ['id' => $id, 'via' => $via, 'reason' => null];
            }
            $tried[] = $via;
        } else {
            $tried[] = 'no name';
        }

        return ['id' => null, 'via' => 'none', 'reason' => implode('; ', $tried)];
    }

    /**
     * A relation's year span when its type implies both ends existed then
     * (CONTEMPORANEOUS_RELATION_TYPES), else null (no temporal signal).
     *
     * @return array{0: int, 1: int}|null
     */
    public static function relationSpan(string $relationshipType, mixed $start, mixed $end): ?array
    {
        if (! in_array($relationshipType, self::CONTEMPORANEOUS_RELATION_TYPES, true)) {
            return null;
        }

        return self::yearSpan(self::yearOf($start), self::yearOf($end));
    }

    /**
     * Signed leading year of a date value ('-382', '1556-01-15', 1598), or null.
     */
    public static function yearOf(mixed $value): ?int
    {
        if (is_int($value)) {
            return $value;
        }
        if (! is_string($value) || preg_match('/^\s*(-?\d+)/', $value, $m) !== 1) {
            return null;
        }

        return (int) $m[1];
    }

    /**
     * [lo, hi] from optional start/end years; one bound alone is a point.
     *
     * @return array{0: int, 1: int}|null
     */
    public static function yearSpan(?int $start, ?int $end): ?array
    {
        $lo = $start ?? $end;
        $hi = $end ?? $start;
        if ($lo === null || $hi === null) {
            return null;
        }

        return [min($lo, $hi), max($lo, $hi)];
    }

    /**
     * Years between two spans (0 = overlap), null when either is unknown.
     * Sign-insensitive: `$a` is also compared as its BCE/CE mirror (the
     * extractor mis-signs years: 'Augustus rules Gallia 27' for 27 BCE).
     *
     * @param  array{0: int, 1: int}|null  $a
     * @param  array{0: int, 1: int}|null  $b
     */
    public static function temporalGap(?array $a, ?array $b): ?int
    {
        if ($a === null || $b === null) {
            return null;
        }
        $gap = static fn (array $x, array $y): int => max(0, max($x[0], $y[0]) - min($x[1], $y[1]));

        return min($gap($a, $b), $gap([-$a[1], -$a[0]], $b));
    }

    /**
     * How two spans of one entity_type relate as an identity signal:
     * 'match' (overlap), 'near' (within the type's tolerance — the same person
     * with slightly different dates), 'conflict' (clearly different eras) or
     * 'unknown' (a side undated, or the type not date-checked). Mirrors
     * pipeline/agent/tools/disambiguation.py temporal_fit (keep in sync).
     *
     * @param  array{0: int, 1: int}|null  $a
     * @param  array{0: int, 1: int}|null  $b
     */
    public static function temporalFit(?string $entityType, ?array $a, ?array $b): string
    {
        $tolerance = self::NAMESAKE_TOLERANCE_YEARS[(string) $entityType] ?? null;
        if ($a === null || $b === null || $tolerance === null) {
            return 'unknown';
        }
        $a = self::blurRoundCentury($a);
        $b = self::blurRoundCentury($b);
        if (min($a[0], $b[0]) < self::DEEP_ANTIQUITY_YEAR) {
            $tolerance += self::DEEP_ANTIQUITY_EXTRA_YEARS;
        }
        $gap = self::temporalGap($a, $b);
        if ($gap === 0) {
            return 'match';
        }

        return $gap <= $tolerance ? 'near' : 'conflict';
    }

    /**
     * A single round-century year (century precision) as ±ROUND_CENTURY_BLUR_YEARS.
     *
     * @param  array{0: int, 1: int}  $span
     * @return array{0: int, 1: int}
     */
    private static function blurRoundCentury(array $span): array
    {
        $year = $span[0];
        if ($span[0] === $span[1] && $year !== 0 && $year % 100 === 0) {
            return [$year - self::ROUND_CENTURY_BLUR_YEARS, $year + self::ROUND_CENTURY_BLUR_YEARS];
        }

        return $span;
    }

    /**
     * @param  array{0: int, 1: int}|null  $a
     * @param  array{0: int, 1: int}|null  $b
     */
    public static function temporallyIncompatible(?string $entityType, ?array $a, ?array $b): bool
    {
        return self::temporalFit($entityType, $a, $b) === 'conflict';
    }

    /**
     * @param  array<string, mixed>  $row  with start_year / end_year
     * @return array{0: int, 1: int}|null
     */
    public static function rowSpan(array $row): ?array
    {
        $start = $row['start_year'] ?? null;
        $end = $row['end_year'] ?? null;

        return self::yearSpan(is_numeric($start) ? (int) $start : null, is_numeric($end) ? (int) $end : null);
    }

    /**
     * Choose among same-name rows (preference order) by date compatibility
     * with `$span`. Each row's own entity_type (else `$entityType`) sets the
     * tolerance. 'conflict' rows are dropped and the best non-empty tier
     * (match > near > unknown) is kept. Returns [row, fit] on success, else
     * [null, reason]: 'none' (no rows); 'namesake_ambiguous' (every row is
     * date-incompatible, or the best tier holds rows date-incompatible with
     * EACH OTHER — dated namesakes, nothing to choose by); 'ambiguous'
     * (`$unique`, for aliases, and the best tier holds several rows). Rows
     * mutually compatible or undated are presumed duplicates: the first wins.
     * Mirrors pipeline/agent/tools/disambiguation.py pick_namesake (keep in sync).
     *
     * @param  list<array<string, mixed>>  $rows
     * @param  array{0: int, 1: int}|null  $span
     * @return array{0: array<string, mixed>|null, 1: string}
     */
    public static function pickNamesake(array $rows, ?array $span, ?string $entityType = null, bool $unique = false): array
    {
        if ($rows === []) {
            return [null, 'none'];
        }

        $tiers = array_fill_keys(self::FIT_ORDER, []);
        foreach ($rows as $row) {
            $fit = self::temporalFit($row['entity_type'] ?? $entityType, $span, self::rowSpan($row));
            if ($fit !== 'conflict') {
                $tiers[$fit][] = $row;
            }
        }

        foreach (self::FIT_ORDER as $fit) {
            $best = $tiers[$fit];
            if ($best === []) {
                continue;
            }
            if ($unique && count($best) > 1) {
                return [null, 'ambiguous'];
            }
            foreach ($best as $i => $first) {
                foreach (array_slice($best, $i + 1) as $second) {
                    if (self::temporallyIncompatible($first['entity_type'] ?? $entityType, self::rowSpan($first), self::rowSpan($second))) {
                        return [null, self::NAMESAKE_AMBIGUOUS];
                    }
                }
            }

            return [$best[0], $fit];
        }

        return [null, self::NAMESAKE_AMBIGUOUS];
    }

    /**
     * @param  array{0: int, 1: int}|null  $span
     */
    public static function describeSpan(?array $span): string
    {
        if ($span === null) {
            return 'undated';
        }

        return $span[0] === $span[1] ? (string) $span[0] : "{$span[0]}..{$span[1]}";
    }

    /**
     * Whether two names plausibly denote the same entity: after normalising
     * (case, diacritics, punctuation) one is a whole-word run inside the other,
     * and their regnal/ordinal markers (roman numerals, digits, ordinal words)
     * are identical. "Eighteenth Dynasty of Egypt" ~ "Eighteenth Dynasty" and
     * "Philip II of France" ~ "Philip II"; but not "World War I" ~ "World War
     * II", "Malik-Shah" ~ "Malik-Shah II", "Qi" ~ "Qing dynasty".
     */
    public static function namesCompatible(string $a, string $b): bool
    {
        $ta = self::tokens($a);
        $tb = self::tokens($b);
        if ($ta === [] || $tb === []) {
            return false;
        }

        if (self::markers($ta) !== self::markers($tb)) {
            return false;
        }

        $sa = ' '.implode(' ', $ta).' ';
        $sb = ' '.implode(' ', $tb).' ';

        return str_contains($sa, $sb) || str_contains($sb, $sa);
    }

    /**
     * Why two names positively denote DIFFERENT entities, or null:
     *   'markers'   — both carry regnal/ordinal markers and they differ
     *                 (World War I vs II, Mithridates VI vs V);
     *   'near_miss' — a token only one side has is a non-inflectional extension
     *                 or a near-spelling of one only the other has (Qi vs Qing
     *                 dynasty, Julian vs Queen Juliana, Romagna vs Romania).
     * Wholly different names (Byzantine Empire vs Imperium Romanum Orientale)
     * are not a conflict. Mirrors pipeline/agent/tools/disambiguation.py
     * names_conflict (keep in sync).
     */
    public static function namesConflict(string $a, string $b): ?string
    {
        $ta = self::tokens($a);
        $tb = self::tokens($b);
        if ($ta === [] || $tb === []) {
            return null;
        }

        $ma = self::markers($ta);
        $mb = self::markers($tb);
        if ($ma !== [] && $mb !== [] && $ma !== $mb) {
            return 'markers';
        }

        $onlyA = array_diff(array_unique(array_diff($ta, $tb)), $ma);
        $onlyB = array_diff(array_unique(array_diff($tb, $ta)), $mb);
        foreach ($onlyA as $x) {
            foreach ($onlyB as $y) {
                if (self::tokensNearMiss($x, $y)) {
                    return 'near_miss';
                }
            }
        }

        return null;
    }

    /**
     * Whether an import record may merge into a row found by QID / OHM id.
     * `$rowNames[0]` is the row's name, the rest its aliases. True when the
     * record's name is compatible with the row's name or an alias (the same
     * test resolve() applies to relation endpoints), or when one of the
     * record's alternative names is and the record's name does not positively
     * conflict with the row's name ('Zhu Di' [alias 'Yongle Emperor'] merges
     * into 'Yongle Emperor'; 'Romagna' never into 'Romania'). Mirrors
     * pipeline/agent/tools/disambiguation.py record_matches_row (keep in sync).
     *
     * @param  list<mixed>  $altNames
     * @param  list<string>  $rowNames
     */
    public static function recordMatchesRow(string $name, array $altNames, array $rowNames): bool
    {
        $rowNames = array_values(array_filter($rowNames, static fn (string $r): bool => trim($r) !== ''));
        if (trim($name) === '' || $rowNames === []) {
            return false;
        }

        foreach ($rowNames as $rowName) {
            if (self::namesCompatible($name, $rowName)) {
                return true;
            }
        }

        if (self::namesConflict($name, $rowNames[0]) !== null) {
            return false;
        }

        foreach ($altNames as $alt) {
            if (! is_string($alt) || trim($alt) === '') {
                continue;
            }
            foreach ($rowNames as $rowName) {
                if (self::namesCompatible($alt, $rowName)) {
                    return true;
                }
            }
        }

        return false;
    }

    /**
     * An entity row's name followed by its aliases.
     *
     * @return list<string>
     */
    public static function namesOfRow(string $entityId): array
    {
        $rowName = (string) DB::table('entities')->where('entity_id', $entityId)->value('name');
        $aliases = DB::table('entity_aliases')->where('entity_id', $entityId)->pluck('name')->all();

        return array_values(array_map('strval', [$rowName, ...$aliases]));
    }

    private static function tokensNearMiss(string $x, string $y): bool
    {
        if ($x === $y) {
            return false;
        }

        [$short, $long] = strlen($x) <= strlen($y) ? [$x, $y] : [$y, $x];
        if (str_starts_with($long, $short)) {
            return strlen($short) >= 2 && ! self::isInflection($short, substr($long, strlen($short)));
        }

        if (strlen($short) < 4) {
            return false;
        }

        return 1 - levenshtein($x, $y) / strlen($long) >= self::NEAR_MISS_SIMILARITY;
    }

    private static function isInflection(string $base, string $suffix): bool
    {
        if (in_array($suffix, self::PLURAL_SUFFIXES, true)) {
            return strlen($base) >= 3;
        }

        return in_array($suffix, self::DERIVED_SUFFIXES, true) && strlen($base) >= 4;
    }

    /**
     * @return list<string>
     */
    private static function tokens(string $name): array
    {
        // Apostrophes / ayn-hamza marks are dropped, not word breaks
        // ("al-Ma'mun" ~ "al-Maʾmun"); mirrors disambiguation._APOSTROPHES.
        $plain = (string) preg_replace('/[\'`\x{00B4}\x{2018}\x{2019}\x{02BB}\x{02BC}\x{02BE}\x{02BF}]/u', '', $name);
        $ascii = mb_strtolower(Str::ascii($plain));
        $parts = preg_split('/[^a-z0-9]+/', $ascii, -1, PREG_SPLIT_NO_EMPTY);

        return $parts === false ? [] : array_values($parts);
    }

    /**
     * Sorted regnal/ordinal markers: roman numerals I–XXXIX, digits, ordinals.
     *
     * @param  list<string>  $tokens
     * @return list<string>
     */
    private static function markers(array $tokens): array
    {
        $markers = array_values(array_filter($tokens, static fn (string $t): bool => ctype_digit($t)
            || in_array($t, self::ORDINALS, true)
            || preg_match('/^x{0,3}(ix|iv|v?i{0,3})$/', $t) === 1));
        sort($markers);

        return $markers;
    }

    private function rowMatchesName(string $entityId, string $name): bool
    {
        if (! array_key_exists($entityId, $this->namesOf)) {
            $this->namesOf[$entityId] = self::namesOfRow($entityId);
        }

        foreach ($this->namesOf[$entityId] as $candidate) {
            if (self::namesCompatible($name, $candidate)) {
                return true;
            }
        }

        return false;
    }

    private function lookupId(string $entityId): ?string
    {
        $id = DB::table('entities')->where('entity_id', $entityId)->value('entity_id');

        return is_string($id) && $id !== '' ? $id : null;
    }

    private function lookupQid(string $wikidataId): ?string
    {
        // Duplicate rows per QID can exist; pick the oldest deterministically.
        $id = DB::table('entities')
            ->where('wikidata_id', $wikidataId)
            ->orderBy('created_at')
            ->orderBy('entity_id')
            ->value('entity_id');

        return is_string($id) && $id !== '' ? $id : null;
    }

    /**
     * Name → alias lookup, date-guarded by `$span` (pickNamesake): exact name
     * rows, else case-insensitive ones; when there are none, or every one is
     * of another era, a row naming it by alias (exactly one in the best tier).
     *
     * @param  array{0: int, 1: int}|null  $span
     * @return array{0: string|null, 1: string} [entity_id, via] or [null, reason]
     */
    private function lookupName(string $name, ?array $span): array
    {
        [$exact, $ci] = $this->nameRows[$name] ??= [
            $this->entityRows(fn ($q) => $q->where('e.name', $name)),
            $this->entityRows(fn ($q) => $q->whereRaw('LOWER(e.name) = LOWER(?)', [$name])),
        ];

        $named = $exact !== [] ? $exact : $ci;
        if ($named !== []) {
            [$row, $verdict] = self::pickNamesake($named, $span);
            if ($row !== null) {
                return [(string) $row['entity_id'], $exact !== [] ? 'name' : 'name_ci'];
            }
            $compatible = array_filter($named, fn (array $r): bool => ! self::temporallyIncompatible($r['entity_type'] ?? null, $span, self::rowSpan($r)));
            if ($compatible !== []) {
                // Several dated namesakes and nothing to choose by.
                return [null, self::NAMESAKE_AMBIGUOUS.': '.count($named)." '{$name}' rows of different eras, none singled out by ".self::describeSpan($span)];
            }
            // Every same-name row is of another era: an alias may still name the right one.
        }

        $aliasRows = $this->aliasRows[$name] ??= $this->entityRows(fn ($q) => $q->whereIn('e.entity_id', DB::table('entity_aliases')
            ->select('entity_id')
            ->whereRaw('LOWER(name) = LOWER(?)', [$name])));

        if ($aliasRows !== []) {
            [$row, $verdict] = self::pickNamesake($aliasRows, $span, unique: true);
            if ($row !== null) {
                return [(string) $row['entity_id'], 'alias'];
            }
            if ($named === [] && $verdict === 'ambiguous') {
                return [null, 'alias ambiguous'];
            }
        }

        if ($named !== [] || $aliasRows !== []) {
            $count = count($named) + count($aliasRows);

            return [null, self::NAMESAKE_AMBIGUOUS.": {$count} '{$name}' row(s)/alias(es), none compatible with ".self::describeSpan($span)];
        }

        return [null, 'no entity/alias named it'];
    }

    /**
     * Entity rows with their type and primary temporal range, oldest first.
     *
     * @param  callable(Builder): mixed  $where
     * @return list<array<string, mixed>>
     */
    private function entityRows(callable $where): array
    {
        $query = DB::table('entities as e')
            ->leftJoin('entity_temporal_ranges as t', function ($join): void {
                $join->on('t.entity_id', '=', 'e.entity_id')->where('t.is_primary', true);
            })
            ->select('e.entity_id', 'e.name', 'e.entity_type', 't.start_year', 't.end_year')
            ->orderBy('e.created_at')
            ->orderBy('e.entity_id')
            ->limit(25);
        $where($query);

        $rows = array_map(static fn (object $r): array => (array) $r, $query->get()->all());
        foreach ($rows as $row) {
            $this->rowInfo[(string) $row['entity_id']] = $row;
        }

        return $rows;
    }

    /**
     * @return array<string, mixed>|null
     */
    private function rowInfo(string $entityId): ?array
    {
        if (! array_key_exists($entityId, $this->rowInfo)) {
            $this->entityRows(fn ($q) => $q->where('e.entity_id', $entityId));
            $this->rowInfo[$entityId] ??= null;
        }

        return $this->rowInfo[$entityId];
    }

    private function clean(?string $value): ?string
    {
        if (! is_string($value)) {
            return null;
        }
        $value = trim($value);

        return $value === '' ? null : $value;
    }
}
