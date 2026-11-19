<?php

declare(strict_types=1);

namespace Tests\Feature\Mcp;

use App\Enums\EntityType;
use App\Mcp\Servers\AtlasServer;
use App\Mcp\Tools\GetConnections;

class GetConnectionsTest extends McpTestCase
{
    public function test_returns_the_center_neighbour_nodes_and_edges_between_ids(): void
    {
        $rome = $this->placed('Rome Test', 12.5, 41.9, -753, 476, ['entity_type' => EntityType::City->value]);
        $caesar = $this->entity('Caesar Test', EntityType::Person, ['impact_score' => 80]);
        $battle = $this->entity('Pharsalus Test', EntityType::EventBattle, ['impact_score' => 40]);
        $this->relate($caesar, $rome, 'born_in', ['start_year' => -100]);
        $this->relate($rome, $battle, 'participated_in');
        $this->entity('Unconnected');

        AtlasServer::tool(GetConnections::class, ['id' => $rome->entity_id])
            ->assertOk()
            ->assertStructuredContentPath('center.id', $rome->entity_id)
            ->assertStructuredContentPath('center.date_label', '753 BC–AD 476')
            ->assertStructuredContentCount(2, 'nodes')
            ->assertStructuredContentCount(2, 'edges')
            ->assertStructuredContentStructure(['edges' => ['*' => ['source', 'target', 'type', 'label', 'start_year', 'end_year']]])
            // Strongest first: same confidence, so the more important neighbour.
            ->assertStructuredContentPath('nodes.0.id', $caesar->entity_id)
            ->assertStructuredContentPath('nodes.0.atlas_url', 'https://atlas.test/entities/'.$caesar->entity_id)
            ->assertStructuredContentPath('nodes.1.id', $battle->entity_id)
            ->assertStructuredContentPath('edges.0.source', $caesar->entity_id)
            ->assertStructuredContentPath('edges.0.target', $rome->entity_id)
            ->assertStructuredContentPath('edges.0.type', 'born_in')
            ->assertStructuredContentPath('edges.0.label', 'born in')
            ->assertStructuredContentPath('edges.1.source', $rome->entity_id)
            ->assertStructuredContentPath('edges.1.target', $battle->entity_id);
    }

    public function test_types_filter_and_limit(): void
    {
        $hub = $this->entity('Hub Test');
        foreach (range(1, 5) as $i) {
            $this->relate($hub, $this->entity("Friend {$i}"), 'allied_with');
        }
        $this->relate($hub, $this->entity('Enemy'), 'at_war_with');

        AtlasServer::tool(GetConnections::class, ['id' => $hub->entity_id, 'limit' => 3])
            ->assertStructuredContentCount(3, 'edges')
            ->assertStructuredContentCount(3, 'nodes');

        AtlasServer::tool(GetConnections::class, ['id' => $hub->entity_id, 'types' => ['at_war_with']])
            ->assertStructuredContentCount(1, 'edges')
            ->assertStructuredContentPath('nodes.0.name', 'Enemy');
    }

    public function test_an_entity_with_no_links_has_empty_lists(): void
    {
        $lonely = $this->entity('Lonely');

        AtlasServer::tool(GetConnections::class, ['id' => $lonely->entity_id])
            ->assertOk()
            ->assertStructuredContentPath('center.name', 'Lonely')
            ->assertStructuredContentPath('nodes', [])
            ->assertStructuredContentPath('edges', []);
    }

    public function test_unknown_id_and_validation_errors(): void
    {
        AtlasServer::tool(GetConnections::class, ['id' => '00000000-0000-4000-8000-000000000000'])->assertHasErrors(['search_atlas']);
        AtlasServer::tool(GetConnections::class, [])->assertHasErrors();
        AtlasServer::tool(GetConnections::class, ['id' => 'nope'])->assertHasErrors();
        $e = $this->entity('Any');
        AtlasServer::tool(GetConnections::class, ['id' => $e->entity_id, 'limit' => 41])->assertHasErrors();
        AtlasServer::tool(GetConnections::class, ['id' => $e->entity_id, 'types' => ['frenemies']])->assertHasErrors();
    }
}
