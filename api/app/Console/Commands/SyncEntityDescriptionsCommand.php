<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Actions\Entity\SyncEntityDescriptionFileAction;
use Illuminate\Console\Command;

/**
 * Load long entity descriptions from resources/entity-descriptions/*.md.
 * Idempotent; descriptions edited since the last sync are kept unless forced.
 *
 *   php artisan entities:sync-descriptions
 *   php artisan entities:sync-descriptions --force
 *
 * File format: docs/implementation-docs/map-story-authoring.md ("Entity descriptions").
 */
class SyncEntityDescriptionsCommand extends Command
{
    public const DIRECTORY = 'entity-descriptions';

    protected $signature = 'entities:sync-descriptions
        {--force : Overwrite descriptions edited since the last sync}
        {--path= : Read this directory instead of resources/entity-descriptions}';

    protected $description = 'Set entity descriptions from resources/entity-descriptions/*.md';

    public function handle(SyncEntityDescriptionFileAction $sync): int
    {
        $directory = $this->option('path') ?: resource_path(self::DIRECTORY);
        $files = glob(rtrim((string) $directory, '/').'/*.md') ?: [];
        sort($files);
        $counts = [];

        foreach ($files as $path) {
            $result = $sync($path, (bool) $this->option('force'));
            $counts[$result['status']] = ($counts[$result['status']] ?? 0) + 1;
            $label = $result['entity'] !== null ? "{$result['file']} → {$result['entity']}" : $result['file'];
            $this->components->twoColumnDetail($label, $result['status'].($result['message'] !== null ? " ({$result['message']})" : ''));
        }

        $this->components->info(collect($counts)->map(fn (int $n, string $status) => "{$n} {$status}")->implode(', ') ?: 'No description files.');

        return ($counts['unresolved'] ?? 0) + ($counts['invalid'] ?? 0) > 0 ? self::FAILURE : self::SUCCESS;
    }
}
