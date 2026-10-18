<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Actions\ContentBundle\ValidateContentBundleAction;
use Illuminate\Console\Command;

/**
 * Validate a content bundle and print what is wrong as `file:line: field: message`.
 *
 *   php artisan content:validate storage/app/bundle.zip --against-site
 *   php artisan content:validate out/ --json
 *
 * Exit code 0 when the bundle is valid (warnings allowed) and 1 when it has errors. Exit code 2 is reserved
 * for the import planner's conflicts (part 2). See docs/schemas/content-bundle.md.
 */
class ContentValidateCommand extends Command
{
    protected $signature = 'content:validate
        {path : Bundle directory or .zip file}
        {--against-site : Also check references and geometries against this database}
        {--json : Print the report as JSON and nothing else}';

    protected $description = 'Validate a content bundle';

    public function handle(ValidateContentBundleAction $validate): int
    {
        $report = $validate((string) $this->argument('path'), (bool) $this->option('against-site'));

        if ($this->option('json')) {
            $this->line((string) json_encode($report->toArray(), JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));

            return $report->isValid() ? self::SUCCESS : self::FAILURE;
        }

        foreach ($report->issues() as $issue) {
            $this->line(($issue->isError() ? 'ERROR ' : 'WARN ').$issue);
        }
        $this->line(sprintf('%d errors, %d warnings', $report->errorCount(), $report->warningCount()));

        return $report->isValid() ? self::SUCCESS : self::FAILURE;
    }
}
