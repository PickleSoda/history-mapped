<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

use App\Support\ContentBundle\RecordType;

/**
 * The ordered findings of one validation run. The issue list is capped per file by IssueSink; the counts
 * (errorCount(), warningCount(), toArray()) are the true totals, including issues dropped by the cap.
 * "…and N more" summary lines are in the list but not in the counts.
 */
final class ValidationReport
{
    /** @var list<Issue> */
    private array $issues = [];

    private int $droppedErrors = 0;

    private int $droppedWarnings = 0;

    private int $summaries = 0;

    public function add(Issue $issue): void
    {
        $this->issues[] = $issue;
    }

    /** Adds an "and N more" line and records how many issues of each severity the cap dropped. */
    public function addSummary(Issue $summary, int $droppedErrors, int $droppedWarnings): void
    {
        $this->issues[] = $summary;
        $this->summaries++;
        $this->droppedErrors += $droppedErrors;
        $this->droppedWarnings += $droppedWarnings;
    }

    /**
     * Stable order for output: by layer (in order of first report), then record files in RecordType order before other files, then line
     * with null last, then the order issues were reported in.
     */
    public function sort(): void
    {
        // Layers keep the order in which they first reported, so a package error found late stays last.
        $layers = [];
        foreach ($this->issues as $issue) {
            $layers[$issue->layer] ??= count($layers);
        }
        $files = [];
        foreach (RecordType::cases() as $i => $type) {
            $files[$type->file()] = $i;
        }
        $keyed = [];
        foreach ($this->issues as $i => $issue) {
            $keyed[] = [$layers[$issue->layer], $files[$issue->file ?? ''] ?? count($files), $issue->line ?? PHP_INT_MAX, $i, $issue];
        }
        usort($keyed, fn (array $a, array $b) => [$a[0], $a[1], $a[2], $a[3]] <=> [$b[0], $b[1], $b[2], $b[3]]);
        $this->issues = array_map(fn (array $k) => $k[4], $keyed);
    }

    /** @return list<Issue> */
    public function issues(): array
    {
        return $this->issues;
    }

    /** @return list<Issue> the errors kept in the list (capped per file) */
    public function errors(): array
    {
        return array_values(array_filter($this->issues, fn (Issue $i) => $i->isError()));
    }

    /** @return list<Issue> the warnings kept in the list, summary lines included */
    public function warnings(): array
    {
        return array_values(array_filter($this->issues, fn (Issue $i) => ! $i->isError()));
    }

    public function errorCount(): int
    {
        return count($this->errors()) + $this->droppedErrors;
    }

    public function warningCount(): int
    {
        return count($this->warnings()) - $this->summaries + $this->droppedWarnings;
    }

    public function isValid(): bool
    {
        return $this->errorCount() === 0;
    }

    public function hasErrorsIn(string $layer): bool
    {
        foreach ($this->issues as $issue) {
            if ($issue->isError() && $issue->layer === $layer) {
                return true;
            }
        }

        return false;
    }

    /** @return array{valid: bool, errors: int, warnings: int, issues: list<array<string, mixed>>} */
    public function toArray(): array
    {
        return [
            'valid' => $this->isValid(),
            'errors' => $this->errorCount(),
            'warnings' => $this->warningCount(),
            'issues' => array_map(fn (Issue $i) => $i->toArray(), $this->issues),
        ];
    }
}
