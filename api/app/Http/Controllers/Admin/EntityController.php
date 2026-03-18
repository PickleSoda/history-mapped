<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin;

use App\Actions\Entity\ListEntitiesAction;
use App\DTOs\EntityFilterData;
use App\Enums\ConfidenceLevel;
use App\Enums\EntityGroup;
use App\Enums\VerificationStatus;
use App\Http\Controllers\Controller;
use App\Models\Entity;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class EntityController extends Controller
{
    /**
     * Display the entity listing page.
     */
    public function index(Request $request, ListEntitiesAction $listEntities): Response
    {
        $filters = new EntityFilterData(
            search: $request->string('search')->value() ?: null,
            group: $request->filled('group') ? EntityGroup::tryFrom($request->string('group')->value()) : null,
            status: $request->filled('status') ? VerificationStatus::tryFrom($request->string('status')->value()) : null,
            minConfidence: $request->filled('confidence') ? ConfidenceLevel::tryFrom($request->string('confidence')->value()) : null,
            sort: $request->string('sort')->value() ?: 'impact',
            perPage: $request->integer('per_page', 25),
            page: $request->integer('page', 1),
        );

        $entities = $listEntities($filters);

        return Inertia::render('entities/index', [
            'entities' => $entities->through(fn (Entity $entity) => [
                'id' => $entity->entity_id,
                'name' => $entity->name,
                'entity_type' => $entity->entity_type?->value,
                'entity_group' => $entity->entity_group?->value,
                'summary' => $entity->summary,
                'impact_score' => $entity->impact_score,
                'temporal_start' => $entity->temporal_start,
                'temporal_end' => $entity->temporal_end,
                'temporal_display_range' => $entity->temporal_display_range,
                'era_label' => $entity->era_label,
                'location_name' => $entity->location_name,
                'verification_status' => $entity->verification_status?->value,
                'confidence' => $entity->confidence?->value,
                'created_at' => $entity->created_at?->toISOString(),
            ]),
            'filters' => [
                'search' => $request->string('search')->value() ?: '',
                'group' => $request->string('group')->value() ?: '',
                'status' => $request->string('status')->value() ?: '',
                'confidence' => $request->string('confidence')->value() ?: '',
                'sort' => $request->string('sort')->value() ?: 'impact',
                'per_page' => $request->integer('per_page', 25),
            ],
            'filterOptions' => [
                'groups' => array_map(
                    fn (EntityGroup $g) => ['value' => $g->value, 'label' => $g->name],
                    EntityGroup::cases(),
                ),
                'statuses' => array_map(
                    fn (VerificationStatus $s) => ['value' => $s->value, 'label' => str_replace('_', ' ', ucfirst($s->value))],
                    VerificationStatus::cases(),
                ),
                'confidences' => array_map(
                    fn (ConfidenceLevel $c) => ['value' => $c->value, 'label' => ucfirst($c->value)],
                    ConfidenceLevel::cases(),
                ),
            ],
        ]);
    }

    /**
     * Display a single entity (placeholder).
     */
    public function show(Entity $entity): Response
    {
        return Inertia::render('entities/show', [
            'entity' => [
                'id' => $entity->entity_id,
                'name' => $entity->name,
                'entity_type' => $entity->entity_type?->value,
                'entity_group' => $entity->entity_group?->value,
                'summary' => $entity->summary,
                'impact_score' => $entity->impact_score,
                'temporal_display_range' => $entity->temporal_display_range,
                'location_name' => $entity->location_name,
                'verification_status' => $entity->verification_status?->value,
                'confidence' => $entity->confidence?->value,
            ],
        ]);
    }
}
