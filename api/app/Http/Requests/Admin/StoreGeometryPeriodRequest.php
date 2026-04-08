<?php

declare(strict_types=1);

namespace App\Http\Requests\Admin;

use App\Enums\ConfidenceLevel;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class StoreGeometryPeriodRequest extends FormRequest
{
    public function authorize(): bool
    {
        return $this->user() !== null;
    }

    /**
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        $geoJsonTypes = ['Point', 'MultiPoint', 'LineString', 'MultiLineString', 'Polygon', 'MultiPolygon'];
        $territoryGeoJsonTypes = ['Polygon', 'MultiPolygon'];

        return [
            'period_type' => ['required', 'string', Rule::in(['territory', 'route', 'spread_zone', 'movement_path', 'presence'])],
            'start_year' => ['required', 'integer', 'lte:end_year'],
            'end_year' => ['required', 'integer', 'gte:start_year'],
            'description' => ['sometimes', 'nullable', 'string', 'max:2000'],
            'provenance_mode' => ['required', 'string', Rule::in(['manual', 'derived'])],
            'relationship_id' => ['sometimes', 'nullable', 'uuid', 'exists:relationships,relationship_id'],
            'source_event_id' => ['sometimes', 'nullable', 'uuid', 'exists:entities,entity_id'],
            'confidence' => ['sometimes', 'nullable', 'string', Rule::enum(ConfidenceLevel::class)],

            'geom' => ['required_without:territory_geom', 'nullable', 'array'],
            'geom.type' => ['required_with:geom', 'string', Rule::in($geoJsonTypes)],
            'geom.coordinates' => ['required_with:geom', 'array'],

            'territory_geom' => ['required_without:geom', 'nullable', 'array'],
            'territory_geom.type' => ['required_with:territory_geom', 'string', Rule::in($territoryGeoJsonTypes)],
            'territory_geom.coordinates' => ['required_with:territory_geom', 'array'],
        ];
    }
}
