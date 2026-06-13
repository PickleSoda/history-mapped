<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Actions\Chronicle\GetEntityChroniclesAction;
use App\Http\Controllers\Controller;
use App\Models\Entity;
use Illuminate\Http\JsonResponse;

class EntityChronicleController extends Controller
{
    /**
     * GET /api/v1/entities/{entity}/chronicles
     *
     * Chronicles this entity appears in, each with the relationship ids it uses
     * (so the client can flag which of the entity's relationships are part of a
     * chronicle).
     */
    public function index(string $entity, GetEntityChroniclesAction $action): JsonResponse
    {
        Entity::where('entity_id', $entity)->firstOrFail();

        $chronicles = $action($entity);

        return response()->json([
            'data' => $chronicles->map(fn ($chronicle): array => [
                'chronicle_id' => $chronicle->chronicle_id,
                'title' => $chronicle->title,
                'slug' => $chronicle->slug,
                'relationship_ids' => $chronicle->entries
                    ->pluck('primary_relationship_id')
                    ->filter()
                    ->unique()
                    ->values()
                    ->all(),
            ])->all(),
        ]);
    }
}
