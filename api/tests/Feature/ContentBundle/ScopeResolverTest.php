<?php

declare(strict_types=1);

namespace Tests\Feature\ContentBundle;

use App\Enums\EntityType;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use App\Models\EntityRelationship;
use App\Models\GeometryPeriod;
use App\Support\ContentBundle\RecordType;
use App\Support\ContentBundle\Scope\ExportScope;
use App\Support\ContentBundle\Scope\ScopeResolver;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

/**
 * Graph: e1 -r1-> e2 -r2-> e3, e4 -r3-> e1, e5 -r4-> e6 (isolated), r5 e3 -> e4.
 * Chronicle "rome": entry1 (primary r1, links e1, e2), entry2 (primary r2, links e3).
 */
class ScopeResolverTest extends TestCase
{
    use RefreshDatabase;

    /** @var array<string, string> */
    private array $e = [];

    /** @var array<string, string> */
    private array $r = [];

    private string $chronicleId;

    /** @var list<string> */
    private array $entryIds = [];

    protected function setUp(): void
    {
        parent::setUp();

        $specs = [
            'e1' => [EntityType::PoliticalEntity, -600, -400],
            'e2' => [EntityType::City, -300, null],
            'e3' => [EntityType::Person, 100, 200],
            'e4' => [EntityType::City, null, 50],
            'e5' => [EntityType::EventBattle, -450, -440],
            'e6' => [EntityType::Person, null, null],
        ];
        // A trigger derives start_year/end_year from the ISO date strings.
        foreach ($specs as $k => [$type, $start, $end]) {
            $entity = Entity::factory()->create(['entity_type' => $type->value, 'entity_group' => $type->group()->value, 'wikidata_id' => null]);
            $this->e[$k] = $entity->entity_id;
            if ($k !== 'e6') {
                DB::table('entity_temporal_ranges')->insert([
                    'entity_id' => $entity->entity_id, 'range_type' => 'primary', 'start_date' => $start === null ? null : (string) $start, 'end_date' => $end === null ? null : (string) $end, 'is_primary' => true,
                ]);
            }
            GeometryPeriod::query()->forceCreate([
                'geometry_period_id' => (string) Str::uuid(), 'entity_id' => $entity->entity_id, 'period_type' => 'territory', 'start_year' => -1, 'end_year' => 1,
                'confidence' => 'high', 'provenance_mode' => 'manual', 'geom' => ['type' => 'Point', 'coordinates' => [12.5, 41.9]],
            ]);
            EntityGeoRef::factory()->create(['entity_id' => $entity->entity_id]);
        }
        // A non-primary range must not count for `years`.
        DB::table('entity_temporal_ranges')->insert(['entity_id' => $this->e['e6'], 'range_type' => 'secondary', 'start_date' => '-450', 'end_date' => '-440', 'is_primary' => false]);

        foreach (['r1' => ['e1', 'e2'], 'r2' => ['e2', 'e3'], 'r3' => ['e4', 'e1'], 'r4' => ['e5', 'e6'], 'r5' => ['e3', 'e4']] as $k => [$s, $t]) {
            $this->r[$k] = $rid = (string) Str::uuid();
            EntityRelationship::query()->create([
                'relationship_id' => $rid, 'source_entity_id' => $this->e[$s], 'target_entity_id' => $this->e[$t], 'relationship_type' => 'allied_with',
            ]);
        }

        $this->chronicleId = Chronicle::factory()->create(['slug' => 'rome'])->chronicle_id;
        Chronicle::factory()->create(['slug' => 'other']);
        foreach ([['r1', ['e1', 'e2']], ['r2', ['e3']]] as $i => [$rel, $links]) {
            $entry = ChronicleEntry::factory()->create(['chronicle_id' => $this->chronicleId, 'sequence_order' => $i + 1, 'primary_relationship_id' => $this->r[$rel]]);
            $this->entryIds[] = $entry->entry_id;
            foreach ($links as $n => $l) {
                DB::table('chronicle_entry_entities')->insert(['entry_id' => $entry->entry_id, 'entity_id' => $this->e[$l], 'role' => 'participant', 'sequence_in_entry' => $n + 1]);
            }
        }
        // An entry in another chronicle, to prove entries are restricted.
        ChronicleEntry::factory()->create(['chronicle_id' => Chronicle::query()->where('slug', 'other')->value('chronicle_id'), 'sequence_order' => 1]);
    }

    /** @param list<string> $ids */
    private function ids(array $ids, array $map): array
    {
        $out = array_map(fn (string $k) => $map[$k], $ids);
        sort($out);

        return $out;
    }

    /** @return array<string, list<string>> sorted ids per record type */
    private function resolveIds(array $specs): array
    {
        $out = [];
        foreach ((new ScopeResolver)->resolve(ExportScope::parse($specs)) as $key => $builder) {
            $type = RecordType::from($key);
            $ids = $builder->get()->map(fn ($m) => (string) $m->getAttribute($type->primaryKey()))->all();
            sort($ids);
            $out[$key] = $ids;
        }

        return $out;
    }

    /** @param list<string> $entities @param list<string> $rels */
    private function assertClosure(array $got, array $entities, array $rels, ?array $chronicles = null, ?array $entries = null): void
    {
        $this->assertSame(array_keys($got), array_map(fn (RecordType $t) => $t->value, RecordType::cases()));
        $this->assertSame($this->ids($entities, $this->e), $got['entities']);
        $this->assertSame($this->ids($rels, $this->r), $got['relationships']);

        $ofEntities = array_map(fn ($k) => $this->e[$k], $entities);
        $byEntity = fn (string $table, string $pk) => DB::table($table)->whereIn('entity_id', $ofEntities)->pluck($pk)->sort()->values()->all();
        $this->assertSame($byEntity('geometry_periods', 'geometry_period_id'), $got['geometry_periods']);
        $this->assertSame($byEntity('entity_geo_refs', 'geo_ref_id'), $got['geo_refs']);

        $this->assertSame($chronicles ?? [], $got['chronicles']);
        $this->assertSame($entries ?? [], $got['chronicle_entries']);
    }

    private function sortedEntries(): array
    {
        $e = $this->entryIds;
        sort($e);

        return $e;
    }

    public function test_entity_scope(): void
    {
        $this->assertClosure($this->resolveIds(['entity:'.$this->e['e1']]), ['e1'], []);
    }

    public function test_entity_scope_includes_relationships_between_selected_entities(): void
    {
        $got = $this->resolveIds(['entity:'.$this->e['e1'], 'entity:'.$this->e['e2']]);
        $this->assertClosure($got, ['e1', 'e2'], ['r1']);
    }

    public function test_neighbours_scope(): void
    {
        // e1 touches e2 (r1) and e4 (r3).
        $got = $this->resolveIds(['neighbours:'.$this->e['e1']]);
        $this->assertClosure($got, ['e1', 'e2', 'e4'], ['r1', 'r3']);
    }

    public function test_type_scope(): void
    {
        $got = $this->resolveIds(['type:city,person']);
        // e2 city, e3 person, e4 city, e6 person; relationships among them: r2 (e2,e3), r5 (e3,e4).
        $this->assertClosure($got, ['e2', 'e3', 'e4', 'e6'], ['r2', 'r5']);
    }

    public function test_group_scope(): void
    {
        $this->assertClosure($this->resolveIds(['group:EVENT']), ['e5'], []);
    }

    public function test_years_scope_with_open_ended_range(): void
    {
        // [-350, 120]: e1 ends -400 (no), e2 open-ended from -300 (yes), e3 100..200 (yes),
        // e4 unknown start (no), e5 ends -440 (no), e6 only a non-primary range (no).
        $got = $this->resolveIds(['years:-350..120']);
        $this->assertClosure($got, ['e2', 'e3'], ['r2']);
    }

    public function test_years_scope_boundaries_are_inclusive(): void
    {
        $got = $this->resolveIds(['years:-400..-400']);
        $this->assertClosure($got, ['e1'], []);
    }

    public function test_chronicle_scope(): void
    {
        $got = $this->resolveIds(['chronicle:rome']);

        // Linked entities e1, e2, e3 plus endpoints of r1 (e1, e2) and r2 (e2, e3).
        // Relationships: both ends in {e1,e2,e3} -> r1, r2; primaries r1, r2.
        $this->assertClosure($got, ['e1', 'e2', 'e3'], ['r1', 'r2'], [$this->chronicleId], $this->sortedEntries());
    }

    public function test_chronicle_scope_pulls_in_primary_relationship_endpoints_not_linked(): void
    {
        $outside = (string) Str::uuid();
        EntityRelationship::query()->create(['relationship_id' => $outside, 'source_entity_id' => $this->e['e5'], 'target_entity_id' => $this->e['e6'], 'relationship_type' => 'allied_with']);
        ChronicleEntry::query()->where('entry_id', $this->entryIds[1])->update(['primary_relationship_id' => $outside]);
        $this->r['r6'] = $outside;

        $got = $this->resolveIds(['chronicle:rome']);

        // Entities: linked e1, e2, e3; endpoints r1 (e1, e2) and r6 (e5, e6).
        $this->assertClosure($got, ['e1', 'e2', 'e3', 'e5', 'e6'], ['r1', 'r2', 'r4', 'r6'], [$this->chronicleId], $this->sortedEntries());
    }

    public function test_union_of_two_specs(): void
    {
        $got = $this->resolveIds(['entity:'.$this->e['e5'], 'entity:'.$this->e['e6'], 'chronicle:rome']);

        $this->assertClosure($got, ['e1', 'e2', 'e3', 'e5', 'e6'], ['r1', 'r2', 'r4'], [$this->chronicleId], $this->sortedEntries());
    }

    public function test_union_of_entity_kinds(): void
    {
        $got = $this->resolveIds(['group:EVENT', 'years:-600..-500']);

        $this->assertClosure($got, ['e1', 'e5'], []);
    }

    public function test_all_is_unrestricted(): void
    {
        $got = $this->resolveIds(['all']);

        $this->assertCount(6, $got['entities']);
        $this->assertCount(5, $got['relationships']);
        $this->assertCount(6, $got['geometry_periods']);
        $this->assertCount(6, $got['geo_refs']);
        $this->assertCount(2, $got['chronicles']);
        $this->assertCount(3, $got['chronicle_entries']);

        foreach ((new ScopeResolver)->resolve(ExportScope::parse([])) as $builder) {
            $this->assertStringNotContainsString(' in (', $builder->toSql());
            $this->assertStringNotContainsString('false', $builder->toSql());
        }
    }

    public function test_ids_file_scope(): void
    {
        $path = tempnam(sys_get_temp_dir(), 'ids');
        file_put_contents($path, $this->e['e1']."\n".$this->e['e2']."\n".Str::uuid()."\n");

        try {
            $got = $this->resolveIds(['ids:'.$path]);
        } finally {
            unlink($path);
        }

        $this->assertClosure($got, ['e1', 'e2'], ['r1']);
    }

    public function test_unknown_chronicle_selects_nothing(): void
    {
        $got = $this->resolveIds(['chronicle:nope']);

        foreach ($got as $ids) {
            $this->assertSame([], $ids);
        }
    }

    public function test_builders_compose_with_lazy_by_id(): void
    {
        $builders = (new ScopeResolver)->resolve(ExportScope::parse(['chronicle:rome']));

        foreach ([RecordType::Entities, RecordType::Relationships, RecordType::ChronicleEntries, RecordType::GeometryPeriods] as $type) {
            $table = (new ($type->modelClass()))->getTable();
            $expected = $builders[$type->value]->get()->map(fn ($m) => (string) $m->getAttribute($type->primaryKey()))->sort()->values()->all();

            $streamed = $builders[$type->value]->clone()
                ->lazyById(2, $table.'.'.$type->primaryKey(), $type->primaryKey())
                ->map(fn ($m) => (string) $m->getAttribute($type->primaryKey()))->all();

            $this->assertNotEmpty($expected);
            $this->assertSame($expected, $streamed, $type->value);
        }
    }
}
