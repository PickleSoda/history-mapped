<?php

declare(strict_types=1);

namespace Tests\Feature\Mcp;

use App\Mcp\Resources\ConnectionsApp;
use App\Mcp\Resources\EntityCardApp;
use App\Mcp\Resources\TimelineApp;
use App\Mcp\Resources\YearMapApp;
use App\Mcp\Servers\AtlasServer;
use PHPUnit\Framework\Attributes\DataProvider;

class ViewsTest extends McpTestCase
{
    /** @return array<string, array{0: class-string, 1: string}> */
    public static function views(): array
    {
        return [
            'entity card' => [EntityCardApp::class, 'createMcpApp'],
            'year map' => [YearMapApp::class, 'maplibre-gl'],
            'connections' => [ConnectionsApp::class, 'createMcpApp'],
            'timeline' => [TimelineApp::class, 'createMcpApp'],
        ];
    }

    #[DataProvider('views')]
    public function test_each_view_is_registered_and_readable(string $class, string $needle): void
    {
        AtlasServer::resource($class)->assertSee($needle);

        $resource = new $class;
        $data = $resource->toArray();
        $this->assertStringStartsWith('ui://', $resource->uri());
        $this->assertSame('text/html;profile=mcp-app', $data['mimeType']);
    }

    public function test_entity_card_declares_only_the_image_hosts(): void
    {
        $csp = (new EntityCardApp)->resolvedAppMeta()['csp'];

        $this->assertEqualsCanonicalizing(['https://upload.wikimedia.org', 'https://thumb.wikimedia.org'], $csp['resourceDomains']);
        $this->assertArrayNotHasKey('connectDomains', $csp);
    }

    public function test_year_map_declares_the_cdn_and_tile_origins(): void
    {
        $csp = (new YearMapApp)->resolvedAppMeta()['csp'];

        $this->assertSame(['https://cdnjs.cloudflare.com'], $csp['resourceDomains']);
        $this->assertEqualsCanonicalizing(['https://www.openhistoricalmap.org', 'https://vtiles.openhistoricalmap.org'], $csp['connectDomains']);
    }

    public function test_graph_and_timeline_need_no_external_origins(): void
    {
        foreach ([ConnectionsApp::class, TimelineApp::class] as $class) {
            $this->assertArrayNotHasKey('csp', (new $class)->resolvedAppMeta());
        }
    }

    public function test_tools_list_links_exactly_the_four_views(): void
    {
        $tools = collect($this->postJson('/mcp', ['jsonrpc' => '2.0', 'id' => 1, 'method' => 'tools/list'], ['Accept' => 'application/json, text/event-stream'])
            ->assertOk()->json('result.tools'))->keyBy('name');

        $linked = $tools->filter(fn (array $t): bool => isset($t['_meta']['ui']['resourceUri']))->map(fn (array $t): string => $t['_meta']['ui']['resourceUri']);

        $this->assertEqualsCanonicalizing(['get-entity', 'what-was-happening', 'get-connections', 'get-chronicle'], $linked->keys()->all());
        $this->assertCount(4, $linked->unique());
        $linked->each(fn (string $uri) => $this->assertStringStartsWith('ui://', $uri));
    }
}
