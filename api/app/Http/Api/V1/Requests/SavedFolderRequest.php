<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Requests;

use App\Models\SavedFolder;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

/**
 * POST /api/v1/me/folders · PATCH /api/v1/me/folders/{folder}
 *
 * Folder names are unique per user (case-sensitive, trimmed).
 */
class SavedFolderRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true; // ownership is enforced by the controller's lookup
    }

    protected function prepareForValidation(): void
    {
        if (is_string($this->input('name'))) {
            $this->merge(['name' => trim($this->input('name'))]);
        }
    }

    /** @return array<string, mixed> */
    public function rules(): array
    {
        $folder = $this->route('folder');
        $creating = $this->isMethod('post');

        return [
            'name' => [
                $creating ? 'required' : 'sometimes',
                'string',
                'max:80',
                Rule::unique('saved_folders', 'name')
                    ->where('user_id', $this->user()->id)
                    ->ignore($folder instanceof SavedFolder ? $folder->id : $folder),
            ],
            'description' => ['sometimes', 'nullable', 'string', 'max:500'],
            'color' => ['sometimes', 'nullable', 'string', 'regex:/^#[0-9a-fA-F]{6}$/'],
        ];
    }

    /** @return array<string, string> */
    public function messages(): array
    {
        return [
            'name.unique' => 'You already have a folder with this name.',
            'color.regex' => 'The colour must be a hex value like #3b82f6.',
        ];
    }
}
