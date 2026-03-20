<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin\Reference;

use App\Http\Controllers\Controller;
use App\Models\HistoricalPeriod;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class HistoricalPeriodController extends Controller
{
    /**
     * Display the historical periods listing page.
     */
    public function index(Request $request): Response
    {
        $search = $request->string('search')->value() ?: null;

        $periods = HistoricalPeriod::query()
            ->with('parent', 'region')
            ->when($search, fn ($q) => $q->where('name', 'ilike', "%{$search}%"))
            ->orderBy('depth_level')
            ->orderBy('sort_order')
            ->orderBy('start_date')
            ->paginate($request->integer('per_page', 50))
            ->withQueryString();

        return Inertia::render('reference/historical-periods', [
            'periods' => $periods->through(fn (HistoricalPeriod $period) => [
                'period_id' => $period->period_id,
                'name' => $period->name,
                'depth_level' => $period->depth_level,
                'parent_name' => $period->parent?->name,
                'start_date' => $period->start_date,
                'end_date' => $period->end_date,
                'geographic_scope' => $period->geographic_scope,
                'periodization_scheme' => $period->periodization_scheme,
                'region_name' => $period->region?->name,
                'color_hex' => $period->color_hex,
                'sort_order' => $period->sort_order,
            ]),
            'filters' => [
                'search' => $search ?? '',
                'per_page' => $request->integer('per_page', 50),
            ],
        ]);
    }
}
