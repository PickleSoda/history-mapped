<?php

declare(strict_types=1);

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

/**
 * POST /contributions/{contribution}/approve · /reject (admin)
 */
class ReviewContributionRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true; // gated by the `contributions.review` route middleware
    }

    /** @return array<string, mixed> */
    public function rules(): array
    {
        return [
            'review_note' => ['sometimes', 'nullable', 'string', 'max:2000'],
            'force' => ['sometimes', 'boolean'],
            'keep_old_name_as_alias' => ['sometimes', 'boolean'],
        ];
    }
}
