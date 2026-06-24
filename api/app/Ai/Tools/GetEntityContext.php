<?php

namespace App\Ai\Tools;

use App\Models\Entity;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Laravel\Ai\Tools\Request;
use LogicException;
use Stringable;

class GetEntityContext extends AgentTool
{
    private Entity $entity;

    public static function name(): string
    {
        return 'get_entity_context';
    }

    public function forEntity(Entity $entity): static
    {
        $this->entity = $entity;

        return $this;
    }

    public function description(): string
    {
        return 'Return the live state of an entity (name, type, Wikidata QID, location, dates, relationships) so the model can ground itself before making changes.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [];
    }

    /**
     * Read-only: return entity context JSON directly, no proposal staged.
     */
    public function handle(Request $request): Stringable|string
    {
        $entity = $this->entity->load([
            'primaryLocation',
            'primaryTemporalRange',
            'outgoingRelationships.targetEntity',
            'incomingRelationships.sourceEntity',
        ]);

        $loc = $entity->primaryLocation;
        $temporal = $entity->primaryTemporalRange;

        $relationships = collect($entity->outgoingRelationships)
            ->map(fn ($r) => [
                'direction' => 'outgoing',
                'type' => $r->relationship_type?->value ?? $r->relationship_type,
                'target' => $r->targetEntity?->name,
                'target_id' => $r->target_entity_id,
            ])
            ->merge(
                collect($entity->incomingRelationships)
                    ->map(fn ($r) => [
                        'direction' => 'incoming',
                        'type' => $r->relationship_type?->value ?? $r->relationship_type,
                        'source' => $r->sourceEntity?->name,
                        'source_id' => $r->source_entity_id,
                    ])
            )
            ->values()
            ->all();

        return json_encode([
            'entity_id' => $entity->entity_id,
            'name' => $entity->name,
            'entity_type' => $entity->entity_type?->value,
            'entity_group' => $entity->entity_group?->value,
            'wikidata_id' => $entity->wikidata_id,
            'summary' => $entity->summary,
            'location' => $loc ? ['lon' => data_get($loc->geom, 'coordinates.0'), 'lat' => data_get($loc->geom, 'coordinates.1'), 'method' => $loc->location_method?->value] : null,
            'temporal_start' => $temporal?->start_date,
            'temporal_end' => $temporal?->end_date,
            'relationships' => $relationships,
        ], JSON_THROW_ON_ERROR);
    }

    public function buildParts(array $args): array
    {
        throw new LogicException('GetEntityContext is a read-only tool — it does not stage proposals.');
    }

    public function applyPart(array $payload, array $resolved): array
    {
        throw new LogicException('GetEntityContext is a read-only tool — it does not apply parts.');
    }
}
