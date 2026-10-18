<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

/**
 * Where every layer reports. It is the one place that downgrades errors on lines unchanged since export
 * (the import never writes unchanged values, so old data problems must not block an export's round trip)
 * and that caps output per layer and file: at most MAX_PER_FILE errors and MAX_PER_FILE warnings are kept, the rest
 * are counted and summarised by finish(). add() returns the severity the issue has after downgrading,
 * whether or not it was kept, so layers can count erroneous lines.
 *
 * The downgrade needs the hash `sha1($line, true)` of each line the issue is about (the normalised line as
 * yielded by BundleReader::lines()). Layers that report later, such as reference checks, keep the hash
 * of each line they saw and pass it along.
 */
final class IssueSink
{
    public const MAX_PER_FILE = 200;

    public const UNCHANGED_SUFFIX = ' (unchanged since export)';

    /** @var array<string, array{error: int, warning: int, droppedErrors: int, droppedWarnings: int, layer: string, file: string, note: string}> */
    private array $files = [];

    public function __construct(private readonly ValidationReport $report, private readonly BaseIndex $base) {}

    /**
     * Cross-line issues (duplicates, dangling references) must pass the hash of EVERY line involved: the
     * issue is downgraded only when all of them are unchanged since export, otherwise a new line that
     * collides with an old one would be excused by the old line's hash. With no hash there is no downgrade.
     * The hashes are looked up in `$issue->file`'s base, so all lines must belong to that file.
     */
    public function add(Issue $issue, string ...$lineHashes): string
    {
        $unchanged = $issue->file !== null && $lineHashes !== [] && $this->allUnchanged(array_map(fn (string $h) => [$issue->file, $h], $lineHashes));

        return $this->record($issue, $unchanged);
    }

    /**
     * Like add() for issues that involve lines of several files (a reference and the line it points at).
     * Each `[file, hash]` pair is looked up in its own file's base; the downgrade needs all of them unchanged.
     *
     * @param  list<array{string, string}>  $lineRefs
     */
    public function addAcross(Issue $issue, array $lineRefs): string
    {
        return $this->record($issue, $lineRefs !== [] && $this->allUnchanged($lineRefs));
    }

    private function record(Issue $issue, bool $unchanged): string
    {
        if ($issue->isError() && $unchanged) {
            $issue = $issue->asWarning(self::UNCHANGED_SUFFIX);
        }

        $state = &$this->state($issue->file ?? '', $issue->layer);
        if ($state[$issue->severity] >= self::MAX_PER_FILE) {
            $state[$issue->isError() ? 'droppedErrors' : 'droppedWarnings']++;
        } else {
            $state[$issue->severity]++;
            $this->report->add($issue);
        }

        return $issue->severity;
    }

    /** @param  non-empty-list<array{string, string}>  $lineRefs */
    private function allUnchanged(array $lineRefs): bool
    {
        foreach ($lineRefs as [$file, $hash]) {
            if (! $this->base->has($file, $hash)) {
                return false;
            }
        }

        return true;
    }

    /** Remember why validation of a file stopped early; shown in its summary. */
    public function note(string $file, string $note): void
    {
        $this->state($file, Issue::STRUCTURE)['note'] = $note;
    }

    /** Adds the "and N more" lines for every file that overflowed. Call after each layer. */
    public function finish(): void
    {
        foreach ($this->files as &$state) {
            $file = $state['file'];
            $errors = $state['droppedErrors'];
            $warnings = $state['droppedWarnings'];
            $where = $file === '' ? null : (string) $file;
            $note = $state['note'];
            if ($errors > 0) {
                $this->report->addSummary(Issue::warning($state['layer'], '…and '.number_format($errors).' more errors in this file'.($note !== '' ? " ({$note})" : ''), $where), $errors, 0);
            } elseif ($note !== '') {
                $this->report->addSummary(Issue::warning($state['layer'], $note, $where), 0, 0);
            }
            if ($warnings > 0) {
                $this->report->addSummary(Issue::warning($state['layer'], '…and '.number_format($warnings).' more warnings in this file', $where), 0, $warnings);
            }
            $state['droppedErrors'] = $state['droppedWarnings'] = 0;
            $state['note'] = '';
        }
    }

    /** @return array{error: int, warning: int, droppedErrors: int, droppedWarnings: int, layer: string, file: string, note: string} */
    private function &state(string $file, string $layer): array
    {
        $this->files[$layer.'|'.$file] ??= ['file' => $file, 'error' => 0, 'warning' => 0, 'droppedErrors' => 0, 'droppedWarnings' => 0, 'layer' => $layer, 'note' => ''];

        return $this->files[$layer.'|'.$file];
    }
}
