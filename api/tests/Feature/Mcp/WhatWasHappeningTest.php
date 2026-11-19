<?php

declare(strict_types=1);

namespace Tests\Feature\Mcp;

use App\Actions\Tag\SyncTagsAction;
use App\Enums\EntityType;
use App\Enums\TagSource;
use App\Mcp\Servers\AtlasServer;
use App\Mcp\Tools\WhatWasHappening;

class WhatWasHappeningTest extends McpTestCase
{
    public function test_lists_mapped_entities_that_existed_at_the_year_by_impact(): void
    {
        $this->placed('Minor Realm', 10, 45, 1400, 1600, ['impact_score' => 10]);
        $major = $this->placed('Major Realm', 20, 50, 1400, 1600, ['impact_score' => 90]);
        $this->placed('Too Early', 10, 45, 100, 200, ['impact_score' => 99]);
        $this->placed('Too Late', 10, 45, 1700, 1800, ['impact_score' => 99]);
        $this->entity('No Point', null, ['impact_score' => 99]);

        AtlasServer::tool(WhatWasHappening::class, ['year' => 1500])
            ->assertOk()
            ->assertStructuredContentPath('year', 1500)
            ->assertStructuredContentPath('bbox', null)
            ->assertStructuredContentPath('region', null)
            ->assertStructuredContentPath('types', null)
            ->assertStructuredContentPath('total', 2)
            ->assertStructuredContentPath('total_capped', false)
            ->assertStructuredContentPath('entities.0.id', $major->entity_id)
            ->assertStructuredContentPath('entities.1.name', 'Minor Realm')
            ->assertStructuredContentPath('atlas_url', 'https://atlas.test/app?t=1500');
    }

    public function test_bc_years_work_and_year_zero_is_refused(): void
    {
        $this->placed('Old Kingdom', 31, 30, -2600, -2100);

        AtlasServer::tool(WhatWasHappening::class, ['year' => -2300])
            ->assertStructuredContentPath('total', 1)
            ->assertStructuredContentPath('entities.0.date_label', '2600 BC–2100 BC')
            ->assertStructuredContentPath('atlas_url', 'https://atlas.test/app?t=-2300');

        AtlasServer::tool(WhatWasHappening::class, ['year' => 0])->assertHasErrors();
    }

    public function test_bbox_filters_and_is_echoed(): void
    {
        $this->placed('Inside Bbox', 10.5, 40.5, 1400, 1600);
        $this->placed('Outside Bbox', 100, -20, 1400, 1600);

        AtlasServer::tool(WhatWasHappening::class, ['year' => 1500, 'bbox' => [0, 30, 20, 50]])
            ->assertStructuredContentPath('total', 1)
            ->assertStructuredContentPath('entities.0.name', 'Inside Bbox')
            ->assertStructuredContentPath('bbox', [0, 30, 20, 50]);
    }

    public function test_region_filters_by_tag_and_is_echoed(): void
    {
        $this->seedTags();
        $paris = $this->placed('Paris Test', 2.3, 48.8, 1400, 1600);
        $this->placed('Nara Test', 135.8, 34.7, 1400, 1600);
        app(SyncTagsAction::class)($paris, ['western-europe'], TagSource::Manual);

        AtlasServer::tool(WhatWasHappening::class, ['year' => 1500, 'region' => 'western-europe'])
            ->assertStructuredContentPath('total', 1)
            ->assertStructuredContentPath('entities.0.id', $paris->entity_id)
            ->assertStructuredContentPath('region', 'western-europe');
    }

    public function test_types_and_limit(): void
    {
        foreach (range(1, 3) as $i) {
            $this->placed("Town {$i}", 1, 1, 1400, 1600, ['entity_type' => EntityType::City->value]);
        }
        $this->placed('A Siege', 1, 1, 1500, 1500, ['entity_type' => EntityType::EventBattle->value]);

        AtlasServer::tool(WhatWasHappening::class, ['year' => 1500, 'limit' => 2])
            ->assertStructuredContentCount(2, 'entities')
            ->assertStructuredContentPath('total', 4);

        AtlasServer::tool(WhatWasHappening::class, ['year' => 1500, 'types' => ['event_battle']])
            ->assertStructuredContentPath('total', 1)
            ->assertStructuredContentPath('types', ['event_battle']);
    }

    public function test_an_empty_year_is_an_empty_list(): void
    {
        AtlasServer::tool(WhatWasHappening::class, ['year' => 1500])
            ->assertOk()
            ->assertStructuredContentPath('total', 0)
            ->assertStructuredContentCount(0, 'entities')
            ->assertSee('Nothing');
    }

    public function test_validation_errors(): void
    {
        $this->seedTags();

        AtlasServer::tool(WhatWasHappening::class, [])->assertHasErrors();
        AtlasServer::tool(WhatWasHappening::class, ['year' => 1500, 'limit' => 51])->assertHasErrors();
        AtlasServer::tool(WhatWasHappening::class, ['year' => 1500, 'bbox' => [0, 1, 2]])->assertHasErrors();
        AtlasServer::tool(WhatWasHappening::class, ['year' => 1500, 'bbox' => [20, 30, 0, 50]])->assertHasErrors();
        AtlasServer::tool(WhatWasHappening::class, ['year' => 1500, 'bbox' => [0, 30, 20, 95]])->assertHasErrors();
        AtlasServer::tool(WhatWasHappening::class, ['year' => 1500, 'bbox' => [0, 30, 20, 50], 'region' => 'western-europe'])->assertHasErrors();
        AtlasServer::tool(WhatWasHappening::class, ['year' => 1500, 'region' => 'atlantis'])->assertHasErrors(['Unknown region']);
        // A tag that exists but is not a region.
        AtlasServer::tool(WhatWasHappening::class, ['year' => 1500, 'region' => 'medieval'])->assertHasErrors();
    }
}
