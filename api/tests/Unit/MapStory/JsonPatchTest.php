<?php

declare(strict_types=1);

namespace Tests\Unit\MapStory;

use App\Support\MapStory\JsonPatch;
use App\Support\MapStory\JsonPatchException;
use App\Support\MapStory\MapStoryFile;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use stdClass;

class JsonPatchTest extends TestCase
{
    private function doc(): stdClass
    {
        return MapStoryFile::decode('{"title":"A","steps":[{"id":"s1","positions":{"a":{"at":[1.0,2.0]}}},{"id":"s2","positions":{}}],"tags":["x"]}');
    }

    private function json(stdClass $doc): string
    {
        return (string) json_encode($doc, MapStoryFile::JSON_FLAGS);
    }

    public function test_the_six_operations(): void
    {
        $doc = JsonPatch::apply($this->doc(), [
            ['op' => 'test', 'path' => '/title', 'value' => 'A'],
            ['op' => 'replace', 'path' => '/title', 'value' => 'B'],
            ['op' => 'add', 'path' => '/steps/1/positions/b', 'value' => ['at' => [3, 4]]],
            ['op' => 'add', 'path' => '/tags/-', 'value' => 'y'],
            ['op' => 'add', 'path' => '/tags/0', 'value' => 'w'],
            ['op' => 'copy', 'from' => '/steps/0/positions/a', 'path' => '/steps/1/positions/c'],
            ['op' => 'move', 'from' => '/steps/1', 'path' => '/steps/0'],
            ['op' => 'remove', 'path' => '/steps/1/positions/a'],
        ]);

        $this->assertSame(
            '{"title":"B","steps":[{"id":"s2","positions":{"b":{"at":[3,4]},"c":{"at":[1.0,2.0]}}},{"id":"s1","positions":{}}],"tags":["w","x","y"]}',
            $this->json($doc),
        );
    }

    public function test_the_original_is_untouched(): void
    {
        $doc = $this->doc();
        JsonPatch::apply($doc, [['op' => 'replace', 'path' => '/steps/0/positions/a/at/0', 'value' => 9]]);

        $this->assertSame(1.0, $doc->steps[0]->positions->a->at[0]);
    }

    public function test_pointer_escapes(): void
    {
        $doc = MapStoryFile::decode('{"a/b":{"c~d":1}}');

        $this->assertSame('{"a/b":{"c~d":2}}', $this->json(JsonPatch::apply($doc, [['op' => 'replace', 'path' => '/a~1b/c~0d', 'value' => 2]])));
    }

    public function test_at_reads_a_pointer(): void
    {
        $this->assertSame('s2', JsonPatch::at($this->doc(), '/steps/1/id'));
        $this->assertNull(JsonPatch::at($this->doc(), '/steps/7/id'));
    }

    /** @return array<string, array{0: array<string, mixed>, 1: string}> */
    public static function failures(): array
    {
        return [
            'unknown op' => [['op' => 'merge', 'path' => '/title'], '`op` must be one of'],
            'missing path' => [['op' => 'replace', 'path' => '/nope', 'value' => 1], "no 'nope' there"],
            'index out of range' => [['op' => 'replace', 'path' => '/steps/5', 'value' => 1], 'index 5 is out of range'],
            'not an index' => [['op' => 'remove', 'path' => '/steps/first'], "'first' is not a list index"],
            'missing value' => [['op' => 'add', 'path' => '/x'], '`value` is missing'],
            'failed test' => [['op' => 'test', 'path' => '/title', 'value' => 'Z'], 'test failed'],
            'move into itself' => [['op' => 'move', 'from' => '/steps', 'path' => '/steps/0/x'], 'into itself'],
            'remove root' => [['op' => 'remove', 'path' => ''], 'whole document'],
        ];
    }

    #[DataProvider('failures')]
    public function test_a_bad_op_rejects_the_patch(array $op, string $message): void
    {
        $this->expectException(JsonPatchException::class);
        $this->expectExceptionMessage($message);

        JsonPatch::apply($this->doc(), [['op' => 'replace', 'path' => '/title', 'value' => 'ok'], $op]);
    }
}
