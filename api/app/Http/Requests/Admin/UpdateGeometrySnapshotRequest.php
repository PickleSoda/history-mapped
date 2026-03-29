<?php

declare(strict_types=1);

namespace App\Http\Requests\Admin;

use App\Enums\ConfidenceLevel;
use App\Enums\GeoRefExternalType;
use App\Enums\GeoRefMatchRole;
use App\Enums\GeoRefProvider;
use App\Enums\GeoRefRetrievalMethod;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

/**
 * Validates geometry snapshot update from the Inertia admin form.
 *
 * PUT /entities/{entity}/snapshots/{snapshot}
 */
class UpdateGeometrySnapshotRequest extends FormRequest
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
            'year_start' => ['sometimes', 'required', 'integer', 'between:-10000,9999'],
            'year_end' => ['sometimes', 'required', 'integer', 'between:-10000,9999', 'gte:year_start'],

            // Geometry
            'geojson' => ['sometimes', 'nullable', 'array'],
            'geojson.type' => ['required_with:geojson', 'string', Rule::in(['Point', 'LineString', 'MultiLineString', 'Feature', 'FeatureCollection', 'GeometryCollection'])],
            'geojson.coordinates' => ['sometimes', 'array'],
            'geojson.geometry' => ['sometimes', 'array'],
            'geojson.features' => ['sometimes', 'array'],
            'geojson.geometries' => ['sometimes', 'array'],

            'territory_geojson' => ['sometimes', 'nullable', 'array'],
            'territory_geojson.type' => ['required_with:territory_geojson', 'string', Rule::in(['Polygon', 'MultiPolygon', 'Feature', 'FeatureCollection', 'GeometryCollection'])],
            'territory_geojson.coordinates' => ['sometimes', 'array'],
            'territory_geojson.geometry' => ['sometimes', 'array'],
            'territory_geojson.features' => ['sometimes', 'array'],
            'territory_geojson.geometries' => ['sometimes', 'array'],

            // Metadata
            'label' => ['sometimes', 'nullable', 'string', 'max:500'],
            'confidence' => ['sometimes', 'nullable', 'string', Rule::enum(ConfidenceLevel::class)],
            'source_citations' => ['sometimes', 'nullable', 'array'],
            'notes' => ['sometimes', 'nullable', 'string', 'max:5000'],
            'display_priority' => ['sometimes', 'nullable', 'integer', 'between:0,100'],

            'geography_reference' => ['sometimes', 'array'],
            'geography_reference.provider' => ['required_with:geography_reference', 'string', Rule::enum(GeoRefProvider::class)],
            'geography_reference.external_type' => ['required_with:geography_reference', 'string', Rule::enum(GeoRefExternalType::class)],
            'geography_reference.external_id' => ['required_with:geography_reference', 'string', 'max:255'],
            'geography_reference.match_role' => ['required_with:geography_reference', 'string', Rule::enum(GeoRefMatchRole::class)],
            'geography_reference.retrieval_method' => ['required_with:geography_reference', 'string', Rule::enum(GeoRefRetrievalMethod::class)],
            'geography_reference.temporal_start' => ['sometimes', 'nullable', 'string', 'max:255'],
            'geography_reference.temporal_end' => ['sometimes', 'nullable', 'string', 'max:255'],
            'geography_reference.temporal_start_year' => ['sometimes', 'nullable', 'integer'],
            'geography_reference.temporal_end_year' => ['sometimes', 'nullable', 'integer', 'gte:geography_reference.temporal_start_year'],
            'geography_reference.external_tags' => ['sometimes', 'nullable', 'array'],
            'geography_reference.source_meta' => ['sometimes', 'nullable', 'array'],
            'geography_reference.match_score' => ['sometimes', 'nullable', 'numeric', 'between:0,1'],
            'geography_reference.is_active' => ['sometimes', 'boolean'],
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
     * @param  \Illuminate\Validation\Validator  $validator
     */
    public function withValidator(\Illuminate\Validation\Validator $validator): void
    {
        $validator->after(function (\Illuminate\Validation\Validator $v): void {
            $geojson = $this->input('geojson');
            $territoryGeojson = $this->input('territory_geojson');

            if (! empty($geojson)) {
                $this->validateGeometryPayload($v, $geojson, 'geojson', ['Point', 'LineString', 'MultiLineString']);
            }

            if (! empty($territoryGeojson)) {
                $this->validateGeometryPayload($v, $territoryGeojson, 'territory_geojson', ['Polygon', 'MultiPolygon']);
            }
        });
    }

    /**
     * @param  array<string, mixed>  $payload
     * @param  array<int, string>  $allowedGeometryTypes
     */
    private function validateGeometryPayload(\Illuminate\Validation\Validator $validator, array $payload, string $field, array $allowedGeometryTypes): void
    {
        $type = $payload['type'] ?? null;

        if (! is_string($type)) {
            $validator->errors()->add("{$field}.type", 'The '.$field.'.type field is required.');

            return;
        }

        $geometries = $this->extractContainedGeometries($payload);

        if (count($geometries) === 0) {
            $validator->errors()->add($field, 'The '.$field.' field must contain at least one geometry.');

            return;
        }

        foreach ($geometries as $index => $geometry) {
            $geometryType = $geometry['type'] ?? null;
            if (! is_string($geometryType) || ! in_array($geometryType, $allowedGeometryTypes, true)) {
                $validator->errors()->add("{$field}.type", 'The selected '.$field.'.type is invalid.');

                return;
            }

            if (! array_key_exists('coordinates', $geometry) || ! is_array($geometry['coordinates'])) {
                $validator->errors()->add("{$field}.coordinates", 'The '.$field.'.coordinates field is required when '.$field.' is present.');

                return;
            }

            if ($index > 5000) {
                $validator->errors()->add($field, 'The '.$field.' field has too many geometries.');

                return;
            }
        }
    }

    /**
     * @param  array<string, mixed>  $payload
     * @return list<array<string, mixed>>
     */
    private function extractContainedGeometries(array $payload): array
    {
        $type = $payload['type'] ?? null;

        if (! is_string($type)) {
            return [];
        }

        if ($type === 'FeatureCollection') {
            $features = $payload['features'] ?? null;
            if (! is_array($features)) {
                return [];
            }

            $geometries = [];
            foreach ($features as $feature) {
                if (! is_array($feature) || ! isset($feature['geometry']) || ! is_array($feature['geometry'])) {
                    continue;
                }

                $geometries = [...$geometries, ...$this->extractContainedGeometries($feature['geometry'])];
            }

            return $geometries;
        }

        if ($type === 'Feature') {
            $geometry = $payload['geometry'] ?? null;
            if (! is_array($geometry)) {
                return [];
            }

            return $this->extractContainedGeometries($geometry);
        }

        if ($type === 'GeometryCollection') {
            $children = $payload['geometries'] ?? null;
            if (! is_array($children)) {
                return [];
            }

            $geometries = [];
            foreach ($children as $child) {
                if (! is_array($child)) {
                    continue;
                }

                $geometries = [...$geometries, ...$this->extractContainedGeometries($child)];
            }

            return $geometries;
        }

        return [$payload];
    }
}
