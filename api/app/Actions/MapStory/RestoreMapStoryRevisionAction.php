<?php

declare(strict_types=1);

namespace App\Actions\MapStory;

use App\Models\MapStory;
use App\Models\MapStoryRevision;
use InvalidArgumentException;

/**
 * Save an earlier revision's document again (as a new `restore` revision, so
 * the restore itself can be undone). It goes through the same checks as any
 * save: a revision that no longer resolves (its entity was deleted) is refused.
 */
class RestoreMapStoryRevisionAction
{
    public function __construct(private SaveMapStoryAction $save) {}

    /** @return array{story: MapStory|null, errors: list<string>, warnings: list<string>} */
    public function __invoke(MapStory $story, MapStoryRevision $revision, ?int $userId = null): array
    {
        if ($revision->map_story_id !== $story->story_id) {
            throw new InvalidArgumentException('That revision belongs to another story.');
        }

        return ($this->save)($story, $revision->document, 'restore', $userId, "Restored revision #{$revision->id} ({$revision->source}, {$revision->created_at?->toDateTimeString()})");
    }
}
