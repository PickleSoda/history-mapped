<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

use App\Support\ContentBundle\BundleReader;
use RuntimeException;

/**
 * Runs the validation layers in order (package, structure, records, references) and stops after the first
 * layer that has errors, since later layers assume the earlier ones held. Errors on lines unchanged since
 * export are downgraded to warnings by the IssueSink before that decision is made. Bad input never throws:
 * reader failures (limits, unreadable entries) become package errors.
 */
final class BundleValidator
{
    /**
     * Opens `$path` and validates it; open failures become one package error.
     *
     * @param  array<string, int>  $openLimits  named BundleReader::open() overrides (maxLineBytes, maxEntries, …)
     */
    public static function validatePath(string $path, bool $againstSite = false, array $openLimits = []): ValidationReport
    {
        try {
            $bundle = BundleReader::open($path, ...$openLimits);
        } catch (RuntimeException $e) {
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
        $sink = new IssueSink($report, new BaseIndex($bundle));

        try {
            (new PackageChecks)->run($bundle, $sink);
            $sink->finish();
            if ($report->hasErrorsIn(Issue::PACKAGE)) {
                return $report;
            }

            (new StructureChecks)->run($bundle, $sink);
            $sink->finish();
            if ($report->hasErrorsIn(Issue::STRUCTURE)) {
                return $report;
            }

            $this->records($bundle, $sink);
            $sink->finish();
            if ($report->hasErrorsIn(Issue::RECORDS)) {
                return $report;
            }

            $this->references($bundle, $sink, $againstSite);
            $sink->finish();
        } catch (RuntimeException $e) {
            // BundleLimitExceededException while reading, or an entry the reader could not open.
            $sink->finish();
            $report->add(Issue::error(Issue::PACKAGE, $e->getMessage()));
        }

        return $report;
    }

    /** Filled in by the records layer. */
    private function records(BundleReader $bundle, IssueSink $sink): void {}

    /** Filled in by the references layer. */
    private function references(BundleReader $bundle, IssueSink $sink, bool $againstSite): void {}
}
