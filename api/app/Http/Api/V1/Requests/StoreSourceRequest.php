<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Requests;

use App\Enums\ReliabilityTier;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

/**
 * Validates source creation payload.
 *
 * POST /api/v1/sources
 */
class StoreSourceRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true; // TODO: policy-based authorization
    }

    /**
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            'title' => ['required', 'string', 'max:1000'],
            'source_type' => ['required', 'string', Rule::enum(ReliabilityTier::class)],
            'document_type' => ['sometimes', 'nullable', 'string', 'max:255'],
            'author' => ['sometimes', 'nullable', 'string', 'max:500'],
            'date_created' => ['sometimes', 'nullable', 'string', 'max:100'],
            'date_discovered' => ['sometimes', 'nullable', 'string', 'max:100'],
            'language' => ['sometimes', 'nullable', 'string', 'max:100'],
            'current_location' => ['sometimes', 'nullable', 'string', 'max:500'],
            'source_url' => ['sometimes', 'nullable', 'url', 'max:2000'],
            'content_hash' => ['sometimes', 'nullable', 'string', 'max:128'],
            'geographic_scope' => ['sometimes', 'nullable', 'string', 'max:500'],
            'temporal_scope' => ['sometimes', 'nullable', 'string', 'max:500'],
            'contemporaneity' => ['sometimes', 'nullable', 'string', 'max:500'],
            'author_bias' => ['sometimes', 'nullable', 'string', 'max:1000'],
            'corroboration' => ['sometimes', 'nullable', 'string', 'max:1000'],
            'scholarly_consensus' => ['sometimes', 'nullable', 'string', 'max:1000'],
        ];
    }
}
