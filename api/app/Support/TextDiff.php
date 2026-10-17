<?php

declare(strict_types=1);

namespace App\Support;

use SebastianBergmann\Diff\Differ;
use SebastianBergmann\Diff\Output\UnifiedDiffOutputBuilder;

/**
 * Word-level text diff, the storage format of a contribution.
 *
 * A diff is an ordered list of `[op, text]` tuples where op is `=` (unchanged),
 * `-` (removed) or `+` (added). Joining the `=`/`-` texts gives the old text,
 * the `=`/`+` texts the new one. Tokens are words, whitespace runs and single
 * punctuation characters, so a fixed comma does not mark the whole word. The
 * SPA's `lib/text-diff.ts` mirrors the tokenizer for its live preview.
 *
 * `byLine` diffs whole lines instead, for list fields where each line is one
 * item that is either kept, added or removed. Items (not separators) are
 * compared, so a diff never pairs up stray newlines; separators are then
 * attached to whichever side(s) need them.
 */
final class TextDiff
{
    public const EQUAL = '=';

    public const DELETE = '-';

    public const INSERT = '+';

    private const TOKEN_PATTERN = '/\s+|[\p{L}\p{N}\p{M}_]+|[^\s\p{L}\p{N}\p{M}_]/u';

    private const WORD_PATTERN = '/[\p{L}\p{N}\p{M}_]+/u';

    /**
     * @return list<array{0: string, 1: string}>
     */
    public static function compute(string $from, string $to, bool $byLine = false): array
    {
        $from = self::normalise($from);
        $to = self::normalise($to);

        if ($from === $to) {
            return $from === '' ? [] : [[self::EQUAL, $from]];
        }

        if ($byLine) {
            return self::computeLines($from, $to);
        }

        $rows = (new Differ(new UnifiedDiffOutputBuilder))
            ->diffToArray(self::tokenize($from), self::tokenize($to));

        // Collapse token rows into runs. Inside a change run removals come
        // before additions, so a replacement reads "old → new".
        $ops = [];
        $removed = '';
        $added = '';

        foreach ($rows as [$token, $type]) {
            if ($type === Differ::REMOVED) {
                $removed .= $token;
            } elseif ($type === Differ::ADDED) {
                $added .= $token;
            } elseif ($type === Differ::OLD) {
                self::pushChange($ops, $removed, $added);
                $removed = $added = '';
                self::push($ops, self::EQUAL, $token);
            }
            // Differ's line-ending warning rows carry none of our text.
        }
        self::pushChange($ops, $removed, $added);

        return self::foldWhitespaceIslands($ops);
    }

    /** @return list<string> */
    public static function tokenize(string $text): array
    {
        preg_match_all(self::TOKEN_PATTERN, $text, $m);

        return $m[0];
    }

    /**
     * Item-level diff of two `\n`-joined lists. Each `\n` goes to the side
     * that has an earlier item: on an unchanged item both sides usually do, so
     * it joins the `=` text; otherwise it is a one-sided addition/removal.
     *
     * @return list<array{0: string, 1: string}>
     */
    private static function computeLines(string $from, string $to): array
    {
        $items = fn (string $s) => $s === '' ? [] : explode("\n", $s);
        $rows = (new Differ(new UnifiedDiffOutputBuilder))->diffToArray($items($from), $items($to));

        $ops = [];
        $removed = $added = '';
        $hasOld = $hasNew = false;

        foreach ($rows as [$item, $type]) {
            if ($type === Differ::REMOVED) {
                $removed .= ($hasOld ? "\n" : '').$item;
                $hasOld = true;
            } elseif ($type === Differ::ADDED) {
                $added .= ($hasNew ? "\n" : '').$item;
                $hasNew = true;
            } elseif ($type === Differ::OLD) {
                if ($hasOld && ! $hasNew) {
                    $removed .= "\n";
                } elseif ($hasNew && ! $hasOld) {
                    $added .= "\n";
                }
                self::pushChange($ops, $removed, $added);
                $removed = $added = '';
                self::push($ops, self::EQUAL, ($hasOld && $hasNew ? "\n" : '').$item);
                $hasOld = $hasNew = true;
            }
        }
        self::pushChange($ops, $removed, $added);

        return $ops;
    }

    /** Line endings to `\n`, so a CRLF paste is not a whole-text change. */
    public static function normalise(string $text): string
    {
        return str_replace(["\r\n", "\r"], "\n", $text);
    }

    /**
     * The text before the change.
     *
     * @param  list<array{0: string, 1: string}>  $ops
     */
    public static function oldText(array $ops): string
    {
        return implode('', array_map(fn (array $op) => $op[0] === self::INSERT ? '' : $op[1], $ops));
    }

    /**
     * The text after the change.
     *
     * @param  list<array{0: string, 1: string}>  $ops
     */
    public static function newText(array $ops): string
    {
        return implode('', array_map(fn (array $op) => $op[0] === self::DELETE ? '' : $op[1], $ops));
    }

    /**
     * Count of changed words (whitespace and punctuation are free).
     *
     * @param  list<array{0: string, 1: string}>  $ops
     * @return array{added: int, removed: int}
     */
    public static function stats(array $ops): array
    {
        $stats = ['added' => 0, 'removed' => 0];
        foreach ($ops as [$op, $text]) {
            if ($op === self::INSERT) {
                $stats['added'] += (int) preg_match_all(self::WORD_PATTERN, $text);
            } elseif ($op === self::DELETE) {
                $stats['removed'] += (int) preg_match_all(self::WORD_PATTERN, $text);
            }
        }

        return $stats;
    }

    /**
     * Append text under `op`, merging into the previous tuple when it matches.
     *
     * @param  list<array{0: string, 1: string}>  $ops
     */
    private static function push(array &$ops, string $op, string $text): void
    {
        if ($text === '') {
            return;
        }
        $last = array_key_last($ops);
        if ($last !== null && $ops[$last][0] === $op) {
            $ops[$last][1] .= $text;

            return;
        }
        $ops[] = [$op, $text];
    }

    /** @param  list<array{0: string, 1: string}>  $ops */
    private static function pushChange(array &$ops, string $removed, string $added): void
    {
        self::push($ops, self::DELETE, $removed);
        self::push($ops, self::INSERT, $added);
    }

    /**
     * A lone whitespace run kept between two changes (`-a +b = -c +d`) reads as
     * noise. Fold it into both sides so the reviewer sees one replacement
     * (`-a c +b d`).
     *
     * @param  list<array{0: string, 1: string}>  $ops
     * @return list<array{0: string, 1: string}>
     */
    private static function foldWhitespaceIslands(array $ops): array
    {
        $out = [];
        $removed = $added = '';
        $inChange = false;
        $count = count($ops);

        for ($i = 0; $i < $count; $i++) {
            [$op, $text] = $ops[$i];

            if ($op === self::DELETE) {
                $removed .= $text;
                $inChange = true;
            } elseif ($op === self::INSERT) {
                $added .= $text;
                $inChange = true;
            } elseif ($inChange && trim($text) === '' && ($ops[$i + 1][0] ?? self::EQUAL) !== self::EQUAL) {
                $removed .= $text;
                $added .= $text;
            } else {
                self::pushChange($out, $removed, $added);
                $removed = $added = '';
                $inChange = false;
                self::push($out, self::EQUAL, $text);
            }
        }
        self::pushChange($out, $removed, $added);

        return $out;
    }
}
