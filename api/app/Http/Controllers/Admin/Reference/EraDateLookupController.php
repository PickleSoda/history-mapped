<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin\Reference;

use App\Http\Controllers\Controller;
use App\Models\EraDateLookup;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class EraDateLookupController extends Controller
{
    /**
     * Display the era date lookup listing page.
     */
    public function index(Request $request): Response
    {
        $search = $request->string('search')->value() ?: null;

        $lookups = EraDateLookup::query()
            ->with('period')
            ->when($search, fn ($q) => $q->where('search_term', 'ilike', "%{$search}%"))
            ->orderBy('search_term')
            ->paginate($request->integer('per_page', 50))
            ->withQueryString();

        return Inertia::render('reference/era-date-lookup', [
            'lookups' => $lookups->through(fn (EraDateLookup $lookup) => [
                'lookup_id' => $lookup->lookup_id,
                'search_term' => $lookup->search_term,
                'resolved_start' => $lookup->resolved_start,
                'resolved_end' => $lookup->resolved_end,
                'geographic_scope' => $lookup->geographic_scope,
                'confidence' => $lookup->confidence,
                'period_name' => $lookup->period?->name,
            ]),
            'filters' => [
                'search' => $search ?? '',
                'per_page' => $request->integer('per_page', 50),
            ],
        ]);
    }
}
