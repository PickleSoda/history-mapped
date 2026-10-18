<?php

declare(strict_types=1);

namespace Tests\Feature\Admin;

use App\Enums\EntityType;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

/**
 * The admin entity form edits only flat, type-specific attributes; saving it
 * must not drop or mangle the rest of the attributes JSONB.
 */
class EntityFormAttributesTest extends TestCase
{
    use RefreshDatabase;

    /** @param  array<string, mixed>  $attributes */
    private function person(array $attributes): Entity
    {
        $entity = Entity::factory()->ofType(EntityType::Person)->create();
        DB::table('entities')->where('entity_id', $entity->entity_id)->update(['attributes' => json_encode($attributes)]);

        return $entity->refresh();
    }

    /** @return array<string, mixed> */
    private function stored(Entity $entity): array
    {
        return json_decode((string) DB::table('entities')->where('entity_id', $entity->entity_id)->value('attributes'), true);
    }

    public function test_form_save_keeps_attributes_it_does_not_edit(): void
    {
        $this->actingAs($this->userWithRole('admin'));
        $entity = $this->person([
            'gender' => 'female',
            'ethnicity' => 'Greek',
            'population' => 5000,
            'is_regent' => true,
            'validation_flags' => ['implausible_lifespan'],
            '_backfill_runs' => [['at' => '2026-10-01', 'tables' => ['aliases']]],
            '_rejected_wikidata_id' => 'Q42',
            'confidence_notes' => 'from one source',
            'media_refs' => [['type' => 'image', 'url' => 'https://x.example/a.jpg']],
        ]);

        // What the edit page sends: its text fields (all values as strings,
        // a cleared field as null) plus whatever an older client mangled.
        $this->put(route('entities.update', $entity), [
            'name' => $entity->name,
            'confidence_notes' => null,
            'attributes' => [
                'gender' => 'male',
                'ethnicity' => null,
                'population' => '5000',
                'is_regent' => 'true',
                'validation_flags' => 'implausible_lifespan',
                '_backfill_runs' => '[object Object]',
                '_rejected_wikidata_id' => 'Q42',
            ],
        ])->assertRedirect()->assertSessionHasNoErrors();

        $attributes = $this->stored($entity);
        $this->assertSame('male', $attributes['gender']);
        $this->assertArrayNotHasKey('ethnicity', $attributes, 'a cleared field is removed');
        $this->assertSame(5000, $attributes['population'], 'an unchanged number keeps its type');
        $this->assertTrue($attributes['is_regent']);
        $this->assertSame(['implausible_lifespan'], $attributes['validation_flags']);
        $this->assertSame([['at' => '2026-10-01', 'tables' => ['aliases']]], $attributes['_backfill_runs']);
        $this->assertSame('Q42', $attributes['_rejected_wikidata_id']);
        $this->assertArrayNotHasKey('confidence_notes', $attributes, 'a cleared top-level note is removed');
        $this->assertEquals([['type' => 'image', 'url' => 'https://x.example/a.jpg']], $attributes['media_refs']);
    }

    public function test_form_save_without_attribute_fields_changes_none(): void
    {
        $this->actingAs($this->userWithRole('admin'));
        $entity = $this->person(['validation_flags' => ['x'], 'gender' => 'female']);

        $this->put(route('entities.update', $entity), ['name' => 'Renamed'])->assertRedirect();

        $this->assertEquals(['validation_flags' => ['x'], 'gender' => 'female'], $this->stored($entity));
        $this->assertSame('Renamed', $entity->fresh()->name);
    }
}
