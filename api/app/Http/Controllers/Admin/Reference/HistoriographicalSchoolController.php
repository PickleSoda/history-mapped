<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin\Reference;

use App\Http\Controllers\Controller;
use App\Models\HistoriographicalSchool;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class HistoriographicalSchoolController extends Controller
{
    /**
     * Display the historiographical schools listing page.
     */
    public function index(Request $request): Response
    {
        $search = $request->string('search')->value() ?: null;

        $schools = HistoriographicalSchool::query()
            ->when($search, fn ($q) => $q->where('name', 'ilike', "%{$search}%"))
            ->orderBy('sort_order')
            ->orderBy('name')
            ->paginate($request->integer('per_page', 50))
            ->withQueryString();

        return Inertia::render('reference/historiographical-schools', [
            'schools' => $schools->through(fn (HistoriographicalSchool $school) => [
                'school_id' => $school->school_id,
                'name' => $school->name,
                'active_from' => $school->active_from,
                'active_to' => $school->active_to,
                'interpretive_framework' => $school->interpretive_framework,
                'geographic_center' => $school->geographic_center,
                'sort_order' => $school->sort_order,
            ]),
            'filters' => [
                'search' => $search ?? '',
                'per_page' => $request->integer('per_page', 50),
            ],
        ]);
    }
}
