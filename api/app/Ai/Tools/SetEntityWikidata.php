<?php

namespace App\Ai\Tools;

use App\Actions\Entity\BackfillEntityAction;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use App\Services\WikidataService;
use Illuminate\Contracts\JsonSchema\JsonSchema;

class SetEntityWikidata extends AgentTool
{
    /**
     * P31 (instance-of) QIDs that indicate a creative/bogus namesake rather
     * than a historical subject. If the fetched QID's P31 intersects this list
     * the request is rejected before staging a proposal.
     */
    public const BOGUS_P31 = [
        'Q7366',      // song
        'Q134556',    // single (music)
        'Q3305213',   // painting
        'Q11424',     // film
        'Q5398426',   // TV series
        'Q7889',      // video game
        'Q79007',     // street
        'Q21191270',  // TV series episode
    ];

    public function __construct(
        private WikidataService $wikidata,
        private BackfillEntityAction $backfill,
    ) {}

    public static function name(): string
    {
        return 'set_entity_wikidata';
    }

    public function description(): string
    {
        return 'Correct an entity\'s Wikidata QID. Guards against wrong-namesake QIDs (songs, streets, paintings, …) by checking P31 instance-of, then cascades the new QID into source_citations and entity_geo_refs provenance.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'entity_id' => $schema->string()->description('UUID of the entity to update')->required(),
            'wikidata_id' => $schema->string()->description('The correct Wikidata QID, e.g. Q638')->required(),
        ];
    }

    public function buildParts(array $args): array
    {
        $entityId = $args['entity_id'];
        $wikidataId = $args['wikidata_id'];

        $meta = $this->wikidata->fetch($wikidataId);

        if ($meta === null) {
            throw new \InvalidArgumentException("QID {$wikidataId} not found on Wikidata.");
        }

        $bogusHits = array_intersect($meta['p31'], self::BOGUS_P31);
        if (! empty($bogusHits)) {
            $hitList = implode(', ', $bogusHits);
            throw new \InvalidArgumentException(
                "QID {$wikidataId} appears to be a namesake rather than a historical entity (P31 contains: {$hitList}). Verify the correct QID with verify_wikidata first."
            );
        }

        $entity = Entity::findOrFail($entityId);

        return [[
            'key' => 'wikidata',
            'tool' => self::name(),
            'payload' => [
                'entity_id' => $entityId,
                'wikidata_id' => $wikidataId,
            ],
            'human_diff' => [
                'summary' => "Set QID → {$wikidataId} ({$meta['label']})",
                'from' => $entity->wikidata_id,
                'to' => $wikidataId,
                'verified_label' => $meta['label'],
            ],
        ]];
    }

    public function applyPart(array $payload, array $resolved): array
    {
        $entity = Entity::findOrFail($payload['entity_id']);
        $old = $entity->wikidata_id;
        $new = $payload['wikidata_id'];

        // Update the primary QID column
        $entity->wikidata_id = $new;

        // Cascade into source_citations (JSON column): update wikidata_id + wikidata_url keys if present
        $citations = $entity->source_citations;
        if (is_array($citations) && array_key_exists('wikidata_id', $citations)) {
            $citations['wikidata_id'] = $new;
            $citations['wikidata_url'] = "https://www.wikidata.org/wiki/{$new}";
            // Reassign the whole array so Eloquent's dirty tracking picks it up
            $entity->source_citations = $citations;
        }

        $entity->save();

        // Cascade into entity_geo_refs: any row whose external_id matches the old QID
        if ($old !== null) {
            EntityGeoRef::query()
                ->where('entity_id', $entity->entity_id)
                ->where('external_id', $old)
                ->update(['external_id' => $new]);
        }

        // Re-derive computed/denormalized data
        ($this->backfill)($entity);

        return [
            'result_id' => $entity->entity_id,
            'summary' => "Wikidata QID updated from {$old} to {$new} with provenance cascade.",
        ];
    }
}
