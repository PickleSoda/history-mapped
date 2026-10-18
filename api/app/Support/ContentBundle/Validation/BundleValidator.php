<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

use App\Support\ContentBundle\BundleLimitExceededException;
use App\Support\ContentBundle\BundleReader;
use App\Support\ContentBundle\BundleReadException;

/**
 * Runs the validation layers in order (package, structure, records, references) and stops after the first
 * layer that has errors, since later layers assume the earlier ones held. Errors on lines unchanged since
 * export are downgraded to warnings by the IssueSink before that decision is made. Problems with the bundle
 * (size limits, corrupt or unreadable entries) become package errors; anything else is a bug or an outage
 * on our side and propagates.
 *
 * Layers are ValidationLayer objects run in the order given. The defaults are the four real layers, with a
 * no-op references layer until ReferenceChecks exists; tests pass their own list. A layer's name() is the
 * Issue layer its errors are counted under.
 */
final class BundleValidator
{
    /** @var list<ValidationLayer> */
    private readonly array $layers;

    private bool $baseOverflowReported = false;

    /** @param  list<ValidationLayer>|null  $layers */
    public function __construct(
        ?array $layers = null,
        ?int $maxErrorLines = null,
        private readonly int $baseIndexMaxLines = BaseIndex::MAX_LINES,
    ) {
        if ($layers !== null && $maxErrorLines !== null) {
            throw new \InvalidArgumentException('maxErrorLines only configures the default layers; pass it to StructureChecks when supplying $layers');
        }
        $this->layers = $layers ?? [
            new PackageChecks,
            new StructureChecks($maxErrorLines ?? StructureChecks::MAX_ERROR_LINES),
            new RecordChecks,
            new NoChecks(Issue::REFERENCES),
        ];
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

        try {
            foreach ($this->layers as $layer) {
                $layer->run($bundle, $sink, $againstSite);
                $this->reportBaseOverflow($base, $sink);
                $sink->finish();
                if ($report->hasErrorsIn($layer->name())) {
                    break;
                }
            }
        } catch (BundleLimitExceededException|BundleReadException $e) {
            $sink->finish();
            $report->add(Issue::error(Issue::PACKAGE, $e->getMessage(), $e->entry));
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
