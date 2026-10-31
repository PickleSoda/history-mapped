<?php

declare(strict_types=1);

namespace App\Actions\MapStory;

use App\Models\MapStory;
use App\Support\MapStory\MapStoryFile;
use Illuminate\Contracts\Database\Query\Expression;
use Illuminate\Support\Facades\DB;
use stdClass;

/**
 * Re-resolve a stored map story against the atlas as it is now
 * (`map-stories:relink`): Q-ids of entities created or merged since the story
 * was saved, step entities' atlas geometry, the period, extent and ambient
 * layer. `map-stories:sync` skips a file it has already synced, so without
 * this a story never links an entity created after it.
 *
 * The stored document is resolved in place (ResolveMapStoryAction on its
 * authored copy); no file is read. The row is saved, with one revision
 * (source `sync`, note `relink`), only when the resolved document or a
 * column derived from it changed. `edited_at`, `edited_by`, `file_hash` and
 * `synced_at` are left alone, so an edited story stays edited and an
 * exported one stays in sync with its file.
 */
class RelinkMapStoryAction
{
    public const NOTE = 'relink';

    public function __construct(private ResolveMapStoryAction $resolve) {}

    /** @return array{status: 'relinked'|'unchanged'|'failed', errors: list<string>} */
    public function __invoke(MapStory $story): array
    {
        if (! $story->document instanceof stdClass) {
            return ['status' => 'failed', 'errors' => ['the story has no document']];
        }

        $doc = MapStoryFile::normaliseMaps(MapStoryFile::authored($story->document));
        $resolved = ($this->resolve)($doc);
        if ($resolved['errors'] !== []) {
            return ['status' => 'failed', 'errors' => $resolved['errors']];
        }
        if (! $this->changed($story, $resolved['document'], $resolved['columns'])) {
            return ['status' => 'unchanged', 'errors' => []];
        }

        DB::transaction(function () use ($story, $doc, $resolved): void {
            $story->fill([...$resolved['columns'], 'document' => $resolved['document']])->save();
            $story->revisions()->create(['document' => $doc, 'source' => 'sync', 'user_id' => null, 'note' => self::NOTE]);
            SaveMapStoryAction::prune($story);
        });

        return ['status' => 'relinked', 'errors' => []];
    }

    /**
     * Whether the resolved document or a derived column differs from the row:
     * the document and the ambient layer compared as JSON values (key order
     * aside: `ambient_steps` is jsonb), the extent in SQL, the rest as cast.
     *
     * @param  array<string, mixed>  $columns
     */
    private function changed(MapStory $story, stdClass $document, array $columns): bool
    {
        if (self::canonical(MapStoryFile::toArray($document)) !== self::canonical(MapStoryFile::toArray($story->document))) {
            return true;
        }
        if (self::canonical($columns['ambient_steps']) !== self::canonical($story->ambient_steps)) {
            return true;
        }

        $scalars = array_diff_key($columns, array_flip(['ambient_steps', 'bbox']));
        if ((clone $story)->fill($scalars)->isDirty(array_keys($scalars))) {
            return true;
        }

        $bbox = $columns['bbox'] instanceof Expression ? (string) $columns['bbox']->getValue(DB::connection()->getQueryGrammar()) : 'NULL::geometry';

        return ! DB::table('map_stories')
            ->where('story_id', $story->story_id)
            ->value(DB::raw("ST_AsEWKT(bbox) IS NOT DISTINCT FROM ST_AsEWKT({$bbox})"));
    }

    /** A decoded JSON value with every object's keys sorted. */
    private static function canonical(mixed $value): mixed
    {
        if (! is_array($value)) {
            return $value;
        }
        $value = array_map(self::canonical(...), $value);
        if (! array_is_list($value)) {
            ksort($value);
        }

        return $value;
    }
}
