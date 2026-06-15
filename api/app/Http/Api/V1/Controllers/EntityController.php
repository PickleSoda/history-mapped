<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Actions\Entity\CreateEntityAction;
use App\Actions\Entity\DeleteEntityAction;
use App\Actions\Entity\GetEntityAction;
use App\Actions\Entity\ListEntitiesAction;
use App\Actions\Entity\MapEntitiesAction;
use App\Actions\Entity\MapEntitiesByYearAction;
use App\Actions\Entity\UpdateEntityAction;
use App\DTOs\EntityData;
use App\DTOs\EntityFilterData;
use App\Http\Api\V1\Requests\ListEntitiesRequest;
use App\Http\Api\V1\Requests\MapEntitiesByYearRequest;
use App\Http\Api\V1\Requests\MapEntitiesRequest;
use App\Http\Api\V1\Requests\StoreEntityRequest;
use App\Http\Api\V1\Requests\UpdateEntityRequest;
use App\Http\Api\V1\Resources\EntityResource;
use App\Http\Api\V1\Resources\EntitySummaryResource;
use App\Http\Controllers\Controller;
use App\Models\Entity;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;
use Illuminate\Support\Facades\DB;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\HttpFoundation\StreamedResponse;

class EntityController extends Controller
{
    /**
     * GET /api/v1/entities
     *
     * List entities with filtering, spatial/temporal queries, and pagination.
     */
    public function index(
        ListEntitiesRequest $request,
        ListEntitiesAction $action,
    ): AnonymousResourceCollection {
        $filters = EntityFilterData::fromArray($request->validated());
        $entities = $action($filters);

        return EntitySummaryResource::collection($entities);
    }

    /**
     * GET /api/v1/entities/map
     *
     * Lightweight GeoJSON FeatureCollection for map rendering.
     */
    public function map(
        MapEntitiesRequest $request,
        MapEntitiesAction $action,
    ): Response {
        $etag = $this->mapEtag($request->validated());

        if ($this->etagMatches($request, $etag)) {
            return response('', 304, $this->cacheHeaders($etag));
        }

        $result = $action($request->validated());

        return $this->streamFeatureCollection($result['features'], $etag);
    }

    /**
     * GET /api/v1/entities/map/year
     *
     * Full-period borders for a given year (no bbox filter).
     */
    public function mapByYear(
        MapEntitiesByYearRequest $request,
        MapEntitiesByYearAction $action,
    ): Response {
        $etag = $this->mapEtag($request->validated());

        if ($this->etagMatches($request, $etag)) {
            return response('', 304, $this->cacheHeaders($etag));
        }

        $result = $action($request->validated());

        return $this->streamFeatureCollection($result['features'], $etag);
    }

    /**
     * Deterministic ETag for a map response: the geometry data-version
     * (max updated_at — one cheap aggregate) combined with the validated
     * request filters. Identical data + identical filters → identical ETag,
     * so a conditional request can short-circuit to 304.
     *
     * @param  array<string, mixed>  $validated
     */
    private function mapEtag(array $validated): string
    {
        $version = DB::table('geometry_periods')->max('updated_at');
        ksort($validated);

        return '"'.sha1(($version ?? 'empty').'|'.json_encode($validated)).'"';
    }

    private function etagMatches(Request $request, string $etag): bool
    {
        $header = $request->headers->get('If-None-Match');

        if ($header === null || $header === '') {
            return false;
        }

        if (trim($header) === '*') {
            return true;
        }

        foreach (explode(',', $header) as $candidate) {
            // Tolerate weak validators (W/"...") and surrounding whitespace.
            $candidate = preg_replace('/^\s*W\//', '', trim($candidate));

            if ($candidate === $etag) {
                return true;
            }
        }

        return false;
    }

    /**
     * @return array<string, string>
     */
    private function cacheHeaders(string $etag): array
    {
        return [
            'ETag' => $etag,
            'Cache-Control' => 'public, max-age=60',
        ];
    }

    private function streamFeatureCollection(iterable $features, ?string $etag = null): StreamedResponse
    {
        $headers = ['Content-Type' => 'application/json'];

        if ($etag !== null) {
            $headers += $this->cacheHeaders($etag);
        }

        return response()->stream(function () use ($features): void {
            echo '{"type":"FeatureCollection","features":[';

            $first = true;

            foreach ($features as $feature) {
                if (! $first) {
                    echo ',';
                }

                $idJson = json_encode($feature['id'], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
                $geometryJson = is_string($feature['geometry_json'] ?? null) ? $feature['geometry_json'] : 'null';
                $propertiesJson = json_encode($feature['properties'], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);

                echo sprintf(
                    '{"type":"Feature","id":%s,"geometry":%s,"properties":%s}',
                    $idJson === false ? 'null' : $idJson,
                    $geometryJson,
                    $propertiesJson === false ? '{}' : $propertiesJson,
                );

                $first = false;
            }

            echo ']}';
        }, 200, $headers);
    }

    /**
     * GET /api/v1/entities/{entity}
     *
     * Single entity with full detail. Optionally include relationships.
     */
    public function show(
        string $entity,
        GetEntityAction $action,
    ): EntityResource {
        $with = [];

        if (request()->boolean('include_relationships')) {
            $with = ['outgoingRelationships.targetEntity', 'incomingRelationships.sourceEntity'];
        }

        return new EntityResource($action($entity, $with));
    }

    /**
     * POST /api/v1/entities
     *
     * Create a new entity.
     */
    public function store(
        StoreEntityRequest $request,
        CreateEntityAction $action,
    ): EntityResource {
        $data = EntityData::fromArray($request->validated());
        $entity = $action($data, $request->user()?->id);

        return (new EntityResource($entity))
            ->response()
            ->setStatusCode(201)
            ->getOriginalContent();
    }

    /**
     * PUT /api/v1/entities/{entity}
     *
     * Update an existing entity. Supports partial updates.
     */
    public function update(
        string $entity,
        UpdateEntityRequest $request,
        UpdateEntityAction $action,
    ): EntityResource {
        $existing = Entity::where('entity_id', $entity)->firstOrFail();
        $data = EntityData::fromArray(
            array_merge(
                ['name' => $existing->name, 'entity_type' => $existing->entity_type->value, 'entity_group' => $existing->entity_group->value],
                $request->validated(),
            ),
        );

        return new EntityResource($action($existing, $data));
    }

    /**
     * DELETE /api/v1/entities/{entity}
     */
    public function destroy(
        string $entity,
        DeleteEntityAction $action,
    ): JsonResponse {
        $existing = Entity::where('entity_id', $entity)->firstOrFail();
        $action($existing);

        return response()->json(null, 204);
    }
}
