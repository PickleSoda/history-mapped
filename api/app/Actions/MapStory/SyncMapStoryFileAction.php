<?php

declare(strict_types=1);

namespace App\Actions\MapStory;

use App\Models\MapStory;
use App\Support\MapStory\MapStoryFile;

/**
 * Load one resources/map-stories/<slug>.json file into `map_stories`.
 *
 * The DB row is the live copy (the admin and the AI agent edit it); the file
 * is a seed or an export. Per row:
 *  - the file is unchanged since it was last synced or exported (`file_hash`
 *    matches): skip;
 *  - the file changed but the row was edited since then: skip and keep the
 *    edits ("kept") — export them first, or force;
 *  - otherwise: check, resolve and save it (SaveMapStoryAction, which writes
 *    a revision first, so a forced overwrite of edits can be restored).
 *
 * `$force` re-syncs an unchanged file and overwrites edits.
 */
class SyncMapStoryFileAction
{
    public const KEPT_EDITS = 'kept admin edits — export first or use --force';

    public function __construct(private SaveMapStoryAction $save) {}

    /**
     * @return array{status: 'created'|'updated'|'unchanged'|'kept'|'failed', slug: string, errors: list<string>, warnings: list<string>}
     */
    public function __invoke(string $path, bool $force = false): array
    {
        $slug = basename($path, '.json');
        $raw = (string) file_get_contents($path);
        $hash = MapStoryFile::hash($raw);

        $existing = MapStory::query()->where('slug', $slug)->first();
        if (! $force && $existing !== null && $existing->file_hash === $hash) {
            return $this->result('unchanged', $slug);
        }
        if (! $force && $existing !== null && $existing->isEdited()) {
            return $this->result('kept', $slug, warnings: [self::KEPT_EDITS]);
        }

        $doc = MapStoryFile::decode($raw);
        if ($doc === null) {
            return $this->result('failed', $slug, ['not a JSON object: '.json_last_error_msg()]);
        }
        if (($doc->slug ?? null) !== $slug) {
            return $this->result('failed', $slug, ["slug '".(is_string($doc->slug ?? null) ? $doc->slug : '')."' must match the file name '{$slug}'"]);
        }

        $saved = ($this->save)(
            $existing,
            $doc,
            $existing === null ? 'import' : 'sync',
            note: 'map-stories:sync from resources/map-stories/'.basename($path).($force && $existing?->isEdited() ? ' (forced over edits)' : ''),
            file: ['file_hash' => $hash, 'source_path' => 'resources/map-stories/'.basename($path)],
        );
        if ($saved['errors'] !== []) {
            return $this->result('failed', $slug, $saved['errors']);
        }

        return $this->result($existing === null ? 'created' : 'updated', $slug);
    }

    /**
     * @param  'created'|'updated'|'unchanged'|'kept'|'failed'  $status
     * @param  list<string>  $errors
     * @param  list<string>  $warnings
     * @return array{status: 'created'|'updated'|'unchanged'|'kept'|'failed', slug: string, errors: list<string>, warnings: list<string>}
     */
    private function result(string $status, string $slug, array $errors = [], array $warnings = []): array
    {
        return ['status' => $status, 'slug' => $slug, 'errors' => $errors, 'warnings' => $warnings];
    }
}
