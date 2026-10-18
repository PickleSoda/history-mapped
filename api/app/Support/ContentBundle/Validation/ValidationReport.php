<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

/**
 * The ordered findings of one validation run.
 */
final class ValidationReport
{
    /** @var list<Issue> */
    private array $issues = [];

    public function add(Issue $issue): void
    {
        $this->issues[] = $issue;
    }

    /** @return list<Issue> */
    public function issues(): array
    {
        return $this->issues;
    }

    /** @return list<Issue> */
    public function errors(): array
    {
        return array_values(array_filter($this->issues, fn (Issue $i) => $i->isError()));
    }

    /** @return list<Issue> */
    public function warnings(): array
    {
        return array_values(array_filter($this->issues, fn (Issue $i) => ! $i->isError()));
    }

    public function isValid(): bool
    {
        return $this->errors() === [];
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
            'errors' => count($this->errors()),
            'warnings' => count($this->warnings()),
            'issues' => array_map(fn (Issue $i) => $i->toArray(), $this->issues),
        ];
    }
}
