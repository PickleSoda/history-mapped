<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Http\Api\V1\Resources\GeometrySnapshotMapResource;
use App\Http\Api\V1\Resources\GeometrySnapshotResource;
use App\Http\Controllers\Controller;
use App\Models\Entity;
use App\Models\GeometryPeriod;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;

class GeometrySnapshotController extends Controller
{
    /**
     * Legacy read endpoint retained for compatibility.
     */
    public function index(Entity $entity): AnonymousResourceCollection
    {
        $periods = GeometryPeriod::query()
            ->where('entity_id', $entity->entity_id)
            ->orderBy('start_year')
            ->orderBy('end_year')
            ->orderBy('created_at')
            ->get();

        return GeometrySnapshotResource::collection($periods);
    }

    /**
     * Legacy read endpoint retained for compatibility.
     */
    public function atYear(Entity $entity, int $year): GeometrySnapshotMapResource
    {
        $period = GeometryPeriod::query()
            ->where('entity_id', $entity->entity_id)
            ->where('start_year', '<=', $year)
            ->where('end_year', '>=', $year)
            ->orderBy('start_year')
            ->orderBy('end_year')
            ->firstOrFail();

        return new GeometrySnapshotMapResource($period);
    }
}
