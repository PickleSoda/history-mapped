<?php

declare(strict_types=1);

namespace App\Actions\Chronicle;

use App\Models\Chronicle;
use Illuminate\Support\Collection;

/**
 * Chronicles an entity appears in — either as the source/target of an entry's
 * primary relationship, or as a secondary entity of an entry.
 *
 * Each returned chronicle carries the primary relationship ids of all its
 * entries so the caller can also mark which of the entity's relationships
 * belong to a chronicle.
 */
class GetEntityChroniclesAction
{
    /**
     * @return Collection<int, Chronicle>
     */
    public function __invoke(string $entityId): Collection
    {
        return Chronicle::query()
            ->whereHas('entries', function ($entry) use ($entityId): void {
                $entry->whereHas('primaryRelationship', function ($rel) use ($entityId): void {
                    $rel->where(function ($w) use ($entityId): void {
                        $w->where('source_entity_id', $entityId)
                            ->orWhere('target_entity_id', $entityId);
                    });
                })->orWhereHas('secondaryEntities', function ($sec) use ($entityId): void {
                    $sec->where('entities.entity_id', $entityId);
                });
            })
            ->with(['entries:entry_id,chronicle_id,primary_relationship_id'])
            ->orderByDesc('impact_score')
            ->get();
    }
}
