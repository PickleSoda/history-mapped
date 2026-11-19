<?php

declare(strict_types=1);

namespace App\Mcp\Support;

/**
 * A short heading for each step of a chronicle, without a model.
 *
 * A chronicle entry has no title, only its narrative and the entities linked
 * to it (the primary relationship's two ends and the secondary entities). The
 * heading is the name of the entity the step is about:
 *
 *   1. candidates are the linked entities that are specific to the step, that
 *      is, linked to at most a quarter of the chronicle's steps (at least 2):
 *      "Rome" in a chronicle about Rome heads nothing;
 *   2. an event (battle, war, treaty, siege...) named in the text wins, then
 *      an event not named, then an end of the primary relationship that the
 *      text names; other linked entities (places, people only mentioned) never
 *      head a step, they are context;
 *   3. among equals the rarer one, then the one named earliest, then the more
 *      important one. An entity the text opens with is skipped, since the
 *      heading would only repeat the first words;
 *   4. with no candidate, the first clause of the narrative: its first
 *      sentence without a leading date phrase ("In 260 BCE the Romans built
 *      a fleet, copying a ship" becomes "The Romans built a fleet"), cut at a
 *      comma or other clause break, or else at a word, within 80 characters.
 *
 * The timeline view removes a heading that starts the text from the body
 * (same rules as `clause()`), so the words are never shown twice.
 */
final class ChronicleHeadings
{
    public const MAX = 80;

    /** The same pattern is in timeline-app.blade.php (DATE_PREFIX). */
    private const DATE_PREFIX = '/^(?:In|By|Around|About|During|Early in|Late in|Until|After|Before|From)\s+(?:(?:early|late|mid|the|c\.|circa)\s+)*\d{1,4}(?:\s*(?:BCE|BC|CE|AD))?(?:\s*[–-]\s*\d{1,4}(?:\s*(?:BCE|BC|CE|AD))?)?(?:\s*,\s*|\s+)/u';

    /**
     * @param  list<array{text: string, entities: list<array{name: string, event: bool, primary: bool, impact: int|null}>}>  $entries
     * @return list<string>
     */
    public static function forEntries(array $entries): array
    {
        $frequency = [];
        foreach ($entries as $entry) {
            foreach (array_unique(array_map(fn (array $e): string => SearchRanking::normalize($e['name']), $entry['entities'])) as $name) {
                $frequency[$name] = ($frequency[$name] ?? 0) + 1;
            }
        }
        $specific = max(2, intdiv(count($entries), 4));

        return array_map(
            fn (array $entry): string => self::pick($entry['text'], $entry['entities'], $frequency, $specific) ?? self::clause($entry['text']),
            $entries,
        );
    }

    /**
     * @param  list<array{name: string, event: bool, primary: bool, impact: int|null}>  $entities
     * @param  array<string, int>  $frequency
     */
    private static function pick(string $text, array $entities, array $frequency, int $specific): ?string
    {
        $haystack = ' '.SearchRanking::normalize($text).' ';
        $best = null;

        foreach ($entities as $e) {
            $name = SearchRanking::normalize($e['name']);
            if ($name === '' || mb_strlen($e['name']) > self::MAX || ($frequency[$name] ?? 1) > $specific) {
                continue;
            }
            $at = mb_strpos($haystack, ' '.$name.' ');
            if ($at === 0) {
                continue; // The text opens with it; the heading would repeat.
            }
            $named = $at !== false;
            if (! $e['event'] && ! ($e['primary'] && $named)) {
                continue; // Only events, and the primary relationship's own ends, make a heading.
            }
            $key = [$e['event'] ? ($named ? 4 : 3) : 2, -($frequency[$name] ?? 1), $named ? -$at : 0, $e['impact'] ?? 0];
            if ($best === null || $key > $best[0]) {
                $best = [$key, trim($e['name'])];
            }
        }

        return $best[1] ?? null;
    }

    /** The first clause of a narrative as a heading (rule 4 above). */
    public static function clause(string $text): string
    {
        $text = trim((string) preg_replace('/\s+/u', ' ', $text));
        $text = (string) preg_replace(self::DATE_PREFIX, '', $text);
        $sentence = preg_match('/^(.+?[.!?])(\s|$)/u', $text, $m) === 1 ? rtrim($m[1], '.!?') : $text;
        $sentence = self::capitalize($sentence);

        // The first clause break after 25 characters, when the sentence is long.
        if (mb_strlen($sentence) > 45 && preg_match('/^(.{25,'.self::MAX.'}?)(?:,|;|:| –| —)\s/u', $sentence, $m) === 1) {
            return $m[1];
        }
        if (mb_strlen($sentence) <= self::MAX) {
            return $sentence;
        }

        return (string) Text::limit($sentence, self::MAX);
    }

    private static function capitalize(string $text): string
    {
        return mb_strtoupper(mb_substr($text, 0, 1)).mb_substr($text, 1);
    }
}
