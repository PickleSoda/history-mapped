<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Requests;

use App\Actions\Graph\GetEntityGraphAction;
use App\Enums\EntityGroup;
use App\Enums\RelationshipType;
use App\Http\Api\V1\Requests\Concerns\ParsesCsvParams;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

/**
 * GET /api/v1/entities/{entity}/graph
 */
class EntityGraphRequest extends FormRequest
{
    use ParsesCsvParams;

    public function authorize(): bool
    {
        return true;
    }

    protected function prepareForValidation(): void
    {
        $this->explodeCsv(['relationship_types', 'groups']);
    }

    /**
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            'depth' => ['nullable', 'integer', 'in:1,2'],
            'relationship_types' => ['nullable', 'array'],
            'relationship_types.*' => ['string', Rule::enum(RelationshipType::class)],
            'groups' => ['nullable', 'array'],
            'groups.*' => ['string', Rule::enum(EntityGroup::class)],
            'from' => ['nullable', 'integer'],
            'to' => ['nullable', 'integer'],
            'limit' => ['nullable', 'integer', 'min:1', 'max:'.GetEntityGraphAction::MAX_LIMIT],
        ];
    }
}
