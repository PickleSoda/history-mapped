<?php

use App\Http\Site\SitemapController;
use App\Http\Site\SitePageController;
use Illuminate\Support\Facades\Route;

/*
|--------------------------------------------------------------------------
| Public site pages and sitemaps rendered by the app
|--------------------------------------------------------------------------
|
| Mounted at /site-pages by bootstrap/app.php. Caddy sends the public site's
| /entities/*, /chronicles/*, /sitemap.xml and /sitemaps/* here with the
| prefix added (docker/Caddyfile), so the paths below are the site's own.
| Public GETs: no session or CSRF, and the `site` rate limit per address.
| See config/site.php and docs/architecture/frontend-app.md.
|
*/

Route::get('/sitemap.xml', [SitemapController::class, 'index'])->name('site.sitemap');
Route::get('/sitemaps/pages.xml', [SitemapController::class, 'pages'])->name('site.sitemap.pages');
Route::get('/sitemaps/chronicles.xml', [SitemapController::class, 'chronicles'])->name('site.sitemap.chronicles');
Route::get('/sitemaps/entities-{prefix}.xml', [SitemapController::class, 'entities'])
    ->where('prefix', '[0-9a-f]{2}')
    ->name('site.sitemap.entities');

Route::get('/entities/{id}', [SitePageController::class, 'entity'])->name('site.entity');
Route::get('/chronicles/{slug}', [SitePageController::class, 'chronicle'])->name('site.chronicle');

// Anything else under those paths is not a page of the site: answer with the
// app's not-found page, not the framework's.
Route::get('/{any}', [SitePageController::class, 'missing'])->where('any', '.*')->name('site.missing');
