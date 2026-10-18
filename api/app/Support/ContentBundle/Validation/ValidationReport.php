<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

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
