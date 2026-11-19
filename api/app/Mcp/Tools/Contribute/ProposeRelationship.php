<?php

declare(strict_types=1);

namespace App\Mcp\Tools\Contribute;

use App\Actions\Contribution\ProposeRelationshipAction;
use App\Enums\ContributionSource;
use App\Enums\RelationshipType;
use App\Mcp\Support\Reply;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Laravel\Mcp\Request;
use Laravel\Mcp\ResponseFactory;
use Laravel\Mcp\Server\Attributes\Description;
use Laravel\Mcp\Server\Tools\Annotations\IsDestructive;
use Laravel\Mcp\Server\Tools\Annotations\IsIdempotent;
use Laravel\Mcp\Server\Tools\Annotations\IsReadOnly;

#[Description('Propose a NEW relationship between two entities. Nothing is created now: it is held as a proposal for a moderator. Each end is an existing entity id (from search-atlas) or the contribution_id that propose-entity returned for one of your own pending entity proposals; a relationship to a pending entity can only be approved after that entity. The type reads from the source\'s side: "source <type> target", e.g. source Julius Caesar, type commanded, target Gallic Wars; source Napoleon, type born_in, target Ajaccio; source Rome, type capital_of, target Roman Empire; source Battle of Hastings, type part_of, target Norman Conquest. Check get-connections first and do not propose one that exists.')]
#[IsReadOnly(false)]
#[IsDestructive(false)]
#[IsIdempotent(false)]
class ProposeRelationship extends ContributeTool
{
    public function schema(JsonSchema $schema): array
    {
        return [
            'source' => $schema->string()->description('Entity id (uuid), or the contribution_id of your pending entity proposal.')->required(),
            'target' => $schema->string()->description('Entity id (uuid), or the contribution_id of your pending entity proposal.')->required(),
            'relationship_type' => $schema->string()->enum(array_column(RelationshipType::cases(), 'value'))
                ->description('Read as "source <type> target".')->required(),
            'start_year' => $schema->integer()->min(-20000)->max(3000)->description('Signed year it began, when known.'),
            'end_year' => $schema->integer()->min(-20000)->max(3000)->description('Signed year it ended, when known.'),
            'description' => $schema->string()->max(2000)->description('One or two sentences on the link.'),
            'sources' => $schema->array()->items($schema->object([
                'title' => $schema->string()->max(300)->description('Source title.'),
                'url' => $schema->string()->max(1000)->description('http(s) link.'),
            ]))->max(10)->description('Where this comes from. Each needs a title or url.'),
            'note' => $schema->string()->max(1000)->description('For the moderator: the reasoning or anything uncertain.'),
        ];
    }

    public function outputSchema(JsonSchema $schema): array
    {
        return [
            'contribution_id' => $schema->integer()->required(),
            'status' => $schema->string()->required(),
            'waits_for' => $schema->array()->items($schema->integer())
                ->description('Entity proposals (contribution ids) that must be approved before this one can be.')->required(),
            'message' => $schema->string()->required(),
        ];
    }

    public function handle(Request $request, ProposeRelationshipAction $propose): ResponseFactory
    {
        $input = $request->validate([
            'source' => ['required', 'string', 'max:64'],
            'target' => ['required', 'string', 'max:64'],
            'relationship_type' => ['required', 'string'],
            'start_year' => ['sometimes', 'nullable', 'integer', 'between:-20000,3000'],
            'end_year' => ['sometimes', 'nullable', 'integer', 'between:-20000,3000'],
            'description' => ['sometimes', 'nullable', 'string', 'max:2000'],
            'sources' => ['sometimes', 'nullable', 'array', 'max:10'],
            'sources.*.title' => ['nullable', 'string', 'max:300'],
            'sources.*.url' => ['nullable', 'string', 'max:1000'],
            'note' => ['sometimes', 'nullable', 'string', 'max:1000'],
        ]);

        $user = $this->account($request);
        $contribution = $propose($user, [
            'source' => $input['source'],
            'target' => $input['target'],
            'relationship_type' => $input['relationship_type'],
            'temporal_start' => isset($input['start_year']) ? (string) $input['start_year'] : null,
            'temporal_end' => isset($input['end_year']) ? (string) $input['end_year'] : null,
            'description' => $input['description'] ?? null,
            'source_citations' => $input['sources'] ?? null,
        ], $input['note'] ?? null, ContributionSource::Mcp, $this->clientName($user));

        $relationship = $contribution->payload['relationship'];
        $waitsFor = array_values(array_filter([
            $relationship['source']['contribution_id'] ?? null,
            $relationship['target']['contribution_id'] ?? null,
        ]));

        return Reply::make(
            "Recorded relationship proposal #{$contribution->id}. A moderator reviews it before it exists in the atlas."
                .($waitsFor === [] ? '' : ' It can only be approved after entity proposal '.implode(' and ', array_map(fn ($id) => "#{$id}", $waitsFor)).'.'),
            [
                'contribution_id' => $contribution->id,
                'status' => $contribution->status->value,
                'waits_for' => $waitsFor,
                'message' => 'Waiting for review. It is not in the atlas yet.',
            ],
        );
    }
}
