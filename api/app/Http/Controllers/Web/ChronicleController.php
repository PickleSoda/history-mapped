<?php

declare(strict_types=1);

namespace App\Http\Controllers\Web;

use App\Actions\Chronicle\CreateChronicleAction;
use App\Actions\Chronicle\DeleteChronicleAction;
use App\Actions\Chronicle\ListChroniclesAction;
use App\Actions\Chronicle\UpdateChronicleAction;
use App\DTOs\ChronicleData;
use App\Enums\ChronicleStatus;
use App\Enums\SourceType;
use App\Http\Controllers\Controller;
use App\Http\Requests\Web\StoreChronicleRequest;
use App\Http\Requests\Web\UpdateChronicleRequest;
use App\Models\Chronicle;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class ChronicleController extends Controller
{
    /**
     * Display the chronicle listing page.
     */
    public function index(Request $request, ListChroniclesAction $listChronicles): Response
    {
        $filters = [
            'search' => $request->string('search')->value() ?: null,
            'status' => $request->string('status')->value() ?: null,
            'page' => $request->integer('page', 1),
            'per_page' => $request->integer('per_page', 20),
        ];

        $chronicles = $listChronicles($filters);

        return Inertia::render('chronicles/index', [
            'chronicles' => [
                'data' => $chronicles->getCollection()->map(fn (Chronicle $c) => [
                    'chronicle_id' => $c->chronicle_id,
                    'title' => $c->title,
                    'slug' => $c->slug,
                    'status' => $c->status?->value,
                    'source_type' => $c->source_type?->value,
                    'entries_count' => $c->entries_count ?? 0,
                    'created_at' => $c->created_at?->toISOString(),
                ]),
                'links' => $chronicles->linkCollection()->toArray(),
                'meta' => [
                    'current_page' => $chronicles->currentPage(),
                    'per_page' => $chronicles->perPage(),
                    'total' => $chronicles->total(),
                    'last_page' => $chronicles->lastPage(),
                ],
            ],
            'filters' => [
                'search' => $filters['search'] ?? '',
                'status' => $filters['status'] ?? '',
            ],
        ]);
    }

    /**
     * Display a single chronicle detail page.
     */
    public function show(string $slug): Response
    {
        $chronicle = Chronicle::with([
            'entries.primaryRelationship.sourceEntity',
            'entries.primaryRelationship.targetEntity',
            'entries.secondaryEntities',
        ])
            ->where('slug', $slug)
            ->firstOrFail();

        return Inertia::render('chronicles/show', [
            'chronicle' => $this->serializeChronicle($chronicle),
        ]);
    }

    /**
     * Show the create chronicle form.
     */
    public function create(): Response
    {
        return Inertia::render('chronicles/create', [
            'statuses' => array_map(
                fn (ChronicleStatus $s) => ['value' => $s->value, 'label' => ucfirst($s->value)],
                ChronicleStatus::cases(),
            ),
            'sourceTypes' => array_map(
                fn (SourceType $s) => ['value' => $s->value, 'label' => str_replace('_', ' ', ucfirst($s->value))],
                SourceType::cases(),
            ),
        ]);
    }

    /**
     * Store a newly created chronicle.
     */
    public function store(StoreChronicleRequest $request, CreateChronicleAction $createChronicle): RedirectResponse
    {
        $data = ChronicleData::fromArray($request->validated());

        $chronicle = $createChronicle($data, (string) $request->user()->id);

        return redirect()
            ->route('chronicles.show', $chronicle->slug)
            ->with('success', 'Chronicle created successfully.');
    }

    /**
     * Show the edit form for an existing chronicle.
     */
    public function edit(string $slug): Response
    {
        $chronicle = Chronicle::with([
            'entries.primaryRelationship',
            'entries.secondaryEntities',
        ])
            ->where('slug', $slug)
            ->firstOrFail();

        return Inertia::render('chronicles/edit', [
            'chronicle' => $this->serializeChronicle($chronicle),
            'statuses' => array_map(
                fn (ChronicleStatus $s) => ['value' => $s->value, 'label' => ucfirst($s->value)],
                ChronicleStatus::cases(),
            ),
            'sourceTypes' => array_map(
                fn (SourceType $s) => ['value' => $s->value, 'label' => str_replace('_', ' ', ucfirst($s->value))],
                SourceType::cases(),
            ),
        ]);
    }

    /**
     * Update the specified chronicle.
     */
    public function update(UpdateChronicleRequest $request, string $slug, UpdateChronicleAction $updateChronicle): RedirectResponse
    {
        $chronicle = Chronicle::where('slug', $slug)->firstOrFail();

        $data = ChronicleData::fromArray($request->validated());

        $updated = $updateChronicle($chronicle, $data);

        return redirect()
            ->route('chronicles.show', $updated->slug)
            ->with('success', 'Chronicle updated successfully.');
    }

    /**
     * Remove the specified chronicle.
     */
    public function destroy(string $slug, DeleteChronicleAction $deleteChronicle): RedirectResponse
    {
        $chronicle = Chronicle::where('slug', $slug)->firstOrFail();

        $deleteChronicle($chronicle);

        return redirect()
            ->route('chronicles.index')
            ->with('success', 'Chronicle deleted successfully.');
    }

    /**
     * Serialize a Chronicle model for Inertia props.
     *
     * @return array<string, mixed>
     */
    private function serializeChronicle(Chronicle $chronicle): array
    {
        return [
            'chronicle_id' => $chronicle->chronicle_id,
            'title' => $chronicle->title,
            'slug' => $chronicle->slug,
            'source_type' => $chronicle->source_type?->value,
            'source_reference' => $chronicle->source_reference,
            'status' => $chronicle->status?->value,
            'metadata' => $chronicle->metadata,
            'created_by' => $chronicle->created_by,
            'created_at' => $chronicle->created_at?->toISOString(),
            'updated_at' => $chronicle->updated_at?->toISOString(),
            'entries' => $chronicle->relationLoaded('entries')
                ? $chronicle->entries->map(fn ($entry) => [
                    'entry_id' => $entry->entry_id,
                    'sequence_order' => $entry->sequence_order,
                    'narrative_text' => $entry->narrative_text,
                    'notes' => $entry->notes,
                    'source_evidence' => $entry->source_evidence,
                    'primary_relationship_id' => $entry->primary_relationship_id,
                    'secondary_entities' => $entry->relationLoaded('secondaryEntities')
                        ? $entry->secondaryEntities->map(fn ($e) => [
                            'entity_id' => $e->entity_id,
                            'name' => $e->name,
                            'role' => $e->pivot->role,
                        ])
                        : [],
                ])
                : [],
        ];
    }
}
