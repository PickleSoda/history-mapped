<?php

declare(strict_types=1);

namespace Tests\Unit\ContentBundle;

use App\Support\ContentBundle\JsonLine;
use PHPUnit\Framework\TestCase;

class JsonLineTest extends TestCase
{
    public function test_unicode_stays_literal(): void
    {
        $this->assertSame('{"name":"Constantinople — Κωνσταντινούπολις"}', JsonLine::encode(['name' => 'Constantinople — Κωνσταντινούπολις']));
    }

    public function test_slashes_are_not_escaped(): void
    {
        $this->assertSame('{"url":"https://a.b/c"}', JsonLine::encode(['url' => 'https://a.b/c']));
    }

    public function test_zero_fraction_is_preserved(): void
    {
        $this->assertSame('{"score":1.0}', JsonLine::encode(['score' => 1.0]));
    }

    public function test_empty_object_encodes_as_braces(): void
    {
        $this->assertSame('{"a":{},"b":[]}', JsonLine::encode(['a' => (object) [], 'b' => []]));
    }

    public function test_object_helper_turns_empty_arrays_into_objects(): void
    {
        $this->assertEquals((object) [], JsonLine::object([]));
        $this->assertSame(['k' => 1], JsonLine::object(['k' => 1]));
        $this->assertNull(JsonLine::object(null));
    }

    public function test_key_order_is_preserved_and_no_trailing_newline(): void
    {
        $line = JsonLine::encode(['z' => 1, 'a' => 2, 'm' => 3]);

        $this->assertSame('{"z":1,"a":2,"m":3}', $line);
        $this->assertStringEndsNotWith("\n", $line);
    }
}
