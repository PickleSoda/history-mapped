<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

use App\Support\ContentBundle\RecordType;

/**
 * Where every layer reports. It is the one place that downgrades errors on lines unchanged since export
 * (the import never writes unchanged values, so old data problems must not block an export's round trip)
 * and that caps output per file: at most MAX_PER_FILE errors and MAX_PER_FILE warnings are kept, the rest
 * are counted and summarised by finish(). add() returns the severity the issue has after downgrading,
 * whether or not it was kept, so layers can count erroneous lines.
 */
final class IssueSink
{
    public const MAX_PER_FILE = 200;

    public const UNCHANGED_SUFFIX = ' (unchanged since export)';

    /** @var array<string, array{error: int, warning: int, dropped: int, layer: string, note: string}> */
    private array $files = [];

    public function __construct(private readonly ValidationReport $report, private readonly BaseIndex $base) {}

    /** @param string|null $rawLine the line's bytes, enabling the unchanged-line downgrade */
    public function add(Issue $issue, ?string $rawLine = null): string
    {
        if ($issue->isError() && $rawLine !== null && $issue->id !== null && $issue->file !== null) {
            $type = RecordType::fromFile($issue->file);
            if ($type !== null && $this->base->isUnchanged($type, $issue->id, $rawLine)) {
                $issue = $issue->asWarning(self::UNCHANGED_SUFFIX);
            }
        }

        $key = $issue->file ?? '';
        $state = &$this->files[$key];
        $state ??= ['error' => 0, 'warning' => 0, 'dropped' => 0, 'layer' => $issue->layer, 'note' => ''];
        if ($state[$issue->severity] >= self::MAX_PER_FILE) {
            $state['dropped']++;
        } else {
            $state[$issue->severity]++;
            $this->report->add($issue);
        }
        $state['layer'] = $issue->layer;

        return $issue->severity;
    }

    /** Remember why validation of a file stopped early; shown in its summary. */
    public function note(string $file, string $note): void
    {
        $this->files[$file] ??= ['error' => 0, 'warning' => 0, 'dropped' => 0, 'layer' => Issue::STRUCTURE, 'note' => ''];
        $this->files[$file]['note'] = $note;
    }

    /** Adds the "and N more" warning for every file that overflowed. Call after each layer. */
    public function finish(): void
    {
        foreach ($this->files as $file => $state) {
            if ($state['dropped'] > 0) {
                $this->report->add(Issue::warning($state['layer'], "…and {$state['dropped']} more issues in this file".$state['note'], $file === '' ? null : $file));
            }
            $this->files[$file]['dropped'] = 0;
            $this->files[$file]['note'] = '';
        }
    }
}
