<?php

declare(strict_types=1);

namespace App\Support\ContentBundle;

use Opis\JsonSchema\Validator;

/**
 * One shared opis Validator whose resolver maps the schemas' `$id` base URL to the schema directory,
 * so `$ref`s between schema files resolve locally. The instance is shared and configured once to collect
 * all errors; callers must not mutate it. Validate decoded objects (stdClass), not arrays.
 */
final class Schemas
{
    public const BASE_URL = 'https://history-mapped.local/schemas/content-bundle/v1/';

    private static ?Validator $validator = null;

    public static function validator(): Validator
    {
        if (self::$validator === null) {
            $validator = new Validator(null, 1000, false); // collect every error, never stop at the first
            $validator->resolver()->registerPrefix(self::BASE_URL, BundleFormat::schemaDir());
            self::$validator = $validator;
        }

        return self::$validator;
    }

    public static function recordSchemaId(RecordType $type): string
    {
        return self::BASE_URL.$type->schemaFile();
    }

    public static function manifestSchemaId(): string
    {
        return self::BASE_URL.'manifest.schema.json';
    }
}
