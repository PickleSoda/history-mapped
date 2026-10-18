<?php

declare(strict_types=1);

namespace App\Support\ContentBundle;

use RuntimeException;

/**
 * Thrown by BundleReader::lines() when a line exceeds the byte limit. The validator catches it and
 * reports `file:line`; lines before the offender have already been yielded.
 */
final class BundleLineTooLongException extends RuntimeException
{
    public function __construct(public readonly string $bundleFile, public readonly int $lineNumber, public readonly int $limit)
    {
        parent::__construct("{$bundleFile} line {$lineNumber} is longer than {$limit} bytes.");
    }
}
