<?php

declare(strict_types=1);

namespace App\Http\Site;

use App\Services\Site\SitePage;
use App\Services\Site\SitePages;
use App\Services\Site\SiteShell;
use Illuminate\Http\Response;

/**
 * Public site pages rendered by the app: the SPA's index.html with one page's
 * title, description and text filled in, so a reader that runs no JavaScript
 * (most AI crawlers, link previews) gets the content. Caddy sends the public
 * site's /entities/* and /chronicles/* here (docker/Caddyfile); the web app
 * then starts and takes over the page. Routes: routes/site.php.
 *
 * Without the shell file there is nothing to fill in: the answer is 503 and
 * Caddy serves the plain index.html instead, as it did before.
 */
class SitePageController
{
    public function __construct(
        private readonly SitePages $pages,
        private readonly SiteShell $shell,
    ) {}

    public function entity(string $id): Response
    {
        $page = $this->pages->entity($id);

        return $page !== null
            ? $this->respond($page, 200)
            : $this->respond($this->pages->notFound(
                'Entity not found',
                'There is no entity at this address. It may have been merged into another one, or the link may be mistyped.',
            ), 404);
    }

    public function chronicle(string $slug): Response
    {
        $page = $this->pages->chronicle($slug);

        return $page !== null
            ? $this->respond($page, 200)
            : $this->respond($this->pages->notFound(
                'Chronicle not found',
                'There is no chronicle at this address. The link may be mistyped, or the chronicle may have been renamed.',
            ), 404);
    }

    /** Any other address under the paths Caddy sends here. */
    public function missing(): Response
    {
        return $this->respond($this->pages->notFound('Page not found', 'There is no page at this address.'), 404);
    }

    private function respond(SitePage $page, int $status): Response
    {
        $html = $this->shell->render($page);

        if ($html === null) {
            return response('The site shell is not available.', 503, [
                'Content-Type' => 'text/plain; charset=utf-8',
                'Retry-After' => '30',
            ]);
        }

        // The shell names the current release's scripts: never reuse a copy
        // without asking, or a visitor is sent to files a deploy removed.
        return response($html, $status, [
            'Content-Type' => 'text/html; charset=utf-8',
            'Cache-Control' => 'no-cache',
        ]);
    }
}
