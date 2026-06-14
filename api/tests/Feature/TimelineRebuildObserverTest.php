<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Enums\ConfidenceLevel;
use App\Enums\RelationshipType;
use App\Jobs\RebuildEntityTimelineJob;
use App\Models\Entity;
use App\Models\EntityLocation;
use App\Models\EntityRelationship;
use App\Support\TimelineRebuild;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Bus;
use Tests\TestCase;

class TimelineRebuildObserverTest extends TestCase
{
    use RefreshDatabase;

    public function test_saving_relationship_rebuilds_both_endpoints(): void
    {
        Bus::fake();

        $source = Entity::factory()->verified()->create();
        $target = Entity::factory()->verified()->create();

        EntityRelationship::create([
            'source_entity_id' => $source->entity_id,
            'target_entity_id' => $target->entity_id,
            'relationship_type' => RelationshipType::Contains,
            'confidence' => ConfidenceLevel::High,
        ]);

        Bus::assertDispatched(
            RebuildEntityTimelineJob::class,
            fn (RebuildEntityTimelineJob $job): bool => $job->entityId === $source->entity_id,
        );
        Bus::assertDispatched(
            RebuildEntityTimelineJob::class,
            fn (RebuildEntityTimelineJob $job): bool => $job->entityId === $target->entity_id,
        );
    }

    public function test_saving_location_rebuilds_entity_timeline(): void
    {
        Bus::fake();

        $entity = Entity::factory()->verified()->create();

        EntityLocation::create([
            'entity_id' => $entity->entity_id,
            'location_name' => 'Test place',
        ]);

        Bus::assertDispatched(
            RebuildEntityTimelineJob::class,
            fn (RebuildEntityTimelineJob $job): bool => $job->entityId === $entity->entity_id,
        );
    }

    public function test_bulk_import_collapses_to_one_rebuild_per_entity(): void
    {
        Bus::fake();

        $a = Entity::factory()->verified()->create();
        $b = Entity::factory()->verified()->create();

        TimelineRebuild::withoutRebuilds(function () use ($a, $b): void {
            // Many writes touching the same two entities during an "import".
            TimelineRebuild::queue($a->entity_id);
            TimelineRebuild::queue($a->entity_id);
            TimelineRebuild::queue($a->entity_id);
            TimelineRebuild::queue($b->entity_id);
            TimelineRebuild::queue($b->entity_id);

            // Nothing dispatched while suppressed.
            Bus::assertNotDispatched(RebuildEntityTimelineJob::class);
        });

        // Exactly one rebuild per affected entity after the import block.
        Bus::assertDispatchedTimes(RebuildEntityTimelineJob::class, 2);
    }
}
