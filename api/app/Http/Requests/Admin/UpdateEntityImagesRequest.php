<?php

declare(strict_types=1);

namespace App\Http\Requests\Admin;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

/**
 * The full, ordered image list for an entity (first = primary). Commons files
 * are named by `file` and their license is re-read from Commons; other images
 * are an https `url` with the credit typed in by the admin.
 */
class UpdateEntityImagesRequest extends FormRequest
{
    public const KINDS = ['image', 'flag', 'coat_of_arms', 'seal', 'logo', 'map', 'plan'];

    public const SOURCES = ['wikidata', 'wikipedia', 'commons', 'external'];

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
            'images' => ['present', 'array', 'max:8'],
            'images.*.file' => ['nullable', 'string', 'max:255', 'required_without:images.*.url'],
            'images.*.url' => ['nullable', 'url:https', 'max:2048'],
            'images.*.kind' => ['required', Rule::in(self::KINDS)],
            'images.*.source' => ['nullable', Rule::in(self::SOURCES)],
            'images.*.property' => ['nullable', 'string', 'regex:/^P\d+$/'],
            'images.*.caption' => ['nullable', 'string', 'max:300'],
            // Only used for non-Commons images; Commons metadata wins otherwise.
            'images.*.author' => ['nullable', 'string', 'max:200'],
            'images.*.license' => ['nullable', 'string', 'max:80'],
            'images.*.license_url' => ['nullable', 'url', 'max:2048'],
            'images.*.page_url' => ['nullable', 'url', 'max:2048'],
        ];
    }
}
