<?php

declare(strict_types=1);

namespace Tests\Unit\ContentBundle;

use App\Support\ContentBundle\Serializers\Values;
use Illuminate\Database\Eloquent\Model;
use PHPUnit\Framework\TestCase;

class ValuesTest extends TestCase
{
    private function model(array $raw): Model
    {
        $m = new class extends Model
        {
            protected $table = 'things';

            protected $guarded = [];
        };

        return $m->newFromBuilder($raw);
    }

    public function test_empty_object_encodes_as_braces(): void
    {
        $this->assertSame('{"a":{},"b":[]}', json_encode(Values::decodeJsonb('{"a":{},"b":[]}')));
    }

    public function test_object_helper_turns_empty_arrays_into_objects(): void
    {
        $this->assertEquals((object) [], Values::object([]));
        $this->assertSame(['k' => 1], Values::object(['k' => 1]));
        $this->assertNull(Values::object(null));
    }

    public function test_decode_jsonb_keeps_objects(): void
    {
        $this->assertNull(Values::decodeJsonb(null));
        $this->assertSame('{"a":{},"b":[]}', json_encode(Values::decodeJsonb('{"a":{},"b":[]}')));
        $this->assertEquals((object) [], Values::object(Values::decodeJsonb('{}')));
    }

    public function test_raw_returns_null_values_but_throws_for_unselected_columns(): void
    {
        $m = $this->model(['a' => null, 'b' => 3]);

        $this->assertNull(Values::raw($m, 'a'));
        $this->assertSame(3, Values::raw($m, 'b'));
        $this->expectException(\LogicException::class);
        Values::raw($m, 'missing');
    }

    public function test_raw_checks_original_not_dirty_attributes(): void
    {
        $m = $this->model(['a' => 1]);
        $m->setAttribute('only_set', 2);

        $this->expectException(\LogicException::class);
        Values::raw($m, 'only_set');
    }

    public function test_jsonb_rejects_non_string_raw_values(): void
    {
        $m = $this->model(['ok' => '[]', 'nul' => null, 'bad' => ['x']]);

        $this->assertSame([], Values::jsonb($m, 'ok'));
        $this->assertNull(Values::jsonb($m, 'nul'));
        $this->assertEquals((object) [], Values::jsonbObject($m, 'ok'));
        $this->expectException(\LogicException::class);
        Values::jsonb($m, 'bad');
    }

    public function test_geojson_requires_the_alias_and_decodes_it(): void
    {
        $m = $this->model(['geom_geojson' => '{"type":"Point","coordinates":[1.5,2]}', 'territory_geom_geojson' => null, 'geom' => 'wkb']);

        $this->assertSame(['type' => 'Point', 'coordinates' => [1.5, 2]], Values::geojson($m, 'geom'));
        $this->assertNull(Values::geojson($m, 'territory_geom'));
        $this->expectException(\LogicException::class);
        Values::geojson($this->model(['geom' => 'wkb']), 'geom');
    }

    public function test_sort_list_orders_by_key_then_encoded_item(): void
    {
        $items = [['n' => 'b', 'x' => 2], ['n' => 'a', 'x' => 9], ['n' => 'b', 'x' => 1]];

        $this->assertSame([['n' => 'a', 'x' => 9], ['n' => 'b', 'x' => 1], ['n' => 'b', 'x' => 2]], Values::sortList($items, fn (array $i) => [$i['n']]));
    }
}
