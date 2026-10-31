<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Actions\MapStory\RelinkMapStoryAction;
use App\Models\MapStory;
use Illuminate\Console\Command;

/**
 * Re-resolve the stored map stories against the atlas as it is now: link
 * Q-ids of entities created (or merged) since a story was synced, and redraw
 * step entities' atlas geometry, period, extent and ambient layer. Reads no
 * files and keeps edits; a story is saved (with a `relink` revision) only
 * when something changed.
 *
 *   php artisan map-stories:relink
 *   php artisan map-stories:relink --slug=black-death --slug=battle-of-cannae
 *
 * Run it after creating entities a story names, and after a full content
 * load. See docs/implementation-docs/map-story-authoring.md.
 */
class RelinkMapStoriesCommand extends Command
{
    protected $signature = 'map-stories:relink
        {--slug=* : Only relink these slugs}';

    protected $description = 'Re-resolve stored map stories against the atlas (new entities, step geometry); keeps edits';

    public function handle(RelinkMapStoryAction $relink): int
    {
        $only = array_values(array_filter((array) $this->option('slug')));
        $query = MapStory::query()->orderBy('slug');
        if ($only !== []) {
            $query->whereIn('slug', $only);
        }
        // One document in memory at a time.
        $ids = $query->pluck('story_id', 'slug');
        $failed = 0;

        foreach (array_diff($only, $ids->keys()->all()) as $slug) {
            $this->components->twoColumnDetail($slug, 'failed: no such story');
            $failed++;
        }

        foreach ($ids as $slug => $id) {
            $story = MapStory::query()->find($id);
            $result = $story === null ? ['status' => 'failed', 'errors' => ['deleted while relinking']] : $relink($story);
            $status = $result['status'] === 'failed' ? 'failed: '.implode('; ', $result['errors']) : $result['status'];
            $this->components->twoColumnDetail((string) $slug, $status);
            if ($result['status'] === 'failed') {
                $failed++;
            }
        }

        return $failed > 0 ? self::FAILURE : self::SUCCESS;
    }
}
