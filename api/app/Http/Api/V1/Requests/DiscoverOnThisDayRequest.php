<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Requests;

use Illuminate\Foundation\Http\FormRequest;

/**
 * GET /api/v1/discover/on-this-day?date=2026-11-20
 *
 * `date` is the reader's local day; without it, the server's UTC day. Only
 * its month and day are used.
 */
class DiscoverOnThisDayRequest extends FormRequest
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
            'date' => ['sometimes', 'string', 'date_format:Y-m-d'],
        ];
    }

    /** @return array{0: int, 1: int} month, day */
    public function monthAndDay(): array
    {
        [, $month, $day] = explode('-', (string) ($this->validated('date') ?? now('UTC')->format('Y-m-d')));

        return [(int) $month, (int) $day];
    }
}
