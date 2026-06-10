<?php

declare(strict_types=1);

namespace App\Http\Controllers\Api\V1;

use App\Http\Api\V1\Resources\ChronicleResource;
use App\Models\Chronicle;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class ChronicleController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        $chronicles = Chronicle::withCount('entries')
            ->orderByDesc('created_at')
            ->paginate($request->input('per_page', 20));

        return ChronicleResource::collection($chronicles)->response();
    }

    public function show(string $slug): JsonResponse
    {
        $chronicle = Chronicle::with([
            'entries.primaryRelationship.sourceEntity',
            'entries.primaryRelationship.targetEntity',
            'entries.secondaryEntities',
        ])
            ->where('slug', $slug)
            ->firstOrFail();

        return (new ChronicleResource($chronicle))->response();
    }
}
