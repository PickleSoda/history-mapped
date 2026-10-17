<?php

declare(strict_types=1);

namespace App\Actions\Tag;

use App\Enums\EntityType;
use App\Enums\TagSource;
use Illuminate\Support\Facades\DB;

/**
 * Recompute every Derived tag in bulk (set-based SQL; ~40k entities in seconds).
 *
 * Chronicles: era tags from start/end year, only for chronicles that have no
 * era tag yet and that an admin has not tagged (admin tags are the whole set).
 *
 * Entities, in order:
 *   1. era from the entity's own primary temporal range;
 *   2. era from its chronicles, when it has no dates of its own;
 *   3. sub-eras (Neolithic, Bronze/Iron Age) from its chronicles, when the
 *      entity's dates fall in the sub-era's window (or it has no dates);
 *   4. region from its chronicles, skipping thematic (cross-regional) ones;
 *   5. theme from entity type;
 *   6. the ancestors of all of the above.
 * An entity "is in" a chronicle when it is the source or target of an entry's
 * primary relationship, or a secondary entity of an entry.
 */
class DeriveTagsAction
{
    /** Types tagged with the era they began in, not every era they span. */
    private const ORIGIN_TYPES = [
        EntityType::City,
        EntityType::InfrastructureMonument,
        EntityType::NaturalResource,
        EntityType::ExtractionInfra,
        EntityType::EducationalInstitution,
        EntityType::CulturalWork,
        EntityType::ReligiousText,
        EntityType::LegalCode,
    ];

    /** @var array<string, list<string>> entity type => theme slugs */
    private const TYPE_THEMES = [
        'event_battle' => ['war'],
        'event_war' => ['war'],
        'military_unit' => ['war'],
        'event_rebellion' => ['war', 'revolution'],
        'event_treaty' => ['diplomacy-law'],
        'diplomatic_relationship' => ['diplomacy-law'],
        'legal_code' => ['diplomacy-law'],
        'event_legal_reform' => ['diplomacy-law', 'revolution'],
        'political_entity' => ['empires-states'],
        'dynasty' => ['empires-states'],
        'religious_movement' => ['religion'],
        'religious_text' => ['religion'],
        'intellectual_movement' => ['ideas'],
        'cultural_work' => ['arts-culture'],
        'infrastructure_monument' => ['arts-culture'],
        'technology' => ['science'],
        'event_tech_adoption' => ['science'],
        'educational_institution' => ['science', 'ideas'],
        'trade_route' => ['trade'],
        'currency_monetary_system' => ['trade'],
        'natural_resource' => ['trade'],
        'extraction_infra' => ['trade'],
        'epidemic_disease' => ['disease'],
        'event_natural_disaster' => ['environment'],
        'migration' => ['migration'],
        'language' => ['language-writing'],
        'social_class' => ['society'],
    ];

    /** Entity ↔ chronicle membership, as a reusable CTE body. */
    private const MEMBERS_SQL = <<<'SQL'
        SELECT r.source_entity_id AS entity_id, ce.chronicle_id
        FROM chronicle_entries ce JOIN relationships r ON r.relationship_id = ce.primary_relationship_id
        UNION
        SELECT r.target_entity_id, ce.chronicle_id
        FROM chronicle_entries ce JOIN relationships r ON r.relationship_id = ce.primary_relationship_id
        UNION
        SELECT cee.entity_id, ce.chronicle_id
        FROM chronicle_entry_entities cee JOIN chronicle_entries ce ON ce.entry_id = cee.entry_id
    SQL;

    /** Top-level era tags: derived straight from dates. */
    private const DATED_ERA = "t.facet = 'era' AND t.parent_slug IS NULL";

    /**
     * Sub-era tags (Neolithic, Bronze/Iron Age). Their timing differs by region
     * (the Americas had no Bronze Age), so they are never derived from dates
     * alone; their years are only a plausibility window for inheritance.
     */
    private const SUB_ERA = "t.facet = 'era' AND t.parent_slug IS NOT NULL";

    /** The overlap test between tag t's years and a span (s, e). */
    private const OVERLAPS = 'COALESCE(t.end_year, 100000) >= %1$s.s AND COALESCE(t.start_year, -100000) <= %1$s.e';

    /**
     * @return array{chronicle_tags: int, entity_tags: int}
     */
    public function __invoke(): array
    {
        return DB::transaction(fn (): array => [
            'chronicle_tags' => $this->deriveChronicles(),
            'entity_tags' => $this->deriveEntities(),
        ]);
    }

    /**
     * Only the chronicle half: cheap (one statement over ~300 rows), so the
     * chronicle importer runs it after every file.
     */
    public function chronicles(): int
    {
        return DB::transaction(fn (): int => $this->deriveChronicles());
    }

    private function deriveChronicles(): int
    {
        DB::table('chronicle_tags')->where('source', TagSource::Derived->value)->delete();

        return DB::affectingStatement(sprintf(<<<'SQL'
            INSERT INTO chronicle_tags (chronicle_id, tag, source, created_at, updated_at)
            SELECT c.chronicle_id, t.slug, 'derived', now(), now()
            FROM chronicles c
            CROSS JOIN LATERAL (SELECT COALESCE(c.start_year, c.end_year) AS s,
                GREATEST(c.start_year, c.end_year) AS e) span
            JOIN tags t ON %s AND %s
            WHERE span.s IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM chronicle_tags x JOIN tags xt ON xt.slug = x.tag
                  WHERE x.chronicle_id = c.chronicle_id AND (xt.facet = 'era' OR x.source = 'manual')
              )
            ON CONFLICT DO NOTHING
        SQL, self::DATED_ERA, sprintf(self::OVERLAPS, 'span')));
    }

    private function deriveEntities(): int
    {
        DB::table('entity_tags')->where('source', TagSource::Derived->value)->delete();

        $count = 0;

        // 1. Era from the entity's own dates.
        $count += DB::affectingStatement(sprintf(<<<'SQL'
            WITH spans AS (%s)
            INSERT INTO entity_tags (entity_id, tag, source, created_at, updated_at)
            SELECT spans.entity_id, t.slug, 'derived', now(), now()
            FROM spans JOIN tags t ON %s AND %s
            ON CONFLICT DO NOTHING
        SQL, $this->spansSql(), self::DATED_ERA, sprintf(self::OVERLAPS, 'spans')));

        // 2. Era from chronicles, for entities without any era tag yet.
        $count += $this->inheritFromChronicles(
            self::DATED_ERA,
            skipThematic: false,
            where: "NOT EXISTS (
                SELECT 1 FROM entity_tags x JOIN tags xt ON xt.slug = x.tag
                WHERE x.entity_id = r.entity_id AND xt.facet = 'era'
            )",
        );

        // 3. Sub-eras, when the entity's own dates fit the window (so Rome, founded
        //    753 BCE, takes Iron Age from its chronicles but not Bronze Age).
        $count += $this->inheritFromChronicles(
            self::SUB_ERA,
            skipThematic: true,
            where: sprintf('NOT EXISTS (SELECT 1 FROM spans WHERE spans.entity_id = r.entity_id)
                OR EXISTS (SELECT 1 FROM spans WHERE spans.entity_id = r.entity_id AND %s)', sprintf(self::OVERLAPS, 'spans')),
        );

        // 4. Region, from chronicles about places rather than themes.
        $count += $this->inheritFromChronicles("t.facet = 'region' AND t.slug <> 'global'", skipThematic: true);

        // 5. Theme from entity type.
        $pairs = [];
        $bindings = [];
        foreach (self::TYPE_THEMES as $type => $themes) {
            foreach ($themes as $theme) {
                $pairs[] = '(?, ?)';
                array_push($bindings, $type, $theme);
            }
        }
        $count += DB::affectingStatement(sprintf(<<<'SQL'
            INSERT INTO entity_tags (entity_id, tag, source, created_at, updated_at)
            SELECT e.entity_id, m.tag, 'derived', now(), now()
            FROM entities e
            JOIN (VALUES %s) AS m(entity_type, tag) ON m.entity_type = e.entity_type::text
            JOIN tags t ON t.slug = m.tag
            ON CONFLICT DO NOTHING
        SQL, implode(', ', $pairs)), $bindings);

        // 6. Ancestors of everything above (Neolithic implies Prehistory).
        $count += DB::affectingStatement(<<<'SQL'
            WITH RECURSIVE up AS (
                SELECT et.entity_id, t.parent_slug AS tag
                FROM entity_tags et JOIN tags t ON t.slug = et.tag
                WHERE t.parent_slug IS NOT NULL
                UNION
                SELECT up.entity_id, t.parent_slug
                FROM up JOIN tags t ON t.slug = up.tag
                WHERE t.parent_slug IS NOT NULL
            )
            INSERT INTO entity_tags (entity_id, tag, source, created_at, updated_at)
            SELECT entity_id, tag, 'derived', now(), now() FROM up
            ON CONFLICT DO NOTHING
        SQL);

        return $count;
    }

    /**
     * Each dated entity's effective span (entity_id, s, e) from its primary
     * temporal range. Origin types and open-ended ranges collapse to the start.
     */
    private function spansSql(): string
    {
        $origin = implode(',', array_map(fn (EntityType $t): string => "'{$t->value}'", self::ORIGIN_TYPES));

        return <<<SQL
            SELECT r.entity_id,
                COALESCE(r.start_year, r.end_year) AS s,
                CASE WHEN r.start_year IS NULL OR r.end_year IS NULL OR e.entity_type::text IN ({$origin})
                    THEN COALESCE(r.start_year, r.end_year)
                    ELSE GREATEST(r.start_year, r.end_year)
                END AS e
            FROM entity_temporal_ranges r
            JOIN entities e ON e.entity_id = r.entity_id
            WHERE r.is_primary AND COALESCE(r.start_year, r.end_year) IS NOT NULL
        SQL;
    }

    /**
     * Copy chronicle tags matching $tagSql onto the chronicles' member entities.
     *
     * Weighted, so hub entities that appear in dozens of chronicles (Rome,
     * Julius Caesar) keep only their dominant tags: a tag is kept when at
     * least half as many of the entity's chronicles carry it as carry its most
     * common tag in the same facet. An entity in one chronicle gets all of it.
     */
    private function inheritFromChronicles(string $tagSql, bool $skipThematic, string $where = 'true'): int
    {
        $thematic = $skipThematic
            ? "WHERE NOT EXISTS (SELECT 1 FROM chronicle_tags th WHERE th.chronicle_id = m.chronicle_id AND th.tag = 'thematic')"
            : '';

        return DB::affectingStatement(sprintf(<<<'SQL'
            WITH members AS (%s),
            spans AS (%s),
            counts AS (
                SELECT m.entity_id, ct.tag, t.facet, count(*) AS n
                FROM members m
                JOIN chronicle_tags ct ON ct.chronicle_id = m.chronicle_id
                JOIN tags t ON t.slug = ct.tag AND %s
                %s
                GROUP BY m.entity_id, ct.tag, t.facet
            ),
            ranked AS (
                SELECT counts.*, max(n) OVER (PARTITION BY entity_id, facet) AS top FROM counts
            )
            INSERT INTO entity_tags (entity_id, tag, source, created_at, updated_at)
            SELECT r.entity_id, r.tag, 'derived', now(), now()
            FROM ranked r
            JOIN tags t ON t.slug = r.tag
            WHERE r.n * 2 >= r.top AND (%s)
            ON CONFLICT DO NOTHING
        SQL, self::MEMBERS_SQL, $this->spansSql(), $tagSql, $thematic, $where));
    }
}
