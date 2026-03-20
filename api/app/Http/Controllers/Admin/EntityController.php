<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin;

use App\Actions\Entity\ListEntitiesAction;
use App\DTOs\EntityFilterData;
use App\Enums\ConfidenceLevel;
use App\Enums\EntityGroup;
use App\Enums\EntityType;
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
            type: $request->filled('type') ? EntityType::tryFrom($request->string('type')->value()) : null,
            group: $request->filled('group') ? EntityGroup::tryFrom($request->string('group')->value()) : null,
            status: $request->filled('status') ? VerificationStatus::tryFrom($request->string('status')->value()) : null,
            minConfidence: $request->filled('confidence') ? ConfidenceLevel::tryFrom($request->string('confidence')->value()) : null,
            temporalStart: $request->filled('date_from') ? $request->string('date_from')->value() : null,
            temporalEnd: $request->filled('date_to') ? $request->string('date_to')->value() : null,
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
                'temporal_display_range' => $entity->temporal_display_range
                    ?? self::computeTemporalRange($entity->temporal_start, $entity->temporal_end),
                'era_label' => $entity->era_label,
                'location_name' => $entity->location_name,
                'verification_status' => $entity->verification_status?->value,
                'confidence' => $entity->confidence?->value,
                'created_at' => $entity->created_at?->toISOString(),
            ]),
            'filters' => [
                'search' => $request->string('search')->value() ?: '',
                'type' => $request->string('type')->value() ?: '',
                'group' => $request->string('group')->value() ?: '',
                'status' => $request->string('status')->value() ?: '',
                'confidence' => $request->string('confidence')->value() ?: '',
                'date_from' => $request->string('date_from')->value() ?: '',
                'date_to' => $request->string('date_to')->value() ?: '',
                'sort' => $request->string('sort')->value() ?: 'impact',
                'per_page' => $request->integer('per_page', 25),
            ],
            'filterOptions' => [
                'types' => array_map(
                    fn (EntityType $t) => ['value' => $t->value, 'label' => self::formatEnumLabel($t->name)],
                    EntityType::cases(),
                ),
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
                'temporal_display_range' => $entity->temporal_display_range
                    ?? self::computeTemporalRange($entity->temporal_start, $entity->temporal_end),
                'location_name' => $entity->location_name,
                'verification_status' => $entity->verification_status?->value,
                'confidence' => $entity->confidence?->value,
            ],
        ]);
    }

    /**
     * Compute a human-readable temporal range from raw start/end year strings.
     *
     * Year strings are integers (possibly negative for BCE).
     * Returns null if both values are absent.
     */
    private static function computeTemporalRange(?string $start, ?string $end): ?string
    {
        if ($start === null && $end === null) {
            return null;
        }

        $formatYear = static function (?string $year): ?string {
            if ($year === null || $year === '') {
                return null;
            }

            $int = (int) $year;

            return $int < 0 ? abs($int) . ' BCE' : $int . ' CE';
        };

        $startLabel = $formatYear($start);
        $endLabel = $formatYear($end);

        if ($startLabel !== null && $endLabel !== null) {
            return $startLabel . ' – ' . $endLabel;
        }

        if ($startLabel !== null) {
            return 'From ' . $startLabel;
        }

        return 'Until ' . $endLabel;
    }

    /**
     * Convert a PascalCase enum name to a human-readable label.
     * e.g. "EventNaturalDisaster" → "Event Natural Disaster"
     */
    private static function formatEnumLabel(string $name): string
    {
        return trim((string) preg_replace('/(?<=[a-z])(?=[A-Z])/', ' ', $name));
    }
}
