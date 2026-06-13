<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Requests;

use App\Enums\ConfidenceLevel;
use App\Enums\EntityGroup;
use App\Enums\EntityType;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

/**
 * Validates query parameters for the map endpoint.
 *
 * GET /api/v1/entities/map?bbox_min_lng=...&temporal_start=...
 */
class MapEntitiesRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    /**
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            // Bounding box is required for map queries
            'bbox_min_lng' => ['required', 'numeric', 'between:-180,180'],
            'bbox_min_lat' => ['required', 'numeric', 'between:-90,90'],
            'bbox_max_lng' => ['required', 'numeric', 'between:-180,180'],
            'bbox_max_lat' => ['required', 'numeric', 'between:-90,90'],
            'year' => ['sometimes', 'integer'],

            // Temporal filter (integer year, negative for BCE)
            'temporal_start' => ['sometimes', 'integer'],
            'temporal_end' => ['sometimes', 'integer'],

            // Optional type/group filter
            'type' => ['sometimes', 'string', Rule::enum(EntityType::class)],
            'types' => ['sometimes', 'array', 'max:30'],
            'types.*' => ['string', Rule::enum(EntityType::class)],
            'group' => ['sometimes', 'string', Rule::enum(EntityGroup::class)],
            'groups' => ['sometimes', 'array', 'max:5'],
            'groups.*' => ['string', Rule::enum(EntityGroup::class)],
            'min_confidence' => ['sometimes', 'string', Rule::enum(ConfidenceLevel::class)],

            // Zoom-level based impact threshold
            // Either provide zoom_level (0–22) and the API derives the threshold,
            // or supply min_impact directly to override it.
            'zoom_level' => ['sometimes', 'integer', 'min:0', 'max:22'],
            'min_impact' => ['sometimes', 'nullable', 'integer', 'min:0', 'max:100'],
            'include_territories' => ['sometimes', 'boolean'],

            // Max features to return (prevent overload)
            'limit' => ['sometimes', 'integer', 'min:1', 'max:5000'],
        ];
    }
}
