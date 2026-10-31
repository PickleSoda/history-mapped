<?php

namespace App\Ai\Tools;

use App\Actions\Entity\ApplyEntityEditsAction;
use App\DTOs\EntityData;
use App\Models\Entity;
use App\Support\EntityAttributeCatalog;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Illuminate\Support\Arr;
use Illuminate\Support\Str;
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
        return 'Return the live state of an entity so you can ground yourself before changing it: every field update_entity_fields can edit (`fields`), '
            .'the type-specific attributes this entity type has with their allowed values and current values (`attribute_fields`), the map location, '
            .'dates and relationships. Call it before editing; fields that are null are simply unset and can be filled in.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'entity_id' => $schema->string()->description('UUID of the entity, if known.'),
            'name' => $schema->string()->description('Entity name to resolve to an id, if the UUID is not known. May also be passed via entity_id.'),
        ];
    }

    /**
     * Read-only: return entity context JSON directly, no proposal staged.
     *
     * Resolves the target entity by UUID or by name (global sessions supply a
     * name — the model has no UUID — and may put it in either field), falling
     * back to a bound entity for entity-scoped sessions. Returns an error
     * payload — never a fatal — when nothing resolves, so a tool call cannot
     * abort the stream. A non-UUID value is treated as a name and never fed to
     * a primary-key lookup (which would throw a QueryException on Postgres).
     */
    public function handle(Request $request): Stringable|string
    {
        $entity = $this->resolveEntity($request);

        if ($entity === null) {
            $ref = $request['entity_id'] ?? $request['name'] ?? null;

            return json_encode([
                'error' => $ref !== null
                    ? "No entity found matching '{$ref}'. Provide a valid entity_id or exact name."
                    : 'No entity specified. Provide an entity_id or name.',
            ], JSON_THROW_ON_ERROR);
        }

        $entity->load([
            'primaryLocation',
            'primaryTemporalRange',
            'entityTags',
            'aliases',
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

        $stored = is_array($entity->attributes) ? $entity->attributes : [];
        $attributeFields = [];
        foreach (EntityAttributeCatalog::fieldsFor($entity->entity_type) as $key => $field) {
            $attributeFields[$key] = ['value' => $stored[$key] ?? null] + $field;
        }

        return json_encode([
            'entity_id' => $entity->entity_id,
            'name' => $entity->name,
            'entity_type' => $entity->entity_type?->value,
            'entity_group' => $entity->entity_group?->value,
            'wikidata_id' => $entity->wikidata_id,
            'summary' => $entity->summary,
            'location' => $loc ? [
                'lon' => data_get($loc->geom, 'coordinates.0'),
                'lat' => data_get($loc->geom, 'coordinates.1'),
                'geometry' => data_get($loc->geom, 'type'),
                'name' => $loc->location_name,
                'method' => $loc->location_method?->value,
                'confidence' => $entity->location_confidence?->value,
                'has_territory' => $loc->territory_geom !== null,
            ] : null,
            'temporal_start' => $temporal?->start_date,
            'temporal_end' => $temporal?->end_date,
            // Everything update_entity_fields edits, current value or null.
            'fields' => $this->editableFields($entity, $stored),
            'attribute_fields' => $attributeFields,
            // Stored keys outside the catalog (pipeline flags, lists): not editable here.
            'other_attribute_keys' => array_values(array_diff(
                array_keys($stored),
                array_keys($attributeFields),
                EntityData::MOVED_KEYS,
            )),
            'relationships' => $relationships,
        ], JSON_THROW_ON_ERROR);
    }

    /**
     * The entity's editable values under update_entity_fields' argument names.
     *
     * @param  array<string, mixed>  $stored
     * @return array<string, mixed>
     */
    private function editableFields(Entity $entity, array $stored): array
    {
        $current = Arr::except(ApplyEntityEditsAction::currentValues($entity), [
            'entity_group', 'wikidata_id', 'geojson', 'territory_geojson', 'temporal_start', 'temporal_end',
        ]);

        return $current + [
            'start' => $entity->primaryTemporalRange?->start_date,
            'end' => $entity->primaryTemporalRange?->end_date,
            'date_raw' => $stored['date_raw'] ?? null,
            'confidence_notes' => $stored['confidence_notes'] ?? null,
            'entity_color' => $stored['entity_color'] ?? null,
            'tags' => ApplyEntityEditsAction::manualTags($entity),
            'alternative_names' => $entity->aliases->pluck('name')->values()->all(),
        ];
    }

    /**
     * Resolve the target entity from the request, or the bound entity, or null.
     * A non-UUID identifier is resolved by name (exact, then contains) and is
     * never passed to a primary-key lookup.
     */
    private function resolveEntity(Request $request): ?Entity
    {
        $needle = $request['entity_id'] ?? $request['name'] ?? null;

        if ($needle === null) {
            return isset($this->entity) ? $this->entity : null;
        }

        if (Str::isUuid($needle)) {
            return Entity::find($needle);
        }

        return Entity::whereRaw('LOWER(name) = LOWER(?)', [$needle])->first()
            ?? Entity::where('name', 'ILIKE', '%'.$needle.'%')->first();
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
