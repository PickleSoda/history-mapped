<?php

declare(strict_types=1);

namespace App\Services\Site;

use Illuminate\Support\Str;

/**
 * The SPA's built index.html, and how a page is written into it.
 *
 * The shell is the file Caddy serves for every site route. Filling a page into
 * it (instead of rendering a separate document) keeps one source for the
 * script and stylesheet tags, whose hashed names change with each release.
 * The text goes inside the root element: React replaces it when it starts, so
 * visitors and crawlers are sent the same HTML.
 */
class SiteShell
{
    public const SITE_NAME = 'History Mapped';

    /** The site's link-preview card, served by the web app (web/public/og-image.jpg). */
    public const DEFAULT_IMAGE = '/og-image.jpg';

    private const ROOT = '<div id="root"></div>';

    /**
     * One shell per worker, re-read when the file behind the path changes.
     *
     * @var array{key: string, html: string}|null
     */
    private static ?array $memo = null;

    /** The shell, or null when it is missing or not the SPA's index.html. */
    public function html(): ?string
    {
        $file = $this->resolve((string) config('site.shell_path'));

        clearstatcache(false, $file);
        if (! is_file($file) || ! is_readable($file)) {
            return null;
        }

        $key = $file.'|'.filemtime($file);
        if (self::$memo === null || self::$memo['key'] !== $key) {
            $html = (string) file_get_contents($file);
            if (! str_contains($html, self::ROOT) || ! str_contains($html, '</head>')) {
                return null;
            }
            self::$memo = ['key' => $key, 'html' => $html];
        }

        return self::$memo['html'];
    }

    /** The shell with the page written into it, or null when there is no shell. */
    public function render(SitePage $page): ?string
    {
        $shell = $this->html();
        if ($shell === null) {
            return null;
        }

        // The shell's own title and description are defaults for pages the
        // app does not render; this page brings its own.
        $html = (string) preg_replace('~<title>.*?</title>\s*~is', '', $shell, 1);
        $html = (string) preg_replace(
            '~<meta\s+(?:name|property)="(?:description|og:[^"]+|twitter:[^"]+)"[^>]*>\s*~i',
            '',
            $html,
        );

        $head = view('site.head', [
            'page' => $page,
            'title' => $page->title === '' ? self::SITE_NAME : $page->title.' · '.self::SITE_NAME,
            'url' => self::url($page->path),
            'siteName' => self::SITE_NAME,
            'defaultImage' => self::url(self::DEFAULT_IMAGE),
            'jsonLd' => $page->jsonLd === null ? null : json_encode(
                $page->jsonLd,
                JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_AMP | JSON_THROW_ON_ERROR,
            ),
        ])->render();

        $html = Str::replaceFirst('</head>', "\n    ".trim($head)."\n  </head>", $html);

        return Str::replaceFirst(self::ROOT, '<div id="root">'.$page->body.'</div>', $html);
    }

    /** Absolute URL of a path on the public site. */
    public static function url(string $path): string
    {
        return rtrim((string) config('app.frontend_url'), '/').'/'.ltrim($path, '/');
    }

    /** Forget the shell read by this worker (tests swap the file). */
    public static function flush(): void
    {
        self::$memo = null;
    }

    /**
     * On the hosted site the shell's directory is the `current` symlink, which
     * each release re-points. PHP remembers how it resolved a path for two
     * minutes, long enough to keep serving the previous release's shell (whose
     * scripts are gone) after a deploy. Reading the link itself is not cached,
     * so follow it by hand.
     */
    private function resolve(string $path): string
    {
        $dir = dirname($path);
        $target = is_link($dir) ? readlink($dir) : false;
        if ($target === false) {
            return $path;
        }

        $base = str_starts_with($target, '/') ? $target : dirname($dir).'/'.$target;

        return rtrim($base, '/').'/'.basename($path);
    }
}
