<?php

declare(strict_types=1);

namespace App\Services;

use Closure;
use Illuminate\Http\Client\PendingRequest;
use Illuminate\Http\Client\RequestException;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;
use RuntimeException;
use Throwable;

/**
 * Finds freely licensed images for entities on Wikimedia and describes them as
 * `media_refs` items. Nothing is downloaded or copied: an item is a link to the
 * Commons thumbnail plus the author/license the reuse terms ask us to show.
 *
 * Sources, all keyless public APIs:
 *  - Wikidata Query Service: image-valued claims (P18 image, P41 flag, …)
 *    and the item's English Wikipedia title.
 *  - English Wikipedia `pageimages`: the article's lead image, kept only when
 *    the file lives on Commons (local enwiki files are usually non-free).
 *  - Commons `imageinfo`: thumbnail URL, size and license metadata.
 *
 * Every request sends a descriptive User-Agent (Wikimedia answers 403 without
 * one); API requests also send `maxlag`, so bulk runs back off when the
 * replicas are busy.
 */
class WikimediaImages
{
    public const WIKIDATA_SPARQL = 'https://query.wikidata.org/sparql';

    public const COMMONS_API = 'https://commons.wikimedia.org/w/api.php';

    public const WIKIPEDIA_API = 'https://en.wikipedia.org/w/api.php';

    /** One of Wikimedia's standard thumbnail steps; other widths are throttled. */
    public const THUMB_WIDTH = 960;

    /** Wikimedia caps titles/ids per request at 50 for clients without bot rights. */
    public const BATCH = 50;

    /** Image-valued Wikidata properties and the kind of picture each holds. */
    public const PROPERTIES = [
        'P18' => 'image',
        'P41' => 'flag',
        'P94' => 'coat_of_arms',
        'P158' => 'seal',
        'P154' => 'logo',
        'P3311' => 'plan',
        'P242' => 'map',
        'P1621' => 'map',
        'P15' => 'map',
        'P1846' => 'map',
        'P1943' => 'map',
    ];

    private const EXTMETADATA = 'LicenseShortName|LicenseUrl|Artist|AttributionRequired|ImageDescription|NonFree|ObjectName';

    private const MAX_LAG_RETRIES = 5;

    /**
     * Image claims and the enwiki title for up to 50 Wikidata items, via the
     * query service: `wbgetentities` would return every claim, megabytes per
     * batch for states and people. `wdt:` gives each property's best-rank
     * values (preferred if any, else normal; never deprecated). Merged
     * (redirected) ids return nothing.
     *
     * @param  list<string>  $qids
     * @return array<string, array{files: array<string, list<string>>, wikipedia: ?string}> keyed by QID;
     *                                                                                      `files` maps property => file names
     */
    public function wikidataFiles(array $qids): array
    {
        $qids = array_values(array_filter($qids, fn (string $q): bool => (bool) preg_match('/^Q\d+$/', $q)));
        if ($qids === []) {
            return [];
        }

        $items = implode(' ', array_map(fn (string $q): string => "wd:{$q}", $qids));
        $properties = implode(' ', array_map(fn (string $p): string => "wdt:{$p}", array_keys(self::PROPERTIES)));

        $rows = $this->sparql(<<<SPARQL
            SELECT ?item ?prop ?file ?title WHERE {
              VALUES ?item { {$items} }
              { VALUES ?prop { {$properties} } ?item ?prop ?file . }
              UNION
              { ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?title . }
            }
            SPARQL);

        $out = [];
        foreach ($rows as $row) {
            $qid = Str::afterLast($row['item']['value'], '/');
            $out[$qid] ??= ['files' => [], 'wikipedia' => null];

            if (isset($row['title'])) {
                $out[$qid]['wikipedia'] = $row['title']['value'];
            } elseif (isset($row['file'])) {
                // Commons files come back as …/Special:FilePath/<url-encoded name>.
                $property = Str::afterLast($row['prop']['value'], '/');
                $out[$qid]['files'][$property][] = str_replace('_', ' ', rawurldecode(Str::afterLast($row['file']['value'], '/')));
            }
        }

        return $out;
    }

    /**
     * Lead images of English Wikipedia articles, when they are Commons files.
     *
     * @param  list<string>  $titles
     * @return array<string, string> requested title => Commons file name
     */
    public function wikipediaPageImages(array $titles): array
    {
        $out = [];
        foreach (array_chunk(array_values(array_unique($titles)), self::BATCH) as $chunk) {
            $json = $this->get(self::WIKIPEDIA_API, [
                'action' => 'query',
                'prop' => 'pageimages',
                'piprop' => 'name|original',
                'titles' => implode('|', $chunk),
                'redirects' => 1,
            ]);

            $resolve = self::titleResolver($json['query'] ?? []);
            $byTitle = [];
            foreach ($json['query']['pages'] ?? [] as $page) {
                $file = self::commonsPageImage($page);
                if ($file !== null) {
                    $byTitle[$page['title']] = $file;
                }
            }

            foreach ($chunk as $title) {
                $file = $byTitle[$resolve($title)] ?? null;
                if ($file !== null) {
                    $out[$title] = $file;
                }
            }
        }

        return $out;
    }

    /**
     * Thumbnail and license metadata for Commons files. Missing, non-image and
     * non-free files are left out.
     *
     * @param  list<string>  $files  file names with or without the "File:" prefix
     * @return array<string, array<string, mixed>> requested name => file info
     */
    public function fileInfo(array $files): array
    {
        $out = [];
        foreach (array_chunk(array_values(array_unique($files)), self::BATCH) as $chunk) {
            $json = $this->get(self::COMMONS_API, [
                'action' => 'query',
                'titles' => implode('|', array_map(self::fileTitle(...), $chunk)),
                'redirects' => 1,
                ...self::imageInfoParams(),
            ]);

            $resolve = self::titleResolver($json['query'] ?? []);
            $byTitle = [];
            foreach ($json['query']['pages'] ?? [] as $page) {
                $info = self::describe($page);
                if ($info !== null) {
                    $byTitle[$page['title']] = $info;
                }
            }

            foreach ($chunk as $file) {
                $info = $byTitle[$resolve(self::fileTitle($file))] ?? null;
                if ($info !== null) {
                    $out[$file] = $info;
                }
            }
        }

        return $out;
    }

    /**
     * Commons files whose title or description matches `$query`.
     *
     * @return list<array<string, mixed>> file info, best match first
     */
    public function searchCommons(string $query, int $limit = 12): array
    {
        $json = $this->get(self::COMMONS_API, [
            'action' => 'query',
            'generator' => 'search',
            'gsrsearch' => "filetype:bitmap|drawing {$query}",
            'gsrnamespace' => 6,
            'gsrlimit' => $limit,
            ...self::imageInfoParams(),
        ]);

        $pages = $json['query']['pages'] ?? [];
        usort($pages, fn (array $a, array $b): int => ($a['index'] ?? 0) <=> ($b['index'] ?? 0));

        return array_values(array_filter(array_map(self::describe(...), $pages)));
    }

    /**
     * English Wikipedia articles matching `$query` that have a Commons lead image.
     *
     * @return list<array{title: string, file: string}> best match first
     */
    public function searchWikipedia(string $query, int $limit = 8): array
    {
        $json = $this->get(self::WIKIPEDIA_API, [
            'action' => 'query',
            'generator' => 'search',
            'gsrsearch' => $query,
            'gsrnamespace' => 0,
            'gsrlimit' => $limit,
            'prop' => 'pageimages',
            'piprop' => 'name|original',
        ]);

        $pages = $json['query']['pages'] ?? [];
        usort($pages, fn (array $a, array $b): int => ($a['index'] ?? 0) <=> ($b['index'] ?? 0));

        $out = [];
        foreach ($pages as $page) {
            $file = self::commonsPageImage($page);
            if ($file !== null) {
                $out[] = ['title' => $page['title'], 'file' => $file];
            }
        }

        return $out;
    }

    /**
     * The Commons file name behind a Commons/Wikipedia file page or an
     * upload.wikimedia.org URL (original or thumbnail); null for anything else.
     */
    public static function fileFromUrl(string $url): ?string
    {
        $parts = parse_url(trim($url));
        $host = strtolower($parts['host'] ?? '');
        $path = rawurldecode($parts['path'] ?? '');

        if (preg_match('/(^|\.)(wikimedia|wikipedia)\.org$/', $host) && preg_match('#/wiki/(?:File|Image):(.+)$#i', $path, $m)) {
            return str_replace('_', ' ', $m[1]);
        }

        if ($host === 'upload.wikimedia.org' && preg_match('#^/wikipedia/commons/(?:thumb/)?[0-9a-f]/[0-9a-f]{2}/([^/]+)#', $path, $m)) {
            return str_replace('_', ' ', $m[1]);
        }

        return null;
    }

    /**
     * A `media_refs` item for a described Commons file.
     *
     * @param  array<string, mixed>  $info  from fileInfo()/searchCommons()
     * @return array<string, mixed>
     */
    public static function item(array $info, string $kind, string $source, ?string $property = null): array
    {
        return array_filter([
            'type' => 'image',
            'kind' => $kind,
            'url' => $info['url'],
            'original_url' => $info['original_url'],
            'page_url' => $info['page_url'],
            'file' => $info['file'],
            'caption' => $info['caption'],
            'author' => $info['author'],
            'license' => $info['license'],
            'license_url' => $info['license_url'],
            'attribution_required' => $info['attribution_required'],
            'width' => $info['width'],
            'height' => $info['height'],
            'source' => $source,
            'property' => $property,
            'fetched_at' => now()->toIso8601String(),
        ], fn ($v) => $v !== null);
    }

    /** @return array<string, mixed> */
    private static function imageInfoParams(): array
    {
        return [
            'prop' => 'imageinfo',
            'iiprop' => 'url|size|mime|extmetadata',
            'iiurlwidth' => self::THUMB_WIDTH,
            'iiextmetadatafilter' => self::EXTMETADATA,
            'iiextmetadatalanguage' => 'en',
        ];
    }

    /**
     * @param  array<string, mixed>  $page  a `query.pages` entry with imageinfo
     * @return array<string, mixed>|null
     */
    private static function describe(array $page): ?array
    {
        $ii = $page['imageinfo'][0] ?? null;
        if (! is_array($ii) || isset($page['missing']) || ! str_starts_with((string) ($ii['mime'] ?? ''), 'image/')) {
            return null;
        }

        $meta = fn (string $key): ?string => isset($ii['extmetadata'][$key]['value'])
            ? (string) $ii['extmetadata'][$key]['value']
            : null;

        if ($meta('NonFree') === 'true') {
            return null;
        }

        $thumb = isset($ii['thumburl']);

        return [
            'file' => Str::after($page['title'], 'File:'),
            'url' => self::stripTracking($thumb ? $ii['thumburl'] : $ii['url']),
            'original_url' => self::stripTracking($ii['url']),
            'page_url' => self::stripTracking($ii['descriptionurl'] ?? $ii['url']),
            'width' => (int) ($thumb ? $ii['thumbwidth'] : $ii['width']),
            'height' => (int) ($thumb ? $ii['thumbheight'] : $ii['height']),
            'caption' => self::plain($meta('ImageDescription'), 300) ?? self::plain($meta('ObjectName'), 300),
            'author' => self::author($meta('Artist')),
            'license' => self::plain($meta('LicenseShortName'), 80),
            'license_url' => $meta('LicenseUrl') ? self::stripTracking($meta('LicenseUrl')) : null,
            'attribution_required' => $meta('AttributionRequired') !== 'false',
        ];
    }

    /**
     * File names of a claim list: preferred rank first, deprecated dropped.
     *
     * @param  list<array<string, mixed>>  $claims
     * @return list<string>
     */
    private static function claimValues(array $claims): array
    {
        $ranked = ['preferred' => [], 'normal' => []];
        foreach ($claims as $claim) {
            $value = $claim['mainsnak']['datavalue']['value'] ?? null;
            $rank = $claim['rank'] ?? 'normal';
            if (is_string($value) && isset($ranked[$rank])) {
                $ranked[$rank][] = $value;
            }
        }

        return [...$ranked['preferred'], ...$ranked['normal']];
    }

    /** @param  array<string, mixed>  $page */
    private static function commonsPageImage(array $page): ?string
    {
        $name = $page['pageimage'] ?? null;
        $source = (string) ($page['original']['source'] ?? '');

        return is_string($name) && str_contains($source, '/wikipedia/commons/')
            ? str_replace('_', ' ', $name)
            : null;
    }

    /**
     * Follows `normalized` and `redirects` from a requested title to the title
     * the pages are keyed by.
     *
     * @param  array<string, mixed>  $query
     * @return Closure(string): string
     */
    private static function titleResolver(array $query): Closure
    {
        $map = [];
        foreach ([...($query['normalized'] ?? []), ...($query['redirects'] ?? [])] as $step) {
            $map[$step['from']] = $step['to'];
        }

        return function (string $title) use ($map): string {
            for ($i = 0; $i < 3 && isset($map[$title]); $i++) {
                $title = $map[$title];
            }

            return $title;
        };
    }

    private static function fileTitle(string $file): string
    {
        return 'File:'.preg_replace('/^(File|Image):/i', '', $file);
    }

    /** Commons appends utm_* campaign parameters to the URLs it hands out. */
    private static function stripTracking(string $url): string
    {
        $query = parse_url($url, PHP_URL_QUERY);
        if (! is_string($query)) {
            return $url;
        }

        parse_str($query, $params);
        $params = array_filter($params, fn ($k) => ! str_starts_with((string) $k, 'utm_'), ARRAY_FILTER_USE_KEY);

        return Str::before($url, '?').($params ? '?'.http_build_query($params) : '');
    }

    /**
     * The Artist field as a name. Boilerplate ("See File history below…",
     * "This vector image includes elements…") is dropped: the file page,
     * which every credit links to, carries the full attribution.
     */
    private static function author(?string $html): ?string
    {
        $text = self::plain($html, 200);

        return $text !== null && preg_match('/^(see file history|this (vector )?(image|file)|own work$)/i', $text) ? null : $text;
    }

    /** Commons metadata is HTML; keep the visible text, collapsed and capped. */
    private static function plain(?string $html, int $max): ?string
    {
        if ($html === null) {
            return null;
        }

        // Templates such as {{Unknown author}} repeat their text in a hidden span.
        $html = (string) preg_replace('#<(\w+)[^>]*display:\s*none[^>]*>.*?</\1>#is', '', $html);
        $text = trim((string) preg_replace('/\s+/u', ' ', html_entity_decode(strip_tags($html), ENT_QUOTES | ENT_HTML5)));

        return $text === '' ? null : Str::limit($text, $max, '…');
    }

    /**
     * @param  array<string, mixed>  $params
     * @return array<string, mixed>
     */
    private function get(string $endpoint, array $params): array
    {
        $params = ['format' => 'json', 'formatversion' => 2, 'maxlag' => 5, ...$params];

        for ($attempt = 0; ; $attempt++) {
            $response = $this->client()->get($endpoint, $params);
            $json = $response->json();

            if (($json['error']['code'] ?? null) === 'maxlag' && $attempt < self::MAX_LAG_RETRIES) {
                sleep(max(1, (int) $response->header('Retry-After')));

                continue;
            }

            if ($response->failed() || ! is_array($json) || isset($json['error'])) {
                throw new RuntimeException(sprintf(
                    'Wikimedia request to %s failed: %s',
                    parse_url($endpoint, PHP_URL_HOST),
                    $json['error']['info'] ?? "HTTP {$response->status()}",
                ));
            }

            return $json;
        }
    }

    /**
     * @return list<array<string, array{value: string}>> result bindings
     */
    private function sparql(string $query): array
    {
        $response = $this->client()
            ->accept('application/sparql-results+json')
            ->asForm()
            ->post(self::WIKIDATA_SPARQL, ['query' => $query]);

        $bindings = $response->json('results.bindings');
        if ($response->failed() || ! is_array($bindings)) {
            throw new RuntimeException("Wikidata query service request failed: HTTP {$response->status()}");
        }

        return $bindings;
    }

    private function client(): PendingRequest
    {
        // Wikimedia rejects requests without a descriptive User-Agent (https://w.wiki/4wJS).
        return Http::acceptJson()
            ->withUserAgent((string) env('WIKIDATA_USER_AGENT', 'history-mapped/1.0 (https://github.com/PickleSoda/history-mapped)'))
            ->timeout(30)
            ->retry(3, 2000, fn (Throwable $e): bool => ! $e instanceof RequestException
                || $e->response->serverError() || $e->response->status() === 429, throw: false);
    }
}
