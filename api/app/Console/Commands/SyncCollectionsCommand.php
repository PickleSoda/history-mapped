<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Actions\Collection\SyncCollectionFileAction;
use Illuminate\Console\Command;

/**
 * Load the curated collections in resources/collections/*.json into
 * `collections`, upserting by slug. Deletes nothing (set `"status": "draft"`
 * to hide a set). An invalid file is reported and skipped; the rest still
 * load, and the command exits non-zero.
 *
 *   php artisan collections:sync
 *   php artisan collections:sync --path=/tmp/collections
 *
 * Format: docs/schemas/collections.md.
 */
class SyncCollectionsCommand extends Command
{
    public const DIRECTORY = 'collections';

    protected $signature = 'collections:sync
        {--path= : Read this directory instead of resources/collections}';

    protected $description = 'Load curated collections from resources/collections into the database';

    public function handle(SyncCollectionFileAction $sync): int
    {
        $directory = $this->option('path') ?: resource_path(self::DIRECTORY);
        $files = glob(rtrim((string) $directory, '/').'/*.json') ?: [];
        sort($files);
        $invalid = 0;

        if ($files === []) {
            $this->components->warn("No collection files in {$directory}");
        }

        foreach ($files as $path) {
            $result = $sync($path);
            $this->components->twoColumnDetail($result['slug'], $result['status']);
            foreach ($result['errors'] as $error) {
                $this->components->error("{$result['slug']}: {$error}");
            }
            foreach ($result['warnings'] as $warning) {
                $this->components->warn("{$result['slug']}: {$warning}");
            }
            if ($result['status'] === 'invalid') {
                $invalid++;
            }
        }

        return $invalid > 0 ? self::FAILURE : self::SUCCESS;
    }
}
