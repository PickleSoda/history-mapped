<?php

declare(strict_types=1);

namespace App\Support\ContentBundle;

use RuntimeException;

/**
 * Thrown by BundleReader when a package exceeds the entry-count or size limits, whether the header
 * says so at open() or the bytes actually read do. The validator reports it as a package error.
 */
final class BundleLimitExceededException extends RuntimeException {}
