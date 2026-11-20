<?php

declare(strict_types=1);

namespace Tests\Feature\Site;

use App\Models\Chronicle;
use App\Models\Collection;
use App\Models\Entity;

/** `/site-pages/sitemap.xml` and `/site-pages/sitemaps/*`: the public site's sitemap. */
class SitemapTest extends SiteTestCase
{
    public function test_index_lists_the_page_chronicle_and_256_entity_files(): void
    {
        $response = $this->get('/site-pages/sitemap.xml');

        $response->assertOk();
        $response->assertHeader('Content-Type', 'application/xml; charset=utf-8');
        $this->assertStringContainsString('max-age=21600', (string) $response->headers->get('Cache-Control'));

        $locs = $this->locs((string) $response->getContent(), 'sitemap');
        $this->assertCount(258, $locs);
        $this->assertSame('https://atlas.test/sitemaps/pages.xml', $locs[0]);
        $this->assertSame('https://atlas.test/sitemaps/chronicles.xml', $locs[1]);
        $this->assertSame('https://atlas.test/sitemaps/entities-00.xml', $locs[2]);
        $this->assertSame('https://atlas.test/sitemaps/entities-ff.xml', $locs[257]);
        $this->assertContains('https://atlas.test/sitemaps/entities-a7.xml', $locs);
    }

    public function test_entity_file_holds_the_entities_of_its_prefix_that_have_a_summary(): void
    {
        $in = $this->entityWithId('ab000000-0000-4000-8000-000000000001', 'Readable entity.');
        $last = $this->entityWithId('abffffff-ffff-4fff-bfff-ffffffffffff', 'Last of the range.');
        $empty = $this->entityWithId('ab000000-0000-4000-8000-000000000002', '');
        $none = $this->entityWithId('ab000000-0000-4000-8000-000000000003', null);
        $next = $this->entityWithId('ac000000-0000-4000-8000-000000000001', 'In the next file.');

        $xml = (string) $this->get('/site-pages/sitemaps/entities-ab.xml')->assertOk()->getContent();
        $locs = $this->locs($xml, 'url');

        $this->assertSame([
            'https://atlas.test/entities/'.$in->entity_id,
            'https://atlas.test/entities/'.$last->entity_id,
        ], $locs);
        $this->assertStringNotContainsString($empty->entity_id, $xml);
        $this->assertStringNotContainsString($none->entity_id, $xml);
        $this->assertStringNotContainsString($next->entity_id, $xml);
        $this->assertMatchesRegularExpression('~<lastmod>\d{4}-\d{2}-\d{2}</lastmod>~', $xml);

        $this->assertSame(
            ['https://atlas.test/entities/'.$next->entity_id],
            $this->locs((string) $this->get('/site-pages/sitemaps/entities-ac.xml')->assertOk()->getContent(), 'url'),
        );
    }

    public function test_entity_file_names_outside_two_hex_digits_are_not_found(): void
    {
        foreach (['entities-zz.xml', 'entities-abc.xml', 'entities-AB.xml', 'entities-a.xml'] as $file) {
            $this->get('/site-pages/sitemaps/'.$file)->assertNotFound();
        }
    }

    public function test_chronicle_file_leaves_out_archived_chronicles(): void
    {
        Chronicle::factory()->create(['slug' => 'beta-tale']);
        Chronicle::factory()->published()->create(['slug' => 'alpha-tale']);
        Chronicle::factory()->archived()->create(['slug' => 'put-away']);

        $locs = $this->locs((string) $this->get('/site-pages/sitemaps/chronicles.xml')->assertOk()->getContent(), 'url');

        $this->assertSame([
            'https://atlas.test/chronicles/alpha-tale',
            'https://atlas.test/chronicles/beta-tale',
        ], $locs);
    }

    public function test_page_file_lists_the_fixed_pages_and_published_collections(): void
    {
        Collection::query()->create(['slug' => 'great-battles', 'title' => 'Great battles', 'items' => [], 'status' => 'published']);
        Collection::query()->create(['slug' => 'not-ready', 'title' => 'Not ready', 'items' => [], 'status' => 'draft']);

        $locs = $this->locs((string) $this->get('/site-pages/sitemaps/pages.xml')->assertOk()->getContent(), 'url');

        $this->assertContains('https://atlas.test/', $locs);
        $this->assertContains('https://atlas.test/browse', $locs);
        $this->assertContains('https://atlas.test/docs', $locs);
        $this->assertContains('https://atlas.test/browse/collections/great-battles', $locs);
        $this->assertNotContains('https://atlas.test/browse/collections/not-ready', $locs);
    }

    private function entityWithId(string $id, ?string $summary): Entity
    {
        return Entity::factory()->verified()->create(['entity_id' => $id, 'summary' => $summary]);
    }

    /**
     * The `<loc>` values of a sitemap, read as XML (so it must be well formed).
     *
     * @return list<string>
     */
    private function locs(string $xml, string $element): array
    {
        $doc = simplexml_load_string($xml);
        $this->assertNotFalse($doc, 'the sitemap is not well-formed XML');

        $locs = [];
        foreach ($doc->{$element} as $node) {
            $locs[] = (string) $node->loc;
        }

        return $locs;
    }
}
