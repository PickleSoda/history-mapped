<?php

declare(strict_types=1);

namespace App\Http\Site;

use App\Models\Chronicle;
use App\Models\Collection;
use App\Services\Site\SiteShell;
use Illuminate\Http\Response;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;

/**
 * The public site's sitemap, generated from the database on request.
 *
 * `/sitemap.xml` is an index of: the fixed pages, the chronicles, and the
 * entities in 256 files, one per first two hex digits of the entity id. Ids
 * are random UUIDs, so each file holds 1/256 of the entities (about 2,500 at
 * 640,000 entities; the format allows 50,000) and is one range scan of the
 * primary key. Nothing is stored: the files are small and crawlers are told to
 * keep them for `site.sitemap_max_age`.
 */
class SitemapController
{
    private const HEX = '0123456789abcdef';

    /** Pages of the web app that are not rows in the database. */
    private const PAGES = ['/', '/browse', '/browse/stories', '/app', '/docs'];

    public function index(): Response
    {
        $files = ['pages', 'chronicles'];
        foreach (str_split(self::HEX) as $a) {
            foreach (str_split(self::HEX) as $b) {
                $files[] = 'entities-'.$a.$b;
            }
        }

        $xml = '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'."\n";
        foreach ($files as $file) {
            $xml .= '<sitemap><loc>'.$this->loc('/sitemaps/'.$file.'.xml').'</loc></sitemap>'."\n";
        }

        return $this->xml($xml.'</sitemapindex>');
    }

    public function pages(): Response
    {
        $urls = array_map(fn (string $path): array => [$path, null], self::PAGES);

        foreach (Collection::query()->published()->ordered()->get(['slug', 'updated_at']) as $set) {
            $urls[] = ['/browse/collections/'.rawurlencode($set->slug), $set->updated_at];
        }

        return $this->urlset($urls);
    }

    public function chronicles(): Response
    {
        $urls = Chronicle::query()
            ->notArchived()
            ->orderBy('slug')
            ->get(['slug', 'updated_at'])
            ->map(fn (Chronicle $c): array => ['/chronicles/'.rawurlencode($c->slug), $c->updated_at])
            ->all();

        return $this->urlset($urls);
    }

    /** Entities whose id starts with the two hex digits `$prefix`, if they have a summary to read. */
    public function entities(string $prefix): Response
    {
        $rows = DB::table('entities')
            ->whereBetween('entity_id', [
                $prefix.'000000-0000-0000-0000-000000000000',
                $prefix.'ffffff-ffff-ffff-ffff-ffffffffffff',
            ])
            ->whereNotNull('summary')
            ->where('summary', '<>', '')
            ->orderBy('entity_id')
            ->get(['entity_id', 'updated_at']);

        return $this->urlset($rows->map(fn (object $row): array => ['/entities/'.$row->entity_id, $row->updated_at])->all());
    }

    /**
     * @param  list<array{0: string, 1: mixed}>  $urls  path and last change (a date, a date string or null)
     */
    private function urlset(array $urls): Response
    {
        $xml = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'."\n";
        foreach ($urls as [$path, $changed]) {
            $xml .= '<url><loc>'.$this->loc($path).'</loc>';
            if ($changed !== null) {
                $xml .= '<lastmod>'.Carbon::parse($changed)->toDateString().'</lastmod>';
            }
            $xml .= '</url>'."\n";
        }

        return $this->xml($xml.'</urlset>');
    }

    private function loc(string $path): string
    {
        return htmlspecialchars(SiteShell::url($path), ENT_XML1 | ENT_QUOTES, 'UTF-8');
    }

    private function xml(string $body): Response
    {
        return response('<?xml version="1.0" encoding="UTF-8"?>'."\n".$body."\n", 200, [
            'Content-Type' => 'application/xml; charset=utf-8',
            'Cache-Control' => 'public, max-age='.(int) config('site.sitemap_max_age'),
        ]);
    }
}
