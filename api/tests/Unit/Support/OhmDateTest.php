<?php

declare(strict_types=1);

namespace Tests\Unit\Support;

use App\Support\OhmDate;
use InvalidArgumentException;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

class OhmDateTest extends TestCase
{
    /** @return array<string, array{int, string, float}> */
    public static function decdates(): array
    {
        return [
            'ce start' => [1900, 'start', 1900.00137],
            'ce end' => [1950, 'end', 1950.99863],
            'bce start' => [-2999, 'start', -2998.99863],
            'bce end' => [-2799, 'end', -2798.00137],
        ];
    }

    #[DataProvider('decdates')]
    public function test_year_to_decdate(int $year, string $bound, float $expected): void
    {
        $this->assertEqualsWithDelta($expected, OhmDate::yearToDecdate($year, $bound), 1e-9);
    }

    public function test_year_to_decdate_rejects_an_unknown_bound(): void
    {
        $this->expectException(InvalidArgumentException::class);

        OhmDate::yearToDecdate(1900, 'middle');
    }

    /** @return array<string, array{?string, ?int}> */
    public static function dates(): array
    {
        return [
            'bce full date' => ['-0027-01-16', -27],
            'ce full date' => ['0476-09-04', 476],
            'year only' => ['1453', 1453],
            'first of January' => ['1800-01-01', 1800],
            'empty' => ['', null],
            'null' => [null, null],
            'free text' => ['c. 1200', null],
            'padded with spaces' => [' 1066 ', 1066],
        ];
    }

    #[DataProvider('dates')]
    public function test_year_from_date(?string $date, ?int $expected): void
    {
        $this->assertSame($expected, OhmDate::yearFromDate($date));
    }

    /** @return array<string, array{?string, ?string, array{0: ?int, 1: ?int}}> */
    public static function ranges(): array
    {
        return [
            'both bounds' => ['1900', '1950', [1900, 1950]],
            'open start' => [null, '1950', [null, 1950]],
        ];
    }

    /** @param array{0: ?int, 1: ?int} $expected */
    #[DataProvider('ranges')]
    public function test_years_from(?string $start, ?string $end, array $expected): void
    {
        $this->assertSame($expected, OhmDate::yearsFrom($start, $end));
    }

    /** @return array<string, array{string, string, ?int}> */
    public static function signedIds(): array
    {
        return [
            'relation is negative' => ['relation', '1880', -1880],
            'node is positive' => ['node', '42', 42],
            'way is positive' => ['way', '7', 7],
            'non-osm type' => ['qid', 'Q1', null],
            'non-numeric id' => ['relation', 'abc', null],
        ];
    }

    #[DataProvider('signedIds')]
    public function test_signed_osm_id(string $externalType, string $externalId, ?int $expected): void
    {
        $this->assertSame($expected, OhmDate::signedOsmId($externalType, $externalId));
    }

    /** @return array<string, array{int, array{types: list<string>, id: string}}> */
    public static function externalTypes(): array
    {
        return [
            'negative is a relation' => [-1880, ['types' => ['relation'], 'id' => '1880']],
            'positive is a node or way' => [42, ['types' => ['node', 'way'], 'id' => '42']],
        ];
    }

    /** @param array{types: list<string>, id: string} $expected */
    #[DataProvider('externalTypes')]
    public function test_external_types_for_signed_id(int $osmId, array $expected): void
    {
        $this->assertSame($expected, OhmDate::externalTypesForSignedId($osmId));
    }

    public function test_external_types_for_signed_id_rejects_zero(): void
    {
        $this->expectException(InvalidArgumentException::class);

        OhmDate::externalTypesForSignedId(0);
    }
}
