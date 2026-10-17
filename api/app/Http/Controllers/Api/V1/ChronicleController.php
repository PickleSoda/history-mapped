<?php

declare(strict_types=1);

namespace App\Http\Controllers\Api\V1;

use App\Actions\Chronicle\ListChroniclesAction;
use App\Http\Api\V1\Requests\ListChroniclesRequest;
use App\Http\Api\V1\Resources\ChronicleResource;
use App\Http\Controllers\Controller;
use App\Models\Chronicle;
use App\Models\EntityRelationship;
use Illuminate\Http\JsonResponse;

class ChronicleController extends Controller
{
    public function index(ListChroniclesRequest $request, ListChroniclesAction $listChronicles): JsonResponse
    {
        $chronicles = $listChronicles($request->validated());

        return ChronicleResource::collection($chronicles)->response();
    }

    public function show(string $slug): JsonResponse
    {
        $chronicle = Chronicle::with([
            ...EntityRelationship::withSummaryEnds('entries.primaryRelationship.'),
            'entries.secondaryEntities',
            'tags',
        ])
            ->where('slug', $slug)
            ->firstOrFail();

        return (new ChronicleResource($chronicle))->response();
    }
}
