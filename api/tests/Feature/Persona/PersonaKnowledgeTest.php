<?php

namespace Tests\Feature\Persona;

use App\Actions\Persona\BuildPersonaKnowledgeAction;
use App\Enums\EntityType;
use App\Support\Persona\AnachronismGuard;
use App\Support\Persona\PersonaKnowledge;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class PersonaKnowledgeTest extends TestCase
{
    use PersonaTestHelpers, RefreshDatabase;

    private function build($person, ?int $k = null, ?int $budget = null): PersonaKnowledge
    {
        return app(BuildPersonaKnowledgeAction::class)($person, $k, $budget);
    }

    public function test_briefing_lists_direct_relationships_with_years(): void
    {
        $p = $this->person();
        $battle = $this->thing(EntityType::EventBattle, 'Battle of Testville', 1740);
        $king = $this->thing(EntityType::PoliticalEntity, 'Kingdom of Tests', 1650);
        $this->link($p, 'victorious_at', $battle, 1740);
        $this->link($p, 'rules', $king, 1745, 1755);

        $text = $this->build($p)->render();

        $this->assertStringContainsString('won at: Battle of Testville (1740)', $text);
        $this->assertStringContainsString('ruled: Kingdom of Tests (1745-1755)', $text);
    }

    public function test_nothing_dated_after_the_knowledge_year_is_included(): void
    {
        $p = $this->person('Old Marcus', 1700, 1760);
        $early = $this->thing(EntityType::EventBattle, 'Battle Before', 1750);
        $late = $this->thing(EntityType::EventBattle, 'Battle After Death', 1770);
        $lateEntity = $this->thing(EntityType::EventWar, 'War Of Later Days', 1790);
        $this->link($p, 'fought_at', $early, 1750);
        $this->link($p, 'fought_at', $late, 1770);   // relationship dated after death
        $this->link($p, 'participated_in', $lateEntity); // undated link, but the entity itself is later
        $this->chronicleEntry($p, 1755, 'Marcus defends the pass in 1755.');
        $this->chronicleEntry($p, 1780, 'Marcus is remembered in 1780.');
        $this->chronicleEntry($p, 1730, 'Marcus is praised, though his fall in 1790 is still to come.');

        $text = $this->build($p)->render();

        $this->assertStringContainsString('Battle Before', $text);
        $this->assertStringNotContainsString('Battle After Death', $text);
        $this->assertStringNotContainsString('War Of Later Days', $text);
        $this->assertStringContainsString('defends the pass', $text);
        $this->assertStringNotContainsString('remembered in 1780', $text);
        $this->assertStringNotContainsString('1790', $text, 'text naming a later year is dropped');
    }

    public function test_a_custom_knowledge_year_is_the_cutoff(): void
    {
        $p = $this->person('Marcus', 1700, 1760);
        $a = $this->thing(EntityType::EventBattle, 'Battle At Forty', 1740);
        $b = $this->thing(EntityType::EventBattle, 'Battle At Fifty', 1750);
        $this->link($p, 'fought_at', $a, 1740);
        $this->link($p, 'fought_at', $b, 1750);

        $text = $this->build($p, 1745)->render();

        $this->assertStringContainsString('Battle At Forty', $text);
        $this->assertStringNotContainsString('Battle At Fifty', $text);
    }

    public function test_a_range_that_ends_after_the_cutoff_is_shown_as_since(): void
    {
        $p = $this->person('Marcus', 1700, 1760);
        $kingdom = $this->thing(EntityType::PoliticalEntity, 'Long Kingdom', 1600, 1900);
        $this->link($p, 'rules', $kingdom, 1740, 1900);

        $text = $this->build($p)->render();

        $this->assertStringContainsString('Long Kingdom (since 1740)', $text);
        $this->assertStringNotContainsString('1900', $text);
    }

    public function test_the_realm_brings_the_wars_and_allies_of_the_ruled_state(): void
    {
        $p = $this->person();
        $kingdom = $this->thing(EntityType::PoliticalEntity, 'Kingdom of Tests', 1650);
        $enemy = $this->thing(EntityType::PoliticalEntity, 'Enemy Duchy', 1600);
        $ally = $this->thing(EntityType::PoliticalEntity, 'Friendly Republic', 1600);
        $this->link($p, 'rules', $kingdom, 1745, 1755);
        $this->link($kingdom, 'at_war_with', $enemy, 1750, 1755);
        $this->link($kingdom, 'allied_with', $ally, 1740);

        $text = $this->build($p)->render();

        $this->assertStringContainsString('Kingdom of Tests — ', $text);
        $this->assertStringContainsString('at war with Enemy Duchy', $text);
        $this->assertStringContainsString('allied with Friendly Republic', $text);
    }

    public function test_nearby_places_active_in_the_lifetime_are_included_and_later_ones_are_not(): void
    {
        $p = $this->person();
        $battle = $this->thing(EntityType::EventBattle, 'Battle of Testville', 1740);
        $this->place($battle, 10.0, 50.0);
        $this->link($p, 'victorious_at', $battle, 1740);

        $near = $this->thing(EntityType::City, 'Nearton', 1500, 1900, 55);
        $this->place($near, 10.5, 50.4);
        $later = $this->thing(EntityType::City, 'Newcity Founded Later', 1800, 1900, 90);
        $this->place($later, 10.2, 50.1);
        $far = $this->thing(EntityType::City, 'Faraway', 1500, 1900, 99);
        $this->place($far, 80.0, 10.0);

        $text = $this->build($p)->render();

        $this->assertStringContainsString('Nearton (city, since 1500)', $text);
        $this->assertStringNotContainsString('Newcity Founded Later', $text);
        $this->assertStringNotContainsString('Faraway', $text);
    }

    public function test_the_briefing_respects_the_token_budget_and_trims_low_priority_first(): void
    {
        $p = $this->person();
        $king = $this->thing(EntityType::PoliticalEntity, 'Kingdom of Tests', 1650);
        $this->link($p, 'rules', $king, 1745, 1755);
        foreach (range(1, 40) as $i) {
            $b = $this->thing(EntityType::EventBattle, "Battle number {$i} of a very long and detailed campaign", 1740 + ($i % 15), null, 50 + $i);
            $this->link($p, 'victorious_at', $b, 1740 + ($i % 15));
        }

        $full = $this->build($p, null, 5000);
        $tight = $this->build($p, null, 50);

        $this->assertLessThanOrEqual(50, PersonaKnowledge::estimateTokens($tight->render()));
        $this->assertGreaterThan(50, PersonaKnowledge::estimateTokens($full->render()));
        $this->assertStringContainsString('and 34 more', $full->render(), 'a long list is capped, not dumped');
        $this->assertStringContainsString('ruled: Kingdom of Tests', $tight->render(), 'relations survive the trim');
    }

    public function test_a_person_with_no_data_yields_an_empty_briefing(): void
    {
        $p = $this->person('Nobody', 1700, 1760, 10);

        $k = $this->build($p);

        $this->assertTrue($k->isEmpty());
        $this->assertSame('', $k->render());
        $this->assertSame('local', $k->reach);
    }

    public function test_a_person_without_dates_has_no_knowledge_year(): void
    {
        $p = $this->person('Undated', 1700, null);

        $this->assertTrue($this->build($p)->isEmpty());
    }

    public function test_anachronism_guard(): void
    {
        $this->assertTrue(AnachronismGuard::isSafe('He crossed the Rubicon in 49 BCE with 5,000 men.', -44));
        $this->assertFalse(AnachronismGuard::isSafe('Rome fell in 476.', -44));
        $this->assertFalse(AnachronismGuard::isSafe('Later, in 1815, he fell.', 1800));
        $this->assertTrue(AnachronismGuard::isSafe('A war of 10,000 men in 1744.', 1760));
        $this->assertNull(AnachronismGuard::snippet('It ended in 1900.', 1800));
        $this->assertSame('Short and safe.', AnachronismGuard::snippet('Short and safe.', 1800));
    }
}
