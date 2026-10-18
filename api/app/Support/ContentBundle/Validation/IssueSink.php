<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

/**
 * Where every layer reports. It is the one place that downgrades errors on lines unchanged since export
 * (the import never writes unchanged values, so old data problems must not block an export's round trip)
 * and that caps output per file: at most MAX_PER_FILE errors and MAX_PER_FILE warnings are kept, the rest
 * are counted and summarised by finish(). add() returns the severity the issue has after downgrading,
 * whether or not it was kept, so layers can count erroneous lines.
 *
 * The downgrade needs the hash `sha1($line, true)` of the line the issue is about (the normalised line as
 * yielded by BundleReader::lines()). Layers that report later, such as reference checks, keep the hash
 * of each line they saw and pass it along.
 */
final class IssueSink
{
    public const MAX_PER_FILE = 200;

    public const UNCHANGED_SUFFIX = ' (unchanged since export)';

    /** @var array<string, array{error: int, warning: int, droppedErrors: int, droppedWarnings: int, layer: string, note: string}> */
    private array $files = [];

    public function __construct(private readonly ValidationReport $report, private readonly BaseIndex $base) {}

    public function add(Issue $issue, ?string $lineHash = null): string
    {
        if ($issue->isError() && $lineHash !== null && $issue->file !== null && $this->base->has($issue->file, $lineHash)) {
            $issue = $issue->asWarning(self::UNCHANGED_SUFFIX);
        }

        $state = &$this->state($issue->file ?? '', $issue->layer);
        $state['layer'] = $issue->layer;
        if ($state[$issue->severity] >= self::MAX_PER_FILE) {
            $state[$issue->isError() ? 'droppedErrors' : 'droppedWarnings']++;
        } else {
            $state[$issue->severity]++;
            $this->report->add($issue);
        }

        return $issue->severity;
    }

    /** Remember why validation of a file stopped early; shown in its summary. */
    public function note(string $file, string $note): void
    {
        $this->state($file, Issue::STRUCTURE)['note'] = $note;
    }

    /** Adds the "and N more" lines for every file that overflowed. Call after each layer. */
    public function finish(): void
    {
        foreach ($this->files as $file => &$state) {
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

    /** @return array{error: int, warning: int, droppedErrors: int, droppedWarnings: int, layer: string, note: string} */
    private function &state(string $file, string $layer): array
    {
        $this->files[$file] ??= ['error' => 0, 'warning' => 0, 'droppedErrors' => 0, 'droppedWarnings' => 0, 'layer' => $layer, 'note' => ''];

        return $this->files[$file];
    }
}
