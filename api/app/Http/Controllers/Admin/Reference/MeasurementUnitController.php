<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin\Reference;

use App\Http\Controllers\Controller;
use App\Models\MeasurementUnit;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class MeasurementUnitController extends Controller
{
    /**
     * Display the measurement units listing page.
     */
    public function index(Request $request): Response
    {
        $search = $request->string('search')->value() ?: null;
        $type = $request->string('type')->value() ?: null;

        $units = MeasurementUnit::query()
            ->when($search, fn ($q) => $q->where('name', 'ilike', "%{$search}%")
                ->orWhere('symbol', 'ilike', "%{$search}%"))
            ->when($type, fn ($q) => $q->where('measurement_type', $type))
            ->orderBy('measurement_type')
            ->orderBy('sort_order')
            ->orderBy('name')
            ->paginate($request->integer('per_page', 50))
            ->withQueryString();

        $types = MeasurementUnit::query()
            ->distinct()
            ->orderBy('measurement_type')
            ->pluck('measurement_type')
            ->filter()
            ->values();

        return Inertia::render('reference/measurement-units', [
            'units' => $units->through(fn (MeasurementUnit $unit) => [
                'unit_id' => $unit->unit_id,
                'name' => $unit->name,
                'symbol' => $unit->symbol,
                'measurement_type' => $unit->measurement_type,
                'si_equivalent' => $unit->si_equivalent,
                'si_unit' => $unit->si_unit,
                'used_by_region' => $unit->used_by_region,
                'used_by_period' => $unit->used_by_period,
                'approximate' => $unit->approximate,
            ]),
            'filters' => [
                'search' => $search ?? '',
                'type' => $type ?? '',
                'per_page' => $request->integer('per_page', 50),
            ],
            'types' => $types,
        ]);
    }
}
