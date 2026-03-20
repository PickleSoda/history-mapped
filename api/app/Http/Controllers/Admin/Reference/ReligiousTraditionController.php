<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin\Reference;

use App\Http\Controllers\Controller;
use App\Models\ReligiousTradition;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class ReligiousTraditionController extends Controller
{
    /**
     * Display the religious traditions listing page.
     */
    public function index(Request $request): Response
    {
        $search = $request->string('search')->value() ?: null;

        $traditions = ReligiousTradition::query()
            ->with('parent')
            ->when($search, fn ($q) => $q->where('name', 'ilike', "%{$search}%"))
            ->orderBy('depth_level')
            ->orderBy('sort_order')
            ->orderBy('name')
            ->paginate($request->integer('per_page', 50))
            ->withQueryString();

        return Inertia::render('reference/religious-traditions', [
            'traditions' => $traditions->through(fn (ReligiousTradition $tradition) => [
                'tradition_id' => $tradition->tradition_id,
                'name' => $tradition->name,
                'depth_level' => $tradition->depth_level,
                'parent_name' => $tradition->parent?->name,
                'tradition_type' => $tradition->tradition_type,
                'origin_date' => $tradition->origin_date,
                'origin_region' => $tradition->origin_region,
                'founder' => $tradition->founder,
                'color_hex' => $tradition->color_hex,
                'sort_order' => $tradition->sort_order,
            ]),
            'filters' => [
                'search' => $search ?? '',
                'per_page' => $request->integer('per_page', 50),
            ],
        ]);
    }
}
