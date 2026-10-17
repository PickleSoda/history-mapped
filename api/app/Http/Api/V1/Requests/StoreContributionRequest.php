<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Requests;

use App\Enums\ContributionTargetType;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

/**
 * POST /api/v1/contributions
 *
 * Shape only; whether the field is editable and the text actually changed is
 * decided by SubmitContributionAction against the live record.
 */
class StoreContributionRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true; // gated by the `contributions.create` route middleware
    }

    /** @return array<string, mixed> */
    public function rules(): array
    {
        $type = ContributionTargetType::tryFrom((string) $this->input('target_type'));
        $field = (string) $this->input('field');

        return [
            'target_type' => ['required', 'string', Rule::enum(ContributionTargetType::class)],
            'target_id' => ['required', 'uuid'],
            'field' => ['required', 'string', Rule::in($type?->editableFields() ?? [])],
            // Empty is allowed (clearing a prose field); null arrives for "".
            'proposed_text' => [
                'present', 'nullable', 'string',
                'max:'.($type?->maxLength($field) ?? ContributionTargetType::MAX_TEXT_LENGTH),
            ],
            'note' => ['sometimes', 'nullable', 'string', 'max:1000'],
        ];
    }
}
