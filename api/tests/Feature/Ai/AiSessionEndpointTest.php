<?php

namespace Tests\Feature\Ai;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Schema;
use Tests\TestCase;

class AiSessionEndpointTest extends TestCase
{
    use RefreshDatabase;

    public function test_agent_conversations_has_context_columns(): void
    {
        $this->assertTrue(Schema::hasColumn('agent_conversations', 'context_type'));
        $this->assertTrue(Schema::hasColumn('agent_conversations', 'context_id'));
    }
}
