<?php

declare(strict_types=1);

namespace App\Http\Requests\Admin;

use App\Enums\ConfidenceLevel;
use App\Enums\DateResolutionMethod;
use App\Enums\DurationType;
use App\Enums\EntityGroup;
use App\Enums\EntityType;
use App\Enums\IconClass;
use App\Enums\LocationResolutionMethod;
use App\Enums\VerificationStatus;
use App\Http\Requests\Admin\Concerns\ValidatesEntityAttributes;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

/**
 * Validates entity update from the Inertia admin form.
 *
 * PUT /entities/{entity}
 *
 * Same rules as StoreEntityRequest; name/type/group are optional for partial saves.
 */
class UpdateEntityRequest extends FormRequest
{
    use ValidatesEntityAttributes;

    public function authorize(): bool
    {
        $user = $this->user();

        if ($user === null) {
            return false;
        }

        // Promoting/changing an entity's verification status is a sensitive action
        // that requires the dedicated `entities.verify` permission, on top of the
        // `entities.write` permission already enforced by the route. Normal edits
        // that leave the status unchanged are unaffected.
        if ($this->isChangingVerificationStatus() && ! $user->can('entities.verify')) {
            return false;
        }

        return true;
    }

    /**
     * Whether this request changes the entity's verification status from its
     * current persisted value.
     */
    protected function isChangingVerificationStatus(): bool
    {
        if (! $this->has('verification_status')) {
            return false;
        }

        $entity = $this->route('entity');
        $current = is_object($entity) ? ($entity->verification_status ?? null) : null;
        $current = $current instanceof \BackedEnum ? $current->value : $current;

        return $this->input('verification_status') !== $current;
    }

    /**
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            // Identity
            'name' => ['sometimes', 'string', 'max:500'],
            'entity_type' => ['sometimes', 'string', Rule::enum(EntityType::class)],
            'entity_group' => ['sometimes', 'string', Rule::enum(EntityGroup::class)],

            // Content
            'summary' => ['sometimes', 'nullable', 'string', 'max:5000'],
            'significance' => ['sometimes', 'nullable', 'string', 'max:5000'],
            'tags' => ['sometimes', 'nullable', 'array'],
            'tags.*' => ['string', 'max:100'],
            'alternative_names' => ['sometimes', 'nullable', 'array'],
            'alternative_names.*' => ['string', 'max:500'],
            'impact_score' => ['sometimes', 'nullable', 'numeric', 'between:0,100'],
            'wikidata_id' => ['sometimes', 'nullable', 'string', 'regex:/^Q\d+$/'],

            // Temporal
            'temporal_start' => ['sometimes', 'nullable', 'string', 'max:50'],
            'temporal_end' => ['sometimes', 'nullable', 'string', 'max:50'],
            'date_raw' => ['sometimes', 'nullable', 'string', 'max:255'],
            'date_method' => ['sometimes', 'nullable', 'string', Rule::enum(DateResolutionMethod::class)],
            'date_confidence' => ['sometimes', 'nullable', 'string', Rule::enum(ConfidenceLevel::class)],
            'duration_type' => ['sometimes', 'nullable', 'string', Rule::enum(DurationType::class)],

            // Spatial
            'location_name' => ['sometimes', 'nullable', 'string', 'max:500'],
            'location_confidence' => ['sometimes', 'nullable', 'string', Rule::enum(ConfidenceLevel::class)],
            'location_method' => ['sometimes', 'nullable', 'string', Rule::enum(LocationResolutionMethod::class)],
            'geojson' => ['sometimes', 'nullable', 'array'],
            'geojson.type' => ['required_with:geojson', 'string', Rule::in(['Point', 'MultiPoint', 'LineString', 'MultiLineString', 'Polygon', 'MultiPolygon'])],
            'geojson.coordinates' => ['required_with:geojson', 'array'],
            'territory_geojson' => ['sometimes', 'nullable', 'array'],
            'territory_geojson.type' => ['required_with:territory_geojson', 'string', Rule::in(['Polygon', 'MultiPolygon'])],
            'territory_geojson.coordinates' => ['required_with:territory_geojson', 'array'],

            // Verification
            'verification_status' => ['sometimes', 'nullable', 'string', Rule::enum(VerificationStatus::class)],
            'confidence' => ['sometimes', 'nullable', 'string', Rule::enum(ConfidenceLevel::class)],
            'confidence_notes' => ['sometimes', 'nullable', 'string', 'max:2000'],

            // Display
            'display_priority' => ['sometimes', 'nullable', 'integer', 'between:0,100'],
            'icon_class' => ['sometimes', 'nullable', 'string', Rule::enum(IconClass::class)],
            'entity_color' => ['sometimes', 'nullable', 'string', 'regex:/^#[0-9a-fA-F]{6}$/'],

            // Type-specific attributes (free-form JSONB)
            'attributes' => ['sometimes', 'nullable', 'array'],

            // Per-type scalar attribute validation
            ...$this->attributeRules(),
        ];
    }
}
