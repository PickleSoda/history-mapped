<?php

declare(strict_types=1);

namespace Tests\Feature\Mcp;

use App\Enums\EntityType;
use App\Mcp\Servers\AtlasServer;
use App\Mcp\Tools\SearchAtlas;

class SearchAtlasTest extends McpTestCase
{
    public function test_returns_entity_summaries_and_matching_chronicles(): void
    {
        $e = $this->placed('Zorbania', 10.5, 40.5, -44, 14, ['summary' => 'A realm of the test.', 'impact_score' => 80]);
        $this->chronicle('Rise of Zorbania');
        $this->chronicle('Unrelated Tale');

        AtlasServer::tool(SearchAtlas::class, ['query' => 'Zorbania'])
            ->assertOk()
            ->assertStructuredContentPath('query', 'Zorbania')
            ->assertStructuredContentPath('total_entities', 1)
            ->assertStructuredContentPath('total_capped', false)
            ->assertStructuredContentPath('entities.0.id', $e->entity_id)
            ->assertStructuredContentPath('entities.0.start_year', -44)
            ->assertStructuredContentPath('entities.0.end_year', 14)
            ->assertStructuredContentPath('entities.0.date_label', '44 BC–AD 14')
            ->assertStructuredContentPath('entities.0.lng', 10.5)
            ->assertStructuredContentPath('entities.0.lat', 40.5)
            ->assertStructuredContentPath('entities.0.place', 'Zorbania place')
            ->assertStructuredContentPath('entities.0.atlas_url', 'https://atlas.test/entities/'.$e->entity_id)
            ->assertStructuredContentPath('entities.0.verification_status', 'human_verified')
            ->assertStructuredContentPath('entities.0.image_url', null)
            ->assertStructuredContentPath('chronicles.0.slug', 'rise-of-zorbania')
            ->assertStructuredContentPath('chronicles.0.atlas_url', 'https://atlas.test/chronicles/rise-of-zorbania')
            ->assertStructuredContentCount(1, 'chronicles')
            ->assertSee('Zorbania');
    }

    public function test_the_text_the_model_reads_carries_ids_and_links_without_nulls(): void
    {
        // MCP Apps hosts keep structuredContent out of the model's context.
        $e = $this->placed('Zorbania', 10.5, 40.5, -44, 14);

        AtlasServer::tool(SearchAtlas::class, ['query' => 'Zorbania'])
            ->assertSee([
                '"id":"'.$e->entity_id.'"',
                '"atlas_url":"https://atlas.test/entities/'.$e->entity_id.'"',
                '"date_label":"44 BC–AD 14"',
            ])
            ->assertDontSee(['"image_url"', ':null']);
    }

    public function test_every_summary_field_is_present(): void
    {
        $this->entity('Quuxland');

        AtlasServer::tool(SearchAtlas::class, ['query' => 'Quuxland'])
            ->assertStructuredContentStructure([
                'entities' => ['*' => ['id', 'name', 'type', 'type_label', 'group', 'start_year', 'end_year', 'date_label', 'summary', 'lng', 'lat', 'place', 'image_url', 'impact_score', 'verification_status', 'atlas_url']],
            ]);
    }

    public function test_limit_types_and_year_narrow_the_result(): void
    {
        foreach (range(1, 4) as $i) {
            $this->placed("Plugh Town {$i}", 1, 1, 100, 200, ['entity_type' => EntityType::City->value]);
        }
        $this->placed('Plugh Battle', 1, 1, 100, 200, ['entity_type' => EntityType::EventBattle->value]);
        $this->placed('Plugh Later', 1, 1, 900, 950, ['entity_type' => EntityType::City->value]);

        AtlasServer::tool(SearchAtlas::class, ['query' => 'Plugh', 'limit' => 2])
            ->assertStructuredContentCount(2, 'entities')
            ->assertStructuredContentPath('total_entities', 6);

        AtlasServer::tool(SearchAtlas::class, ['query' => 'Plugh', 'types' => ['event_battle']])
            ->assertStructuredContentPath('total_entities', 1)
            ->assertStructuredContentPath('entities.0.type', 'event_battle')
            ->assertStructuredContentPath('entities.0.type_label', 'Battle');

        AtlasServer::tool(SearchAtlas::class, ['query' => 'Plugh', 'year' => 920])
            ->assertStructuredContentPath('total_entities', 1)
            ->assertStructuredContentPath('entities.0.name', 'Plugh Later');
    }

    public function test_long_summaries_are_cut_at_a_word(): void
    {
        $this->entity('Wordy Place', null, ['summary' => str_repeat('alpha beta gamma ', 60)]);

        $summary = AtlasServer::tool(SearchAtlas::class, ['query' => 'Wordy Place']);
        $summary->assertStructuredContent(fn ($json) => $json
            ->where('entities.0.summary', fn (string $s): bool => mb_strlen($s) <= 300 && str_ends_with($s, '…') && ! str_contains($s, 'gamm…'))
            ->etc());
    }

    public function test_archived_chronicles_are_hidden(): void
    {
        $this->chronicle('Hidden Fnord Saga', [], ['status' => 'archived']);
        $this->chronicle('Shown Fnord Saga');

        AtlasServer::tool(SearchAtlas::class, ['query' => 'Fnord'])
            ->assertStructuredContentCount(1, 'chronicles')
            ->assertStructuredContentPath('chronicles.0.slug', 'shown-fnord-saga');
    }

    public function test_no_matches_is_an_empty_list_not_an_error(): void
    {
        AtlasServer::tool(SearchAtlas::class, ['query' => 'Nothingatallhere'])
            ->assertOk()
            ->assertStructuredContentPath('total_entities', 0)
            ->assertStructuredContentCount(0, 'entities');
    }

    public function test_validation_errors(): void
    {
        AtlasServer::tool(SearchAtlas::class, [])->assertHasErrors();
        AtlasServer::tool(SearchAtlas::class, ['query' => 'a'])->assertHasErrors();
        AtlasServer::tool(SearchAtlas::class, ['query' => 'Rome', 'limit' => 21])->assertHasErrors();
        AtlasServer::tool(SearchAtlas::class, ['query' => 'Rome', 'types' => ['dragon']])->assertHasErrors();
        AtlasServer::tool(SearchAtlas::class, ['query' => 'Rome', 'year' => 0])->assertHasErrors();
    }
}
