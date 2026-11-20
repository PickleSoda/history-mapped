<?php

declare(strict_types=1);

namespace App\Services\Site;

/**
 * What the app fills into the SPA shell for one page: the head tags and the
 * text that sits in the root element until the application starts.
 */
final readonly class SitePage
{
    /**
     * @param  string  $title  The page's own title, without the site name
     * @param  string  $path  Path on the public site, e.g. `/entities/{id}`
     * @param  string  $body  Trusted HTML for the root element (a rendered view)
     * @param  array<string, mixed>|null  $jsonLd  schema.org description of the page
     * @param  string|null  $image  Absolute URL of a picture for link previews
     * @param  bool  $index  False adds `noindex` and leaves out the page's address (not-found pages)
     */
    public function __construct(
        public string $title,
        public string $description,
        public string $path,
        public string $body,
        public ?array $jsonLd = null,
        public ?string $image = null,
        public bool $index = true,
    ) {}
}
