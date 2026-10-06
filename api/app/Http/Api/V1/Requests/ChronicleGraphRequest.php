<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Requests;

use App\Enums\RelationshipType;
use App\Http\Api\V1\Requests\Concerns\ParsesCsvParams;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

/**
 * GET /api/v1/chronicles/{slug}/graph
 */
class ChronicleGraphRequest extends FormRequest
{
    use ParsesCsvParams;

    public function authorize(): bool
    {
        return true;
    }

    protected function prepareForValidation(): void
    {
        $this->explodeCsv(['relationship_types']);
    }

    /**
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            'external' => ['nullable', 'boolean'],
            'external_limit' => ['nullable', 'integer', 'min:0', 'max:100'],
            'relationship_types' => ['nullable', 'array'],
            'relationship_types.*' => ['string', Rule::enum(RelationshipType::class)],
        ];
    }
}
