<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Requests;

use App\Enums\GeoRefExternalType;
use App\Enums\GeoRefProvider;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class ResolveOhmFeatureRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    /**
     * A feature is named either by `external_type` + `external_id`, or by the
     * signed `osm_id` that OHM tiles carry (spec D3: negative = relation,
     * positive = node or way). The two forms are mutually exclusive.
     *
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            'provider' => ['required', 'string', Rule::enum(GeoRefProvider::class)],
            'external_type' => ['required_without:osm_id', 'string', Rule::enum(GeoRefExternalType::class), 'prohibits:osm_id'],
            'external_id' => ['required_without:osm_id', 'string', 'max:255', 'prohibits:osm_id'],
            'osm_id' => ['required_without:external_id', 'integer', 'not_in:0'],
            'target_year' => ['required', 'integer'],
        ];
    }
}
