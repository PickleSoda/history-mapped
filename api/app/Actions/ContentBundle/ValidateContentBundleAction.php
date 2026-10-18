<?php

declare(strict_types=1);

namespace App\Actions\ContentBundle;

use App\Support\ContentBundle\Validation\BundleValidator;
use App\Support\ContentBundle\Validation\ValidationReport;

/**
 * Validates a content bundle (directory or .zip). Problems with the bundle, including an unreadable path
 * or archive, are reported as issues; this never throws for a bad bundle. `$againstSite` also checks
 * references and geometries against the database the app is connected to.
 */
final class ValidateContentBundleAction
{
    public function __invoke(string $path, bool $againstSite = false): ValidationReport
    {
        return BundleValidator::validatePath($path, $againstSite);
    }
}
