<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin\Reference;

use App\Http\Controllers\Controller;
use App\Models\GeographicRegion;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class GeographicRegionController extends Controller
{
    /**
     * Display the geographic regions listing page.
     */
    public function index(Request $request): Response
    {
        $search = $request->string('search')->value() ?: null;

        $regions = GeographicRegion::query()
            ->with('parent')
            ->when($search, fn ($q) => $q->where('name', 'ilike', "%{$search}%"))
            ->orderBy('depth_level')
            ->orderBy('sort_order')
            ->orderBy('name')
            ->paginate($request->integer('per_page', 50))
            ->withQueryString();

        return Inertia::render('reference/geographic-regions', [
            'regions' => $regions->through(fn (GeographicRegion $region) => [
                'region_id' => $region->region_id,
                'name' => $region->name,
                'depth_level' => $region->depth_level,
                'parent_name' => $region->parent?->name,
                'modern_countries' => $region->modern_countries,
                'batch_priority' => $region->batch_priority,
                'sort_order' => $region->sort_order,
            ]),
            'filters' => [
                'search' => $search ?? '',
                'per_page' => $request->integer('per_page', 50),
            ],
        ]);
    }
}
