<?php

declare(strict_types=1);

namespace App\Mcp\Tools\Contribute;

use App\Actions\Contribution\SubmitContributionAction;
use App\Enums\ContributionSource;
use App\Enums\ContributionTargetType;
use App\Mcp\Support\Reply;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Illuminate\Validation\Rule;
use Illuminate\Validation\ValidationException;
use Laravel\Mcp\Request;
use Laravel\Mcp\ResponseFactory;
use Laravel\Mcp\Server\Attributes\Description;
use Laravel\Mcp\Server\Tools\Annotations\IsDestructive;
use Laravel\Mcp\Server\Tools\Annotations\IsIdempotent;
use Laravel\Mcp\Server\Tools\Annotations\IsReadOnly;

#[Description('Suggest a correction to one prose field of an existing atlas record. Nothing changes until a moderator approves it. Targets: an entity (name, summary, significance, description, aliases), a relationship (description), a chronicle (title, description) or a chronicle step (narrative_text). Give the complete corrected text for that field, not a patch. Look the current text up first (get-entity, get-chronicle) so the correction is against what is there now. At most 50 suggestions may wait for review per account.')]
#[IsReadOnly(false)]
#[IsDestructive(false)]
#[IsIdempotent(false)]
class SuggestCorrection extends ContributeTool
{
    public function schema(JsonSchema $schema): array
    {
        return [
            'target_type' => $schema->string()->enum(array_column(ContributionTargetType::cases(), 'value'))
                ->description('entity, relationship, chronicle or chronicle_entry.')->required(),
            'target_id' => $schema->string()->format('uuid')
                ->description('Id of the record (entity id, relationship id, chronicle id or chronicle step id, from the read tools).')->required(),
            'field' => $schema->string()
                ->description('entity: name | summary | significance | description | aliases (one alias per line). relationship: description. chronicle: title | description. chronicle_entry: narrative_text.')->required(),
            'proposed_text' => $schema->string()->max(ContributionTargetType::MAX_TEXT_LENGTH)
                ->description('The full corrected text for the field.')->required(),
            'note' => $schema->string()->max(1000)
                ->description('Why: the evidence or source for the correction. Moderators read this.'),
        ];
    }

    public function outputSchema(JsonSchema $schema): array
    {
        return [
            'contribution_id' => $schema->integer()->required(),
            'status' => $schema->string()->required(),
            'message' => $schema->string()->required(),
        ];
    }

    public function handle(Request $request, SubmitContributionAction $submit): ResponseFactory
    {
        $input = $request->validate([
            'target_type' => ['required', 'string', Rule::enum(ContributionTargetType::class)],
            'target_id' => ['required', 'uuid'],
            'field' => ['required', 'string', 'max:64'],
            'proposed_text' => ['required', 'string', 'max:'.ContributionTargetType::MAX_TEXT_LENGTH],
            'note' => ['sometimes', 'nullable', 'string', 'max:1000'],
        ]);
        $type = ContributionTargetType::from($input['target_type']);
        if (mb_strlen($input['proposed_text']) > $type->maxLength($input['field'])) {
            throw ValidationException::withMessages(['proposed_text' => 'The text for this field can be at most '.$type->maxLength($input['field']).' characters.']);
        }

        $user = $this->account($request);
        $contribution = $submit(
            $user, $type, $input['target_id'], $input['field'], $input['proposed_text'], $input['note'] ?? null,
            ContributionSource::Mcp, $this->clientName($user),
        );

        return Reply::make(
            "Recorded suggestion #{$contribution->id}. A moderator will review it; nothing has changed yet.",
            [
                'contribution_id' => $contribution->id,
                'status' => $contribution->status->value,
                'message' => 'Waiting for review. The user can follow it under My contributions on the atlas.',
            ],
        );
    }
}
