<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Models\Entity;
use Illuminate\Support\Facades\DB;

/**
 * Merge a duplicate (loser) entity into a surviving entity.
 *
 * Ports the logic from pipeline/merge_entities.py::merge() to PHP/Eloquent.
 *
 * Steps (all inside one DB transaction):
 *  1. Delete loser relationships that would collide with an existing survivor
 *     relationship (same type + same endpoints once loser→survivor rewrite applied).
 *  2. Re-point relationships.source_entity_id loser→survivor.
 *  3. Re-point relationships.target_entity_id loser→survivor.
 *  4. Delete self-loops (source_entity_id = target_entity_id = survivor).
 *  5. chronicle_entry_entities: delete loser link when survivor already linked to same
 *     entry (RESTRICT FK dedup), then re-point remaining loser links to survivor.
 *  6. entity_timeline_entries: re-point location_entity_id and related_entity_id.
 *  7. Delete the loser — CASCADE removes its geo_refs/temporal_ranges/aliases/tags/
 *     timeline primary rows.
 */
class MergeEntitiesAction
{
    public function __invoke(string $survivorId, string $loserId): Entity
    {
        // Verify both entities exist before entering the transaction
        $loser = Entity::findOrFail($loserId);
        $survivor = Entity::findOrFail($survivorId);

        DB::transaction(function () use ($survivorId, $loserId): void {
            // ── Step 1: Drop colliding loser relationships ────────────────────
            //
            // Delete any loser relationship where, after rewriting loser→survivor,
            // the resulting (source, target, type) triple already exists for survivor.
            DB::statement(<<<'SQL'
                DELETE FROM relationships AS l
                WHERE (l.source_entity_id = :loser OR l.target_entity_id = :loser2)
                  AND EXISTS (
                    SELECT 1
                    FROM relationships s
                    WHERE s.relationship_type = l.relationship_type
                      AND (CASE WHEN l.source_entity_id = :loser3 THEN :surv  ELSE l.source_entity_id END) = s.source_entity_id
                      AND (CASE WHEN l.target_entity_id = :loser4 THEN :surv2 ELSE l.target_entity_id END) = s.target_entity_id
                  )
            SQL, [
                'loser' => $loserId,
                'loser2' => $loserId,
                'loser3' => $loserId,
                'surv' => $survivorId,
                'loser4' => $loserId,
                'surv2' => $survivorId,
            ]);

            // ── Step 2: Re-point source side ──────────────────────────────────
            DB::table('relationships')
                ->where('source_entity_id', $loserId)
                ->update(['source_entity_id' => $survivorId]);

            // ── Step 3: Re-point target side ──────────────────────────────────
            DB::table('relationships')
                ->where('target_entity_id', $loserId)
                ->update(['target_entity_id' => $survivorId]);

            // ── Step 4: Remove self-loops ─────────────────────────────────────
            DB::table('relationships')
                ->where('source_entity_id', $survivorId)
                ->where('target_entity_id', $survivorId)
                ->delete();

            // ── Step 5a: chronicle_entry_entities — dedup (RESTRICT FK) ───────
            //
            // Where both loser and survivor are linked to the same entry, the loser
            // link cannot be re-pointed (PK conflict). Drop the loser link instead.
            DB::table('chronicle_entry_entities AS l')
                ->whereExists(function ($query) use ($survivorId): void {
                    $query->selectRaw(1)
                        ->from('chronicle_entry_entities AS s')
                        ->where('s.entity_id', $survivorId)
                        ->whereColumn('s.entry_id', 'l.entry_id');
                })
                ->where('l.entity_id', $loserId)
                ->delete();

            // ── Step 5b: chronicle_entry_entities — re-point remainder ────────
            DB::table('chronicle_entry_entities')
                ->where('entity_id', $loserId)
                ->update(['entity_id' => $survivorId]);

            // ── Step 6: entity_timeline_entries secondary refs ────────────────
            DB::table('entity_timeline_entries')
                ->where('location_entity_id', $loserId)
                ->update(['location_entity_id' => $survivorId]);

            DB::table('entity_timeline_entries')
                ->where('related_entity_id', $loserId)
                ->update(['related_entity_id' => $survivorId]);

            // ── Step 7: Delete loser ──────────────────────────────────────────
            // CASCADE removes: geo_refs, temporal_ranges, aliases, tags,
            //                  timeline primary rows (entity_timeline_entries.entity_id).
            DB::table('entities')
                ->where('entity_id', $loserId)
                ->delete();
        });

        return $survivor;
    }
}
