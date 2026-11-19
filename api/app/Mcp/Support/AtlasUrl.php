<?php

declare(strict_types=1);

namespace App\Mcp\Support;

/**
 * Links into the public atlas site, so a model can cite a record and a reader
 * can open it. The base is the SPA's origin (`app.frontend_url`), not the API's.
 */
final class AtlasUrl
{
    public static function entity(string $id): string
    {
        return self::base().'/entities/'.$id;
    }

    public static function chronicle(string $slug): string
    {
        return self::base().'/chronicles/'.rawurlencode($slug);
    }

    /** The map at a signed year, optionally with one entity selected. */
    public static function map(int $year, ?string $selectedId = null): string
    {
        return self::base().'/app?t='.$year.($selectedId !== null ? '&sel='.$selectedId : '');
    }

    private static function base(): string
    {
        return rtrim((string) config('app.frontend_url'), '/');
    }
}
