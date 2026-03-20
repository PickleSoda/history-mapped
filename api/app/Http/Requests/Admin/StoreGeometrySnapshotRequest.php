<?php

declare(strict_types=1);

namespace App\Http\Requests\Admin;

use App\Enums\ConfidenceLevel;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

/**
 * Validates geometry snapshot creation from the Inertia admin form.
 *
 * POST /entities/{entity}/snapshots
 */
class StoreGeometrySnapshotRequest extends FormRequest
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
        return [
            // Temporal validity
            'year_start' => ['required', 'integer', 'between:-10000,9999'],
            'year_end' => ['required', 'integer', 'between:-10000,9999', 'gte:year_start'],

            // Geometry — at least one must be provided
            'geojson' => ['sometimes', 'nullable', 'array'],
            'geojson.type' => ['required_with:geojson', 'string', Rule::in(['Point', 'LineString', 'MultiLineString'])],
            'geojson.coordinates' => ['required_with:geojson', 'array'],

            'territory_geojson' => ['sometimes', 'nullable', 'array'],
            'territory_geojson.type' => ['required_with:territory_geojson', 'string', Rule::in(['Polygon', 'MultiPolygon'])],
            'territory_geojson.coordinates' => ['required_with:territory_geojson', 'array'],

            // Metadata
            'label' => ['sometimes', 'nullable', 'string', 'max:500'],
            'confidence' => ['sometimes', 'nullable', 'string', Rule::enum(ConfidenceLevel::class)],
            'source_citations' => ['sometimes', 'nullable', 'array'],
            'notes' => ['sometimes', 'nullable', 'string', 'max:5000'],
            'display_priority' => ['sometimes', 'nullable', 'integer', 'between:0,100'],
        ];
    }

    /**
     * @return array<string, string>
     */
    public function messages(): array
    {
        return [
            'year_end.gte' => 'The year end must be greater than or equal to year start.',
        ];
    }

    /**
     * Add a custom validation rule: at least one geometry field must be present.
     *
     * @param  \Illuminate\Validation\Validator  $validator
     */
    public function withValidator(\Illuminate\Validation\Validator $validator): void
    {
        $validator->after(function (\Illuminate\Validation\Validator $v): void {
            $geojson = $this->input('geojson');
            $territoryGeojson = $this->input('territory_geojson');

            if (empty($geojson) && empty($territoryGeojson)) {
                $v->errors()->add('geojson', 'At least one geometry (geojson or territory_geojson) must be provided.');
            }
        });
    }
}
