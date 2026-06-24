<?php

namespace Tests\Feature\Ai;

use App\Ai\ProposalApplier;
use App\Ai\ToolRegistry;
use App\Ai\Tools\AgentTool;
use App\Models\Ai\ProposedChange;
use App\Models\User;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ProposalApplierTest extends TestCase
{
    use RefreshDatabase;

    public function test_dependent_part_waits_for_its_dependency_then_substitutes_result_id(): void
    {
        // register a fake tool that echoes payload + injected dependency id
        app()->bind('ai.tool.fake', fn () => new class extends AgentTool
        {
            public static function name(): string
            {
                return 'fake';
            }

            public function description(): string
            {
                return 'fake tool';
            }

            public function schema(JsonSchema $s): array
            {
                return [];
            }

            public function buildParts(array $args): array
            {
                return [];
            }

            public function applyPart(array $payload, array $resolved): array
            {
                return ['result_id' => ($resolved['depends'] ?? 'X').':'.$payload['v'], 'summary' => 'ok'];
            }
        });
        app(ToolRegistry::class)->register('fake', 'ai.tool.fake');

        $user = User::factory()->create();
        $change = ProposedChange::create(['user_id' => $user->id, 'context_type' => 'entity', 'context_id' => 'e1']);
        $a = $change->parts()->create(['key' => 'a', 'tool' => 'fake', 'payload' => ['v' => 'A'], 'human_diff' => []]);
        $b = $change->parts()->create(['key' => 'b', 'tool' => 'fake', 'payload' => ['v' => 'B'], 'human_diff' => [], 'depends_on' => 'a']);

        $applier = app(ProposalApplier::class);

        // applying B before A throws (dependency not applied)
        $this->expectExceptionMessage('depends_on');
        $applier->applyPart($b);
        $this->assertSame('pending', $b->fresh()->status);

        // apply A, then B substitutes A's result_id
        $applier->applyPart($a);
        $this->assertSame('X:A', $a->fresh()->result_id);
        $applier->applyPart($b->fresh());
        $this->assertSame('X:A:B', $b->fresh()->result_id);
    }
}
