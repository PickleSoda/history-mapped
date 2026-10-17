<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Support\TextDiff;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

class TextDiffTest extends TestCase
{
    /** @return array<string, array{string, string}> */
    public static function pairs(): array
    {
        return [
            'typo' => ['The battle of Marathon was fougth in 490 BC.', 'The battle of Marathon was fought in 490 BC.'],
            'insert' => ['Rome fell.', 'Rome finally fell.'],
            'delete' => ['A very very long reign.', 'A very long reign.'],
            'rewrite' => ['alpha beta gamma', 'one two three four'],
            'from empty' => ['', 'A brand new summary.'],
            'to empty' => ['Old summary.', ''],
            'unicode' => ['Ἀθῆναι était la cité', 'Ἀθῆναι était une cité'],
            'newlines' => ["First line.\nSecond line.", "First line.\n\nSecond, longer line."],
        ];
    }

    #[DataProvider('pairs')]
    public function test_the_diff_round_trips_to_both_texts(string $from, string $to): void
    {
        $ops = TextDiff::compute($from, $to);

        $this->assertSame($from, TextDiff::oldText($ops));
        $this->assertSame($to, TextDiff::newText($ops));
    }

    public function test_a_fixed_typo_marks_only_that_word(): void
    {
        $ops = TextDiff::compute('was fougth in 490', 'was fought in 490');

        $this->assertSame([
            ['=', 'was '],
            ['-', 'fougth'],
            ['+', 'fought'],
            ['=', ' in 490'],
        ], $ops);
        $this->assertSame(['added' => 1, 'removed' => 1], TextDiff::stats($ops));
    }

    public function test_punctuation_is_its_own_token(): void
    {
        $ops = TextDiff::compute('Athens, Sparta', 'Athens; Sparta');

        $this->assertSame([['=', 'Athens'], ['-', ','], ['+', ';'], ['=', ' Sparta']], $ops);
        $this->assertSame(['added' => 0, 'removed' => 0], TextDiff::stats($ops));
    }

    public function test_whitespace_between_two_changes_is_folded_into_one_replacement(): void
    {
        $ops = TextDiff::compute('keep alpha beta keep', 'keep one two keep');

        $this->assertSame([
            ['=', 'keep '],
            ['-', 'alpha beta'],
            ['+', 'one two'],
            ['=', ' keep'],
        ], $ops);
    }

    public function test_by_line_mode_treats_each_line_as_one_item(): void
    {
        $from = "Charles the Wise\nKarl V";
        $to = "Charles le Sage\nCharles the Wise";
        $ops = TextDiff::compute($from, $to, byLine: true);

        $this->assertSame([['+', "Charles le Sage\n"], ['=', 'Charles the Wise'], ['-', "\nKarl V"]], $ops);
        $this->assertSame($from, TextDiff::oldText($ops));
        $this->assertSame($to, TextDiff::newText($ops));
    }

    /** @return array<string, array{string, string}> */
    public static function lists(): array
    {
        return [
            'add first' => ["B\nC", "A\nB\nC"],
            'add last' => ["A\nB", "A\nB\nC"],
            'remove middle' => ["A\nB\nC", "A\nC"],
            'remove all' => ["A\nB", ''],
            'from empty' => ['', "A\nB"],
            'swap all' => ["A\nB", "C\nD"],
            'mixed' => ["A\nC\nE", "B\nC\nD\nE\nF"],
        ];
    }

    #[DataProvider('lists')]
    public function test_by_line_mode_round_trips(string $from, string $to): void
    {
        $ops = TextDiff::compute($from, $to, byLine: true);

        $this->assertSame($from, TextDiff::oldText($ops));
        $this->assertSame($to, TextDiff::newText($ops));
    }

    public function test_line_endings_are_normalised(): void
    {
        $this->assertSame([['=', "a\nb"]], TextDiff::compute("a\r\nb", "a\nb"));
        $this->assertSame([], TextDiff::compute('', ''));
    }
}
