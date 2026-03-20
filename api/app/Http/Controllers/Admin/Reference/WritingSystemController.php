<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin\Reference;

use App\Http\Controllers\Controller;
use App\Models\WritingSystem;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class WritingSystemController extends Controller
{
    /**
     * Display the writing systems listing page.
     */
    public function index(Request $request): Response
    {
        $search = $request->string('search')->value() ?: null;

        $systems = WritingSystem::query()
            ->with('derivedFrom')
            ->when($search, fn ($q) => $q->where('name', 'ilike', "%{$search}%"))
            ->orderBy('name')
            ->paginate($request->integer('per_page', 50))
            ->withQueryString();

        return Inertia::render('reference/writing-systems', [
            'systems' => $systems->through(fn (WritingSystem $system) => [
                'system_id' => $system->system_id,
                'name' => $system->name,
                'code' => $system->code,
                'system_type' => $system->system_type,
                'direction' => $system->direction,
                'origin_date' => $system->origin_date,
                'derived_from_name' => $system->derivedFrom?->name,
                'still_in_use' => $system->still_in_use,
            ]),
            'filters' => [
                'search' => $search ?? '',
                'per_page' => $request->integer('per_page', 50),
            ],
        ]);
    }
}
