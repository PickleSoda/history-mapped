<?php

namespace Tests\Feature\Ai;

use App\Enums\EntityType;
use App\Http\Requests\Admin\UpdateEntityRequest;
use App\Support\EntityAttributeCatalog;
use Illuminate\Support\Facades\Validator;
use Illuminate\Support\Str;
use Tests\TestCase;

/**
 * The catalog the AI editor reads must stay in step with the admin form's
 * validation (ValidatesEntityAttributes): every validated attribute is in it,
 * and every value it offers passes validation for its type.
 */
class EntityAttributeCatalogTest extends TestCase
{
    /** @return array<string, mixed> */
    private function rulesFor(EntityType $type): array
    {
        return UpdateEntityRequest::create('/', 'PUT', ['entity_type' => $type->value])->rules();
    }

    public function test_every_validated_attribute_is_in_the_catalog(): void
    {
        $validated = collect(array_keys($this->rulesFor(EntityType::PoliticalEntity)))
            ->filter(fn (string $key) => Str::startsWith($key, 'attributes.'))
            ->map(fn (string $key) => Str::after($key, 'attributes.'))
            ->values()
            ->all();

        $this->assertNotEmpty($validated);
        $this->assertSame([], array_values(array_diff($validated, EntityAttributeCatalog::allKeys())));
    }

    public function test_every_offered_value_passes_validation_for_its_type(): void
    {
        foreach (EntityType::cases() as $type) {
            $rules = $this->rulesFor($type);

            foreach (EntityAttributeCatalog::fieldsFor($type) as $key => $field) {
                $samples = match ($field['kind']) {
                    'choice' => $field['values'],
                    'number' => [42],
                    'boolean' => [true],
                    default => ['Some text'],
                };

                foreach ($samples as $value) {
                    $validator = Validator::make(['attributes' => [$key => $value]], ["attributes.{$key}" => $rules["attributes.{$key}"] ?? []]);
                    $this->assertFalse($validator->fails(), "{$type->value}.{$key} = ".json_encode($value).' fails: '.implode(' ', $validator->errors()->all()));
                }
            }
        }
    }

    public function test_every_type_with_a_form_section_has_fields(): void
    {
        $this->assertSame(30, count(array_filter(EntityType::cases(), fn (EntityType $t) => EntityAttributeCatalog::fieldsFor($t) !== [])));
        $this->assertNull(EntityAttributeCatalog::problem(EntityType::Person, 'gender', null), 'null always clears a known key');
        $this->assertNotNull(EntityAttributeCatalog::problem(EntityType::Person, 'political_subtype', 'empire'));
    }
}
