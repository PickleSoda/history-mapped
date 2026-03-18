<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Actions\Source\CreateSourceAction;
use App\DTOs\SourceData;
use App\Http\Api\V1\Requests\StoreSourceRequest;
use App\Http\Api\V1\Resources\SourceResource;
use App\Http\Controllers\Controller;
use App\Models\Source;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;

class SourceController extends Controller
{
    /**
     * GET /api/v1/sources
     *
     * List sources with optional search and pagination.
     */
    public function index(): AnonymousResourceCollection
    {
        $query = Source::query()->orderBy('created_at', 'desc');

        if ($search = request('search')) {
            $query->whereRaw(
                "to_tsvector('english', title) @@ plainto_tsquery('english', ?)",
                [$search],
            );
        }

        if ($type = request('source_type')) {
            $query->where('source_type', $type);
        }

        $perPage = min((int) request('per_page', 25), 100);

        return SourceResource::collection($query->paginate($perPage));
    }

    /**
     * GET /api/v1/sources/{source}
     */
    public function show(string $source): SourceResource
    {
        $model = Source::where('source_id', $source)->firstOrFail();

        return new SourceResource($model);
    }

    /**
     * POST /api/v1/sources
     */
    public function store(
        StoreSourceRequest $request,
        CreateSourceAction $action,
    ): JsonResponse {
        $data = SourceData::fromArray($request->validated());
        $source = $action($data);

        return (new SourceResource($source))
            ->response()
            ->setStatusCode(201);
    }
}
