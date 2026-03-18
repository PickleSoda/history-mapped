<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Requests;

use App\Enums\ConfidenceLevel;
use App\Enums\EntityGroup;
use App\Enums\EntityType;
use App\Enums\VerificationStatus;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

/**
 * Validates query parameters for the entity list/search endpoint.
 *
 * GET /api/v1/entities?search=rome&group=POLITY&bbox_min_lng=10&...
 */
class ListEntitiesRequest extends FormRequest
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
            'search' => ['sometimes', 'string', 'max:255'],

            // Type filters
            'type' => ['sometimes', 'string', Rule::enum(EntityType::class)],
            'types' => ['sometimes', 'array', 'max:30'],
            'types.*' => ['string', Rule::enum(EntityType::class)],
            'group' => ['sometimes', 'string', Rule::enum(EntityGroup::class)],

            // Verification
            'status' => ['sometimes', 'string', Rule::enum(VerificationStatus::class)],
            'min_confidence' => ['sometimes', 'string', Rule::enum(ConfidenceLevel::class)],

            // Tags
            'tag' => ['sometimes', 'string', 'max:100'],

            // Spatial: bounding box (all four required together)
            'bbox_min_lng' => ['sometimes', 'required_with:bbox_min_lat,bbox_max_lng,bbox_max_lat', 'numeric', 'between:-180,180'],
            'bbox_min_lat' => ['sometimes', 'required_with:bbox_min_lng,bbox_max_lng,bbox_max_lat', 'numeric', 'between:-90,90'],
            'bbox_max_lng' => ['sometimes', 'required_with:bbox_min_lng,bbox_min_lat,bbox_max_lat', 'numeric', 'between:-180,180'],
            'bbox_max_lat' => ['sometimes', 'required_with:bbox_min_lng,bbox_min_lat,bbox_max_lng', 'numeric', 'between:-90,90'],

            // Spatial: near point (all three required together)
            'near_lng' => ['sometimes', 'required_with:near_lat,near_radius', 'numeric', 'between:-180,180'],
            'near_lat' => ['sometimes', 'required_with:near_lng,near_radius', 'numeric', 'between:-90,90'],
            'near_radius' => ['sometimes', 'required_with:near_lng,near_lat', 'numeric', 'min:1', 'max:1000000'],

            // Temporal
            'temporal_start' => ['sometimes', 'string', 'max:50'],
            'temporal_end' => ['sometimes', 'string', 'max:50'],
            'exists_at' => ['sometimes', 'string', 'max:50'],

            // Hierarchy
            'parent_id' => ['sometimes', 'uuid'],

            // Sorting
            'sort' => ['sometimes', 'string', Rule::in([
                'relevance', 'impact', 'recent', 'chronological', 'distance', 'name',
            ])],

            // Pagination
            'per_page' => ['sometimes', 'integer', 'min:1', 'max:100'],
            'page' => ['sometimes', 'integer', 'min:1'],

            // Includes
            'include_relationships' => ['sometimes', 'boolean'],
        ];
    }
}
