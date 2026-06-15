<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Requests;

use App\Enums\ConfidenceLevel;
use App\Enums\EntityGroup;
use App\Enums\EntityType;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class MapEntitiesByYearRequest extends FormRequest
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
            'year' => ['required', 'integer'],
            'type' => ['sometimes', 'string', Rule::enum(EntityType::class)],
            'types' => ['sometimes', 'array', 'max:30'],
            'types.*' => ['string', Rule::enum(EntityType::class)],
            'min_confidence' => ['sometimes', 'string', Rule::enum(ConfidenceLevel::class)],
            'min_impact' => ['sometimes', 'nullable', 'integer', 'min:0', 'max:100'],
            'group' => ['sometimes', 'string', Rule::enum(EntityGroup::class)],
            'groups' => ['sometimes', 'array', 'max:5'],
            'groups.*' => ['string', Rule::enum(EntityGroup::class)],
            'all_periods' => ['sometimes', 'boolean'],
            'limit' => ['sometimes', 'integer', 'min:1', 'max:100000'],
        ];
    }
}
