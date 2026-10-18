<?php

declare(strict_types=1);

namespace App\Support\ContentBundle;

use RuntimeException;

/**
 * Thrown by BundleReader when a bundle cannot be opened or an entry cannot be read to the end (missing path,
 * not a zip, bad CRC, truncated stream). It describes the package, not the server, so the validator reports it.
 */
final class BundleReadException extends RuntimeException
{
    /** @param string|null $entry the bundle entry that failed, when the failure is about one entry */
    public function __construct(string $message, public readonly ?string $entry = null)
    {
        parent::__construct($message);
    }
}
