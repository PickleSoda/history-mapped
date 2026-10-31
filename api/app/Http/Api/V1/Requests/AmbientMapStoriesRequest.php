<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Requests;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Validator;

/**
 * GET /api/v1/map-stories/ambient?year=1348&bbox=-15,25,50,65
 *
 * `bbox` is west,south,east,north in degrees and optional (none: the whole
 * world). Longitudes may wrap, as on /entities/map: west > east crosses the
 * antimeridian.
 */
class AmbientMapStoriesRequest extends FormRequest
{
    private const NUMBER = '-?\d+(\.\d+)?';

    public function authorize(): bool
    {
        return true;
    }

    /**
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        $n = self::NUMBER;

        return [
            'year' => ['required', 'integer'],
            'bbox' => ['sometimes', 'string', "regex:/^{$n},{$n},{$n},{$n}$/"],
        ];
    }

    /** @return list<callable(Validator): void> */
    public function after(): array
    {
        return [function (Validator $validator): void {
            $box = $this->bbox();
            if ($box !== null && ($box[1] < -90 || $box[3] > 90 || $box[1] > $box[3])) {
                $validator->errors()->add('bbox', 'bbox: south and north must lie in -90..90, south ≤ north.');
            }
        }];
    }

    /** @return array{0: float, 1: float, 2: float, 3: float}|null west, south, east, north */
    public function bbox(): ?array
    {
        $bbox = $this->query('bbox');
        if (! is_string($bbox) || preg_match('/^'.self::NUMBER.'(,'.self::NUMBER.'){3}$/', $bbox) !== 1) {
            return null;
        }
        [$w, $s, $e, $n] = array_map(floatval(...), explode(',', $bbox));

        return [$w, $s, $e, $n];
    }
}
