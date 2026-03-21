<?php

declare(strict_types=1);

namespace App\Http\Requests\Admin;

use App\Enums\ConfidenceLevel;
use App\Enums\RelationshipType;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

/**
 * Validates relationship creation from the Inertia admin UI.
 *
 * POST /entities/{entity}/relationships
 *
 * The source_entity_id is taken from the route model binding ({entity}),
 * not from the request body.
 */
class StoreRelationshipRequest extends FormRequest
{
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
            'target_entity_id' => ['required', 'uuid', 'exists:entities,entity_id'],
            'relationship_type' => ['required', 'string', Rule::enum(RelationshipType::class)],
            'temporal_start' => ['sometimes', 'nullable', 'string', 'max:50'],
            'temporal_end' => ['sometimes', 'nullable', 'string', 'max:50'],
            'description' => ['sometimes', 'nullable', 'string', 'max:2000'],
            'confidence' => ['sometimes', 'nullable', 'string', Rule::enum(ConfidenceLevel::class)],
            'source_citations' => ['sometimes', 'nullable', 'array'],
        ];
    }
}
