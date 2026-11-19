<?php

declare(strict_types=1);

namespace App\Http\Responses;

use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

/**
 * Fortify's browser (non-JSON) auth redirects land on the admin dashboard.
 * Accounts without `admin.access` would only meet a 403 there, so send them
 * to the public site's landing page (`/`; the atlas itself is at `/app`)
 * instead. JSON responses (the SPA) are left untouched. The exception is a
 * sign-in that began at the OAuth consent page (an MCP client such as Claude
 * connecting to /mcp/contribute): that returns to the authorize URL, whatever
 * the account's role, so the connect flow can finish.
 */
trait SendsNonStaffToAtlas
{
    /** @param  Request  $request */
    public function toResponse($request): Response
    {
        if (! $request->wantsJson() && ! self::resumesOAuthAuthorization($request) && ! $request->user()?->can('admin.access')) {
            return redirect()->away(config('app.frontend_url').'/');
        }

        return parent::toResponse($request);
    }

    private static function resumesOAuthAuthorization(Request $request): bool
    {
        $intended = (string) $request->session()->get('url.intended', '');

        return str_starts_with((string) parse_url($intended, PHP_URL_PATH), '/oauth/authorize');
    }
}
