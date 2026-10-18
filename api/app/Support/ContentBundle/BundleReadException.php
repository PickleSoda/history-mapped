<?php

declare(strict_types=1);

namespace App\Support\ContentBundle;

use RuntimeException;

/**
 * Thrown by BundleReader when a bundle cannot be opened or an entry cannot be read to the end (missing path,
 * not a zip, bad CRC, truncated stream). It describes the package, not the server, so the validator reports it.
 */
final class BundleReadException extends RuntimeException {}
