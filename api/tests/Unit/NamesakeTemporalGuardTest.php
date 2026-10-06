<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Services\EntityReferenceResolver as R;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

/**
 * Temporal namesake guard (same name, different era). Mirrors
 * pipeline/agent/tests/test_namesake_guard.py (keep in sync).
 */
class NamesakeTemporalGuardTest extends TestCase
{
    private const MACEDON = ['entity_id' => 'philip-macedon', 'entity_type' => 'person', 'start_year' => -382, 'end_year' => -336];

    private const SPAIN = ['entity_id' => 'philip-spain', 'entity_type' => 'person', 'start_year' => 1527, 'end_year' => 1598];

    private const CHARLES_FRANCE = ['entity_id' => 'charles-france', 'entity_type' => 'person', 'start_year' => 1338, 'end_year' => 1380];

    private const CHARLES_HRE = ['entity_id' => 'charles-hre', 'entity_type' => 'person', 'start_year' => 1500, 'end_year' => 1558];

    private const UNDATED = ['entity_id' => 'philip-undated', 'entity_type' => 'person', 'start_year' => null, 'end_year' => null];

    /**
     * @return array<string, array{string, array{0: int, 1: int}|null, array{0: int, 1: int}|null, string}>
     */
    public static function fits(): array
    {
        return [
            'Philip II Macedon vs Spain' => ['person', [-382, -336], [1527, 1598], 'conflict'],
            'Charles V France vs HRE' => ['person', [1338, 1380], [1500, 1558], 'conflict'],
            'HRE election vs French king' => ['person', [1519, 1519], [1338, 1380], 'conflict'],
            'reign vs lifespan' => ['person', [1556, 1598], [1527, 1598], 'match'],
            'one date inside' => ['person', [1519, 1519], [1500, 1558], 'match'],
            '4y after death' => ['person', [1602, 1602], [1527, 1598], 'near'],
            'within 60y' => ['person', [1650, 1650], [1527, 1598], 'near'],
            'beyond 60y' => ['person', [1690, 1690], [1527, 1598], 'conflict'],
            'round century CE is ±100' => ['person', [19, 19], [100, 100], 'match'],
            'round century BCE is ±100' => ['person', [-728, -728], [-800, -800], 'match'],
            'round 1700 spans 1600-1800' => ['person', [1700, 1700], [1527, 1598], 'near'],
            'round 1900 still far' => ['person', [1900, 1900], [1527, 1598], 'conflict'],
            'deep antiquity widens' => ['person', [-1524, -1524], [-1460, -1440], 'near'],
            'same gap in CE is not' => ['person', [1462, 1462], [1527, 1598], 'conflict'],
            'sign-insensitive' => ['person', [27, 27], [-63, 14], 'match'],
            'polities unchecked' => ['political_entity', [639, 969], [-3150, -30], 'unknown'],
            'cities unchecked' => ['city', [1500, 1600], [-500, -400], 'unknown'],
            'reference undated' => ['person', null, [1527, 1598], 'unknown'],
            'row undated' => ['person', [1527, 1598], null, 'unknown'],
        ];
    }

    /**
     * @param  array{0: int, 1: int}|null  $a
     * @param  array{0: int, 1: int}|null  $b
     */
    #[DataProvider('fits')]
    public function test_temporal_fit(string $type, ?array $a, ?array $b, string $expected): void
    {
        $this->assertSame($expected, R::temporalFit($type, $a, $b));
    }

    public function test_temporal_gap_and_spans(): void
    {
        $this->assertSame(0, R::temporalGap([1556, 1598], [1527, 1598]));
        // 1863y apart; the BCE/CE mirror (336-382 CE) is still 1145y away.
        $this->assertSame(1145, R::temporalGap([-382, -336], [1527, 1598]));
        $this->assertNull(R::temporalGap(null, [1, 2]));
        $this->assertSame([1556, 1556], R::yearSpan(1556, null));
        $this->assertSame([-336, 1598], R::yearSpan(1598, -336));
        $this->assertNull(R::yearSpan(null, null));
        $this->assertSame(-382, R::yearOf('-382'));
        $this->assertSame(1556, R::yearOf('1556-01-15'));
        $this->assertSame(1598, R::yearOf(1598));
        $this->assertNull(R::yearOf('c. 1500'));
    }

    public function test_relation_span_only_for_contemporaneous_types(): void
    {
        $this->assertSame([1556, 1598], R::relationSpan('rules', '1556', '1598'));
        $this->assertSame([-333, -333], R::relationSpan('victorious_at', '-0333', null));
        $this->assertNull(R::relationSpan('influenced_by', '1260', null));
        $this->assertNull(R::relationSpan('rules', null, null));
    }

    public function test_pick_namesake_chooses_the_date_compatible_row(): void
    {
        $this->assertSame([self::SPAIN, 'match'], R::pickNamesake([self::MACEDON, self::SPAIN], [1556, 1598]));
        $this->assertSame([self::MACEDON, 'match'], R::pickNamesake([self::MACEDON, self::SPAIN], [-359, -336]));
        $this->assertSame([self::CHARLES_HRE, 'match'], R::pickNamesake([self::CHARLES_FRANCE, self::CHARLES_HRE], [1519, 1519]));
        $this->assertSame([self::CHARLES_FRANCE, 'match'], R::pickNamesake([self::CHARLES_FRANCE, self::CHARLES_HRE], [1364, 1380]));
    }

    public function test_pick_namesake_rejects_a_lone_incompatible_row(): void
    {
        $this->assertSame([null, R::NAMESAKE_AMBIGUOUS], R::pickNamesake([self::MACEDON], [1556, 1598]));
        $this->assertSame([null, R::NAMESAKE_AMBIGUOUS], R::pickNamesake([self::CHARLES_FRANCE], [1519, 1519]));
    }

    public function test_pick_namesake_undated_reference_between_dated_namesakes_is_ambiguous(): void
    {
        $this->assertSame([null, R::NAMESAKE_AMBIGUOUS], R::pickNamesake([self::MACEDON, self::SPAIN], null));
    }

    public function test_pick_namesake_keeps_pre_guard_behaviour_without_a_signal(): void
    {
        $this->assertSame([self::MACEDON, 'unknown'], R::pickNamesake([self::MACEDON], null));
        $this->assertSame([self::UNDATED, 'unknown'], R::pickNamesake([self::UNDATED, self::MACEDON], null));
        $duplicate = ['entity_id' => 'philip-spain-dup', 'start_year' => 1556, 'end_year' => 1598] + self::SPAIN;
        $this->assertSame([self::SPAIN, 'match'], R::pickNamesake([self::SPAIN, $duplicate], [1580, 1580]));
        $this->assertSame([null, 'none'], R::pickNamesake([], [1, 2]));
    }

    public function test_pick_namesake_prefers_a_dated_match_over_an_undated_row(): void
    {
        $this->assertSame([self::SPAIN, 'match'], R::pickNamesake([self::UNDATED, self::MACEDON, self::SPAIN], [1556, 1598]));
        $this->assertSame([self::UNDATED, 'unknown'], R::pickNamesake([self::MACEDON, self::UNDATED], [1556, 1598]));
    }

    public function test_pick_namesake_unique_mode_for_aliases(): void
    {
        $a = ['entity_id' => 'a'] + self::SPAIN;
        $b = ['entity_id' => 'b'] + self::SPAIN;
        $this->assertSame([null, 'ambiguous'], R::pickNamesake([$a, $b], [1556, 1598], unique: true));
        $this->assertSame([$a, 'match'], R::pickNamesake([self::MACEDON, $a], [1556, 1598], unique: true));
    }

    public function test_pick_namesake_never_date_checks_polities(): void
    {
        $old = ['entity_id' => 'e1', 'entity_type' => 'political_entity', 'start_year' => -3150, 'end_year' => -30];
        $new = ['entity_id' => 'e2', 'entity_type' => 'political_entity', 'start_year' => 1922, 'end_year' => null];
        $this->assertSame([$old, 'unknown'], R::pickNamesake([$old, $new], [639, 969]));
    }
}
