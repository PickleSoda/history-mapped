<?php

declare(strict_types=1);

namespace App\Actions\MapStory;

use App\Models\MapStory;
use App\Models\MapStoryRevision;
use App\Support\MapStory\MapStoryFile;
use App\Support\MapStory\MapStoryWarnings;
use Illuminate\Support\Facades\DB;
use InvalidArgumentException;
use stdClass;

/**
 * Save a map story's whole document — the one write path for the admin
 * editor, the AI agent, `map-stories:sync` and revision restores.
 *
 * The document is checked (MapStoryDocument; its slug must match the story's
 * and be free for a new one) and resolved against the atlas
 * (ResolveMapStoryAction); any error blocks the save and nothing is written.
 * Otherwise a revision of the authored document is written first (and, the
 * first time a story is edited, one of the version before it), then the row,
 * in one transaction; the newest MapStoryRevision::MAX_PER_STORY revisions are
 * kept. The plausibility warnings (MapStoryWarnings) come back but never block.
 *
 * Bookkeeping: a `sync`/`import` save records the file it came from
 * (`file_hash`, `synced_at`, `source_path`); any other save sets `edited_at`
 * and `edited_by` — and, when the document is exactly what the file holds
 * (a restore of the file's version), `synced_at` too, so it no longer counts
 * as edited.
 */
class SaveMapStoryAction
{
    public function __construct(private ResolveMapStoryAction $resolve) {}

    /**
     * @param  MapStory|null  $story  null creates a story
     * @param  stdClass  $document  the authored document (resolved ids, if any, are dropped and re-resolved)
     * @param  string  $source  one of MapStoryRevision::SOURCES
     * @param  array{file_hash?: string, source_path?: string}  $file  for a sync or import: the file it came from
     * @return array{story: MapStory|null, errors: list<string>, warnings: list<string>}
     */
    public function __invoke(?MapStory $story, stdClass $document, string $source, ?int $userId = null, ?string $note = null, array $file = []): array
    {
        if (! in_array($source, MapStoryRevision::SOURCES, true)) {
            throw new InvalidArgumentException("Unknown revision source '{$source}'.");
        }

        $doc = MapStoryFile::normaliseMaps(MapStoryFile::authored($document));
        $current = $story !== null && $story->document instanceof stdClass ? MapStoryFile::authored($story->document) : null;
        if ($current !== null) {
            $doc = MapStoryFile::keepNumberTypes($doc, $current);
        }
        $array = MapStoryFile::toArray($doc);

        $errors = CheckMapStoryAction::structuralErrors($array, $story);
        $slug = $array['slug'] ?? null;
        if ($errors !== []) {
            return ['story' => $story, 'errors' => $errors, 'warnings' => []];
        }

        $resolved = ($this->resolve)($doc);
        if ($resolved['errors'] !== []) {
            return ['story' => $story, 'errors' => $resolved['errors'], 'warnings' => []];
        }
        $warnings = MapStoryWarnings::of($array);

        $story = DB::transaction(function () use ($story, $doc, $current, $resolved, $source, $userId, $note, $file, $slug): MapStory {
            $story ??= new MapStory(['slug' => $slug]);

            if ($story->exists && $current !== null && ! $story->revisions()->exists()) {
                $story->revisions()->create([
                    'document' => $current,
                    'source' => $story->source_path !== null ? 'sync' : 'admin',
                    'user_id' => null,
                    'note' => 'The version before the first edit',
                ]);
            }

            $now = now();
            $story->fill([...$resolved['columns'], 'document' => $resolved['document']]);
            if (in_array($source, ['sync', 'import'], true)) {
                $story->fill([
                    'file_hash' => $file['file_hash'] ?? $story->file_hash,
                    'source_path' => $file['source_path'] ?? $story->source_path,
                    'synced_at' => $now,
                ]);
            } else {
                $story->fill(['edited_at' => $now, 'edited_by' => $userId]);
                if ($story->file_hash !== null && MapStoryFile::hash(MapStoryFile::encode($doc)) === $story->file_hash) {
                    $story->synced_at = $now;
                }
            }
            $story->save();

            $story->revisions()->create([
                'document' => $doc,
                'source' => $source,
                'user_id' => $userId,
                'note' => $note,
            ]);
            $this->prune($story);

            return $story;
        });

        return ['story' => $story->refresh(), 'errors' => [], 'warnings' => $warnings];
    }

    /** Keep the newest MAX_PER_STORY revisions. */
    private function prune(MapStory $story): void
    {
        $keep = MapStoryRevision::query()
            ->where('map_story_id', $story->story_id)
            ->orderByDesc('id')
            ->limit(MapStoryRevision::MAX_PER_STORY)
            ->pluck('id');

        MapStoryRevision::query()
            ->where('map_story_id', $story->story_id)
            ->whereNotIn('id', $keep)
            ->delete();
    }
}
