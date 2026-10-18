<?php

declare(strict_types=1);

namespace App\Support\ContentBundle;

use RuntimeException;

/**
 * Thrown by BundleReader when a package exceeds the entry-count or size limits, whether the header
 * says so at open() or the bytes actually read do. The validator reports it as a package error.
 */
final class BundleLimitExceededException extends RuntimeException
{
    /** @param string|null $entry the bundle entry that hit the limit, when the limit is about one entry */
    public function __construct(string $message, public readonly ?string $entry = null)
    {
        parent::__construct($message);
    }
}
