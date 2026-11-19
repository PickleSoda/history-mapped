<?php

declare(strict_types=1);

namespace App\Mcp\Tools\Contribute;

use App\Actions\Contribution\DescribeContributionTargetsAction;
use App\Enums\ContributionStatus;
use App\Http\Api\V1\Controllers\ContributionController;
use App\Mcp\Support\Reply;
use App\Models\Contribution;
use App\Support\ContributionProposal;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Illuminate\Validation\Rule;
use Laravel\Mcp\Request;
use Laravel\Mcp\ResponseFactory;
use Laravel\Mcp\Server\Attributes\Description;
use Laravel\Mcp\Server\Tools\Annotations\IsDestructive;
use Laravel\Mcp\Server\Tools\Annotations\IsIdempotent;
use Laravel\Mcp\Server\Tools\Annotations\IsReadOnly;

#[Description('List the signed-in user\'s own contributions (corrections and proposals made here or on the atlas) with their review status (pending, approved, rejected, withdrawn) and any note from the moderator. Own rows only, newest first. Use it to check what has been decided and to find the ids of pending entity proposals for propose-relationship.')]
#[IsReadOnly(false)]
#[IsDestructive(false)]
#[IsIdempotent]
class MyContributions extends ContributeTool
{
    private const DEFAULT_LIMIT = 20;

    public function schema(JsonSchema $schema): array
    {
        return [
            'status' => $schema->string()->enum(array_column(ContributionStatus::cases(), 'value'))->description('Only this status.'),
            'limit' => $schema->integer()->min(1)->max(50)->description('Rows to return, 1 to 50 (default 20).'),
        ];
    }

    public function outputSchema(JsonSchema $schema): array
    {
        return [
            'contributions' => $schema->array()->items($schema->object([
                'id' => $schema->integer()->required(),
                'kind' => $schema->string()->description('edit (a text correction), or create (a proposed new entity or relationship).')->required(),
                'about' => $schema->string()->description('The record or proposal this concerns.')->required(),
                'field' => $schema->string()->nullable()->required(),
                'summary' => $schema->string()->description('What was proposed.')->required(),
                'status' => $schema->string()->required(),
                'review_note' => $schema->string()->nullable()->required(),
                'created_entity_id' => $schema->string()->description('For an approved proposal, the id of the record that was created.')->nullable()->required(),
                'source' => $schema->string()->required(),
                'submitted_at' => $schema->string()->nullable()->required(),
                'reviewed_at' => $schema->string()->nullable()->required(),
            ]))->required(),
            'total' => $schema->integer()->required(),
        ];
    }

    public function handle(Request $request, DescribeContributionTargetsAction $describe): ResponseFactory
    {
        $input = $request->validate([
            'status' => ['sometimes', 'nullable', Rule::enum(ContributionStatus::class)],
            'limit' => ['sometimes', 'nullable', 'integer', 'min:1', 'max:50'],
        ]);
        $user = $this->account($request);

        $query = $user->contributions()->latest()->orderByDesc('id');
        if (! empty($input['status'])) {
            $query->where('status', $input['status']);
        }
        $total = (clone $query)->count();
        $rows = $query->limit((int) ($input['limit'] ?? self::DEFAULT_LIMIT))->get();
        ContributionController::attachTargets($rows, $describe);

        $items = $rows->map(fn (Contribution $c): array => [
            'id' => $c->id,
            'kind' => $c->kind->value,
            'about' => $c->targetInfo['label'] ?? 'Removed record',
            'field' => $c->field,
            'summary' => $c->isCreate()
                ? ContributionProposal::summary($c)
                : '“'.mb_strimwidth((string) $c->proposed_text, 0, 200, '…').'”',
            'status' => $c->status->value,
            'review_note' => $c->review_note,
            'created_entity_id' => $c->isCreate() ? $c->target_id : null,
            'source' => $c->source->value,
            'submitted_at' => $c->created_at?->toISOString(),
            'reviewed_at' => $c->reviewed_at?->toISOString(),
        ])->all();

        return Reply::make(
            $total === 0 ? 'No contributions yet.' : count($items).' of '.$total.' contributions.',
            ['contributions' => $items, 'total' => $total],
        );
    }
}
