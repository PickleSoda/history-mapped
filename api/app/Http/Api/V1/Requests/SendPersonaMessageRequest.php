<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Requests;

use Illuminate\Foundation\Http\FormRequest;

class SendPersonaMessageRequest extends FormRequest
{
    public function authorize(): bool
    {
        return $this->user() !== null;
    }

    /** @return array<string, mixed> */
    public function rules(): array
    {
        return [
            'message' => ['required', 'string', 'max:'.(int) config('persona.limits.message_chars', 2000)],
        ];
    }

    protected function prepareForValidation(): void
    {
        if (is_string($this->input('message'))) {
            $this->merge(['message' => trim($this->input('message'))]);
        }
    }
}
