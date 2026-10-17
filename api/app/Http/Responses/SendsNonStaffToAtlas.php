<?php

declare(strict_types=1);

namespace App\Http\Responses;

use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

/**
 * Fortify's browser (non-JSON) auth redirects land on the admin dashboard.
 * Accounts without `admin.access` would only meet a 403 there, so send them
 * to the public atlas instead. JSON responses (the SPA) are left untouched.
 */
trait SendsNonStaffToAtlas
{
    /** @param  Request  $request */
    public function toResponse($request): Response
    {
        if (! $request->wantsJson() && ! $request->user()?->can('admin.access')) {
            return redirect()->away(config('app.frontend_url').'/');
        }

        return parent::toResponse($request);
    }
}
