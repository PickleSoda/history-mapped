<?php

declare(strict_types=1);

namespace Tests\Feature\Site;

use App\Enums\EntityType;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use App\Models\EntityRelationship;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

/**
 * `/site-pages/entities/{id}` and `/site-pages/chronicles/{slug}`: the SPA
 * shell with one page's head tags and text written into it (routes/site.php).
 */
class SitePageTest extends SiteTestCase
{
    public function test_entity_page_is_the_shell_with_the_entity_written_in(): void
    {
        $hannibal = Entity::factory()->verified()->ofType(EntityType::Person)->atLocation('Carthage')
            ->withTemporalRange('-247', '-183')
            ->create([
                'name' => 'Hannibal',
                'summary' => 'Carthaginian general who crossed the Alps.',
                'significance' => 'He won at Cannae.',
                'description' => "First paragraph.\n\nSecond paragraph.",
                'wikidata_id' => 'Q36456',
            ]);
        $cannae = Entity::factory()->verified()->ofType(EntityType::EventBattle)->withTemporalRange('-216', '-216')
            ->create(['name' => 'Battle of Cannae']);
        $this->relate($hannibal, $cannae, 'commanded');
        $carthage = Entity::factory()->verified()->ofType(EntityType::City)->create(['name' => 'Carthage']);
        $this->relate($carthage, $hannibal, 'governed_by');

        $chronicle = Chronicle::factory()->create(['title' => 'The Second Punic War', 'slug' => 'second-punic-war']);
        $this->step($chronicle, 1, 'Hannibal crosses the Alps.', [$hannibal]);

        $response = $this->get('/site-pages/entities/'.$hannibal->entity_id);

        $response->assertOk();
        $response->assertHeader('Content-Type', 'text/html; charset=utf-8');
        $this->assertStringContainsString('no-cache', (string) $response->headers->get('Cache-Control'));
        $html = (string) $response->getContent();

        // Head: the page's own tags replace the shell's defaults.
        $this->assertSame(1, substr_count($html, '<title>'));
        $this->assertStringContainsString('<title>Hannibal · History Mapped</title>', $html);
        $this->assertSame(1, preg_match_all('/<meta\s+name="description"/', $html));
        $this->assertStringContainsString('<meta name="description" content="Carthaginian general who crossed the Alps.">', $html);
        $this->assertStringNotContainsString('The default description of the shell.', $html);
        $this->assertStringContainsString('<link rel="canonical" href="https://atlas.test/entities/'.$hannibal->entity_id.'">', $html);
        $this->assertSame(1, substr_count($html, 'property="og:title"'));
        $this->assertStringContainsString('<meta property="og:title" content="Hannibal">', $html);
        // No picture of his own: the site's card, once (the shell's image tags are replaced).
        $this->assertSame(1, substr_count($html, 'property="og:image'));
        $this->assertStringContainsString('<meta property="og:image" content="https://atlas.test/og-image.jpg">', $html);
        $this->assertSame(1, substr_count($html, 'name="twitter:card"'));
        $this->assertStringNotContainsString('noindex', $html);

        $ld = $this->jsonLd($html);
        $this->assertSame('WebPage', $ld['@type']);
        $this->assertSame('https://atlas.test/entities/'.$hannibal->entity_id, $ld['url']);
        $this->assertSame('Person', $ld['about']['@type']);
        $this->assertSame(['https://www.wikidata.org/wiki/Q36456'], $ld['about']['sameAs']);

        // The shell's own tags are kept: the app still starts.
        $this->assertStringContainsString('src="/assets/index-release-a.js"', $html);
        $this->assertStringContainsString('<noscript>', $html);

        // Body: the text sits inside the root element.
        $this->assertMatchesRegularExpression('~<div id="root"><article id="hm-static">.*</article></div>~s', $html);
        $this->assertStringContainsString('<h1>Hannibal</h1>', $html);
        $this->assertStringContainsString('Person · 247 BCE – 183 BCE', $html);
        $this->assertStringContainsString('Carthage', $html);
        $this->assertStringContainsString('<h2>Significance</h2>', $html);
        $this->assertStringContainsString('<p>First paragraph.</p>', $html);
        $this->assertStringContainsString('<p>Second paragraph.</p>', $html);
        $this->assertStringContainsString('Commanded <a href="/entities/'.$cannae->entity_id.'">Battle of Cannae</a> (Battle, 216 BCE)', $html);
        $this->assertStringContainsString('Governs <a href="/entities/'.$carthage->entity_id.'">Carthage</a>', $html);
        $this->assertStringContainsString('<a href="/chronicles/second-punic-war">The Second Punic War</a>', $html);
        $this->assertStringContainsString('<a href="/app?sel='.$hannibal->entity_id.'&amp;full=1">Open on the globe</a>', $html);
        $this->assertStringContainsString('Wikidata Q36456', $html);
    }

    public function test_entity_text_is_escaped_in_the_head_and_the_body(): void
    {
        $entity = Entity::factory()->verified()->create([
            'name' => 'A "quoted" <b>name</b>',
            'summary' => 'Text with </script><script>alert(1)</script> and an & sign.',
        ]);

        $html = (string) $this->get('/site-pages/entities/'.$entity->entity_id)->assertOk()->getContent();

        $this->assertStringNotContainsString('<b>name</b>', $html);
        $this->assertStringNotContainsString('<script>alert(1)</script>', $html);
        $this->assertStringContainsString('<h1>A &quot;quoted&quot; &lt;b&gt;name&lt;/b&gt;</h1>', $html);
        // The structured data survives as JSON with the same text.
        $this->assertSame('A "quoted" <b>name</b>', $this->jsonLd($html)['name']);
    }

    public function test_entity_without_prose_gets_a_generated_description(): void
    {
        $entity = Entity::factory()->verified()->ofType(EntityType::City)->withTemporalRange('1200', '1300')
            ->create(['name' => 'Testopolis', 'summary' => null, 'significance' => null, 'description' => null]);

        $html = (string) $this->get('/site-pages/entities/'.$entity->entity_id)->assertOk()->getContent();

        $this->assertStringContainsString(
            '<meta name="description" content="Testopolis: city, 1200 CE – 1300 CE, on History Mapped.">',
            $html,
        );
    }

    public function test_a_place_named_like_the_entity_is_said_once(): void
    {
        $entity = Entity::factory()->verified()->ofType(EntityType::City)->atLocation('Rome')->withTemporalRange('-753', '-753')
            ->create(['name' => 'Rome']);

        $html = (string) $this->get('/site-pages/entities/'.$entity->entity_id)->assertOk()->getContent();

        $this->assertStringContainsString('<p class="hm-meta">City · 753 BCE</p>', $html);
    }

    public function test_unknown_entity_is_a_404_in_the_shell(): void
    {
        foreach ([(string) Str::uuid(), 'not-a-uuid', '12'] as $id) {
            $response = $this->get('/site-pages/entities/'.$id);

            $response->assertNotFound();
            $html = (string) $response->getContent();
            $this->assertStringContainsString('<title>Entity not found · History Mapped</title>', $html);
            $this->assertStringContainsString('<meta name="robots" content="noindex">', $html);
            $this->assertStringNotContainsString('rel="canonical"', $html);
            $this->assertStringContainsString('src="/assets/index-release-a.js"', $html);
        }
    }

    public function test_chronicle_page_lists_its_steps_in_order(): void
    {
        $rome = Entity::factory()->verified()->create(['name' => 'Rome']);
        $carthage = Entity::factory()->verified()->create(['name' => 'Carthage']);
        $hannibal = Entity::factory()->verified()->create(['name' => 'Hannibal']);
        $war = $this->relate($rome, $carthage, 'at_war_with');

        $chronicle = Chronicle::factory()->create([
            'title' => 'The Second Punic War',
            'slug' => 'second-punic-war',
            'description' => 'Rome and Carthage fight for the western Mediterranean.',
            'start_year' => -218,
            'end_year' => -201,
        ]);
        $this->step($chronicle, 2, 'Hannibal wins at Cannae.', [$hannibal], ['start_year' => -216, 'end_year' => -216]);
        $this->step($chronicle, 1, 'War is declared.', [], [
            'start_year' => -218,
            'end_year' => -218,
            'primary_relationship_id' => $war->relationship_id,
        ]);

        $html = (string) $this->get('/site-pages/chronicles/second-punic-war')->assertOk()->getContent();

        $this->assertStringContainsString('<title>The Second Punic War · History Mapped</title>', $html);
        $this->assertStringContainsString(
            '<meta name="description" content="Rome and Carthage fight for the western Mediterranean.">',
            $html,
        );
        $this->assertStringContainsString('<link rel="canonical" href="https://atlas.test/chronicles/second-punic-war">', $html);
        $this->assertStringContainsString('Chronicle · 2 steps · 218 BCE – 201 BCE', $html);
        $this->assertStringContainsString('<h2>1. 218 BCE</h2>', $html);
        $this->assertStringContainsString('<h2>2. 216 BCE</h2>', $html);
        $this->assertLessThan(strpos($html, 'Hannibal wins at Cannae.'), strpos($html, 'War is declared.'));
        // A step links the entities of its relationship and its other entities.
        $this->assertStringContainsString('<a href="/entities/'.$rome->entity_id.'">Rome</a>', $html);
        $this->assertStringContainsString('<a href="/entities/'.$carthage->entity_id.'">Carthage</a>', $html);
        $this->assertStringContainsString('<a href="/entities/'.$hannibal->entity_id.'">Hannibal</a>', $html);
        $this->assertStringContainsString('<a href="/app?chron=second-punic-war">Open on the globe</a>', $html);
    }

    public function test_chronicle_without_a_description_gets_the_generated_line(): void
    {
        $chronicle = Chronicle::factory()->create([
            'title' => 'Short Tale', 'slug' => 'short-tale', 'description' => null, 'start_year' => 100, 'end_year' => 100,
        ]);
        $this->step($chronicle, 1, 'Only step.');

        $html = (string) $this->get('/site-pages/chronicles/short-tale')->assertOk()->getContent();

        $this->assertStringContainsString(
            '<meta name="description" content="Short Tale: a chronicle in 1 steps, 100 CE, on History Mapped.">',
            $html,
        );
    }

    public function test_archived_and_unknown_chronicles_are_404(): void
    {
        Chronicle::factory()->archived()->create(['slug' => 'put-away']);

        foreach (['put-away', 'never-existed'] as $slug) {
            $response = $this->get('/site-pages/chronicles/'.$slug);

            $response->assertNotFound();
            $this->assertStringContainsString('<title>Chronicle not found · History Mapped</title>', (string) $response->getContent());
        }
    }

    public function test_other_paths_get_the_site_not_found_page(): void
    {
        $response = $this->get('/site-pages/entities/'.Str::uuid().'/extra');

        $response->assertNotFound();
        $this->assertStringContainsString('<title>Page not found · History Mapped</title>', (string) $response->getContent());
    }

    public function test_without_the_shell_file_the_answer_is_503(): void
    {
        $entity = Entity::factory()->verified()->create();
        $this->useShell($this->siteDir.'/nowhere/index.html');

        $this->get('/site-pages/entities/'.$entity->entity_id)->assertStatus(503);

        // A file that is not the SPA's index.html is no shell either.
        file_put_contents($this->siteDir.'/plain.html', '<html><head></head><body>hello</body></html>');
        $this->useShell($this->siteDir.'/plain.html');

        $this->get('/site-pages/entities/'.$entity->entity_id)->assertStatus(503);
    }

    public function test_a_new_release_behind_the_current_symlink_is_picked_up(): void
    {
        $entity = Entity::factory()->verified()->create();
        $current = $this->siteDir.'/current';
        symlink('releases/release-a', $current);
        $this->useShell($current.'/index.html');

        $first = (string) $this->get('/site-pages/entities/'.$entity->entity_id)->assertOk()->getContent();
        $this->assertStringContainsString('index-release-a.js', $first);

        // What the installer does on a deploy: a new release, then one rename.
        $this->writeShell('release-b');
        symlink('releases/release-b', $current.'.tmp');
        rename($current.'.tmp', $current);

        $second = (string) $this->get('/site-pages/entities/'.$entity->entity_id)->assertOk()->getContent();
        $this->assertStringContainsString('index-release-b.js', $second);
        $this->assertStringNotContainsString('index-release-a.js', $second);
    }

    public function test_pages_set_no_cookie_and_are_rate_limited_per_address(): void
    {
        config(['site.rate_limit' => 2]);
        $entity = Entity::factory()->verified()->create();
        $url = '/site-pages/entities/'.$entity->entity_id;

        $first = $this->get($url)->assertOk();
        $this->assertSame([], $first->headers->getCookies());
        $this->get($url)->assertOk();
        $this->get($url)->assertStatus(429);
    }

    private function relate(Entity $a, Entity $b, string $type): EntityRelationship
    {
        return EntityRelationship::create([
            'relationship_id' => (string) Str::uuid(),
            'source_entity_id' => $a->entity_id,
            'target_entity_id' => $b->entity_id,
            'relationship_type' => $type,
            'confidence' => 'high',
        ]);
    }

    /** @param list<Entity> $entities */
    private function step(Chronicle $chronicle, int $sequence, string $text, array $entities = [], array $state = []): ChronicleEntry
    {
        $entry = ChronicleEntry::factory()->create($state + [
            'chronicle_id' => $chronicle->chronicle_id,
            'sequence_order' => $sequence,
            'narrative_text' => $text,
        ]);
        foreach ($entities as $i => $entity) {
            DB::table('chronicle_entry_entities')->insert([
                'entry_id' => $entry->entry_id,
                'entity_id' => $entity->entity_id,
                'sequence_in_entry' => $i,
            ]);
        }

        return $entry;
    }

    /** @return array<string, mixed> */
    private function jsonLd(string $html): array
    {
        $this->assertSame(1, preg_match('~<script type="application/ld\+json">(.*?)</script>~s', $html, $m));

        return json_decode($m[1], true, flags: JSON_THROW_ON_ERROR);
    }
}
