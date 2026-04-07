<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin;

use App\Http\Api\V1\Resources\GeometrySnapshotResource;
use App\Http\Controllers\Controller;
use App\Models\Entity;
use App\Models\GeometryPeriod;
use Symfony\Component\HttpKernel\Exception\HttpException;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;
use Illuminate\Support\Facades\Validator;
use Illuminate\Validation\ValidationException;

class GeometrySnapshotController extends Controller
{
    public function index(Entity $entity): AnonymousResourceCollection
    {
        $periods = GeometryPeriod::query()
            ->where('entity_id', $entity->entity_id)
            ->orderBy('start_year')
            ->orderBy('end_year')
            ->orderBy('created_at')
            ->get();

        return GeometrySnapshotResource::collection($periods);
    }

    public function store(Request $request, Entity $entity): JsonResponse
    {
        $this->ensureLegacyWriteEnabled();

        $validated = $this->validatePayload($request);

        $period = GeometryPeriod::query()->create([
            'entity_id' => $entity->entity_id,
            'period_type' => $validated['period_type'],
            'start_year' => $validated['start_year'],
            'end_year' => $validated['end_year'],
            'geom' => $validated['geom'] ?? null,
            'territory_geom' => $validated['territory_geom'] ?? null,
            'description' => $validated['description'] ?? null,
            'provenance_mode' => $validated['provenance_mode'],
            'relationship_id' => $validated['relationship_id'] ?? null,
            'source_event_id' => $validated['source_event_id'] ?? null,
            'created_by' => (string) $request->user()->id,
        ]);

        $period = GeometryPeriod::query()
            ->where('entity_id', $entity->entity_id)
            ->where('period_type', $validated['period_type'])
            ->where('start_year', $validated['start_year'])
            ->where('end_year', $validated['end_year'])
            ->orderByDesc('created_at')
            ->firstOrFail();

        return (new GeometrySnapshotResource($period))
            ->response()
            ->setStatusCode(201);
    }

    public function update(Request $request, Entity $entity, string $snapshot): GeometrySnapshotResource
    {
        $this->ensureLegacyWriteEnabled();

        $period = GeometryPeriod::query()
            ->where('geometry_period_id', $snapshot)
            ->where('entity_id', $entity->entity_id)
            ->firstOrFail();

        $validated = $this->validatePayload($request);

        $period->fill([
            'period_type' => $validated['period_type'],
            'start_year' => $validated['start_year'],
            'end_year' => $validated['end_year'],
            'geom' => $validated['geom'] ?? null,
            'territory_geom' => $validated['territory_geom'] ?? null,
            'description' => $validated['description'] ?? null,
            'provenance_mode' => $validated['provenance_mode'],
            'relationship_id' => $validated['relationship_id'] ?? null,
            'source_event_id' => $validated['source_event_id'] ?? null,
        ]);
        $period->save();

        $period = GeometryPeriod::query()
            ->where('geometry_period_id', $period->geometry_period_id)
            ->firstOrFail();

        return new GeometrySnapshotResource($period);
    }

    public function destroy(Entity $entity, string $snapshot): JsonResponse
    {
        $this->ensureLegacyWriteEnabled();

        $period = GeometryPeriod::query()
            ->where('geometry_period_id', $snapshot)
            ->where('entity_id', $entity->entity_id)
            ->firstOrFail();

        $period->delete();

        return response()->json(null, 204);
    }

    /**
     * @return array<string, mixed>
     */
    private function validatePayload(Request $request): array
    {
        $validator = Validator::make($request->all(), [
            'period_type' => ['required', 'string', 'in:presence,territory'],
            'start_year' => ['required', 'integer'],
            'end_year' => ['required', 'integer', 'gte:start_year'],
            'geom' => ['nullable', 'array'],
            'territory_geom' => ['nullable', 'array'],
            'description' => ['nullable', 'string', 'max:2000'],
            'provenance_mode' => ['required', 'string', 'in:manual,derived'],
            'relationship_id' => ['nullable', 'uuid'],
            'source_event_id' => ['nullable', 'uuid'],
        ]);

        $validator->after(function ($validator): void {
            $data = $validator->getData();

            if (($data['period_type'] ?? null) === 'presence') {
                $validator->errors()->add(
                    'period_type',
                    'Presence periods are relationship-derived and cannot be created manually.',
                );
            }

            if (($data['geom'] ?? null) === null && ($data['territory_geom'] ?? null) === null) {
                $validator->errors()->add(
                    'geom',
                    'Either geom or territory_geom must be provided.',
                );
            }
        });

        if ($validator->fails()) {
            throw new ValidationException($validator);
        }

        $validated = $validator->validated();

        return $validated;
    }

    private function ensureLegacyWriteEnabled(): void
    {
        if ((bool) config('entity_model.entity_model_v2_write_enabled', false)) {
            throw new HttpException(410, 'Legacy geometry snapshot write endpoints are disabled.');
        }
    }
}
