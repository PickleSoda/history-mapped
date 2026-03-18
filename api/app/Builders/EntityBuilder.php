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
     * Coordinates in SRID 4326 (WGS84 lon/lat).
     */
    public function inBbox(float $minLng, float $minLat, float $maxLng, float $maxLat): self
    {
        return $this->whereRaw(
            'geom && ST_MakeEnvelope(?, ?, ?, ?, 4326)',
            [$minLng, $minLat, $maxLng, $maxLat],
        );
    }

    /**
     * Entities whose territory geometry intersects a bounding box.
     */
    public function territoryInBbox(float $minLng, float $minLat, float $maxLng, float $maxLat): self
    {
        return $this->whereRaw(
            'territory_geom && ST_MakeEnvelope(?, ?, ?, ?, 4326)',
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
            'ST_DWithin(geom::geography, ST_Point(?, ?)::geography, ?)',
            [$lng, $lat, $radiusMeters],
        );
    }

    /**
     * Order by distance from a point (KNN using <-> operator on GIST index).
     */
    public function orderByDistanceFrom(float $lng, float $lat): self
    {
        return $this->orderByRaw(
            'geom <-> ST_Point(?, ?)::geometry',
            [$lng, $lat],
        );
    }

    // ── Temporal Queries ─────────────────────────────────────

    /**
     * Entities that overlap a given time range.
     * An entity overlaps if its temporal_start <= range end AND temporal_end >= range start.
     */
    public function inTimeRange(string $start, string $end): self
    {
        return $this->where('temporal_start', '<=', $end)
            ->where('temporal_end', '>=', $start);
    }

    /**
     * Entities that existed at a specific point in time.
     */
    public function existsAt(string $date): self
    {
        return $this->where('temporal_start', '<=', $date)
            ->where('temporal_end', '>=', $date);
    }

    /**
     * Entities starting after a given date.
     */
    public function startingAfter(string $date): self
    {
        return $this->where('temporal_start', '>=', $date);
    }

    /**
     * Entities ending before a given date.
     */
    public function endingBefore(string $date): self
    {
        return $this->where('temporal_end', '<=', $date);
    }

    // ── Text Search ──────────────────────────────────────────

    /**
     * Full-text search on entity name using the GIN index.
     */
    public function search(string $term): self
    {
        return $this->whereRaw(
            "to_tsvector('english', name) @@ plainto_tsquery('english', ?)",
            [$term],
        );
    }

    /**
     * Partial name match (ILIKE) — fallback for short or non-English terms.
     */
    public function nameLike(string $term): self
    {
        return $this->where('name', 'ILIKE', '%' . $term . '%');
    }

    // ── Hierarchy ────────────────────────────────────────────

    public function childrenOf(string $parentEntityId): self
    {
        return $this->where('parent_entity_id', $parentEntityId);
    }

    public function roots(): self
    {
        return $this->whereNull('parent_entity_id');
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
        return $this->whereRaw('? = ANY(tags)', [$tag]);
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
        return $this->orderBy('temporal_start');
    }

    // ── Select Presets ───────────────────────────────────────

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
            'temporal_start',
            'temporal_end',
            'display_priority',
            'icon_class',
            'entity_color',
            'impact_score',
        ])->selectRaw('ST_AsGeoJSON(geom)::jsonb AS geojson');
    }
}
