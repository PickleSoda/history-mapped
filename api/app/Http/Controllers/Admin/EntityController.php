<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin;

use App\Actions\Entity\CreateEntityAction;
use App\Actions\Entity\DeleteEntityAction;
use App\Actions\Entity\ListEntitiesAction;
use App\Actions\Entity\UpdateEntityAction;
use App\DTOs\EntityData;
use App\DTOs\EntityFilterData;
use App\Enums\ConfidenceLevel;
use App\Enums\DateResolutionMethod;
use App\Enums\DurationType;
use App\Enums\EntityGroup;
use App\Enums\EntityType;
use App\Enums\IconClass;
use App\Enums\LocationResolutionMethod;
use App\Enums\VerificationStatus;
use App\Http\Controllers\Controller;
use App\Http\Requests\Admin\StoreEntityRequest;
use App\Http\Requests\Admin\UpdateEntityRequest;
use App\Models\Entity;
use Illuminate\Http\RedirectResponse;
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
            temporalStart: $request->filled('date_from') ? (int) $request->string('date_from')->value() : null,
            temporalEnd: $request->filled('date_to') ? (int) $request->string('date_to')->value() : null,
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
                'temporal_display_range' => ($entity->attributes['temporal_display_range'] ?? null)
                    ?? self::computeTemporalRange($entity->temporal_start, $entity->temporal_end),
                'era_label' => $entity->attributes['era_label'] ?? null,
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
     * Show the create entity form.
     */
    public function create(): Response
    {
        return Inertia::render('entities/create', [
            'formOptions' => self::buildFormOptions(),
        ]);
    }

    /**
     * Store a newly created entity.
     */
    public function store(StoreEntityRequest $request, CreateEntityAction $createEntity): RedirectResponse
    {
        $validated = $request->validated();

        $data = EntityData::fromArray(array_merge($validated, [
            'attributes' => $validated['attributes'] ?? null,
        ]));

        $entity = $createEntity($data, (string) $request->user()->id);

        return redirect()
            ->route('entities.show', $entity->entity_id)
            ->with('success', 'Entity created successfully.');
    }

    /**
     * Display a single entity detail page.
     */
    public function show(Entity $entity): Response
    {
        return Inertia::render('entities/show', [
            'entity' => self::buildEntityDetail($entity),
        ]);
    }

    /**
     * Show the edit form for an existing entity.
     */
    public function edit(Entity $entity): Response
    {
        return Inertia::render('entities/edit', [
            'entity' => self::buildEntityDetail($entity),
            'formOptions' => self::buildFormOptions(),
        ]);
    }

    /**
     * Update an existing entity.
     */
    public function update(UpdateEntityRequest $request, Entity $entity, UpdateEntityAction $updateEntity): RedirectResponse
    {
        $validated = $request->validated();

        $data = EntityData::fromArray(array_merge(
            // Seed with current values so fromArray required fields are satisfied
            [
                'name' => $entity->name,
                'entity_type' => $entity->entity_type?->value,
                'entity_group' => $entity->entity_group?->value,
            ],
            $validated,
            ['attributes' => $validated['attributes'] ?? null],
        ));

        $updateEntity($entity, $data);

        return redirect()
            ->route('entities.show', $entity->entity_id)
            ->with('success', 'Entity updated successfully.');
    }

    /**
     * Delete an entity.
     */
    public function destroy(Entity $entity, DeleteEntityAction $deleteEntity): RedirectResponse
    {
        $deleteEntity($entity);

        return redirect()
            ->route('entities.index')
            ->with('success', 'Entity deleted.');
    }

    // ── Private helpers ──────────────────────────────────────────────────────

    /**
     * Build the full entity detail array for show/edit pages.
     *
     * @return array<string, mixed>
     */
    private static function buildEntityDetail(Entity $entity): array
    {
        $entity->loadMissing(['primaryTemporalRange', 'primaryLocation', 'entityTags', 'aliases']);

        return [
            'id' => $entity->entity_id,
            'name' => $entity->name,
            'entity_type' => $entity->entity_type?->value,
            'entity_group' => $entity->entity_group?->value,
            'summary' => $entity->summary,
            'significance' => $entity->significance,
            'impact_score' => $entity->impact_score,
            'wikidata_id' => $entity->wikidata_id,
            'temporal_start' => $entity->primaryTemporalRange?->start_date,
            'temporal_end' => $entity->primaryTemporalRange?->end_date,
            'date_raw' => $entity->attributes['date_raw'] ?? null,
            'date_method' => $entity->date_method?->value,
            'date_confidence' => $entity->date_confidence?->value,
            'duration_type' => $entity->duration_type?->value,
            'temporal_display_range' => ($entity->attributes['temporal_display_range'] ?? null)
                ?? self::computeTemporalRange($entity->primaryTemporalRange?->start_date, $entity->primaryTemporalRange?->end_date),
            'location_name' => $entity->primaryLocation?->location_name,
            'location_confidence' => $entity->location_confidence?->value,
            'location_method' => $entity->location_method?->value,
            'verification_status' => $entity->verification_status?->value,
            'confidence' => $entity->confidence?->value,
            'confidence_notes' => $entity->attributes['confidence_notes'] ?? null,
            'display_priority' => $entity->display_priority,
            'icon_class' => $entity->icon_class?->value,
            'entity_color' => $entity->attributes['entity_color'] ?? null,
            'tags' => $entity->entityTags->pluck('tag')->values()->all(),
            'alternative_names' => $entity->aliases->pluck('name')->values()->all(),
            'attributes' => $entity->attributes ?? [],
            'era_label' => $entity->attributes['era_label'] ?? null,
            'geojson' => $entity->primaryLocation?->geom,
            'territory_geojson' => $entity->primaryLocation?->territory_geom,
            'geometry_periods_url' => route('entities.geometry-periods.index', $entity),
            'created_at' => $entity->created_at?->toISOString(),
            'updated_at' => $entity->updated_at?->toISOString(),
        ];
    }

    /**
     * Build the enum option lists passed to create/edit form pages.
     *
     * @return array<string, list<array{value: string, label: string}>>
     */
    private static function buildFormOptions(): array
    {
        return [
            'types' => array_map(
                fn (EntityType $t) => [
                    'value' => $t->value,
                    'label' => self::formatEnumLabel($t->name),
                    'group' => $t->group()->value,
                ],
                EntityType::cases(),
            ),
            'groups' => array_map(
                fn (EntityGroup $g) => ['value' => $g->value, 'label' => $g->name],
                EntityGroup::cases(),
            ),
            'statuses' => array_map(
                fn (VerificationStatus $s) => ['value' => $s->value, 'label' => self::formatEnumLabel($s->name)],
                VerificationStatus::cases(),
            ),
            'confidences' => array_map(
                fn (ConfidenceLevel $c) => ['value' => $c->value, 'label' => ucfirst($c->value)],
                ConfidenceLevel::cases(),
            ),
            'dateMethods' => array_map(
                fn (DateResolutionMethod $m) => ['value' => $m->value, 'label' => self::formatEnumLabel($m->name)],
                DateResolutionMethod::cases(),
            ),
            'durationTypes' => array_map(
                fn (DurationType $d) => ['value' => $d->value, 'label' => self::formatEnumLabel($d->name)],
                DurationType::cases(),
            ),
            'locationMethods' => array_map(
                fn (LocationResolutionMethod $m) => ['value' => $m->value, 'label' => self::formatEnumLabel($m->name)],
                LocationResolutionMethod::cases(),
            ),
            'iconClasses' => array_map(
                fn (IconClass $i) => ['value' => $i->value, 'label' => self::formatEnumLabel($i->name)],
                IconClass::cases(),
            ),
        ];
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

            return $int < 0 ? abs($int).' BCE' : $int.' CE';
        };

        $startLabel = $formatYear($start);
        $endLabel = $formatYear($end);

        if ($startLabel !== null && $endLabel !== null) {
            return $startLabel.' – '.$endLabel;
        }

        if ($startLabel !== null) {
            return 'From '.$startLabel;
        }

        return 'Until '.$endLabel;
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
