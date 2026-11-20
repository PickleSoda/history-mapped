<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Requests;

use Carbon\CarbonImmutable;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Validator;

/**
 * GET /api/v1/discover/quest?date=2026-11-20
 *
 * `date` is the reader's local day; without it, the server's UTC day. It must
 * be within `discover.quest.date_tolerance_days` (2) of the server's UTC day:
 * every time zone's "today" is, and the answers cached per date stay few.
 */
class DiscoverQuestRequest extends FormRequest
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

    /** @return list<callable(Validator): void> */
    public function after(): array
    {
        return [function (Validator $validator): void {
            $date = $this->query('date');
            if (! is_string($date) || $validator->errors()->has('date')) {
                return;
            }

            $tolerance = (int) config('discover.quest.date_tolerance_days');
            $today = CarbonImmutable::now('UTC')->startOfDay();
            $day = CarbonImmutable::createFromFormat('!Y-m-d', $date, 'UTC');
            if (abs($day->getTimestamp() - $today->getTimestamp()) > $tolerance * 86400) {
                $validator->errors()->add('date', "The date must be within {$tolerance} days of today.");
            }
        }];
    }

    /** The day asked for, YYYY-MM-DD. */
    public function day(): string
    {
        return (string) ($this->validated('date') ?? now('UTC')->format('Y-m-d'));
    }
}
