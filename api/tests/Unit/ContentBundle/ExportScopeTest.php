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
            $scope = ExportScope::parse(['ids:'.$path]);
            $this->assertSame([self::A, self::B], $scope->entityIds());
            $this->assertSame(['ids:'.$path], $scope->specs());
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
            $this->expectExceptionMessage('Line 3');
            ExportScope::parse(['ids:'.$path]);
        } finally {
            unlink($path);
        }
    }

    public function test_missing_ids_file_is_rejected(): void
    {
        $this->expectException(InvalidArgumentException::class);
        $this->expectExceptionMessage('Cannot read ids file');
        ExportScope::parse(['ids:/nonexistent/ids.txt']);
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
