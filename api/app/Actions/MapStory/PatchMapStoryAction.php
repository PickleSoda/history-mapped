<?php

declare(strict_types=1);

namespace App\Actions\MapStory;

use App\Models\MapStory;
use App\Support\MapStory\JsonPatch;
use App\Support\MapStory\JsonPatchException;
use App\Support\MapStory\MapStoryFile;
use stdClass;

/**
 * Apply RFC 6902 JSON Patch ops to a story's authored document, all or none:
 * an op that cannot apply, or a patched document that fails the checks,
 * rejects the whole patch with the errors and writes nothing; otherwise it is
 * saved through SaveMapStoryAction (one revision). `dryRun` only checks.
 */
class PatchMapStoryAction
{
    public function __construct(private SaveMapStoryAction $save, private ResolveMapStoryAction $resolve) {}

    /**
     * @param  list<array<string, mixed>>  $ops
     * @return array{story: MapStory|null, errors: list<string>, warnings: list<string>, document: stdClass|null}
     */
    public function __invoke(MapStory $story, array $ops, string $source, ?int $userId = null, ?string $note = null, bool $dryRun = false): array
    {
        $current = MapStoryFile::authored($story->document);
        try {
            $patched = MapStoryFile::normaliseMaps(JsonPatch::apply($current, $ops));
        } catch (JsonPatchException $e) {
            return ['story' => $story, 'errors' => [$e->getMessage()], 'warnings' => [], 'document' => null];
        }
        $patched = MapStoryFile::keepNumberTypes($patched, $current);

        if ($dryRun) {
            $check = CheckMapStoryAction::check($patched, $story, $this->resolve);

            return ['story' => $story, ...$check, 'document' => $check['errors'] === [] ? $patched : null];
        }

        $saved = ($this->save)($story, $patched, $source, $userId, $note);

        return [...$saved, 'document' => $saved['errors'] === [] ? $patched : null];
    }
}
