<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Models\Entity;
use App\Models\EntityGeoRef;
use Illuminate\Support\Facades\DB;

/**
 * Set an entity's Wikidata QID and cascade it into the entity's provenance —
 * the `source_citations` JSON (`wikidata_id`/`wikidata_url`) and any
 * `entity_geo_refs.external_id` that still references the old QID — atomically,
 * then re-derive geometry/timeline via backfill.
 *
 * Extracted from the SetEntityWikidata agent tool so the write path matches the
 * "business logic lives in Actions" convention and the cascade is transactional.
 */
class SetEntityWikidataAction
{
    public function __construct(private BackfillEntityAction $backfill) {}

    public function __invoke(Entity $entity, string $newQid): Entity
    {
        $old = $entity->wikidata_id;

        DB::transaction(function () use ($entity, $newQid, $old): void {
            $entity->wikidata_id = $newQid;

            // Cascade into source_citations (JSON column): update the QID keys if
            // present. Reassign the whole array so Eloquent dirty-tracking fires.
            $citations = $entity->source_citations;
            if (is_array($citations) && array_key_exists('wikidata_id', $citations)) {
                $citations['wikidata_id'] = $newQid;
                $citations['wikidata_url'] = "https://www.wikidata.org/wiki/{$newQid}";
                $entity->source_citations = $citations;
            }

            $entity->save();

            // Cascade into entity_geo_refs: any ref still pointing at the old QID.
            if ($old !== null) {
                EntityGeoRef::query()
                    ->where('entity_id', $entity->entity_id)
                    ->where('external_id', $old)
                    ->update(['external_id' => $newQid]);
            }
        });

        ($this->backfill)($entity);

        return $entity;
    }
}
