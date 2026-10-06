<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Services\EntityReferenceResolver;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

class EntityReferenceResolverTest extends TestCase
{
    /**
     * @return array<string, array{string, string, bool}>
     */
    public static function namePairs(): array
    {
        return [
            // Same entity, different label (legitimate QID merges).
            'suffix' => ['Eighteenth Dynasty of Egypt', 'Eighteenth Dynasty', true],
            'regnal kept' => ['Philip II of France', 'Philip II', true],
            'prefix' => ['Federation of Malaya', 'Malaya', true],
            'diacritics' => ['Cordoba', 'Córdoba', true],
            'apostrophe dropped' => ["al-Ma'mun", 'al-Maʾmun', true],
            'non-decomposing letter' => ['Dai Viet', 'Đại Việt', true],
            'unicode dash' => ['Soviet–Afghan War', 'Soviet-Afghan War', true],
            'case' => ['qing', 'Qing dynasty', true],
            // Wrong-QID merges seen in the campaign data.
            'regnal differs' => ['World War I', 'World War II', false],
            'regnal missing' => ['Malik-Shah', 'Malik-Shah II', false],
            'regnal vs epithet' => ['Mithridates VI Eupator', 'Mithridates V', false],
            'substring not word' => ['Qi', 'Qing dynasty', false],
            'prefix not word' => ['Julian', 'Queen Juliana', false],
            'unrelated' => ['Canaan', 'Caana', false],
            'phase numerals' => ['Late Helladic I', 'Late Helladic IIIB', false],
        ];
    }

    #[DataProvider('namePairs')]
    public function test_names_compatible(string $a, string $b, bool $expected): void
    {
        $this->assertSame($expected, EntityReferenceResolver::namesCompatible($a, $b));
        $this->assertSame($expected, EntityReferenceResolver::namesCompatible($b, $a));
    }

    /**
     * Mirrors pipeline/agent/tests/test_name_guard.py.
     *
     * @return array<string, array{string, string, string|null}>
     */
    public static function conflictPairs(): array
    {
        return [
            'world war' => ['World War I', 'World War II', 'markers'],
            'mithridates' => ['Mithridates VI', 'Mithridates V of Pontus', 'markers'],
            'abbas' => ['Abbas II', 'Abbas I of Persia', 'markers'],
            'ordinal words' => ['Eighteenth Dynasty of Egypt', 'Nineteenth Dynasty of Egypt', 'markers'],
            'qi/qing' => ['Qi', 'Qing dynasty', 'near_miss'],
            'qin/qing' => ['Qin', 'Qing dynasty', 'near_miss'],
            'julian/juliana' => ['Julian', 'Queen Juliana', 'near_miss'],
            'romagna/romania' => ['Romagna', 'Romania', 'near_miss'],
            'gaza/gazala' => ['Battle of Gaza', 'Battle of Gazala', 'near_miss'],
            'prussia/russia' => ['Prussia', 'Russia', 'near_miss'],
            'unrelated is no conflict' => ['Byzantine Empire', 'Imperium Romanum Orientale', null],
            'plural' => ['Ottomans', 'Ottoman Empire', null],
            'demonym' => ['Assyria', 'Assyrian Empire', null],
            'sub-phrase' => ['Rome', 'Ancient Rome', null],
            'one-sided marker' => ['Malik-Shah', 'Malik-Shah II', null],
        ];
    }

    #[DataProvider('conflictPairs')]
    public function test_names_conflict(string $a, string $b, ?string $expected): void
    {
        $this->assertSame($expected, EntityReferenceResolver::namesConflict($a, $b));
        $this->assertSame($expected, EntityReferenceResolver::namesConflict($b, $a));
    }

    /**
     * @return array<string, array{string, list<string>, list<string>, bool}>
     */
    public static function recordRowCases(): array
    {
        return [
            'wrong war' => ['World War I', [], ['World War II', 'Second World War'], false],
            'wrong regnal' => ['Mithridates VI', [], ['Mithridates V of Pontus'], false],
            'prefix dynasty' => ['Qi', [], ['Qing dynasty', 'Great Qing'], false],
            'first name' => ['Julian', [], ['Queen Juliana'], false],
            'near-miss despite shared ohm alias' => ['Romagna', ['Romagne'], ['Romania', 'Romagne'], false],
            'record alias' => ['Zhu Di', ['Yongle Emperor'], ['Yongle Emperor'], true],
            'row alias' => ['Zhu Di', [], ['Yongle Emperor', 'Zhu Di'], true],
            'sub-phrase' => ['Rome', [], ['Ancient Rome'], true],
            'same' => ['Eighteenth Dynasty of Egypt', [], ['Eighteenth Dynasty of Egypt'], true],
        ];
    }

    /**
     * @param  list<string>  $alts
     * @param  list<string>  $row
     */
    #[DataProvider('recordRowCases')]
    public function test_record_matches_row(string $name, array $alts, array $row, bool $expected): void
    {
        $this->assertSame($expected, EntityReferenceResolver::recordMatchesRow($name, $alts, $row));
    }

    public function test_uuid_detection(): void
    {
        $this->assertTrue(EntityReferenceResolver::isUuid('11111111-1111-1111-1111-111111111111'));
        $this->assertFalse(EntityReferenceResolver::isUuid('Franks'));
        $this->assertFalse(EntityReferenceResolver::isUuid(null));
    }
}
