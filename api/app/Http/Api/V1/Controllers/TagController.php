<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Enums\TagFacet;
use App\Http\Controllers\Controller;
use App\Models\Tag;
use Illuminate\Http\JsonResponse;

class TagController extends Controller
{
    /**
     * GET /api/v1/tags
     *
     * The whole tag vocabulary with usage counts, for building tag pickers and
     * resolving the slugs that chronicle and entity payloads carry. Unused
     * topic tags are left out.
     */
    public function index(): JsonResponse
    {
        $tags = Tag::query()
            ->ordered()
            ->withCount(['chronicles', 'entities'])
            ->get()
            ->reject(fn (Tag $t): bool => $t->facet === TagFacet::Topic
                && $t->chronicles_count === 0 && $t->entities_count === 0);

        return response()->json([
            'data' => $tags->map(fn (Tag $t): array => [
                'slug' => $t->slug,
                'name' => $t->name,
                'facet' => $t->facet->value,
                'parent' => $t->parent_slug,
                'description' => $t->description,
                'start_year' => $t->start_year,
                'end_year' => $t->end_year,
                'chronicle_count' => $t->chronicles_count,
                'entity_count' => $t->entities_count,
            ])->values()->all(),
            'facets' => array_map(
                fn (TagFacet $f): array => ['key' => $f->value, 'label' => $f->label()],
                TagFacet::cases(),
            ),
        ])->header('Cache-Control', 'public, max-age=300');
    }
}
