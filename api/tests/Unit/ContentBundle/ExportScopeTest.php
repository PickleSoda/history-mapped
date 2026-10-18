<?php

declare(strict_types=1);

namespace Tests\Unit\ContentBundle;

use App\Support\ContentBundle\Scope\ExportScope;
use InvalidArgumentException;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

class ExportScopeTest extends TestCase
{
    private const A = '3f2b8c1e-5a47-4d0e-9b6a-1c2d3e4f5a6b';

    private const B = '7a1d9e20-8c3b-4f5a-a1b2-2d3e4f5a6b7c';

    public function test_empty_means_all(): void
    {
        $scope = ExportScope::parse([]);

        $this->assertTrue($scope->isAll());
        $this->assertSame(['all'], $scope->specs());
    }

    public function test_all_with_other_specs_is_all(): void
    {
        $scope = ExportScope::parse(['chronicle:rome', 'all']);

        $this->assertTrue($scope->isAll());
        $this->assertSame(['all'], $scope->specs());
    }

    public function test_valid_forms_normalise_in_input_order_without_duplicates(): void
    {
        $scope = ExportScope::parse([
            'chronicle:rome', 'entity:'.strtoupper(self::A), 'neighbours:'.self::B,
            'type:city,person,city', 'group:POLITY', 'years:-500..-100', 'years:+5..7', 'entity:'.self::A, 'chronicle:rome',
        ]);

        $this->assertFalse($scope->isAll());
        $this->assertSame([
            'chronicle:rome', 'entity:'.self::A, 'neighbours:'.self::B,
            'type:city,person', 'group:POLITY', 'years:-500..-100', 'years:5..7',
        ], $scope->specs());
        $this->assertSame(['rome'], $scope->chronicleSlugs());
        $this->assertSame([self::A], $scope->entityIds());
        $this->assertSame([self::B], $scope->neighbourIds());
        $this->assertSame(['city', 'person'], $scope->types());
        $this->assertSame(['POLITY'], $scope->groups());
        $this->assertSame([[-500, -100], [5, 7]], $scope->yearRanges());
    }

    public function test_ids_file_is_read_and_spec_keeps_the_path(): void
    {
        $path = tempnam(sys_get_temp_dir(), 'ids');
        file_put_contents($path, "# comment\n\n".self::A."\n  ".strtoupper(self::B)."  \n");

        try {
            $scope = ExportScope::parse(['ids:'.$path], true);
            $this->assertSame([self::A, self::B], $scope->entityIds());
            $this->assertSame(['ids:'.basename($path)], $scope->specs());
        } finally {
            unlink($path);
        }
    }

    public function test_ids_file_with_bad_line_reports_line_number(): void
    {
        $path = tempnam(sys_get_temp_dir(), 'ids');
        file_put_contents($path, self::A."\n\nnot-a-uuid\n");

        try {
            $this->expectException(InvalidArgumentException::class);
            $this->expectExceptionMessage('line 3 is not a uuid');
            ExportScope::parse(['ids:'.$path], true);
        } finally {
            unlink($path);
        }
    }

    public function test_missing_ids_file_is_rejected(): void
    {
        $this->expectException(InvalidArgumentException::class);
        $this->expectExceptionMessage('cannot read ids file ids.txt');
        ExportScope::parse(['ids:/nonexistent/ids.txt'], true);
    }

    public function test_ids_file_errors_never_echo_content(): void
    {
        $path = tempnam(sys_get_temp_dir(), 'ids');
        file_put_contents($path, "SECRET=hunter2\n");

        try {
            ExportScope::parse(['ids:'.$path], true);
            $this->fail('Expected InvalidArgumentException');
        } catch (InvalidArgumentException $e) {
            $this->assertStringNotContainsString('hunter2', $e->getMessage());
        } finally {
            unlink($path);
        }
    }

    public function test_empty_ids_file_is_allowed_and_selects_nothing(): void
    {
        $path = tempnam(sys_get_temp_dir(), 'ids');

        try {
            $scope = ExportScope::parse(['ids:'.$path], true);
            $this->assertSame([], $scope->entityIds());
            $this->assertFalse($scope->isAll());
        } finally {
            unlink($path);
        }
    }

    public function test_ids_pointing_at_a_directory_is_rejected(): void
    {
        $this->expectException(InvalidArgumentException::class);
        $this->expectExceptionMessage('cannot read ids file');
        ExportScope::parse(['ids:'.sys_get_temp_dir()], true);
    }

    public function test_ids_is_rejected_without_the_flag(): void
    {
        $this->expectException(InvalidArgumentException::class);
        $this->expectExceptionMessage('ids: lists are only available from the command line');
        ExportScope::parse(['ids:/proc/self/environ']);
    }

    public function test_trailing_newline_does_not_pass(): void
    {
        foreach (['entity:'.self::A."\n", 'neighbours:'.self::A."\n", "years:1..2\n", "chronicle:rome\n"] as $spec) {
            try {
                ExportScope::parse([$spec]);
                $this->fail('Accepted '.json_encode($spec));
            } catch (InvalidArgumentException) {
                $this->addToAssertionCount(1);
            }
        }
    }

    public function test_year_bounds_match_the_schema(): void
    {
        $year = json_decode(file_get_contents(dirname(__DIR__, 3).'/resources/schemas/content-bundle/v1/common.schema.json'), true)['$defs']['year'];

        $this->assertSame($year['minimum'], ExportScope::YEAR_MIN);
        $this->assertSame($year['maximum'], ExportScope::YEAR_MAX);
        $this->assertSame([[-20000, 3000]], ExportScope::parse(['years:-20000..3000'])->yearRanges());
    }

    public function test_slug_rule_matches_the_schema(): void
    {
        $slug = json_decode(file_get_contents(dirname(__DIR__, 3).'/resources/schemas/content-bundle/v1/common.schema.json'), true)['$defs']['slug'];

        $this->assertSame($slug['pattern'], ExportScope::SLUG_PATTERN);
        $this->assertSame($slug['maxLength'], ExportScope::SLUG_MAX_LENGTH);
        $this->assertSame(['chronicle:'.str_repeat('a', 255)], ExportScope::parse(['chronicle:'.str_repeat('a', 255)])->specs());
    }

    /** @return array<string, array{string}> */
    public static function invalidSpecs(): array
    {
        return [
            'bare word' => ['everything'],
            'unknown kind' => ['planet:mars'],
            'empty chronicle' => ['chronicle:'],
            'bad entity uuid' => ['entity:123'],
            'bad neighbours uuid' => ['neighbours:zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz'],
            'unknown type' => ['type:city,spaceship'],
            'unknown group' => ['group:NOPE'],
            'lowercase group' => ['group:polity'],
            'years not numbers' => ['years:a..b'],
            'years no separator' => ['years:100'],
            'years reversed' => ['years:100..-100'],
            'year below min' => ['years:-20001..0'],
            'year above max' => ['years:0..3001'],
            'year overflow' => ['years:0..99999999999999999999'],
            'slug uppercase' => ['chronicle:Rome'],
            'slug with slash' => ['chronicle:a/b'],
            'slug whitespace' => ['chronicle:a b'],
            'slug too long' => ['chronicle:'.str_repeat('a', 256)],
            'all with value' => ['all:yes'],
        ];
    }

    #[DataProvider('invalidSpecs')]
    public function test_invalid_specs_throw_naming_the_spec(string $spec): void
    {
        try {
            ExportScope::parse(['all', $spec]);
            $this->fail('Expected InvalidArgumentException');
        } catch (InvalidArgumentException $e) {
            $this->assertStringContainsString($spec, $e->getMessage());
        }
    }
}
