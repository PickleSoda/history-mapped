<?php

declare(strict_types=1);

namespace Tests\Feature\Contribution;

use App\Actions\Contribution\DescribeContributionTargetsAction;
use App\Actions\Contribution\SubmitContributionAction;
use App\Enums\ContributionTargetType;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use App\Models\EntityRelationship;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Str;
use Tests\TestCase;

/** A contribution's `public_url` opens the record in the atlas, which lives at `/app` (the landing page is `/`). */
class ContributionAtlasLinksTest extends TestCase
{
    use RefreshDatabase;

    public function test_public_urls_point_into_the_atlas_at_app(): void
    {
        $user = $this->userWithRole('user');
        $submit = app(SubmitContributionAction::class);
        $entity = Entity::factory()->create(['summary' => 'Old.']);
        $target = Entity::factory()->create();
        $relationship = EntityRelationship::query()->create([
            'relationship_id' => (string) Str::uuid(),
            'source_entity_id' => $entity->entity_id,
            'target_entity_id' => $target->entity_id,
            'relationship_type' => 'allied_with',
            'description' => 'Old.',
        ]);
        $chronicle = Chronicle::factory()->create(['slug' => 'punic-wars', 'description' => 'Old.']);
        ChronicleEntry::factory()->create(['chronicle_id' => $chronicle->chronicle_id, 'sequence_order' => 1]);
        $second = ChronicleEntry::factory()->create(['chronicle_id' => $chronicle->chronicle_id, 'sequence_order' => 2, 'narrative_text' => 'Old.']);

        $contributions = [
            $submit($user, ContributionTargetType::Entity, $entity->entity_id, 'summary', 'New.'),
            $submit($user, ContributionTargetType::Relationship, $relationship->relationship_id, 'description', 'New.'),
            $submit($user, ContributionTargetType::Chronicle, $chronicle->chronicle_id, 'description', 'New.'),
            $submit($user, ContributionTargetType::ChronicleEntry, $second->entry_id, 'narrative_text', 'New.'),
        ];

        $described = app(DescribeContributionTargetsAction::class)($contributions);
        $url = fn (int $i): string => $described[DescribeContributionTargetsAction::key($contributions[$i])]['public_url'];
        $base = config('app.frontend_url');

        $this->assertSame("{$base}/app?sel={$entity->entity_id}&full=1", $url(0));
        $this->assertSame("{$base}/app?sel={$entity->entity_id}&full=1", $url(1));
        $this->assertSame("{$base}/app?chron=punic-wars&full=1", $url(2));
        $this->assertSame("{$base}/app?chron=punic-wars&step=1&full=1", $url(3), 'the second step is step 1 (0-based)');
    }
}
