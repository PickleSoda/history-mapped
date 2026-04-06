<?php

declare(strict_types=1);

namespace App\Actions\EntityGeoRef;

use App\Models\EntityGeoRef;
use Illuminate\Database\Eloquent\ModelNotFoundException;
use Illuminate\Support\Facades\DB;

class ResolveOhmFeatureAction
{
    /**
     * @param  array{provider: string, external_type: string, external_id: string, target_year: int}  $payload
     * @return array{
     *     entity: array{id: string, name: string, entity_type: string|null, entity_group: string|null},
     *     geo_ref_id: string,
     *     resolution_source: string,
     *     geometry: array<string, mixed>
     * }
     */
    public function __invoke(array $payload): array
    {
        $match = DB::table('entity_geo_refs as gr')
            ->join('entities as e', 'e.entity_id', '=', 'gr.entity_id')
            ->select('gr.geo_ref_id')
            ->where('gr.provider', $payload['provider'])
            ->where('gr.external_type', $payload['external_type'])
            ->where('gr.external_id', $payload['external_id'])
            ->where('gr.is_active', true)
            ->where(function ($query) use ($payload): void {
                $query->whereNull('gr.temporal_start_year')
                    ->orWhere('gr.temporal_start_year', '<=', $payload['target_year']);
            })
            ->where(function ($query) use ($payload): void {
                $query->whereNull('gr.temporal_end_year')
                    ->orWhere('gr.temporal_end_year', '>=', $payload['target_year']);
            })
            ->orderByRaw('CASE WHEN e.primary_geo_ref_id = gr.geo_ref_id THEN 0 ELSE 1 END')
            ->orderByRaw("CASE WHEN gr.match_role = 'primary' THEN 0 ELSE 1 END")
            ->orderByRaw('gr.match_score DESC NULLS LAST')
            ->orderByDesc('gr.updated_at')
            ->orderBy('gr.geo_ref_id')
            ->first();

        if ($match === null) {
            throw (new ModelNotFoundException)->setModel(EntityGeoRef::class);
        }

        /** @var EntityGeoRef $geoRef */
        $geoRef = EntityGeoRef::query()
            ->with('entity')
            ->findOrFail($match->geo_ref_id);

        $entity = $geoRef->entity;

        if ($entity === null) {
            throw (new ModelNotFoundException)->setModel(EntityGeoRef::class);
        }

        $baseGeometry = $entity->territory_geom ?? $entity->geom;

        if (! is_array($baseGeometry)) {
            throw (new ModelNotFoundException)->setModel(EntityGeoRef::class);
        }

        return [
            'entity' => [
                'id' => $entity->entity_id,
                'name' => $entity->name,
                'entity_type' => $entity->entity_type?->value,
                'entity_group' => $entity->entity_group?->value,
            ],
            'geo_ref_id' => $geoRef->geo_ref_id,
            'resolution_source' => 'entity_geom',
            'geometry' => $baseGeometry,
        ];
    }
}
