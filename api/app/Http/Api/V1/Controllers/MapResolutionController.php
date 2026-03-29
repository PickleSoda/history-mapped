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
}
