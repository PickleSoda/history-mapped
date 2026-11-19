<?php

declare(strict_types=1);

namespace App\Mcp\Tools\Contribute;

use App\Actions\Contribution\ProposeEntityAction;
use App\Enums\ContributionSource;
use App\Enums\EntityType;
use App\Exceptions\EntityQidExistsException;
use App\Exceptions\PossibleDuplicatesException;
use App\Mcp\Support\AtlasUrl;
use App\Mcp\Support\Reply;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Laravel\Mcp\Request;
use Laravel\Mcp\ResponseFactory;
use Laravel\Mcp\Server\Attributes\Description;
use Laravel\Mcp\Server\Tools\Annotations\IsDestructive;
use Laravel\Mcp\Server\Tools\Annotations\IsIdempotent;
use Laravel\Mcp\Server\Tools\Annotations\IsReadOnly;

#[Description('Propose a NEW entity (a person, place, battle, polity, work and so on) that the atlas lacks. Nothing is created now: it is held as a proposal and a moderator creates it only after approving it. Search first (search-atlas) and do not propose what exists. If the atlas already has the Wikidata QID, nothing is recorded and that entity is returned. If entities with the same name and type exist near the same time, nothing is recorded and they are returned as possible_duplicates: show them to the user, and only if the user confirms this is a different entity call again with acknowledge_duplicates true. Give dates as signed years (1066 is AD 1066, -44 is 44 BC; no year 0) and cite sources. Add the relationships with propose-relationship, using the contribution_id this returns.')]
#[IsReadOnly(false)]
#[IsDestructive(false)]
#[IsIdempotent(false)]
class ProposeEntity extends ContributeTool
{
    public function schema(JsonSchema $schema): array
    {
        return [
            'name' => $schema->string()->min(2)->max(500)->description('The entity\'s usual English name.')->required(),
            'entity_type' => $schema->string()->enum(array_column(EntityType::cases(), 'value'))
                ->description('One of the 30 atlas types, e.g. person, city, event_battle, political_entity.')->required(),
            'summary' => $schema->string()->max(5000)->description('One or two plain sentences saying what it is.'),
            'description' => $schema->string()->max(20000)->description('Longer prose, only if you have well-sourced detail.'),
            'start_year' => $schema->integer()->min(-20000)->max(3000)->description('Signed year it began or the person was born. No year 0.'),
            'end_year' => $schema->integer()->min(-20000)->max(3000)->description('Signed year it ended or the person died. Not before start_year.'),
            'place' => $schema->string()->max(500)->description('Where, as a place name (e.g. "Hastings, England").'),
            'latitude' => $schema->number()->min(-90)->max(90)->description('Decimal degrees; give with longitude.'),
            'longitude' => $schema->number()->min(-180)->max(180)->description('Decimal degrees; give with latitude.'),
            'wikidata_qid' => $schema->string()->pattern('^[Qq][0-9]+$')->description('Wikidata id such as "Q517", when known.'),
            'alternative_names' => $schema->array()->items($schema->string()->max(500))->max(20)->description('Other names and spellings.'),
            'sources' => $schema->array()->items($schema->object([
                'title' => $schema->string()->max(300)->description('Source title.'),
                'url' => $schema->string()->max(1000)->description('http(s) link.'),
            ]))->max(10)->description('Where the facts come from. Each needs a title or url.'),
            'note' => $schema->string()->max(1000)->description('For the moderator: why this belongs in the atlas, anything uncertain.'),
            'acknowledge_duplicates' => $schema->boolean()
                ->description('Set true only after the user has seen the possible_duplicates and confirmed this is a different entity.'),
        ];
    }

    public function outputSchema(JsonSchema $schema): array
    {
        return [
            'recorded' => $schema->boolean()->description('True when a proposal was stored.')->required(),
            'contribution_id' => $schema->integer()->description('Use this as source or target in propose-relationship.')->nullable()->required(),
            'status' => $schema->string()->nullable()->required(),
            'existing_entity' => $schema->object([
                'id' => $schema->string()->required(),
                'name' => $schema->string()->required(),
                'atlas_url' => $schema->string()->required(),
            ])->description('Set when the Wikidata QID is already in the atlas.')->nullable()->required(),
            'possible_duplicates' => $schema->array()->items($schema->object([
                'id' => $schema->string()->required(),
                'name' => $schema->string()->required(),
                'type' => $schema->string()->required(),
                'start_year' => $schema->integer()->nullable()->required(),
                'end_year' => $schema->integer()->nullable()->required(),
                'atlas_url' => $schema->string()->required(),
            ]))->required(),
            'message' => $schema->string()->required(),
        ];
    }

    public function handle(Request $request, ProposeEntityAction $propose): ResponseFactory
    {
        $input = $request->validate([
            'name' => ['required', 'string', 'min:2', 'max:500'],
            'entity_type' => ['required', 'string'],
            'summary' => ['sometimes', 'nullable', 'string', 'max:5000'],
            'description' => ['sometimes', 'nullable', 'string', 'max:20000'],
            'start_year' => ['sometimes', 'nullable', 'integer'],
            'end_year' => ['sometimes', 'nullable', 'integer'],
            'place' => ['sometimes', 'nullable', 'string', 'max:500'],
            'latitude' => ['nullable', 'numeric', 'between:-90,90', 'required_with:longitude'],
            'longitude' => ['nullable', 'numeric', 'between:-180,180', 'required_with:latitude'],
            'wikidata_qid' => ['sometimes', 'nullable', 'string', 'regex:/^[Qq]\d+$/'],
            'alternative_names' => ['sometimes', 'nullable', 'array', 'max:20'],
            'alternative_names.*' => ['string', 'max:500'],
            'sources' => ['sometimes', 'nullable', 'array', 'max:10'],
            'sources.*.title' => ['nullable', 'string', 'max:300'],
            'sources.*.url' => ['nullable', 'string', 'max:1000'],
            'note' => ['sometimes', 'nullable', 'string', 'max:1000'],
            'acknowledge_duplicates' => ['sometimes', 'nullable', 'boolean'],
        ]);

        $user = $this->account($request);

        try {
            $contribution = $propose($user, [
                'name' => $input['name'],
                'entity_type' => $input['entity_type'],
                'summary' => $input['summary'] ?? null,
                'description' => $input['description'] ?? null,
                'temporal_start' => isset($input['start_year']) ? (string) $input['start_year'] : null,
                'temporal_end' => isset($input['end_year']) ? (string) $input['end_year'] : null,
                'location_name' => $input['place'] ?? null,
                'geojson' => isset($input['latitude'], $input['longitude'])
                    ? ['type' => 'Point', 'coordinates' => [(float) $input['longitude'], (float) $input['latitude']]]
                    : null,
                'wikidata_id' => isset($input['wikidata_qid']) ? strtoupper($input['wikidata_qid']) : null,
                'alternative_names' => $input['alternative_names'] ?? null,
                'source_citations' => $input['sources'] ?? null,
            ], $input['note'] ?? null, (bool) ($input['acknowledge_duplicates'] ?? false), ContributionSource::Mcp, $this->clientName($user));
        } catch (EntityQidExistsException $e) {
            $existing = ['id' => $e->entity->entity_id, 'name' => $e->entity->name, 'atlas_url' => AtlasUrl::entity($e->entity->entity_id)];

            return Reply::make(
                "Not recorded: the atlas already has {$e->entity->wikidata_id} as \"{$e->entity->name}\". Use that entity; to fix it, use suggest-correction.",
                ['recorded' => false, 'contribution_id' => null, 'status' => null, 'existing_entity' => $existing, 'possible_duplicates' => [], 'message' => 'The Wikidata QID is already in the atlas.'],
            );
        } catch (PossibleDuplicatesException $e) {
            $duplicates = array_map(fn (array $d): array => [
                'id' => $d['entity_id'],
                'name' => $d['name'],
                'type' => $d['entity_type'],
                'start_year' => $d['start_year'],
                'end_year' => $d['end_year'],
                'atlas_url' => AtlasUrl::entity($d['entity_id']),
            ], $e->duplicates);

            return Reply::make(
                'Not recorded yet: the atlas has entities with the same name and type around the same time. Show them to the user. If the user confirms this is a different entity, call propose-entity again with acknowledge_duplicates true; otherwise use the existing entity.',
                ['recorded' => false, 'contribution_id' => null, 'status' => null, 'existing_entity' => null, 'possible_duplicates' => $duplicates, 'message' => $e->getMessage()],
            );
        }

        return Reply::make(
            "Recorded proposal #{$contribution->id} for \"{$input['name']}\". A moderator reviews it before it exists in the atlas. To link it, call propose-relationship with contribution_id {$contribution->id}.",
            [
                'recorded' => true,
                'contribution_id' => $contribution->id,
                'status' => $contribution->status->value,
                'existing_entity' => null,
                'possible_duplicates' => [],
                'message' => 'Waiting for review. It is not in the atlas yet.',
            ],
        );
    }
}
