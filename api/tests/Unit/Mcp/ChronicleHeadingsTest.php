<?php

declare(strict_types=1);

namespace Tests\Unit\Mcp;

use App\Mcp\Support\ChronicleHeadings;
use PHPUnit\Framework\TestCase;

class ChronicleHeadingsTest extends TestCase
{
    private static function e(string $name, bool $event = false, bool $primary = false, ?int $impact = 50): array
    {
        return ['name' => $name, 'event' => $event, 'primary' => $primary, 'impact' => $impact];
    }

    public function test_a_named_event_heads_its_step(): void
    {
        $headings = ChronicleHeadings::forEntries([
            ['text' => 'In 260 BCE the consul Gaius Duilius defeated the Carthaginian fleet off Mylae.', 'entities' => [self::e('Rome', false, true), self::e('Battle of Mylae', true), self::e('Gaius Duilius')]],
            ['text' => 'Rome then built more ships.', 'entities' => [self::e('Rome', false, true)]],
        ]);

        // The battle is not named in the text ("off Mylae"), but an event link still beats a person.
        $this->assertSame('Battle of Mylae', $headings[0]);
    }

    public function test_an_event_named_in_the_text_beats_one_that_is_not(): void
    {
        $headings = ChronicleHeadings::forEntries([[
            'text' => 'The fleet won at Cape Ecnomus, and the Battle of Cape Ecnomus opened Africa.',
            'entities' => [self::e('First Punic War', true), self::e('Battle of Cape Ecnomus', true)],
        ]]);

        $this->assertSame('Battle of Cape Ecnomus', $headings[0]);
    }

    public function test_an_entity_in_most_steps_heads_none_of_them(): void
    {
        $entries = [];
        foreach (range(1, 8) as $i) {
            $entries[] = ['text' => "Rome did thing number {$i} in the region around the sea, again.", 'entities' => [self::e('Rome', false, true)]];
        }

        foreach (ChronicleHeadings::forEntries($entries) as $heading) {
            $this->assertStringStartsWith('Rome did thing', $heading);
        }
    }

    public function test_an_entity_the_text_opens_with_is_skipped_so_the_words_are_not_repeated(): void
    {
        $headings = ChronicleHeadings::forEntries([[
            'text' => 'Hastings was fought on a ridge near Senlac, and the English line broke.',
            'entities' => [self::e('Hastings', true)],
        ]]);

        $this->assertSame('Hastings was fought on a ridge near Senlac', $headings[0]);
    }

    public function test_a_plain_place_or_mentioned_person_never_heads_a_step(): void
    {
        $headings = ChronicleHeadings::forEntries([[
            'text' => 'Settlers founded a colony on the coast of Sicily.',
            'entities' => [self::e('Sicily'), self::e('Chalcis', false, false)],
        ]]);

        $this->assertSame('Settlers founded a colony on the coast of Sicily', $headings[0]);
    }

    public function test_a_primary_end_named_in_the_text_can_head_a_step(): void
    {
        $headings = ChronicleHeadings::forEntries([[
            'text' => 'Settlers founded Sybaris on the Gulf of Taranto around 720 BCE.',
            'entities' => [self::e('Sybaris', false, true)],
        ]]);

        $this->assertSame('Sybaris', $headings[0]);
    }

    public function test_the_clause_fallback_drops_a_date_and_cuts_at_a_clause(): void
    {
        $this->assertSame('The Romans built a fleet of 120 warships', ChronicleHeadings::clause('In 260 BCE the Romans built a fleet of 120 warships, copying a shipwrecked quinquereme. Then they sailed.'));
        $this->assertSame('Caesar crosses the Rubicon', ChronicleHeadings::clause('Caesar crosses the Rubicon. Civil war begins.'));
        $this->assertSame('Euboean Greeks founded Cumae', ChronicleHeadings::clause('Around 740 BCE Euboean Greeks founded Cumae.'));
    }

    public function test_the_clause_fallback_cuts_a_long_sentence_at_a_word(): void
    {
        $long = 'Settlers from many distant cities and islands gathered gradually along the winding southern coast of the peninsula over several generations';
        $heading = ChronicleHeadings::clause($long);

        $this->assertLessThanOrEqual(ChronicleHeadings::MAX, mb_strlen($heading));
        $this->assertStringEndsWith('…', $heading);
        $this->assertStringNotContainsString('peni…', $heading);
        $this->assertStringStartsWith('Settlers from', $heading);
    }
}
