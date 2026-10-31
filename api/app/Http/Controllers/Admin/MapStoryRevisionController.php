<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin;

use App\Actions\MapStory\RestoreMapStoryRevisionAction;
use App\Http\Controllers\Controller;
use App\Models\MapStory;
use App\Models\MapStoryRevision;
use App\Support\MapStory\MapStoryFile;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

/** A map story's revisions (JSON, the editor's drawer): list, one document, restore. */
class MapStoryRevisionController extends Controller
{
    public function index(string $slug): JsonResponse
    {
        $story = $this->story($slug);

        return response()->json([
            'data' => $story->revisions()->with('user:id,name')->get(['id', 'map_story_id', 'source', 'user_id', 'note', 'created_at'])
                ->map(fn (MapStoryRevision $r) => [
                    'id' => $r->id,
                    'source' => $r->source,
                    'user' => $r->user?->name,
                    'note' => $r->note,
                    'created_at' => $r->created_at?->toISOString(),
                ]),
        ]);
    }

    public function show(string $slug, int $revision): JsonResponse
    {
        $rev = $this->revision($this->story($slug), $revision);

        return response()->json(['data' => [
            'id' => $rev->id,
            'source' => $rev->source,
            'note' => $rev->note,
            'created_at' => $rev->created_at?->toISOString(),
            'document_json' => json_encode($rev->document, MapStoryFile::JSON_FLAGS),
        ]]);
    }

    public function restore(Request $request, string $slug, int $revision, RestoreMapStoryRevisionAction $restore): JsonResponse
    {
        $story = $this->story($slug);
        $result = $restore($story, $this->revision($story, $revision), $request->user()?->id);
        if ($result['errors'] !== []) {
            return response()->json(['errors' => $result['errors'], 'warnings' => []], 422);
        }

        return response()->json(MapStoryController::saved($result['story'], $result['warnings']));
    }

    private function story(string $slug): MapStory
    {
        return MapStory::query()->where('slug', $slug)->firstOrFail();
    }

    private function revision(MapStory $story, int $id): MapStoryRevision
    {
        return MapStoryRevision::query()->where('map_story_id', $story->story_id)->findOrFail($id);
    }
}
