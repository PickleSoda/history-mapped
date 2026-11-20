<?php

declare(strict_types=1);

namespace App\Support\Discover;

use App\Enums\VerificationStatus;
use App\Services\RelationGraphSupport;
use Illuminate\Support\Facades\DB;

/**
 * The entity as every Discover endpoint gives it: enough for a card and a
 * link into the atlas.
 *
 *   { id, name, entity_type, entity_group, summary, start_year, end_year, at, has_map_story }
 *
 * The endpoints choose their few entities from a small table or an index and
 * come here with the ids; this reads those rows by primary key.
 *
 *   - `at` is the map point, [lng, lat] to five decimals: the primary
 *     location's point, else the earliest geometry period's (the rule of
 *     GetChroniclePlacesAction, which is where the tiles draw it); null when
 *     the entity has neither.
 *   - `start_year` / `end_year` are the primary date range's years, else the
 *     earliest geometry period's.
 *   - Entities in a status the tiles hide (flagged, rejected, merged) are not
 *     returned.
 */
final class DiscoverEntities
{
    /** Five decimals: about a metre, plenty for a map point. */
    private const PRECISION = 5;

    /**
     * The statuses the atlas shows: the list in `tiles.atlas_entity_features`
     * and MapEntitiesAction.
     *
     * @var list<VerificationStatus>
     */
    public const VISIBLE_STATUSES = [
        VerificationStatus::PipelineDraft,
        VerificationStatus::OhmDraft,
        VerificationStatus::AutoValidated,
        VerificationStatus::NeedsReview,
        VerificationStatus::InReview,
        VerificationStatus::HumanVerified,
        VerificationStatus::ExpertVerified,
    ];

    /** The visible statuses as a SQL list for `verification_status IN (…)`. */
    public static function visibleStatusSql(): string
    {
        return implode(', ', array_map(
            fn (VerificationStatus $status): string => "'{$status->value}'",
            self::VISIBLE_STATUSES,
        ));
    }

    /**
     * The shape of each visible entity among `$ids`, keyed by id.
     *
     * @param  list<string>  $ids
     * @return array<string, array<string, mixed>>
     */
    public static function byId(array $ids): array
    {
        return array_map(self::shape(...), self::rows($ids));
    }

    /**
     * The raw rows behind byId(), keyed by id, for a caller that also needs
     * the primary location's name (`location_name`).
     *
     * @param  list<string>  $ids
     * @return array<string, object>
     */
    public static function rows(array $ids): array
    {
        $ids = array_values(array_unique($ids));
        if ($ids === []) {
            return [];
        }

        $statuses = self::visibleStatusSql();
        $rows = DB::select(
            <<<SQL
            SELECT e.entity_id, e.name, e.entity_type::text AS entity_type, e.entity_group::text AS entity_group, e.summary,
                   CASE WHEN dates.start_year IS NULL AND dates.end_year IS NULL THEN period.start_year ELSE dates.start_year END AS start_year,
                   CASE WHEN dates.start_year IS NULL AND dates.end_year IS NULL THEN period.end_year ELSE dates.end_year END AS end_year,
                   ST_X(point.at) AS lng, ST_Y(point.at) AS lat,
                   place.location_name,
                   EXISTS (SELECT 1 FROM map_stories ms WHERE ms.entity_id = e.entity_id) AS has_map_story
            FROM entities e
            LEFT JOIN LATERAL (
                SELECT el.geom, el.location_name
                FROM entity_locations el
                WHERE el.entity_id = e.entity_id AND el.is_primary = true
                ORDER BY el.updated_at DESC NULLS LAST, el.created_at DESC NULLS LAST
                LIMIT 1
            ) place ON true
            LEFT JOIN LATERAL (
                SELECT COALESCE(gp.geom, gp.territory_geom) AS geom, gp.start_year, gp.end_year
                FROM geometry_periods gp
                WHERE gp.entity_id = e.entity_id
                ORDER BY gp.start_year, gp.geometry_period_id
                LIMIT 1
            ) period ON true
            LEFT JOIN LATERAL (
                SELECT etr.start_year, etr.end_year
                FROM entity_temporal_ranges etr
                WHERE etr.entity_id = e.entity_id AND etr.is_primary = true
                ORDER BY etr.updated_at DESC NULLS LAST, etr.created_at DESC NULLS LAST
                LIMIT 1
            ) dates ON true
            CROSS JOIN LATERAL (SELECT ST_PointOnSurface(COALESCE(place.geom, period.geom)) AS at) point
            WHERE e.entity_id = ANY(?::uuid[]) AND e.verification_status IN ({$statuses})
            SQL,
            [RelationGraphSupport::pgArray($ids)],
        );

        $byId = [];
        foreach ($rows as $row) {
            $byId[(string) $row->entity_id] = $row;
        }

        return $byId;
    }

    /** @return array{id: string, name: string, entity_type: string, entity_group: string, summary: string|null, start_year: int|null, end_year: int|null, at: array{0: float, 1: float}|null, has_map_story: bool} */
    public static function shape(object $row): array
    {
        return [
            'id' => (string) $row->entity_id,
            'name' => (string) $row->name,
            'entity_type' => (string) $row->entity_type,
            'entity_group' => (string) $row->entity_group,
            'summary' => $row->summary,
            'start_year' => $row->start_year !== null ? (int) $row->start_year : null,
            'end_year' => $row->end_year !== null ? (int) $row->end_year : null,
            'at' => $row->lng !== null && $row->lat !== null
                ? [round((float) $row->lng, self::PRECISION), round((float) $row->lat, self::PRECISION)]
                : null,
            'has_map_story' => (bool) $row->has_map_story,
        ];
    }
}
