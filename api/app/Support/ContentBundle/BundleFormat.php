<?php

declare(strict_types=1);

namespace App\Support\ContentBundle;

/**
 * Constants of the content-bundle on-disk format. Bump VERSION (and add a v2 schema dir) for breaking changes.
 */
final class BundleFormat
{
    public const FORMAT = 'history-mapped/content-bundle';

    public const VERSION = 1;

    public const MANIFEST = 'manifest.json';

    public const BASE_DIR = '_base';

    public const LICENSE = 'LICENSE.md';

    /** Directory holding the v1 JSON Schemas (a method because resource_path() is a runtime helper). */
    public static function schemaDir(): string
    {
        return resource_path('schemas/content-bundle/v1');
    }
}
