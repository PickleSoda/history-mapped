<?php

use App\Http\Middleware\HandleAppearance;
use App\Http\Middleware\HandleInertiaRequests;
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Middleware\AddLinkHeadersForPreloadedAssets;
use Illuminate\Support\Facades\Route;
use Spatie\Permission\Middleware\PermissionMiddleware;
use Spatie\Permission\Middleware\RoleMiddleware;
use Spatie\Permission\Middleware\RoleOrPermissionMiddleware;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        api: __DIR__.'/../routes/api.php',
        apiPrefix: 'api',
        commands: __DIR__.'/../routes/console.php',
        health: '/up',
        // Vector tiles served by the app (TILES_DRIVER=app): Martin's /tiles
        // URLs, outside the `api` group (no session, CSRF or throttle).
        then: function (): void {
            Route::prefix('tiles')->group(base_path('routes/tiles.php'));

            // Entity and chronicle pages of the public site with their text in
            // the HTML, and its sitemap (routes/site.php). Caddy sends those
            // paths of the site here. No session or CSRF; the `site` limiter.
            Route::prefix('site-pages')->middleware('throttle:site')->group(base_path('routes/site.php'));
        },
    )
    ->withMiddleware(function (Middleware $middleware): void {
        // Behind Nginx (TLS terminated at the proxy), trust the forwarded
        // headers so Laravel sees the original https scheme — otherwise asset()
        // / Vite emit http:// URLs that the browser blocks as mixed content.
        $middleware->trustProxies(at: '*');

        $middleware->statefulApi();
        // The `api` limiter (AppServiceProvider): API_RATE_LIMIT requests a minute.
        $middleware->throttleApi();
        $middleware->encryptCookies(except: ['appearance', 'sidebar_state']);

        // spatie/laravel-permission middleware aliases (used to gate write routes).
        $middleware->alias([
            'role' => RoleMiddleware::class,
            'permission' => PermissionMiddleware::class,
            'role_or_permission' => RoleOrPermissionMiddleware::class,
        ]);

        $middleware->web(append: [
            HandleAppearance::class,
            HandleInertiaRequests::class,
            AddLinkHeadersForPreloadedAssets::class,
        ]);
    })
    ->withExceptions(function (Exceptions $exceptions): void {
        //
    })->create();
