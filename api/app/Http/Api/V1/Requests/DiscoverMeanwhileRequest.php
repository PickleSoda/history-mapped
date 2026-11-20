<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Requests;

use Illuminate\Foundation\Http\FormRequest;

/**
 * GET /api/v1/discover/meanwhile?year=1066
 *
 * `year` is required: an integer from `discover.meanwhile.min_year` (-4000)
 * to the current year, BCE negative.
 */
class DiscoverMeanwhileRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    /**
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            'year' => ['required', 'integer', 'between:'.(int) config('discover.meanwhile.min_year').','.(int) now('UTC')->year],
        ];
    }
}
