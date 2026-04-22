<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Requests;

use App\Enums\GeoRefExternalType;
use App\Enums\GeoRefMatchRole;
use App\Enums\GeoRefProvider;
use App\Enums\GeoRefRetrievalMethod;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class StoreEntityGeoRefRequest extends FormRequest
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
            'provider' => ['required', 'string', Rule::enum(GeoRefProvider::class)],
            'external_type' => ['required', 'string', Rule::enum(GeoRefExternalType::class)],
            'external_id' => ['required', 'string', 'max:255'],
            'geometry_period_id' => ['sometimes', 'nullable', 'uuid'],
            'match_role' => ['required', 'string', Rule::enum(GeoRefMatchRole::class)],
            'retrieval_method' => ['required', 'string', Rule::enum(GeoRefRetrievalMethod::class)],
            'temporal_start' => ['sometimes', 'nullable', 'string', 'max:255'],
            'temporal_end' => ['sometimes', 'nullable', 'string', 'max:255'],
            'temporal_start_year' => ['sometimes', 'nullable', 'integer'],
            'temporal_end_year' => ['sometimes', 'nullable', 'integer', 'gte:temporal_start_year'],
            'external_tags' => ['sometimes', 'nullable', 'array'],
            'source_meta' => ['sometimes', 'nullable', 'array'],
            'match_score' => ['sometimes', 'nullable', 'numeric', 'between:0,1'],
            'is_active' => ['sometimes', 'boolean'],
        ];
    }
}
