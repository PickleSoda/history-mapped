<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Http\Requests\Admin\StoreGeometryPeriodRequest;
use App\Http\Requests\Admin\UpdateGeometryPeriodRequest;
use App\Models\Entity;
use App\Models\GeometryPeriod;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Str;

class EntityGeometryPeriodController extends Controller
{
    public function index(Entity $entity): JsonResponse
    {
        $periods = $entity->geometryPeriods()
            ->select([
                'geometry_period_id',
                'entity_id',
                'period_type',
                'start_year',
                'end_year',
                'description',
                'provenance_mode',
                'relationship_id',
                'source_event_id',
                'confidence',
                'created_at',
                'updated_at',
            ])
            ->selectRaw('geom IS NOT NULL as has_geom')
            ->selectRaw('territory_geom IS NOT NULL as has_territory_geom')
            ->orderBy('start_year')
            ->orderBy('end_year')
            ->get();

        return response()->json([
            'data' => $periods->map(fn (GeometryPeriod $period) => self::toSummaryPayload($period)),
        ]);
    }

    public function show(Entity $entity, GeometryPeriod $geometryPeriod): JsonResponse
    {
        if ($geometryPeriod->entity_id !== $entity->entity_id) {
            abort(404);
        }

        return response()->json([
            'data' => self::toPayload($geometryPeriod),
        ]);
    }

    public function store(StoreGeometryPeriodRequest $request, Entity $entity): JsonResponse
    {
        $period = new GeometryPeriod(array_merge(
            $request->validated(),
            ['created_by' => (string) $request->user()->id],
        ));

        $period->geometry_period_id = (string) Str::uuid();
        $period->entity()->associate($entity);
        $period->save();

        return response()->json([
            'data' => self::toPayload($period->fresh()),
        ], 201);
    }

    public function update(UpdateGeometryPeriodRequest $request, Entity $entity, GeometryPeriod $geometryPeriod): JsonResponse
    {
        if ($geometryPeriod->entity_id !== $entity->entity_id) {
            abort(404);
        }

        $geometryPeriod->update($request->validated());

        return response()->json([
            'data' => self::toPayload($geometryPeriod->fresh()),
        ]);
    }

    public function destroy(Entity $entity, GeometryPeriod $geometryPeriod): JsonResponse
    {
        if ($geometryPeriod->entity_id !== $entity->entity_id) {
            abort(404);
        }

        $geometryPeriod->delete();

        return response()->json(null, 204);
    }

    /**
     * @return array<string, mixed>
     */
    private static function toPayload(GeometryPeriod $period): array
    {
        return [
            'geometry_period_id' => $period->geometry_period_id,
            'entity_id' => $period->entity_id,
            'period_type' => $period->period_type,
            'start_year' => $period->start_year,
            'end_year' => $period->end_year,
            'description' => $period->description,
            'provenance_mode' => $period->provenance_mode,
            'relationship_id' => $period->relationship_id,
            'source_event_id' => $period->source_event_id,
            'confidence' => $period->confidence?->value,
            'geom' => $period->geom,
            'territory_geom' => $period->territory_geom,
            'created_at' => $period->created_at?->toISOString(),
            'updated_at' => $period->updated_at?->toISOString(),
        ];
    }

    /**
     * @return array<string, mixed>
     */
    private static function toSummaryPayload(GeometryPeriod $period): array
    {
        return [
            'geometry_period_id' => $period->geometry_period_id,
            'entity_id' => $period->entity_id,
            'period_type' => $period->period_type,
            'start_year' => $period->start_year,
            'end_year' => $period->end_year,
            'description' => $period->description,
            'provenance_mode' => $period->provenance_mode,
            'relationship_id' => $period->relationship_id,
            'source_event_id' => $period->source_event_id,
            'confidence' => $period->confidence?->value,
            'has_geom' => (bool) ($period->has_geom ?? false),
            'has_territory_geom' => (bool) ($period->has_territory_geom ?? false),
            'created_at' => $period->created_at?->toISOString(),
            'updated_at' => $period->updated_at?->toISOString(),
        ];
    }
}
