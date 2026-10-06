<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Actions\Graph\GetEntityGraphAction;
use App\Http\Api\V1\Requests\EntityGraphRequest;
use App\Http\Controllers\Controller;
use App\Models\Entity;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Str;

class EntityGraphController extends Controller
{
    /**
     * GET /api/v1/entities/{entity}/graph
     *
     * Relation neighbourhood (1-2 hops) of an entity as nodes + edges.
     */
    public function show(string $entity, EntityGraphRequest $request, GetEntityGraphAction $action): JsonResponse
    {
        abort_unless(Str::isUuid($entity) && Entity::query()->whereKey($entity)->exists(), 404);

        return response()->json(['data' => $action($entity, $request->validated())]);
    }
}
