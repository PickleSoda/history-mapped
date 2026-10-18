<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

/** One broken record rule: a JSON pointer into the record and a plain-language message. */
final readonly class RuleViolation
{
    public function __construct(
        public string $field,
        public string $message,
        public string $severity = Issue::ERROR,
    ) {}
}
