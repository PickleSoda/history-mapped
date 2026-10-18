<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

use App\Support\ContentBundle\BundleLimitExceededException;
use App\Support\ContentBundle\BundleReader;
use App\Support\ContentBundle\BundleReadException;
use Closure;

/**
 * Runs the validation layers in order (package, structure, records, references) and stops after the first
 * layer that has errors, since later layers assume the earlier ones held. Errors on lines unchanged since
 * export are downgraded to warnings by the IssueSink before that decision is made. Problems with the bundle
 * (size limits, corrupt or unreadable entries) become package errors; anything else is a bug or an outage
 * on our side and propagates.
 *
 * The records and references layers are closures `(BundleReader, IssueSink, bool $againstSite): void`
 * so they can be swapped out in tests; the defaults are the real layers.
 */
final class BundleValidator
{
    /** @var Closure(BundleReader, IssueSink, bool): void */
    private readonly Closure $records;

    /** @var Closure(BundleReader, IssueSink, bool): void */
    private readonly Closure $references;

    private bool $baseOverflowReported = false;

    /**
     * @param  (Closure(BundleReader, IssueSink, bool): void)|null  $records
     * @param  (Closure(BundleReader, IssueSink, bool): void)|null  $references
     */
    public function __construct(
        ?Closure $records = null,
        ?Closure $references = null,
        private readonly int $maxErrorLines = StructureChecks::MAX_ERROR_LINES,
        private readonly int $baseIndexMaxLines = BaseIndex::MAX_LINES,
    ) {
        // Task 7 replaces these defaults with the records and references layers.
        $this->records = $records ?? static function (BundleReader $bundle, IssueSink $sink, bool $againstSite): void {};
        $this->references = $references ?? static function (BundleReader $bundle, IssueSink $sink, bool $againstSite): void {};
    }

    /**
     * Opens `$path` and validates it; open failures become one package error.
     *
     * @param  array<string, int>  $openLimits  named BundleReader::open() overrides (maxLineBytes, maxEntries, …)
     */
    public static function validatePath(string $path, bool $againstSite = false, array $openLimits = []): ValidationReport
    {
        try {
            $bundle = BundleReader::open($path, ...$openLimits);
        } catch (BundleLimitExceededException|BundleReadException $e) {
            $report = new ValidationReport;
            $report->add(Issue::error(Issue::PACKAGE, $e->getMessage()));

            return $report;
        }

        try {
            return (new self)->validate($bundle, $againstSite);
        } finally {
            $bundle->close();
        }
    }

    public function validate(BundleReader $bundle, bool $againstSite = false): ValidationReport
    {
        $report = new ValidationReport;
        $base = new BaseIndex($bundle, $this->baseIndexMaxLines);
        $sink = new IssueSink($report, $base);

        $layers = [
            Issue::PACKAGE => fn () => (new PackageChecks)->run($bundle, $sink),
            Issue::STRUCTURE => fn () => (new StructureChecks($this->maxErrorLines))->run($bundle, $sink),
            Issue::RECORDS => fn () => ($this->records)($bundle, $sink, $againstSite),
            Issue::REFERENCES => fn () => ($this->references)($bundle, $sink, $againstSite),
        ];

        try {
            foreach ($layers as $layer => $run) {
                $run();
                $this->reportBaseOverflow($base, $sink);
                $sink->finish();
                if ($report->hasErrorsIn($layer)) {
                    break;
                }
            }
        } catch (BundleLimitExceededException|BundleReadException $e) {
            $sink->finish();
            $report->add(Issue::error(Issue::PACKAGE, $e->getMessage()));
        }

        return $report;
    }

    private function reportBaseOverflow(BaseIndex $base, IssueSink $sink): void
    {
        if ($base->overflowed() && ! $this->baseOverflowReported) {
            $this->baseOverflowReported = true;
            $sink->add(Issue::warning(Issue::STRUCTURE, 'the _base snapshot has more than '.number_format($base->maxLines()).' lines; errors on unchanged lines are not downgraded to warnings'));
        }
    }
}
