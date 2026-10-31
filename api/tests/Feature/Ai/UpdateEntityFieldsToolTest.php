<?php

namespace Tests\Feature\Ai;

use App\Actions\Tag\SyncTagsAction;
use App\Ai\Tools\UpdateEntityFields;
use App\Enums\ConfidenceLevel;
use App\Enums\DateResolutionMethod;
use App\Enums\DurationType;
use App\Enums\EntityType;
use App\Enums\TagSource;
use App\Enums\VerificationStatus;
use App\Models\Entity;
use App\Models\EntityAlias;
use App\Models\EntityTemporalRange;
use App\Support\EntityAttributeCatalog;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Laravel\Ai\Tools\Request;
use Symfony\Component\HttpKernel\Exception\AccessDeniedHttpException;
use Tests\TestCase;

class UpdateEntityFieldsToolTest extends TestCase
{
    use RefreshDatabase;

    public function test_build_parts_diffs_only_provided_fields(): void
    {
        $entity = Entity::factory()->create([
            'name' => 'Byzantine Empire',
            'summary' => 'Old summary',
        ]);

        $tool = app(UpdateEntityFields::class);
        $parts = $tool->buildParts([
            'entity_id' => $entity->entity_id,
            'summary' => 'New summary',
        ]);

        $this->assertCount(1, $parts);
        $this->assertSame('update_entity_fields', $parts[0]['tool']);
        $this->assertArrayHasKey('summary', $parts[0]['human_diff']['diff']);
        $this->assertArrayNotHasKey('name', $parts[0]['human_diff']['diff']);
        $this->assertSame('Old summary', $parts[0]['human_diff']['diff']['summary']['from']);
        $this->assertSame('New summary', $parts[0]['human_diff']['diff']['summary']['to']);
    }

    public function test_apply_part_updates_summary_and_preserves_other_fields(): void
    {
        $entity = Entity::factory()->create([
            'name' => 'Byzantine Empire',
            'summary' => 'Old summary',
            'significance' => 'Very significant',
        ]);

        $tool = app(UpdateEntityFields::class);
        $result = $tool->applyPart([
            'entity_id' => $entity->entity_id,
            'summary' => 'Updated summary',
        ], ['user_id' => 'u1']);

        $this->assertSame($entity->entity_id, $result['result_id']);
        $this->assertSame('Fields updated', $result['summary']);

        $entity->refresh();
        $this->assertSame('Updated summary', $entity->summary);
        // Other fields preserved
        $this->assertSame('Byzantine Empire', $entity->name);
        $this->assertSame('Very significant', $entity->significance);
    }

    public function test_apply_part_updates_name(): void
    {
        $entity = Entity::factory()->create(['name' => 'Old Name']);

        $tool = app(UpdateEntityFields::class);
        $tool->applyPart([
            'entity_id' => $entity->entity_id,
            'name' => 'New Name',
        ], ['user_id' => 'u1']);

        $entity->refresh();
        $this->assertSame('New Name', $entity->name);
    }

    public function test_apply_part_preserves_end_date_when_only_start_year_supplied(): void
    {
        $entity = Entity::factory()->create();
        EntityTemporalRange::query()->create([
            'entity_id' => $entity->entity_id,
            'range_type' => 'primary',
            'is_primary' => true,
            'start_date' => '-100',
            'end_date' => '50',
        ]);

        $tool = app(UpdateEntityFields::class);
        $tool->applyPart([
            'entity_id' => $entity->entity_id,
            'start_year' => -90,
        ], ['user_id' => 'u1']);

        $entity->load('primaryTemporalRange');
        $temporal = $entity->primaryTemporalRange;
        $this->assertNotNull($temporal, 'Primary temporal range should exist');
        $this->assertSame('-90', $temporal->start_date, 'start_date should be updated to -90');
        $this->assertSame('50', $temporal->end_date, 'end_date should be preserved at 50');
    }

    public function test_apply_part_preserves_start_date_when_only_end_year_supplied(): void
    {
        $entity = Entity::factory()->create();
        EntityTemporalRange::query()->create([
            'entity_id' => $entity->entity_id,
            'range_type' => 'primary',
            'is_primary' => true,
            'start_date' => '-100',
            'end_date' => '50',
        ]);

        $tool = app(UpdateEntityFields::class);
        $tool->applyPart([
            'entity_id' => $entity->entity_id,
            'end_year' => 75,
        ], ['user_id' => 'u1']);

        $entity->load('primaryTemporalRange');
        $temporal = $entity->primaryTemporalRange;
        $this->assertNotNull($temporal, 'Primary temporal range should exist');
        $this->assertSame('-100', $temporal->start_date, 'start_date should be preserved at -100');
        $this->assertSame('75', $temporal->end_date, 'end_date should be updated to 75');
    }

    /** Stage through buildParts, then apply the staged payload — the real flow. */
    private function proposeAndApply(array $args, ?string $userId = 'u1'): void
    {
        $tool = app(UpdateEntityFields::class);
        $parts = $tool->buildParts($args);
        $tool->applyPart($parts[0]['payload'], ['user_id' => $userId]);
    }

    public function test_edits_attributes_tags_and_aliases_without_dropping_the_rest(): void
    {
        $values = fn (string $key) => EntityAttributeCatalog::fieldsFor(EntityType::PoliticalEntity)[$key]['values'];
        $entity = Entity::factory()->ofType(EntityType::PoliticalEntity)->create([
            'attributes' => ['government_type' => $values('government_type')[0], 'review_flags' => ['geo']],
        ]);
        EntityAlias::query()->create(['entity_id' => $entity->entity_id, 'name' => 'Rome', 'is_primary' => true]);
        EntityAlias::query()->create(['entity_id' => $entity->entity_id, 'name' => 'Roma', 'is_primary' => false]);
        app(SyncTagsAction::class)($entity, ['antiquity', 'mediterranean'], TagSource::Manual);
        app(SyncTagsAction::class)($entity, ['derived-era'], TagSource::Derived);

        $this->proposeAndApply([
            'entity_id' => $entity->entity_id,
            'attributes' => ['political_subtype' => $values('political_subtype')[0]],
            'clear' => ['government_type'],
            'add_tags' => ['Roman'],
            'remove_tags' => ['antiquity'],
            'add_alternative_names' => ['Urbs'],
            'remove_alternative_names' => ['roma'],
        ]);

        $entity->refresh()->load('aliases', 'entityTags');
        $this->assertSame($values('political_subtype')[0], $entity->attributes['political_subtype']);
        $this->assertArrayNotHasKey('government_type', $entity->attributes);
        $this->assertSame(['geo'], $entity->attributes['review_flags'], 'attributes the edit did not name are kept');

        $manual = $entity->entityTags->where('source', TagSource::Manual->value)->pluck('tag')->sort()->values()->all();
        $this->assertSame(['mediterranean', 'roman'], array_map('strtolower', $manual));
        $this->assertContains('derived-era', $entity->entityTags->pluck('tag')->all(), 'derived tags are untouched');

        $aliases = $entity->aliases->pluck('is_primary', 'name')->all();
        $this->assertEqualsCanonicalizing(['Rome', 'Urbs'], array_keys($aliases));
        $this->assertTrue((bool) $aliases['Rome'], 'a kept alias keeps its primary flag');
    }

    public function test_a_date_edit_keeps_how_the_dates_were_resolved(): void
    {
        // Only the temporal row knows how the dates were resolved.
        $entity = Entity::factory()->create(['duration_type' => null, 'date_method' => null, 'date_confidence' => null]);
        EntityTemporalRange::query()->create([
            'entity_id' => $entity->entity_id,
            'range_type' => 'primary',
            'is_primary' => true,
            'start_date' => '-100',
            'end_date' => '50',
            'duration_type' => DurationType::Period,
            'date_method' => DateResolutionMethod::SourceDatabase,
            'date_confidence' => ConfidenceLevel::High,
        ]);

        $this->proposeAndApply(['entity_id' => $entity->entity_id, 'start_year' => -90]);

        $temporal = $entity->load('primaryTemporalRange')->primaryTemporalRange;
        $this->assertSame('-90', $temporal->start_date);
        $this->assertSame(DurationType::Period, $temporal->duration_type);
        $this->assertSame(DateResolutionMethod::SourceDatabase, $temporal->date_method);
        $this->assertSame(ConfidenceLevel::High, $temporal->date_confidence);
    }

    public function test_clear_empties_fields_and_a_date_bound(): void
    {
        $entity = Entity::factory()->create(['significance' => 'Big', 'impact_score' => 70]);
        EntityTemporalRange::query()->create([
            'entity_id' => $entity->entity_id, 'range_type' => 'primary', 'is_primary' => true,
            'start_date' => '1200', 'end_date' => '1300',
        ]);

        $this->proposeAndApply(['entity_id' => $entity->entity_id, 'clear' => ['significance', 'impact_score', 'end_year']]);

        $entity->refresh()->load('primaryTemporalRange');
        $this->assertNull($entity->significance);
        $this->assertNull($entity->impact_score);
        $this->assertSame('1200', $entity->primaryTemporalRange->start_date);
        $this->assertNull($entity->primaryTemporalRange->end_date);
    }

    public function test_sets_scalar_fields_the_form_has(): void
    {
        $entity = Entity::factory()->create();

        $this->proposeAndApply([
            'entity_id' => $entity->entity_id,
            'impact_score' => 85,
            'display_priority' => 60,
            'confidence' => 'medium',
            'icon_class' => 'crown',
            'entity_color' => '#aa3300',
            'date_raw' => 'c. 1200 BCE',
        ]);

        $entity->refresh();
        $this->assertEquals(85, $entity->impact_score);
        $this->assertSame(60, $entity->display_priority);
        $this->assertSame('medium', $entity->confidence->value);
        $this->assertSame('crown', $entity->icon_class->value);
        $this->assertSame('#aa3300', $entity->attributes['entity_color']);
        $this->assertSame('c. 1200 BCE', $entity->attributes['date_raw']);
    }

    public function test_tells_the_model_what_is_wrong_with_an_argument(): void
    {
        $entity = Entity::factory()->ofType(EntityType::PoliticalEntity)->create();
        $tool = app(UpdateEntityFields::class)->withContext([
            'user_id' => 'u1', 'context_type' => 'entity', 'context_id' => $entity->entity_id,
        ]);

        $unknown = json_decode($tool->handle(new Request([
            'entity_id' => $entity->entity_id, 'attributes' => ['birth_date' => '1200'],
        ])), true);
        $this->assertStringContainsString("'birth_date' is not an attribute of political_entity", $unknown['error']);
        $this->assertStringContainsString('political_subtype', $unknown['error']);

        $badChoice = json_decode($tool->handle(new Request([
            'entity_id' => $entity->entity_id, 'attributes' => ['political_subtype' => 'galactic_federation'],
        ])), true);
        $this->assertStringContainsString('must be one of', $badChoice['error']);

        $badColor = json_decode($tool->handle(new Request([
            'entity_id' => $entity->entity_id, 'entity_color' => 'red',
        ])), true);
        $this->assertStringContainsString('Invalid value', $badColor['error']);
    }

    public function test_changing_verification_status_needs_the_verify_permission(): void
    {
        $entity = Entity::factory()->create(['verification_status' => VerificationStatus::PipelineDraft->value]);
        $args = ['entity_id' => $entity->entity_id, 'verification_status' => VerificationStatus::HumanVerified->value];

        try {
            $this->proposeAndApply($args, (string) $this->userWithRole('history_moderator')->id);
            $this->fail('A moderator without entities.verify must not change the status.');
        } catch (AccessDeniedHttpException) {
            $this->assertSame(VerificationStatus::PipelineDraft, $entity->refresh()->verification_status);
        }

        $this->proposeAndApply($args, (string) $this->userWithRole('admin')->id);
        $this->assertSame(VerificationStatus::HumanVerified, $entity->refresh()->verification_status);
    }
}
