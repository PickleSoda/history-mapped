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
 * Validates entity creation from the Inertia admin form.
 *
 * POST /entities
 */
class StoreEntityRequest extends FormRequest
{
    use ValidatesEntityAttributes;
    public function authorize(): bool
    {
        return $this->user() !== null;
    }

    /**
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            // Identity
            'name' => ['required', 'string', 'max:500'],
            'entity_type' => ['required', 'string', Rule::enum(EntityType::class)],
            'entity_group' => ['required', 'string', Rule::enum(EntityGroup::class)],

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

            // Hierarchy
            'parent_entity_id' => ['sometimes', 'nullable', 'uuid', 'exists:entities,entity_id'],
            'successor_entity_id' => ['sometimes', 'nullable', 'uuid', 'exists:entities,entity_id'],

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
