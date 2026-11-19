<?php

declare(strict_types=1);

namespace App\Mcp\Support;

use Laravel\Mcp\Response;
use Laravel\Mcp\ResponseFactory;

/**
 * A tool result. MCP Apps hosts (Claude among them) give the model only the
 * text content; structuredContent goes to the view and is "not added to model
 * context". So the text carries a one-line summary and the same data as
 * compact JSON (nulls and the duplicate thumbnail dropped), and
 * structuredContent carries it in full for the views.
 */
final class Reply
{
    /** Keys the model never needs: the views use them. */
    private const VIEW_ONLY = ['image_url'];

    /** @param array<string, mixed> $data */
    public static function make(string $summary, array $data): ResponseFactory
    {
        $json = json_encode(self::forModel($data), JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);

        return Response::make(Response::text($summary."\n\n".$json))->withStructuredContent($data);
    }

    /**
     * @param  array<array-key, mixed>  $data
     * @return array<array-key, mixed>
     */
    private static function forModel(array $data): array
    {
        $out = [];
        foreach ($data as $key => $value) {
            if ($value === null || (is_string($key) && in_array($key, self::VIEW_ONLY, true))) {
                continue;
            }
            $out[$key] = is_array($value) ? self::forModel($value) : $value;
        }

        return array_is_list($data) ? array_values($out) : $out;
    }
}
