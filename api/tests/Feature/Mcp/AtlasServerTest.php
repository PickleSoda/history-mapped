<?php

declare(strict_types=1);

namespace Tests\Feature\Mcp;

use App\Mcp\Servers\AtlasServer;
use App\Mcp\Tools\FindChronicles;
use App\Mcp\Tools\GetChronicle;
use App\Mcp\Tools\GetConnections;
use App\Mcp\Tools\GetEntity;
use App\Mcp\Tools\SearchAtlas;
use App\Mcp\Tools\WhatWasHappening;

class AtlasServerTest extends McpTestCase
{
    private const TOOLS = ['search-atlas', 'get-entity', 'what-was-happening', 'get-connections', 'find-chronicles', 'get-chronicle'];

    public function test_registers_the_six_read_tools(): void
    {
        AtlasServer::tools()->assertRegistered([
            SearchAtlas::class, GetEntity::class, WhatWasHappening::class,
            GetConnections::class, FindChronicles::class, GetChronicle::class,
        ]);
    }

    public function test_tools_list_over_http_shows_annotations_and_schemas(): void
    {
        $tools = collect($this->postJson('/mcp', ['jsonrpc' => '2.0', 'id' => 1, 'method' => 'tools/list'], ['Accept' => 'application/json, text/event-stream'])
            ->assertOk()->json('result.tools'));

        $this->assertEqualsCanonicalizing(self::TOOLS, $tools->pluck('name')->all());
        foreach ($tools as $tool) {
            $this->assertTrue($tool['annotations']['readOnlyHint'], $tool['name']);
            $this->assertTrue($tool['annotations']['idempotentHint'], $tool['name']);
            $this->assertNotEmpty($tool['description'], $tool['name']);
            $this->assertNotEmpty($tool['inputSchema']['properties'], $tool['name']);
            $this->assertNotEmpty($tool['outputSchema']['properties'], $tool['name']);
        }
    }

    public function test_tools_call_over_http_returns_json_rpc_with_structured_content(): void
    {
        $this->placed('Httpia', 10, 40, 1400, 1600);

        $response = $this->postJson('/mcp', [
            'jsonrpc' => '2.0',
            'id' => 7,
            'method' => 'tools/call',
            'params' => ['name' => 'search-atlas', 'arguments' => ['query' => 'Httpia']],
        ], ['Accept' => 'application/json, text/event-stream']);

        $response->assertOk()
            ->assertJsonPath('jsonrpc', '2.0')
            ->assertJsonPath('id', 7)
            ->assertJsonPath('result.isError', false)
            ->assertJsonPath('result.structuredContent.entities.0.name', 'Httpia')
            ->assertJsonPath('result.structuredContent.total_entities', 1);
        $this->assertStringContainsString('Httpia', $response->json('result.content.0.text'));
    }

    public function test_a_failed_call_over_http_is_a_tool_error(): void
    {
        $response = $this->postJson('/mcp', [
            'jsonrpc' => '2.0',
            'id' => 8,
            'method' => 'tools/call',
            'params' => ['name' => 'get-chronicle', 'arguments' => ['slug' => 'nope']],
        ], ['Accept' => 'application/json, text/event-stream']);

        $response->assertOk()->assertJsonPath('result.isError', true);
    }
}
