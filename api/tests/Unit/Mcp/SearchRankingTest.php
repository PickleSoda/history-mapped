<?php

declare(strict_types=1);

namespace Tests\Unit\Mcp;

use App\Mcp\Support\EntitySearch;
use App\Mcp\Support\SearchRanking;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

class SearchRankingTest extends TestCase
{
    /** @return array<string, array{string, string, float}> */
    public static function qualities(): array
    {
        return [
            'exact' => ['Hastings', 'hastings', 1.0],
            'accents and punctuation fold' => ['Napoléon', 'napoleon', 1.0],
            'starts with whole words' => ['Napoleon III', 'napoleon', 0.9],
            'whole words inside' => ['Battle of Hastings', 'hastings', 0.8],
            'sentence-like name loses 0.3' => ['Caesar releases Aristobulus II', 'caesar', 0.6],
            'start of a longer word' => ['Napoleonic Wars', 'napoleon', 0.45],
            'start of a later word' => ['Kingdom of Italy (Napoleonic)', 'napoleon', 0.4],
            'inside a word' => ['Wyoming', 'ming', 0.2],
        ];
    }

    #[DataProvider('qualities')]
    public function test_match_quality_tiers(string $name, string $query, float $expected): void
    {
        $this->assertEqualsWithDelta($expected, SearchRanking::quality($name, $query), 0.0001);
    }

    public function test_a_typo_is_scored_by_trigram_similarity(): void
    {
        $q = SearchRanking::quality('Napoleon', 'napolean');
        $this->assertGreaterThan(0.6, $q);
        $this->assertLessThanOrEqual(0.75, $q);
        $this->assertSame(0.0, SearchRanking::quality('Zzz', 'napolean'));
    }

    public function test_similarity_matches_pg_trgm(): void
    {
        // select similarity('word', 'words'): 0.5714286 in pg_trgm.
        $this->assertEqualsWithDelta(0.5714, SearchRanking::similarity('word', 'words'), 0.001);
        $this->assertSame(1.0, SearchRanking::similarity('rome', 'rome'));
    }

    public function test_a_famous_event_outranks_namesake_towns_but_a_weak_match_does_not(): void
    {
        $rows = [
            ['Hastings', 73], ['Hastings', 67], ['Hastings Banda', 74],
            ['Battle of Hastings', 92], ['Hastingsville', 99], ['Hasting', 50],
        ];

        $names = array_map(
            fn (array $r): string => $r[0],
            SearchRanking::rank($rows, 'hastings', fn (array $r) => $r[0], fn (array $r) => $r[1]),
        );

        $this->assertSame('Battle of Hastings', $names[0]);
        $this->assertSame('Hastings', $names[1], 'the exact name still comes next');
        $this->assertLessThan(array_search('Hastingsville', $names, true), array_search('Hastings Banda', $names, true), 'a whole-word match beats a prefix of a word, whatever its impact');
    }

    public function test_a_name_shared_by_many_is_a_namesake_and_loses_its_exact_bonus(): void
    {
        $rows = [['Alexander', 71], ['Alexander', 66], ['Alexander', 60], ['Alexander', 57], ['Alexander', 55], ['Alexander the Great', 70]];

        $first = SearchRanking::rank($rows, 'alexander', fn (array $r) => $r[0], fn (array $r) => $r[1])[0];

        $this->assertSame('Alexander the Great', $first[0]);
    }

    public function test_a_name_shared_by_two_keeps_most_of_its_exact_bonus(): void
    {
        $rows = [['Rome', 98], ['Rome', 80], ['Sack of Rome', 92]];

        $ranked = SearchRanking::rank($rows, 'rome', fn (array $r) => $r[0], fn (array $r) => $r[1]);

        $this->assertSame([['Rome', 98], ['Rome', 80], ['Sack of Rome', 92]], $ranked);
    }

    public function test_missing_impact_counts_as_low_and_ties_keep_input_order(): void
    {
        $ranked = SearchRanking::rank([['Foo B', null], ['Foo A', 40]], 'foo', fn (array $r) => $r[0], fn (array $r) => $r[1]);

        $this->assertSame('Foo B', $ranked[0][0]);
        $this->assertSame([], SearchRanking::rank([], 'foo', fn ($r) => $r, fn ($r) => 1));
    }

    public function test_chronicle_mentions_add_prominence_up_to_a_cap(): void
    {
        $this->assertSame(0.0, EntitySearch::prominence(0));
        $this->assertSame(5.5, EntitySearch::prominence(1));
        $this->assertSame(30.0, EntitySearch::prominence(83));

        // Julius Caesar (impact 70, 83 mentions) against a bulk-imported namesake start (68, none).
        $rows = [['Caesar Baronius', 68.0], ['Julius Caesar', 70 + EntitySearch::prominence(83)]];
        $first = SearchRanking::rank($rows, 'caesar', fn (array $r) => $r[0], fn (array $r) => $r[1])[0];
        $this->assertSame('Julius Caesar', $first[0]);
    }
}
