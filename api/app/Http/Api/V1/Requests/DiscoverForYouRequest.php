<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Requests;

use App\Http\Api\V1\Requests\Concerns\ParsesCsvParams;
use Illuminate\Foundation\Http\FormRequest;

/**
 * GET /api/v1/discover/for-you?ids=uuid,uuid,…
 *
 * `ids` are the entities this browser opened lately, most recent first: 1 to
 * `discover.for_you.max_ids` (12) UUIDs, comma-separated (or `ids[]=…`). Ids
 * the atlas does not know are ignored, not refused.
 */
class DiscoverForYouRequest extends FormRequest
{
    use ParsesCsvParams;

    public function authorize(): bool
    {
        return true;
    }

    protected function prepareForValidation(): void
    {
        $this->explodeCsv(['ids']);
    }

    /**
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            'ids' => ['required', 'array', 'min:1', 'max:'.(int) config('discover.for_you.max_ids')],
            'ids.*' => ['string', 'uuid'],
        ];
    }

    /** @return list<string> */
    public function ids(): array
    {
        return array_values($this->validated('ids'));
    }
}
