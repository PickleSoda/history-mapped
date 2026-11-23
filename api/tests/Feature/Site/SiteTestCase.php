<?php

declare(strict_types=1);

namespace Tests\Feature\Site;

use App\Services\Site\SiteShell;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\File;
use Tests\TestCase;

/**
 * A stand-in for the built SPA: a directory with an index.html shaped like
 * Vite's output (default title and description, hashed script and stylesheet
 * tags, an empty root element).
 */
abstract class SiteTestCase extends TestCase
{
    use RefreshDatabase;

    protected string $siteDir;

    protected function setUp(): void
    {
        parent::setUp();

        $this->siteDir = sys_get_temp_dir().'/hm-site-'.bin2hex(random_bytes(6));
        File::ensureDirectoryExists($this->siteDir);
        $this->useShell($this->writeShell('release-a'));

        config(['app.frontend_url' => 'https://atlas.test']);
    }

    protected function tearDown(): void
    {
        File::deleteDirectory($this->siteDir);
        SiteShell::flush();

        parent::tearDown();
    }

    /** Write a release's index.html; its script is named after the release. */
    protected function writeShell(string $release): string
    {
        $dir = $this->siteDir.'/releases/'.$release;
        File::ensureDirectoryExists($dir);
        File::put($dir.'/index.html', <<<HTML
            <!DOCTYPE html>
            <html lang="en">
              <head>
                <meta charset="UTF-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                <title>History Mapped</title>
                <meta
                  name="description"
                  content="The default description of the shell."
                />
                <meta property="og:title" content="History Mapped" />
                <meta property="og:image" content="https://atlas.test/og-image.jpg" />
                <meta property="og:image:width" content="1200" />
                <meta name="twitter:card" content="summary_large_image" />
                <script type="module" crossorigin src="/assets/index-{$release}.js"></script>
                <link rel="stylesheet" crossorigin href="/assets/index-{$release}.css">
              </head>
              <body>
                <div id="root"></div>
                <noscript><p>The atlas needs JavaScript to run.</p></noscript>
              </body>
            </html>
            HTML);

        return $dir.'/index.html';
    }

    protected function useShell(string $path): void
    {
        config(['site.shell_path' => $path]);
        SiteShell::flush();
    }
}
