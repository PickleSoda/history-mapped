<?php

declare(strict_types=1);

namespace App\Builders;

use App\Enums\ConfidenceLevel;
use App\Enums\EntityGroup;
use App\Enums\EntityType;
use App\Enums\VerificationStatus;
use Illuminate\Database\Eloquent\Builder;

/**
 * Custom query builder for Entity model.
 *
 * Replaces model scopes with type-safe, chainable, reusable query methods.
 * Usage: Entity::query()->ofType(...)->verified()->inBbox(...)
 *
 * @template TModel of \App\Models\Entity
 *
 * @extends Builder<TModel>
 */
class EntityBuilder extends Builder
{
    // ── Type / Group Filters ──────────────────────────────────

    public function ofType(EntityType $type): self
    {
        return $this->where('entity_type', $type->value);
    }

    public function ofGroup(EntityGroup $group): self
    {
        return $this->where('entity_group', $group->value);
    }

    /**
     * Filter by multiple entity types (OR).
     *
     * @param  list<EntityType>  $types
     */
    public function ofTypes(array $types): self
    {
        return $this->whereIn('entity_type', array_map(
            fn (EntityType $t): string => $t->value,
            $types,
        ));
    }

    /**
     * Filter by multiple entity groups (OR).
     *
     * @param  list<EntityGroup>  $groups
     */
    public function ofGroups(array $groups): self
    {
        return $this->whereIn('entity_group', array_map(
            fn (EntityGroup $g): string => $g->value,
            $groups,
        ));
    }

    // ── Verification / Confidence ────────────────────────────

    public function verified(): self
    {
        return $this->whereIn('verification_status', [
            VerificationStatus::HumanVerified->value,
            VerificationStatus::ExpertVerified->value,
        ]);
    }

    public function withStatus(VerificationStatus $status): self
    {
        return $this->where('verification_status', $status->value);
    }

    public function withMinConfidence(ConfidenceLevel $level): self
    {
        // Confidence levels ordered: unresolved < low < medium < high
        $ordered = [
            ConfidenceLevel::Unresolved->value,
            ConfidenceLevel::Low->value,
            ConfidenceLevel::Medium->value,
            ConfidenceLevel::High->value,
        ];

        $minIndex = array_search($level->value, $ordered, true);
        $acceptable = array_slice($ordered, (int) $minIndex);

        return $this->whereIn('confidence', $acceptable);
    }

    // ── Spatial Queries (PostGIS) ────────────────────────────

    /**
     * Entities whose point geometry intersects a bounding box.
     * Coordinates in SRID 4326 (wg S84 lon/lat).
     */
    public function inBbox(float $minLng, float $minLat, float $maxLng, float $maxLat): self
    {
        return $this->whereRaw(
            sprintf('%s && ST_MakeEnvelope(?, ?, ?, ?, 4326)', self::primaryLocationGeomSql()),
            [$minLng, $minLat, $maxLng, $maxLat],
        );
    }

    /**
     * Entities whose territory geometry intersects a bounding box.
     */
    public function territoryInBbox(float $minLng, float $minLat, float $maxLng, float $maxLat): self
    {
        return $this->whereRaw(
            sprintf('%s && ST_MakeEnvelope(?, ?, ?, ?, 4326)', self::primaryLocationTerritorySql()),
            [$minLng, $minLat, $maxLng, $maxLat],
        );
    }

    /**
     * Entities within a given distance (meters) from a point.
     * Uses geography cast for accurate distance on the sphere.
     */
    public function nearPoint(float $lng, float $lat, float $radiusMeters): self
    {
        return $this->whereRaw(
            sprintf('ST_DWithin((%s)::geography, ST_Point(?, ?)::geography, ?)', self::primaryLocationGeomSql()),
            [$lng, $lat, $radiusMeters],
        );
    }

    /**
     * Order by distance from a point (KNN using <-> operator on GIST index).
     */
    public function orderByDistanceFrom(float $lng, float $lat): self
    {
        return $this->orderByRaw(
            sprintf('(%s) <-> ST_Point(?, ?)::geometry', self::primaryLocationGeomSql()),
            [$lng, $lat],
        );
    }

    // ── Temporal Queries ─────────────────────────────────────

    /**
     * Entities that overlap a given time range (integer years).
     * An entity overlaps if its start year <= range end AND end year >= range start.
     */
    public function inTimeRange(int $startYear, int $endYear): self
    {
        return $this->whereRaw(
            sprintf(
                'COALESCE(%s, %d) <= ? AND COALESCE(%s, %d) >= ?',
                self::primaryTemporalStartYearSql(),
                PHP_INT_MAX,
                self::primaryTemporalEndYearSql(),
                PHP_INT_MIN,
            ),
            [$endYear, $startYear],
        );
    }

    /**
     * Entities that existed at a specific year.
     */
    public function existsAt(int $year): self
    {
        return $this->whereRaw(
            sprintf(
                'COALESCE(%s, %d) <= ? AND COALESCE(%s, %d) >= ?',
                self::primaryTemporalStartYearSql(),
                PHP_INT_MAX,
                self::primaryTemporalEndYearSql(),
                PHP_INT_MIN,
            ),
            [$year, $year],
        );
    }

    /**
     * Entities starting after a given year.
     */
    public function startingAfter(int $year): self
    {
        return $this->whereRaw(
            sprintf('COALESCE(%s, %d) >= ?', self::primaryTemporalStartYearSql(), PHP_INT_MIN),
            [$year],
        );
    }

    /**
     * Entities ending before a given year.
     */
    public function endingBefore(int $year): self
    {
        return $this->whereRaw(
            sprintf('COALESCE(%s, %d) <= ?', self::primaryTemporalEndYearSql(), PHP_INT_MAX),
            [$year],
        );
    }

    // ── Text Search ──────────────────────────────────────────

    /**
     * Fuzzy name search. Combines three signals so typos and partial terms
     * still match (not just exact word stems):
     *   - trigram similarity (pg_trgm `%`) — typo tolerance
     *   - ILIKE substring — partial / prefix matches
     *   - full-text (tsvector) — whole-word relevance
     * All three are index-backed (trigram GIN + FTS GIN).
     */
    public function search(string $term): self
    {
        return $this->where(function (Builder $q) use ($term): void {
            $q->whereRaw('name % ?', [$term])
                ->orWhere('name', 'ILIKE', '%'.$term.'%')
                ->orWhereRaw("to_tsvector('english', name) @@ plainto_tsquery('english', ?)", [$term]);
        });
    }

    /**
     * Partial name match (ILIKE) — fallback for short or non-English terms.
     */
    public function nameLike(string $term): self
    {
        return $this->where('name', 'ILIKE', '%'.$term.'%');
    }

    /**
     * Order by trigram similarity to a term (best fuzzy matches first).
     */
    public function orderBySimilarity(string $term): self
    {
        return $this->orderByRaw('similarity(name, ?) DESC', [$term]);
    }

    // ── Attribute (JSONB) Queries ─────────────────────────────

    /**
     * Filter by a JSONB attribute value.
     * Example: ->hasAttribute('government_type', 'monarchy')
     */
    public function hasAttribute(string $key, mixed $value): self
    {
        return $this->whereRaw(
            'attributes @> ?::jsonb',
            [json_encode([$key => $value])],
        );
    }

    /**
     * Filter entities that have a specific tag.
     * Uses the text[] array contains operator.
     */
    public function hasTag(string $tag): self
    {
        return $this->whereExists(function (Builder $query) use ($tag): void {
            $query->selectRaw('1')
                ->from('entity_tags as et')
                ->whereColumn('et.entity_id', 'entities.entity_id')
                ->where('et.tag', $tag);
        });
    }

    // ── Sorting Presets ──────────────────────────────────────

    public function orderByImpact(): self
    {
        return $this->orderByDesc('impact_score');
    }

    public function orderByRecent(): self
    {
        return $this->orderByDesc('created_at');
    }

    public function orderByChronological(): self
    {
        return $this->orderByRaw(self::primaryTemporalStartYearSql().' ASC NULLS LAST');
    }

    // ── Select Presets ───────────────────────────────────────

    /**
     * Pre-compute geometry columns as GeoJSON inline in the query.
     *
     * Adds `geom_geojson` and `territory_geom_geojson` virtual columns
     * that the GeoJson cast picks up automatically, eliminating the
     * per-row DB round-trip (N+1) on list endpoints.
     */
    public function withGeoJson(): self
    {
        return $this->select(['entities.*'])
            ->selectRaw(sprintf('%s AS temporal_start', self::primaryTemporalStartDateSql()))
            ->selectRaw(sprintf('%s AS temporal_end', self::primaryTemporalEndDateSql()))
            ->selectRaw(sprintf('%s AS location_name', self::primaryLocationNameSql()))
            ->selectRaw(sprintf('ST_AsGeoJSON(%s)::jsonb AS geom_geojson', self::primaryLocationGeomSql()))
            ->selectRaw(sprintf('ST_AsGeoJSON(%s)::jsonb AS territory_geom_geojson', self::primaryLocationTerritorySql()))
            ->selectRaw("COALESCE((SELECT json_agg(et.tag ORDER BY et.tag) FROM entity_tags et WHERE et.entity_id = entities.entity_id), '[]'::json) AS entity_tags_json");
    }

    /**
     * Minimal columns for map rendering (GeoJSON FeatureCollection).
     * Avoids loading heavy text/JSONB fields.
     */
    public function selectForMap(): self
    {
        return $this->select([
            'entity_id',
            'name',
            'entity_type',
            'entity_group',
            'display_priority',
            'icon_class',
            'impact_score',
        ])
            ->selectRaw(sprintf('%s AS temporal_start', self::primaryTemporalStartDateSql()))
            ->selectRaw(sprintf('%s AS temporal_end', self::primaryTemporalEndDateSql()))
            ->selectRaw("attributes->>'entity_color' AS entity_color")
            ->selectRaw(sprintf(
                'ST_AsGeoJSON(COALESCE(%s, %s)) AS geojson',
                self::primaryLocationTerritorySql(),
                self::primaryLocationGeomSql(),
            ));
    }

    private static function primaryTemporalStartYearSql(): string
    {
        return '(SELECT etr.start_year FROM entity_temporal_ranges etr WHERE etr.entity_id = entities.entity_id AND etr.is_primary = true ORDER BY etr.updated_at DESC NULLS LAST, etr.created_at DESC NULLS LAST LIMIT 1)';
    }

    private static function primaryTemporalEndYearSql(): string
    {
        return '(SELECT etr.end_year FROM entity_temporal_ranges etr WHERE etr.entity_id = entities.entity_id AND etr.is_primary = true ORDER BY etr.updated_at DESC NULLS LAST, etr.created_at DESC NULLS LAST LIMIT 1)';
    }

    private static function primaryTemporalStartDateSql(): string
    {
        return '(SELECT etr.start_date FROM entity_temporal_ranges etr WHERE etr.entity_id = entities.entity_id AND etr.is_primary = true ORDER BY etr.updated_at DESC NULLS LAST, etr.created_at DESC NULLS LAST LIMIT 1)';
    }

    private static function primaryTemporalEndDateSql(): string
    {
        return '(SELECT etr.end_date FROM entity_temporal_ranges etr WHERE etr.entity_id = entities.entity_id AND etr.is_primary = true ORDER BY etr.updated_at DESC NULLS LAST, etr.created_at DESC NULLS LAST LIMIT 1)';
    }

    private static function primaryLocationNameSql(): string
    {
        return '(SELECT el.location_name FROM entity_locations el WHERE el.entity_id = entities.entity_id AND el.is_primary = true ORDER BY el.updated_at DESC NULLS LAST, el.created_at DESC NULLS LAST LIMIT 1)';
    }

    private static function primaryLocationGeomSql(): string
    {
        return '(SELECT el.geom FROM entity_locations el WHERE el.entity_id = entities.entity_id AND el.is_primary = true ORDER BY el.updated_at DESC NULLS LAST, el.created_at DESC NULLS LAST LIMIT 1)';
    }

    private static function primaryLocationTerritorySql(): string
    {
        return '(SELECT el.territory_geom FROM entity_locations el WHERE el.entity_id = entities.entity_id AND el.is_primary = true ORDER BY el.updated_at DESC NULLS LAST, el.created_at DESC NULLS LAST LIMIT 1)';
    }
}
