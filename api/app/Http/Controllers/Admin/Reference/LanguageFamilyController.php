<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin\Reference;

use App\Http\Controllers\Controller;
use App\Models\LanguageFamily;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class LanguageFamilyController extends Controller
{
    /**
     * Display the language families listing page.
     */
    public function index(Request $request): Response
    {
        $search = $request->string('search')->value() ?: null;

        $families = LanguageFamily::query()
            ->with('parent')
            ->when($search, fn ($q) => $q->where('name', 'ilike', "%{$search}%"))
            ->orderBy('depth_level')
            ->orderBy('sort_order')
            ->orderBy('name')
            ->paginate($request->integer('per_page', 50))
            ->withQueryString();

        return Inertia::render('reference/language-families', [
            'families' => $families->through(fn (LanguageFamily $family) => [
                'family_id' => $family->family_id,
                'name' => $family->name,
                'depth_level' => $family->depth_level,
                'parent_name' => $family->parent?->name,
                'proto_language' => $family->proto_language,
                'estimated_origin' => $family->estimated_origin,
                'estimated_homeland' => $family->estimated_homeland,
                'living_languages' => $family->living_languages,
                'status' => $family->status,
                'sort_order' => $family->sort_order,
            ]),
            'filters' => [
                'search' => $search ?? '',
                'per_page' => $request->integer('per_page', 50),
            ],
        ]);
    }
}
