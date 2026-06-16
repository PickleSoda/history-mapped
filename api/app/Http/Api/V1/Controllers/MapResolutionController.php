<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Actions\EntityGeoRef\ResolveOhmFeatureAction;
use App\Http\Api\V1\Requests\ResolveOhmFeatureRequest;
use App\Http\Controllers\Controller;
use Illuminate\Database\Eloquent\ModelNotFoundException;
use Illuminate\Http\JsonResponse;

class MapResolutionController extends Controller
{
    public function resolveOhmFeature(
        ResolveOhmFeatureRequest $request,
        ResolveOhmFeatureAction $action,
    ): JsonResponse {
        try {
            $result = $action->__invoke($request->validated());
        } catch (ModelNotFoundException) {
            return response()->json([
                'message' => 'No matching active geography reference was found.',
            ], 404);
        }

        return response()->json([
            'data' => $result,
        ]);
    }

    /**
     * Read-only counterpart of {@see resolveOhmFeature()} for the public atlas
     * GET route. It shares the same logic but is a distinct controller action so
     * Wayfinder generates a separate, non-colliding route helper (one method
     * bound to both a GET and a POST at the same URL collides during generation).
     */
    public function showOhmFeature(
        ResolveOhmFeatureRequest $request,
        ResolveOhmFeatureAction $action,
    ): JsonResponse {
        return $this->resolveOhmFeature($request, $action);
    }
}
