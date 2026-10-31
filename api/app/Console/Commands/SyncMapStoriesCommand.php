<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Actions\MapStory\SyncMapStoryFileAction;
use App\Models\MapStory;
use Illuminate\Console\Command;

/**
 * Load the battle maps in resources/map-stories/*.json into `map_stories`.
 * Idempotent: unchanged files (same hash) are skipped.
 *
 *   php artisan map-stories:sync
 *   php artisan map-stories:sync --slug=battle-of-cannae --force
 *   php artisan map-stories:sync --prune
 *
 * Authoring: docs/implementation-docs/map-story-authoring.md.
 */
class SyncMapStoriesCommand extends Command
{
    public const DIRECTORY = 'map-stories';

    protected $signature = 'map-stories:sync
        {--slug=* : Only sync these slugs (file names without .json)}
        {--prune : Delete synced stories whose file is gone}
        {--force : Re-sync files whose content has not changed}
        {--path= : Read this directory instead of resources/map-stories}';

    protected $description = 'Load map stories (battle maps) from resources/map-stories into the database';

    public function handle(SyncMapStoryFileAction $sync): int
    {
        $directory = $this->option('path') ?: resource_path(self::DIRECTORY);
        $files = glob(rtrim((string) $directory, '/').'/*.json') ?: [];
        sort($files);
        $only = array_values(array_filter((array) $this->option('slug')));
        $failed = 0;

        foreach ($files as $path) {
            if ($only !== [] && ! in_array(basename($path, '.json'), $only, true)) {
                continue;
            }
            $result = $sync($path, (bool) $this->option('force'));
            $this->components->twoColumnDetail($result['slug'], $result['status']);
            foreach ($result['errors'] as $error) {
                $this->components->error($error);
            }
            if ($result['status'] === 'failed') {
                $failed++;
            }
        }

        if ($this->option('prune')) {
            $present = array_map(fn (string $path) => basename($path, '.json'), $files);
            $pruned = MapStory::query()
                ->whereNotNull('source_path')
                ->whereNotIn('slug', $present)
                ->delete();
            $this->components->twoColumnDetail('Pruned', (string) $pruned);
        }

        return $failed > 0 ? self::FAILURE : self::SUCCESS;
    }
}
