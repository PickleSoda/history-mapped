<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Actions\ContentBundle\ExportContentBundleAction;
use App\Support\ContentBundle\Profile;
use App\Support\ContentBundle\Scope\ExportScope;
use Illuminate\Console\Command;
use InvalidArgumentException;
use RuntimeException;

/**
 * Export entities, relationships, geometry, geo refs and chronicles as a content bundle (directory or .zip).
 *
 *   php artisan content:export storage/app/bundle.zip --scope=chronicle:rome --profile=public
 *   php artisan content:export out/ --scope=type:city --scope=years:-500..500
 *
 * With no --scope the whole dataset is exported. See docs/schemas/content-bundle.md.
 */
class ContentExportCommand extends Command
{
    protected $signature = 'content:export
        {path : Target directory (must be empty or absent) or a .zip file}
        {--scope=* : Scope spec (all, chronicle:<slug>, entity:<uuid>, ids:<file>, neighbours:<uuid>, type:<a,b>, group:<g>, years:<from>..<to>)}
        {--profile=full : full or public (public drops internal data and adds LICENSE.md)}
        {--source= : Free-text origin recorded in the manifest (default: app environment)}';

    protected $description = 'Export content as a versioned bundle of JSONL files';

    public function handle(ExportContentBundleAction $export): int
    {
        $profile = Profile::tryFrom((string) $this->option('profile'));
        if ($profile === null) {
            $this->error('Unknown profile "'.$this->option('profile').'"; expected full or public.');

            return self::FAILURE;
        }

        try {
            $scope = ExportScope::parse(array_map('strval', (array) $this->option('scope')), allowIdsFiles: true);
            $source = $this->option('source');
            $manifest = $export((string) $this->argument('path'), $scope, $profile, $source === null || $source === '' ? null : (string) $source);
        } catch (InvalidArgumentException|RuntimeException $e) {
            $this->error($e->getMessage());

            return self::FAILURE;
        }

        foreach ($manifest['counts'] as $type => $count) {
            $this->line(sprintf('%-18s %d', $type, $count));
        }
        if ($manifest['counts']['entities'] === 0 && ! $scope->isAll()) {
            $this->warn('Warning: scope selected no entities.');
        }
        $this->info('Bundle written to '.$this->argument('path'));

        return self::SUCCESS;
    }
}
