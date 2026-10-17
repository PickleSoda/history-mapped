<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Requests;

use App\Enums\ChronicleStatus;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

/**
 * GET /api/v1/chronicles?search=bronze&tags[]=medieval&tags[]=europe&sort=chronological
 *
 * `tags` may also be comma-separated (tags=medieval,europe).
 */
class ListChroniclesRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    protected function prepareForValidation(): void
    {
        if (is_string($this->input('tags'))) {
            $this->merge(['tags' => array_values(array_filter(explode(',', $this->input('tags'))))]);
        }
    }

    /**
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            'search' => ['sometimes', 'nullable', 'string', 'max:255'],
            'status' => ['sometimes', 'nullable', 'string', Rule::enum(ChronicleStatus::class)],
            'tags' => ['sometimes', 'array', 'max:20'],
            'tags.*' => ['string', 'max:100'],
            'sort' => ['sometimes', 'string', Rule::in(['recent', 'chronological', 'title', 'impact'])],
            'per_page' => ['sometimes', 'integer', 'min:1', 'max:100'],
            'page' => ['sometimes', 'integer', 'min:1'],
        ];
    }
}
