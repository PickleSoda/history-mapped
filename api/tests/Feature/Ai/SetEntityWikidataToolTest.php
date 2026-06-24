<?php

namespace Tests\Feature\Ai;

use App\Ai\Tools\SetEntityWikidata;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class SetEntityWikidataToolTest extends TestCase
{
    use RefreshDatabase;

    // ── helpers ─────────────────────────────────────────────────────────────

    private function fakeWikidata(string $qid, array $p31 = ['Q839954'], string $label = 'Test Entity'): void
    {
        Http::fake([
            '*' => Http::response([
                'entities' => [
                    $qid => [
                        'labels' => ['en' => ['value' => $label]],
                        'descriptions' => ['en' => ['value' => 'A historical subject']],
                        'claims' => [
                            'P31' => array_map(
                                fn (string $id) => ['mainsnak' => ['datavalue' => ['value' => ['id' => $id]]]],
                                $p31,
                            ),
                        ],
                    ],
                ],
            ]),
        ]);
    }

    private function fakeWikidataNotFound(): void
    {
        Http::fake(['*' => Http::response(['entities' => []])]);
    }

    // ── 1. Happy path + cascade ──────────────────────────────────────────────

    public function test_apply_part_updates_qid_and_cascades_into_source_citations_and_geo_ref(): void
    {
        $this->fakeWikidata('Q42', ['Q839954'], 'Karnak Temple');

        $entity = Entity::factory()->create([
            'wikidata_id' => 'Q_OLD',
            'source_citations' => [
                'wikidata_id' => 'Q_OLD',
                'wikidata_url' => 'https://www.wikidata.org/wiki/Q_OLD',
                'wikipedia_url' => 'https://en.wikipedia.org/wiki/Karnak',
            ],
        ]);

        $geoRef = EntityGeoRef::factory()->forEntity($entity)->create([
            'external_id' => 'Q_OLD',
        ]);

        $tool = app(SetEntityWikidata::class);
        $parts = $tool->buildParts([
            'entity_id' => $entity->entity_id,
            'wikidata_id' => 'Q42',
        ]);

        $this->assertCount(1, $parts);
        $this->assertSame('wikidata', $parts[0]['key']);
        $this->assertSame('set_entity_wikidata', $parts[0]['tool']);
        $this->assertSame('Q_OLD', $parts[0]['human_diff']['from']);
        $this->assertSame('Q42', $parts[0]['human_diff']['to']);
        $this->assertSame('Karnak Temple', $parts[0]['human_diff']['verified_label']);

        $result = $tool->applyPart($parts[0]['payload'], ['user_id' => 'u1']);

        $this->assertSame($entity->entity_id, $result['result_id']);

        // Entity.wikidata_id updated
        $entity->refresh();
        $this->assertSame('Q42', $entity->wikidata_id);

        // source_citations.wikidata_id + wikidata_url cascaded
        $citations = $entity->source_citations;
        $this->assertSame('Q42', $citations['wikidata_id']);
        $this->assertSame('https://www.wikidata.org/wiki/Q42', $citations['wikidata_url']);
        // Other keys preserved
        $this->assertSame('https://en.wikipedia.org/wiki/Karnak', $citations['wikipedia_url']);

        // EntityGeoRef.external_id cascaded
        $geoRef->refresh();
        $this->assertSame('Q42', $geoRef->external_id);
    }

    // ── 2. Geo-ref rows with a different external_id are NOT touched ─────────

    public function test_apply_part_does_not_update_geo_refs_with_different_external_id(): void
    {
        $this->fakeWikidata('Q99', ['Q839954'], 'Egypt');

        $entity = Entity::factory()->create(['wikidata_id' => 'Q_OLD']);

        $unrelatedGeoRef = EntityGeoRef::factory()->forEntity($entity)->create([
            'external_id' => 'SOME_OTHER_ID',
            'temporal_start_year' => 100,
            'temporal_end_year' => 200,
        ]);

        $tool = app(SetEntityWikidata::class);
        $tool->applyPart([
            'entity_id' => $entity->entity_id,
            'wikidata_id' => 'Q99',
        ], ['user_id' => 'u1']);

        $unrelatedGeoRef->refresh();
        $this->assertSame('SOME_OTHER_ID', $unrelatedGeoRef->external_id);
    }

    // ── 3. Namesake reject — bogus P31 ──────────────────────────────────────

    public function test_build_parts_throws_when_p31_is_a_song(): void
    {
        // Q7366 = song — the kind of wrong-namesake that caused the "Egypt" incident
        Http::fake([
            '*' => Http::response([
                'entities' => [
                    'Q816324' => [
                        'labels' => ['en' => ['value' => 'Egypt (Kate Bush song)']],
                        'claims' => [
                            'P31' => [
                                ['mainsnak' => ['datavalue' => ['value' => ['id' => 'Q7366']]]],
                            ],
                        ],
                    ],
                ],
            ]),
        ]);

        $entity = Entity::factory()->create(['wikidata_id' => 'Q79']);

        $tool = app(SetEntityWikidata::class);

        $this->expectException(\InvalidArgumentException::class);
        $this->expectExceptionMessageMatches('/namesake/i');

        $tool->buildParts([
            'entity_id' => $entity->entity_id,
            'wikidata_id' => 'Q816324',
        ]);
    }

    public function test_build_parts_throws_when_p31_is_a_street(): void
    {
        // Q79007 = street — the kind of wrong-namesake that caused the "Karnak" incident
        Http::fake([
            '*' => Http::response([
                'entities' => [
                    'Q123456' => [
                        'labels' => ['en' => ['value' => 'Karnak (street)']],
                        'claims' => [
                            'P31' => [
                                ['mainsnak' => ['datavalue' => ['value' => ['id' => 'Q79007']]]],
                            ],
                        ],
                    ],
                ],
            ]),
        ]);

        $entity = Entity::factory()->create(['wikidata_id' => 'Q79']);

        $tool = app(SetEntityWikidata::class);

        $this->expectException(\InvalidArgumentException::class);
        $tool->buildParts([
            'entity_id' => $entity->entity_id,
            'wikidata_id' => 'Q123456',
        ]);
    }

    // ── 4. Not found reject ─────────────────────────────────────────────────

    public function test_build_parts_throws_when_qid_not_found(): void
    {
        $this->fakeWikidataNotFound();

        $entity = Entity::factory()->create(['wikidata_id' => 'Q79']);

        $tool = app(SetEntityWikidata::class);

        $this->expectException(\InvalidArgumentException::class);
        $this->expectExceptionMessageMatches('/not found/i');

        $tool->buildParts([
            'entity_id' => $entity->entity_id,
            'wikidata_id' => 'Q9999999',
        ]);
    }

    // ── 5. source_citations without wikidata_id key is left untouched ───────

    public function test_apply_part_skips_source_citations_cascade_when_key_absent(): void
    {
        $this->fakeWikidata('Q42', ['Q839954'], 'Karnak Temple');

        $entity = Entity::factory()->create([
            'wikidata_id' => 'Q_OLD',
            'source_citations' => ['wikipedia_url' => 'https://en.wikipedia.org/wiki/Karnak'],
        ]);

        $tool = app(SetEntityWikidata::class);
        $tool->applyPart([
            'entity_id' => $entity->entity_id,
            'wikidata_id' => 'Q42',
        ], ['user_id' => 'u1']);

        $entity->refresh();
        $this->assertSame('Q42', $entity->wikidata_id);
        // No wikidata_id key was injected
        $this->assertArrayNotHasKey('wikidata_id', $entity->source_citations ?? []);
    }
}
