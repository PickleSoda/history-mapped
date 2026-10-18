<?php

declare(strict_types=1);

namespace App\Support\ContentBundle;

/**
 * The single JSON encoding used for bundle lines, so identical records always produce identical bytes.
 */
final class JsonLine
{
    private const FLAGS = JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRESERVE_ZERO_FRACTION | JSON_THROW_ON_ERROR;

    /**
     * Encode one record as a single line, without a trailing newline. Key order is preserved.
     *
     * @param  array<string, mixed>  $record
     */
    public static function encode(array $record): string
    {
        return json_encode($record, self::FLAGS);
    }
}
