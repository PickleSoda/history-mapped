<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Requests;

use App\Http\Api\V1\Requests\Concerns\ParsesCsvParams;
use App\Support\MapStory\MapStoryVocabulary;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

/**
 * GET /api/v1/map-stories?kind=battle&sort=year&per_page=20&page=1
 *
 * `kind` may list several kinds (kind=battle,naval_battle,siege or kind[]=…).
 * `sort` is `year` (oldest first, undated last; the default) or `title`.
 */
class ListMapStoriesRequest extends FormRequest
{
    use ParsesCsvParams;

    public function authorize(): bool
    {
        return true;
    }

    protected function prepareForValidation(): void
    {
        $this->explodeCsv(['kind']);
    }

    /**
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            'kind' => ['sometimes', 'array', 'max:20'],
            'kind.*' => ['string', Rule::in(MapStoryVocabulary::STORY_KINDS)],
            'sort' => ['sometimes', 'string', Rule::in(['year', 'title'])],
            'per_page' => ['sometimes', 'integer', 'min:1', 'max:100'],
            'page' => ['sometimes', 'integer', 'min:1'],
        ];
    }
}
