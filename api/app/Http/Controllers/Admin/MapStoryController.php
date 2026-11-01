<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin;

use App\Actions\MapStory\CheckMapStoryAction;
use App\Actions\MapStory\CreateMapStoryAction;
use App\Actions\MapStory\SaveMapStoryAction;
use App\Http\Controllers\Controller;
use App\Models\Chronicle;
use App\Models\Entity;
use App\Models\MapStory;
use App\Support\MapStory\MapStoryAmbient;
use App\Support\MapStory\MapStoryFile;
use App\Support\MapStory\MapStoryVocabulary as V;
use App\Support\MapStory\MapStoryWarnings;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\Rule;
use Inertia\Inertia;
use Inertia\Response;
use stdClass;

/**
 * The admin's map-story editor: the list, a split editor (structured form +
 * the public SPA as a live preview), whole-document saves with errors and
 * warnings, a dry-run validation, creation from an entity or a chronicle,
 * and deletion. Every write goes through the MapStory actions; revisions are
 * in MapStoryRevisionController. The DB row is the live copy — see
 * docs/implementation-docs/map-story-authoring.md § Editing.
 */
class MapStoryController extends Controller
{
    public function index(Request $request): Response
    {
        $search = trim($request->string('search')->value());
        $kind = $request->string('kind')->value();
        $edited = $request->string('edited')->value();

        $stories = MapStory::query()
            ->with(['entity:entity_id,name', 'chronicle:chronicle_id,slug,title', 'editor:id,name'])
            ->when($search !== '', fn ($q) => $q->where(fn ($q) => $q->where('title', 'ilike', "%{$search}%")->orWhere('slug', 'ilike', "%{$search}%")))
            ->when(in_array($kind, V::STORY_KINDS, true), fn ($q) => $q->where('kind', $kind))
            ->when($edited === '1', fn ($q) => $q->edited())
            ->when($edited === '0', fn ($q) => $q->whereNotIn('story_id', MapStory::query()->edited()->select('story_id')))
            ->orderByDesc(DB::raw('COALESCE(edited_at, updated_at)'))
            ->paginate(25, ['story_id', 'entity_id', 'chronicle_id', 'slug', 'kind', 'title', 'year', 'step_count', 'ambient', 'source_path', 'synced_at', 'edited_at', 'edited_by', 'updated_at'])
            ->withQueryString();

        return Inertia::render('map-stories/index', [
            'stories' => $stories->through(fn (MapStory $s) => self::summary($s)),
            'filters' => ['search' => $search, 'kind' => $kind, 'edited' => $edited],
            'kinds' => V::STORY_KINDS,
        ]);
    }

    /** The story page is its editor. */
    public function show(string $slug): RedirectResponse
    {
        return redirect()->route('map-stories.edit', $slug);
    }

    public function edit(Request $request, string $slug): Response
    {
        $story = $this->story($slug);
        $story->loadMissing(['entity:entity_id,name,wikidata_id', 'chronicle:chronicle_id,slug,title', 'editor:id,name']);
        $authored = MapStoryFile::authored($story->document);

        return Inertia::render('map-stories/edit', [
            'story' => self::summary($story),
            // A JSON string, so the editor gets the document exactly (empty objects stay {}).
            'document_json' => json_encode($authored, MapStoryFile::JSON_FLAGS),
            'warnings' => MapStoryWarnings::of(MapStoryFile::toArray($authored)),
            'entries' => $story->chronicle_id === null ? [] : DB::table('chronicle_entries')
                ->where('chronicle_id', $story->chronicle_id)
                ->orderBy('sequence_order')
                ->get(['sequence_order', 'start_year', DB::raw('left(narrative_text, 90) as text')])
                ->map(fn (object $e) => ['sequence_order' => (int) $e->sequence_order, 'start_year' => $e->start_year, 'text' => $e->text]),
            'linked' => self::linked($authored),
            'vocabulary' => self::vocabulary(),
            // The atlas (the editor adds ?story=…&sstep=0&preview=1).
            'preview_url' => config('app.frontend_url').'/app',
            'can_edit' => (bool) $request->user()?->can('entities.write'),
            'ai_context' => $story->entity_id !== null
                ? ['type' => 'entity', 'id' => $story->entity_id]
                : ['type' => 'chronicle', 'id' => $story->chronicle_id],
        ]);
    }

    /**
     * Atlas entities for the editor's pickers: by name (or a Q-id), most
     * prominent first, with their Q-id and years.
     */
    public function entities(Request $request): JsonResponse
    {
        $q = trim($request->string('q')->value());
        if (mb_strlen($q) < 2) {
            return response()->json(['data' => []]);
        }
        $rows = Entity::query()
            ->with('primaryTemporalRange:entity_id,start_year,end_year')
            ->when(preg_match('/^Q[1-9][0-9]*$/i', $q) === 1,
                fn ($query) => $query->where('wikidata_id', strtoupper($q)),
                fn ($query) => $query->where('name', 'ilike', '%'.addcslashes($q, '%_\\').'%'))
            ->orderByRaw('impact_score DESC NULLS LAST')
            ->limit(12)
            ->get(['entity_id', 'name', 'wikidata_id', 'entity_type']);

        return response()->json(['data' => $rows->map(fn (Entity $e) => [
            'id' => $e->entity_id,
            'name' => $e->name,
            'wikidata' => $e->wikidata_id,
            'type' => $e->entity_type?->value,
            'start_year' => $e->primaryTemporalRange?->start_year,
            'end_year' => $e->primaryTemporalRange?->end_year,
        ])]);
    }

    /** A new story for an entity or a chronicle: a skeleton to fill in the editor. */
    public function store(Request $request, CreateMapStoryAction $create): RedirectResponse
    {
        $data = $request->validate([
            'entity_id' => ['required_without:chronicle_id', 'nullable', 'uuid', 'exists:entities,entity_id'],
            'chronicle_id' => ['required_without:entity_id', 'nullable', 'uuid', 'exists:chronicles,chronicle_id'],
            'kind' => ['required', Rule::in(V::STORY_KINDS)],
            'title' => ['required', 'string', 'max:120'],
            'year' => ['required', 'integer', 'between:-10000,2100'],
        ]);
        $owner = isset($data['entity_id'])
            ? Entity::query()->findOrFail($data['entity_id'])
            : Chronicle::query()->findOrFail($data['chronicle_id']);

        $result = $create($owner, $data['kind'], $data['title'], (int) $data['year'], source: 'admin', userId: $request->user()?->id);
        if ($result['errors'] !== [] || $result['story'] === null) {
            return back()->withErrors(['story' => implode(' · ', $result['errors'])]);
        }

        return redirect()->route('map-stories.edit', $result['story']->slug)->with('success', 'Map story created — fill it in and save.');
    }

    /** Save the whole document; errors block it (422), warnings come back. */
    public function update(Request $request, string $slug, SaveMapStoryAction $save): JsonResponse
    {
        $story = $this->story($slug);
        $data = $request->validate([
            'document' => ['required', 'string'],
            'note' => ['nullable', 'string', 'max:500'],
        ]);
        $document = MapStoryFile::decode($data['document']);
        if ($document === null) {
            return response()->json(['errors' => ['document: not a JSON object'], 'warnings' => []], 422);
        }

        $result = $save($story, $document, 'admin', $request->user()?->id, $data['note'] ?? null);
        if ($result['errors'] !== []) {
            return response()->json(['errors' => $result['errors'], 'warnings' => []], 422);
        }

        return response()->json(self::saved($result['story'], $result['warnings']));
    }

    /** A dry run of a save: the errors and warnings, nothing written. */
    public function validateDocument(Request $request, string $slug, CheckMapStoryAction $check): JsonResponse
    {
        $story = $this->story($slug);
        $data = $request->validate(['document' => ['required', 'string']]);
        $document = MapStoryFile::decode($data['document']);
        if ($document === null) {
            return response()->json(['errors' => ['document: not a JSON object'], 'warnings' => []]);
        }

        return response()->json($check($document, $story));
    }

    /** Hard-delete the row (its revisions go with it). A file of the same slug re-seeds it on the next sync. */
    public function destroy(string $slug): RedirectResponse
    {
        $story = $this->story($slug);
        $story->delete();
        $file = $story->source_path !== null ? " Its file ({$story->source_path}) will re-create it on the next map-stories:sync unless you delete the file too." : '';

        return redirect()->route('map-stories.index')->with('success', "Deleted '{$story->title}'.{$file}");
    }

    public function story(string $slug): MapStory
    {
        return MapStory::query()->where('slug', $slug)->firstOrFail();
    }

    /**
     * The response to a successful save or restore.
     *
     * @param  list<string>  $warnings
     * @return array<string, mixed>
     */
    public static function saved(MapStory $story, array $warnings): array
    {
        $story->loadMissing(['entity:entity_id,name', 'chronicle:chronicle_id,slug,title', 'editor:id,name']);

        return [
            'story' => self::summary($story),
            'document_json' => json_encode(MapStoryFile::authored($story->document), MapStoryFile::JSON_FLAGS),
            'errors' => [],
            'warnings' => $warnings,
        ];
    }

    /**
     * The atlas entity behind every Q-id the document links (sides, commanders,
     * units, features, step entities, areas), so the editor can show whether a
     * link resolves and under which name.
     *
     * @return array<string, array{id: string, name: string, type: string|null}>
     */
    public static function linked(stdClass $document): array
    {
        preg_match_all('/"wikidata":"(Q[1-9][0-9]*)"/', (string) json_encode($document, MapStoryFile::JSON_FLAGS), $m);
        $qids = array_values(array_unique($m[1]));
        if ($qids === []) {
            return [];
        }

        return Entity::query()->whereIn('wikidata_id', $qids)
            ->orderByRaw('impact_score DESC NULLS LAST')
            ->get(['entity_id', 'name', 'wikidata_id', 'entity_type'])
            ->unique('wikidata_id')
            ->mapWithKeys(fn (Entity $e) => [$e->wikidata_id => ['id' => $e->entity_id, 'name' => $e->name, 'type' => $e->entity_type?->value]])
            ->all();
    }

    /** @return array<string, mixed> */
    public static function summary(MapStory $story): array
    {
        return [
            'id' => $story->story_id,
            'slug' => $story->slug,
            'title' => $story->title,
            'kind' => $story->kind,
            'year' => $story->year,
            'step_count' => $story->step_count,
            'ambient' => (bool) $story->ambient,
            'entity' => $story->entity ? ['id' => $story->entity->entity_id, 'name' => $story->entity->name] : null,
            'chronicle' => $story->chronicle ? ['id' => $story->chronicle->chronicle_id, 'slug' => $story->chronicle->slug, 'title' => $story->chronicle->title] : null,
            'source_path' => $story->source_path,
            'edited' => $story->isEdited(),
            'edited_at' => $story->edited_at?->toISOString(),
            'edited_by' => $story->editor?->name,
            'synced_at' => $story->synced_at?->toISOString(),
            'updated_at' => $story->updated_at?->toISOString(),
        ];
    }

    /**
     * The vocabulary the editor's selects offer.
     *
     * @return array<string, mixed>
     */
    public static function vocabulary(): array
    {
        return [
            'story_kinds' => V::STORY_KINDS,
            'battle_kinds' => V::BATTLE_KINDS,
            'military_kinds' => V::MILITARY_KINDS,
            'unit_kinds' => V::UNIT_KINDS,
            'point_unit_kinds' => V::POINT_UNIT_KINDS,
            'shapes' => V::SHAPES,
            'unit_states' => V::UNIT_STATES,
            'move_types' => V::MOVE_TYPES,
            'note_kinds' => V::NOTE_KINDS,
            'feature_kinds' => V::FEATURE_KINDS,
            'feature_states' => V::FEATURE_STATES,
            'route_kinds' => V::ROUTE_KINDS,
            'region_kinds' => V::REGION_KINDS,
            'legend_styles' => V::LEGEND_STYLES,
            'lights' => V::LIGHTS,
            'wind_strengths' => V::WIND_STRENGTHS,
            'source_kinds' => V::SOURCE_KINDS,
            'max_beats' => V::MAX_BEATS,
            'text_limits' => MapStoryWarnings::TEXT_LIMITS,
            'route_colors' => MapStoryAmbient::ROUTE_COLORS,
            'region_colors' => MapStoryAmbient::REGION_COLORS,
        ];
    }
}
