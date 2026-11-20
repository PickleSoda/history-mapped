<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Actions\Chronicle\GetChroniclePlacesAction;
use App\Http\Controllers\Controller;
use App\Models\Chronicle;
use Illuminate\Http\JsonResponse;

class ChroniclePlacesController extends Controller
{
    /**
     * GET /api/v1/chronicles/{slug}/places
     *
     * The map point and OpenHistoricalMap link of each of the chronicle's
     * entities, for the player's step layer.
     */
    public function show(string $slug, GetChroniclePlacesAction $action): JsonResponse
    {
        $chronicle = Chronicle::query()->where('slug', $slug)->notArchived()->firstOrFail();

        return response()->json(['data' => $action($chronicle)]);
    }
}
