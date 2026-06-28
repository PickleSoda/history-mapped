<?php

namespace App\Ai\Tools;

use App\Models\Ai\ProposedChange;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Illuminate\JsonSchema\Types\Type;
use Laravel\Ai\Contracts\Tool;
use Laravel\Ai\Tools\Request;
use Stringable;

abstract class AgentTool implements Tool
{
    /** Route/conversation context injected by the agent (user_id, context_type, context_id, conversation_id). */
    protected array $context = [];

    /** Registry key — NOT part of the SDK Tool contract. */
    abstract public static function name(): string;

    abstract public function description(): Stringable|string;

    /** @return array<string,Type> */
    abstract public function schema(JsonSchema $schema): array;

    /** @return list<array{key:string,tool:string,payload:array,human_diff:array,depends_on?:?string}> */
    abstract public function buildParts(array $args): array;

    /** @return array{result_id:string,summary:string} */
    abstract public function applyPart(array $payload, array $resolved): array;

    public function withContext(array $context): static
    {
        $this->context = $context;

        return $this;
    }

    /**
     * Model-facing entry point (laravel/ai Tool contract). Stages a
     * ProposedChange from the model's args + injected context and returns a
     * JSON summary STRING the model relays. The model never applies.
     */
    public function handle(Request $request): Stringable|string
    {
        $change = ProposedChange::create([
            'user_id' => $this->context['user_id'],
            'conversation_id' => $this->context['conversation_id'] ?? null,
            'context_type' => $this->context['context_type'],
            'context_id' => $this->context['context_id'],
        ]);
        foreach ($this->buildParts($request->all()) as $part) {
            $change->parts()->create([
                'key' => $part['key'], 'tool' => $part['tool'],
                'payload' => $part['payload'], 'human_diff' => $part['human_diff'],
                'depends_on' => $part['depends_on'] ?? null,
            ]);
        }

        return json_encode([
            'proposal_id' => $change->id,
            'parts' => $change->parts()->get(['key', 'tool', 'human_diff'])->toArray(),
            'note' => 'Proposed. Awaiting the operator to Apply each part.',
        ], JSON_THROW_ON_ERROR);
    }
}
