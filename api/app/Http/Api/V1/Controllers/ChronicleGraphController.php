<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Actions\Graph\GetChronicleGraphAction;
use App\Http\Api\V1\Requests\ChronicleGraphRequest;
use App\Http\Controllers\Controller;
use App\Models\Chronicle;
use Illuminate\Http\JsonResponse;

class ChronicleGraphController extends Controller
{
    /**
     * GET /api/v1/chronicles/{slug}/graph
     *
     * Whole-chronicle entity/relation graph with per-step membership.
     */
    public function show(string $slug, ChronicleGraphRequest $request, GetChronicleGraphAction $action): JsonResponse
    {
        $chronicle = Chronicle::query()->where('slug', $slug)->firstOrFail();

        return response()->json(['data' => $action($chronicle, $request->validated())]);
    }
}
