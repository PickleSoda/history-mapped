<?php

declare(strict_types=1);

namespace Tests\Feature\Mcp;

use App\Enums\EntityType;
use App\Mcp\Servers\AtlasServer;
use App\Mcp\Tools\FindChronicles;
use App\Mcp\Tools\GetChronicle;

class ChronicleToolsTest extends McpTestCase
{
    public function test_find_by_query_returns_rows_with_tags_and_entry_counts(): void
    {
        $this->seedTags();
        $c = $this->chronicle('Tang China Rises', ['china', 'medieval'], ['start_year' => 618, 'end_year' => 907, 'description' => 'The Tang dynasty.']);
        $this->entry($c, 1, 'One.');
        $this->entry($c, 2, 'Two.');
        $this->chronicle('Something Else');

        AtlasServer::tool(FindChronicles::class, ['query' => 'Tang'])
            ->assertOk()
            ->assertStructuredContentCount(1, 'chronicles')
            ->assertStructuredContentPath('chronicles.0.slug', 'tang-china-rises')
            ->assertStructuredContentPath('chronicles.0.title', 'Tang China Rises')
            ->assertStructuredContentPath('chronicles.0.start_year', 618)
            ->assertStructuredContentPath('chronicles.0.end_year', 907)
            ->assertStructuredContentPath('chronicles.0.summary', 'The Tang dynasty.')
            ->assertStructuredContentPath('chronicles.0.entry_count', 2)
            ->assertStructuredContentPath('chronicles.0.atlas_url', 'https://atlas.test/chronicles/tang-china-rises')
            ->assertStructuredContent(fn ($json) => $json
                ->where('chronicles.0.tags', fn ($tags): bool => in_array('china', $tags->toArray(), true) && in_array('medieval', $tags->toArray(), true))
                ->etc());
    }

    public function test_find_by_tags_and_limit(): void
    {
        $this->seedTags();
        foreach (range(1, 3) as $i) {
            $this->chronicle("Eastern Tale {$i}", ['china']);
        }
        $this->chronicle('Western Tale', ['france']);

        AtlasServer::tool(FindChronicles::class, ['tags' => ['china']])->assertStructuredContentCount(3, 'chronicles');
        AtlasServer::tool(FindChronicles::class, ['tags' => ['china'], 'limit' => 2])->assertStructuredContentCount(2, 'chronicles');
        AtlasServer::tool(FindChronicles::class, ['tags' => ['no-such-tag']])->assertOk()->assertStructuredContentCount(0, 'chronicles');
    }

    public function test_find_hides_archived_and_validates(): void
    {
        $this->chronicle('Retired Saga', [], ['status' => 'archived']);

        AtlasServer::tool(FindChronicles::class, ['query' => 'Retired'])->assertStructuredContentCount(0, 'chronicles');
        AtlasServer::tool(FindChronicles::class, [])->assertHasErrors(['Give a query, tags, or both.']);
        AtlasServer::tool(FindChronicles::class, ['query' => 'x'])->assertHasErrors();
        AtlasServer::tool(FindChronicles::class, ['query' => 'Saga', 'limit' => 21])->assertHasErrors();
    }

    public function test_get_chronicle_returns_ordered_entries_with_entity_and_place(): void
    {
        $this->seedTags();
        $c = $this->chronicle('Rubicon Tale', ['rome'], ['start_year' => -49, 'end_year' => -44, 'description' => 'Caesar crosses.']);
        $caesar = $this->entity('Caesar Test', EntityType::Person);
        $this->entry($c, 2, 'Caesar is killed. The Senate panics.', [], ['start_year' => -44, 'end_year' => -44]);
        $this->entry($c, 1, 'Caesar crosses the Rubicon. Civil war begins.', [$caesar], [
            'start_year' => -49,
            'end_year' => -49,
            'approximate_location' => ['lat' => 44.1, 'lon' => 12.4],
        ]);

        AtlasServer::tool(GetChronicle::class, ['slug' => 'rubicon-tale'])
            ->assertOk()
            ->assertStructuredContentPath('chronicle.slug', 'rubicon-tale')
            ->assertStructuredContentPath('chronicle.summary', 'Caesar crosses.')
            ->assertStructuredContentPath('chronicle.start_year', -49)
            ->assertStructuredContentPath('chronicle.tags', ['rome'])
            ->assertStructuredContentPath('chronicle.atlas_url', 'https://atlas.test/chronicles/rubicon-tale')
            ->assertStructuredContentCount(2, 'entries')
            ->assertStructuredContentPath('entries.0.sequence', 1)
            ->assertStructuredContentPath('entries.0.title', 'Caesar crosses the Rubicon')
            ->assertStructuredContentPath('entries.0.date_label', '49 BC')
            ->assertStructuredContentPath('entries.0.text', 'Caesar crosses the Rubicon. Civil war begins.')
            ->assertStructuredContentPath('entries.0.entity.id', $caesar->entity_id)
            ->assertStructuredContentPath('entries.0.entity.atlas_url', 'https://atlas.test/entities/'.$caesar->entity_id)
            ->assertStructuredContentPath('entries.0.lng', 12.4)
            ->assertStructuredContentPath('entries.0.lat', 44.1)
            ->assertStructuredContentPath('entries.1.sequence', 2)
            ->assertStructuredContentPath('entries.1.entity', null)
            ->assertStructuredContentPath('entries.1.lng', null);
    }

    public function test_a_step_is_headed_by_its_event_not_by_its_own_words(): void
    {
        $c = $this->chronicle('Norman Tale');
        $battle = $this->entity('Battle of Hastings', EntityType::EventBattle, ['impact_score' => 92]);
        $harold = $this->entity('Harold Godwinson', EntityType::Person);
        $this->entry($c, 1, 'In 1066 William of Normandy defeated Harold at Senlac Hill, near Hastings.', [$harold, $battle], ['start_year' => 1066, 'end_year' => 1066]);
        $this->entry($c, 2, 'William was crowned at Westminster, and the Conquest began, with castles.', [$harold]);

        AtlasServer::tool(GetChronicle::class, ['slug' => 'norman-tale'])
            ->assertStructuredContentPath('entries.0.title', 'Battle of Hastings')
            ->assertStructuredContentPath('entries.0.text', 'In 1066 William of Normandy defeated Harold at Senlac Hill, near Hastings.')
            ->assertStructuredContentPath('entries.1.title', 'William was crowned at Westminster');
    }

    public function test_entries_are_capped_at_sixty_and_the_text_says_so(): void
    {
        $c = $this->chronicle('Long Saga');
        foreach (range(1, 65) as $i) {
            $this->entry($c, $i, str_repeat('word ', 200));
        }

        AtlasServer::tool(GetChronicle::class, ['slug' => 'long-saga'])
            ->assertStructuredContentCount(60, 'entries')
            ->assertStructuredContentPath('entries.59.sequence', 60)
            ->assertStructuredContent(fn ($json) => $json
                ->where('entries.0.text', fn (string $t): bool => mb_strlen($t) <= 600)
                ->etc())
            ->assertSee('capped at the first 60 of 65 steps');
    }

    public function test_get_chronicle_unknown_or_archived_slug_is_an_error(): void
    {
        $this->chronicle('Retired Saga', [], ['status' => 'archived']);

        AtlasServer::tool(GetChronicle::class, ['slug' => 'retired-saga'])->assertHasErrors(['find_chronicles']);
        AtlasServer::tool(GetChronicle::class, ['slug' => 'nope'])->assertHasErrors(['find_chronicles']);
        AtlasServer::tool(GetChronicle::class, [])->assertHasErrors();
    }
}
