<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin\Reference;

use App\Http\Controllers\Controller;
use App\Models\SourceTypeDefinition;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class SourceTypeDefinitionController extends Controller
{
    /**
     * Display the source type definitions listing page.
     */
    public function index(Request $request): Response
    {
        $search = $request->string('search')->value() ?: null;

        $definitions = SourceTypeDefinition::query()
            ->when($search, fn ($q) => $q->where('enum_name', 'ilike', "%{$search}%")
                ->orWhere('description', 'ilike', "%{$search}%"))
            ->orderBy('enum_name')
            ->paginate($request->integer('per_page', 50))
            ->withQueryString();

        return Inertia::render('reference/source-type-definitions', [
            'definitions' => $definitions->through(fn (SourceTypeDefinition $definition) => [
                'definition_id' => $definition->definition_id,
                'enum_name' => $definition->enum_name,
                'enum_value' => $definition->enum_value,
                'description' => $definition->description,
                'default_confidence' => $definition->default_confidence,
                'requires_corroboration' => $definition->requires_corroboration,
                'weight_in_scoring' => $definition->weight_in_scoring,
            ]),
            'filters' => [
                'search' => $search ?? '',
                'per_page' => $request->integer('per_page', 50),
            ],
        ]);
    }
}
