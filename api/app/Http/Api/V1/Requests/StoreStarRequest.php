<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Requests;

use App\Enums\SaveableType;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

/**
 * POST /api/v1/me/stars
 */
class StoreStarRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true; // signed-in users star into their own account
    }

    /** @return array<string, mixed> */
    public function rules(): array
    {
        return [
            'type' => ['required', 'string', Rule::enum(SaveableType::class)],
            'id' => ['required', 'uuid'],
            'folder_ids' => ['sometimes', 'array', 'max:100'],
            'folder_ids.*' => ['integer', 'distinct'],
        ];
    }
}
