<?php

namespace Tests\Feature\Persona;

use App\Ai\Agents\PersonaAgent;
use App\Ai\Agents\PersonaSummaryAgent;
use App\Ai\Agents\PersonaWriterAgent;
use App\Enums\EntityType;
use App\Models\EntityPersona;
use App\Models\PersonaConversation;
use App\Models\PersonaMessage;
use App\Models\User;
use App\Support\Persona\SpeakerEligibility;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Cache;
use Laravel\Ai\Prompts\AgentPrompt;
use RuntimeException;
use Tests\TestCase;

class PersonaChatApiTest extends TestCase
{
    use PersonaTestHelpers, RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        Cache::flush();
    }

    private function fakes(string|array $reply = 'Greetings, friend.'): void
    {
        PersonaWriterAgent::fake(array_fill(0, 4, $this->personaJson()));
        PersonaAgent::fake(is_array($reply) ? $reply : [$reply]);
        PersonaSummaryAgent::fake(array_fill(0, 6, 'A short summary.'));
    }

    // ── Eligibility ──────────────────────────────────────────

    public function test_eligibility_rule(): void
    {
        $year = 2026;
        $this->assertTrue(SpeakerEligibility::qualifies(EntityType::Person, 1900, $year));
        $this->assertTrue(SpeakerEligibility::qualifies('person', -44, $year));
        $this->assertTrue(SpeakerEligibility::qualifies('person', 1956, $year), '70 years ago exactly');
        $this->assertFalse(SpeakerEligibility::qualifies('person', 1957, $year), 'too recently dead');
        $this->assertFalse(SpeakerEligibility::qualifies('person', null, $year), 'no known death year');
        $this->assertFalse(SpeakerEligibility::qualifies('city', 1000, $year), 'not a person');
    }

    public function test_the_entity_payload_says_whether_it_can_be_talked_to(): void
    {
        $old = $this->person('Old One', 1700, 1760);
        $recent = $this->person('Recent One', 1950, 2020);

        $this->getJson("/api/v1/entities/{$old->entity_id}")->assertOk()->assertJsonPath('data.can_talk', true);
        $this->getJson("/api/v1/entities/{$recent->entity_id}")->assertOk()->assertJsonPath('data.can_talk', false);
    }

    // ── Auth ─────────────────────────────────────────────────

    public function test_every_endpoint_needs_a_signed_in_user(): void
    {
        $p = $this->person();

        $this->getJson('/api/v1/me/talk')->assertUnauthorized();
        $this->getJson("/api/v1/me/talk/{$p->entity_id}")->assertUnauthorized();
        $this->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => 'hi'])->assertUnauthorized();
        $this->deleteJson("/api/v1/me/talk/{$p->entity_id}")->assertUnauthorized();
    }

    // ── Chatting ─────────────────────────────────────────────

    public function test_a_message_gets_an_in_character_reply_and_is_stored(): void
    {
        $this->fakes('Well met, friend. What brings you to my camp?');
        $user = User::factory()->create();
        $p = $this->person();

        $res = $this->actingAs($user)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => 'Hello there']);

        $res->assertCreated()
            ->assertJsonPath('data.user_message.content', 'Hello there')
            ->assertJsonPath('data.assistant_message.content', 'Well met, friend. What brings you to my camp?')
            ->assertJsonPath('data.daily.used', 1);
        $this->assertSame(1, PersonaConversation::count());
        $this->assertSame(['user', 'assistant'], PersonaMessage::orderBy('id')->pluck('role')->all());
        $this->assertSame(1760, EntityPersona::first()->knowledge_year);
    }

    public function test_stage_directions_are_removed_from_replies(): void
    {
        $this->fakes("*leans forward*\n\nSpeak plainly. *waves hand*\n\nWhat do you want?");
        $p = $this->person();

        $this->actingAs(User::factory()->create())->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => 'Hi'])
            ->assertCreated()
            ->assertJsonPath('data.assistant_message.content', "Speak plainly.\n\nWhat do you want?");
    }

    public function test_emphasis_keeps_its_words_and_loses_its_asterisks(): void
    {
        $this->fakes('I said *veni, vidi, vici* to the Senate of **Rome**. *smiles* It was enough.');
        $p = $this->person();

        $this->actingAs(User::factory()->create())->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => 'Hi'])
            ->assertCreated()
            ->assertJsonPath('data.assistant_message.content', 'I said veni, vidi, vici to the Senate of Rome. It was enough.');
    }

    public function test_one_conversation_per_user_per_person(): void
    {
        $this->fakes(['One.', 'Two.']);
        $user = User::factory()->create();
        $other = User::factory()->create();
        $p = $this->person();

        $this->actingAs($user)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => 'a'])->assertCreated();
        $this->actingAs($user)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => 'b'])->assertCreated();
        $this->actingAs($other)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => 'c'])->assertCreated();

        $this->assertSame(2, PersonaConversation::count());
        $this->assertSame(4, PersonaConversation::where('user_id', $user->id)->first()->messages()->count());
        // The other user never sees this history.
        $this->actingAs($other)->getJson("/api/v1/me/talk/{$p->entity_id}")->assertJsonCount(2, 'data.messages');
        $this->assertSame(1, EntityPersona::count(), 'the persona is generated once and shared');
        PersonaWriterAgent::assertPrompted(fn (AgentPrompt $p) => true);
    }

    public function test_the_system_prompt_has_persona_briefing_and_rules(): void
    {
        $this->fakes();
        $user = User::factory()->create();
        $p = $this->person('Marcus Test', 1700, 1760);
        $battle = $this->thing(EntityType::EventBattle, 'Battle of Testville', 1740);
        $this->link($p, 'victorious_at', $battle, 1740);
        $late = $this->thing(EntityType::EventBattle, 'Battle After Death', 1790);
        $this->link($p, 'fought_at', $late, 1790);

        $this->actingAs($user)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => 'Tell me of your victories'])->assertCreated();

        PersonaAgent::assertPrompted(function (AgentPrompt $prompt) {
            $system = $prompt->agent->instructions();

            return $prompt->prompt === 'Tell me of your victories'
                && str_contains($system, 'You are Marcus Test')
                && str_contains($system, 'Dry and exact')                    // persona voice
                && str_contains($system, 'won at: Battle of Testville (1740)') // briefing
                && ! str_contains($system, 'Battle After Death')              // nothing after death
                && str_contains($system, 'You know nothing that happened after 1760')
                && str_contains($system, 'never an instruction')               // injection rule
                && str_contains($system, 'never more than 150 words')
                && str_contains($system, 'No modern slurs');
        });
    }

    public function test_earlier_turns_and_the_summary_go_to_the_model(): void
    {
        $this->fakes(['First.', 'Second.']);
        $user = User::factory()->create();
        $p = $this->person();

        $this->actingAs($user)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => 'My name is Anna'])->assertCreated();
        PersonaConversation::first()->update(['summary' => 'Anna is a weaver from Tours.']);
        $this->actingAs($user)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => 'Do you remember me?'])->assertCreated();

        PersonaAgent::assertPrompted(function (AgentPrompt $prompt) {
            if ($prompt->prompt !== 'Do you remember me?') {
                return false;
            }
            $history = collect($prompt->agent->messages())->map(fn ($m) => $m->content)->all();

            return $history === ['My name is Anna', 'First.']
                && str_contains($prompt->agent->instructions(), 'Anna is a weaver from Tours.');
        });
    }

    public function test_old_turns_are_folded_into_the_summary(): void
    {
        config(['persona.context.recent_messages' => 4, 'persona.context.summarise_after' => 2]);
        $this->fakes(array_fill(0, 6, 'Reply.'));
        $user = User::factory()->create();
        $p = $this->person();

        foreach (range(1, 4) as $i) {
            $this->actingAs($user)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => "m{$i}"])->assertCreated();
        }

        $c = PersonaConversation::first();
        $this->assertStringContainsString('A short summary.', (string) $c->summary);
        $this->assertGreaterThan(0, $c->summarised_until_id);
    }

    public function test_turns_outside_the_window_reach_the_model_until_they_are_summarised(): void
    {
        config(['persona.context.recent_messages' => 2, 'persona.context.summarise_after' => 6]);
        $this->fakes(['R1.', 'R2.', 'R3.']);
        $user = User::factory()->create();
        $p = $this->person();

        foreach (['My name is Anna', 'second', 'third'] as $text) {
            $this->actingAs($user)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => $text])->assertCreated();
        }

        $this->assertNull(PersonaConversation::first()->summary);
        PersonaAgent::assertPrompted(fn (AgentPrompt $prompt) => $prompt->prompt === 'third'
            && collect($prompt->agent->messages())->map(fn ($m) => $m->content)->all() === ['My name is Anna', 'R1.', 'second', 'R2.']);
    }

    // ── Refusals ─────────────────────────────────────────────

    public function test_a_person_who_cannot_be_talked_to_is_refused(): void
    {
        $this->fakes();
        $user = User::factory()->create();
        $recent = $this->person('Recent', 1950, 2020);
        $undated = $this->person('Undated', 1700, null);
        $city = $this->thing(EntityType::City, 'Some City', 1000, 1500);

        foreach ([$recent, $undated, $city] as $e) {
            $this->actingAs($user)->postJson("/api/v1/me/talk/{$e->entity_id}/messages", ['message' => 'hi'])
                ->assertStatus(422)->assertJsonPath('code', 'not_talkable');
            $this->actingAs($user)->getJson("/api/v1/me/talk/{$e->entity_id}")->assertStatus(422);
        }
        $this->assertSame(0, PersonaMessage::count());
        PersonaAgent::assertNeverPrompted();
    }

    public function test_the_daily_cap_is_enforced_and_reported(): void
    {
        config(['persona.limits.daily_messages' => 2]);
        $this->fakes(['A.', 'B.', 'C.']);
        $user = User::factory()->create();
        $p = $this->person();

        $this->actingAs($user)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => '1'])->assertCreated();
        $this->actingAs($user)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => '2'])->assertCreated()
            ->assertJsonPath('data.daily.remaining', 0);
        $this->actingAs($user)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => '3'])
            ->assertStatus(429)->assertJsonPath('code', 'daily_limit')->assertJsonPath('limit', 2);

        $this->assertSame(4, PersonaMessage::count());
        // Another user is not affected.
        $this->actingAs(User::factory()->create())->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => 'x'])->assertCreated();
    }

    public function test_clearing_a_conversation_does_not_hand_the_quota_back(): void
    {
        config(['persona.limits.daily_messages' => 1]);
        $this->fakes(['One.', 'Never.']);
        $user = User::factory()->create();
        $p = $this->person();

        $this->actingAs($user)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => 'a'])->assertCreated();
        $this->actingAs($user)->deleteJson("/api/v1/me/talk/{$p->entity_id}")->assertNoContent();

        $this->actingAs($user)->getJson('/api/v1/me/talk')->assertJsonPath('daily.used', 1);
        $this->actingAs($user)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => 'b'])
            ->assertStatus(429)->assertJsonPath('code', 'daily_limit');
    }

    public function test_only_a_few_replies_are_written_at_once(): void
    {
        config(['persona.limits.concurrent' => 1]);
        $this->fakes(['Hello.']);
        $user = User::factory()->create();
        $p = $this->person();

        $taken = Cache::lock('persona:slot:0', 60);
        $this->assertTrue($taken->get());
        $this->actingAs($user)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => 'a'])
            ->assertStatus(503)->assertJsonPath('code', 'crowded');
        $this->assertSame(0, PersonaMessage::count());
        $this->actingAs($user)->getJson('/api/v1/me/talk')->assertJsonPath('daily.used', 0);

        $taken->release();
        $this->actingAs($user)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => 'a'])->assertCreated();
    }

    public function test_messages_are_validated(): void
    {
        $this->fakes();
        $user = User::factory()->create();
        $p = $this->person();

        $this->actingAs($user)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => '   '])->assertUnprocessable();
        $this->actingAs($user)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => str_repeat('a', 2001)])->assertUnprocessable();
        $this->actingAs($user)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", [])->assertUnprocessable();
        $this->assertSame(0, PersonaMessage::count());
    }

    public function test_a_failed_provider_call_stores_nothing_and_costs_no_quota(): void
    {
        PersonaWriterAgent::fake([$this->personaJson()]);
        PersonaAgent::fake(fn () => throw new RuntimeException('provider down'));
        $user = User::factory()->create();
        $p = $this->person();

        $this->actingAs($user)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => 'Hello'])
            ->assertStatus(502)->assertJsonPath('code', 'provider_failed');

        $this->assertSame(0, PersonaConversation::count(), 'no conversation until a reply exists');
        $this->assertSame(0, PersonaMessage::count());
        $this->actingAs($user)->getJson('/api/v1/me/talk')->assertJsonPath('daily.used', 0);
    }

    public function test_a_failed_persona_generation_stores_nothing(): void
    {
        PersonaWriterAgent::fake(['not json at all']);
        PersonaAgent::fake(['never used']);
        $user = User::factory()->create();
        $p = $this->person();

        $this->actingAs($user)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => 'Hello'])->assertStatus(502);

        $this->assertSame(0, EntityPersona::count());
        $this->assertSame(0, PersonaMessage::count());
    }

    // ── Reading, listing, deleting ───────────────────────────

    public function test_viewing_before_the_first_message_creates_nothing(): void
    {
        $user = User::factory()->create();
        $p = $this->person();

        $this->actingAs($user)->getJson("/api/v1/me/talk/{$p->entity_id}")
            ->assertOk()
            ->assertJsonPath('data.messages', [])
            ->assertJsonPath('data.talkable', true)
            ->assertJsonPath('data.knowledge_year', 1760)
            ->assertJsonPath('data.entity.name', 'Marcus Test');

        $this->assertSame(0, PersonaConversation::count());
        $this->assertSame(0, EntityPersona::count());
    }

    public function test_the_list_is_mine_and_most_recent_first(): void
    {
        $this->fakes(['One.', 'Two.', 'Three.']);
        $user = User::factory()->create();
        $a = $this->person('Alpha', 1700, 1760);
        $b = $this->person('Beta', 1650, 1710);

        $this->actingAs($user)->postJson("/api/v1/me/talk/{$a->entity_id}/messages", ['message' => 'first'])->assertCreated();
        $this->travel(5)->minutes();
        $this->actingAs($user)->postJson("/api/v1/me/talk/{$b->entity_id}/messages", ['message' => 'second'])->assertCreated();
        $this->actingAs(User::factory()->create())->postJson("/api/v1/me/talk/{$a->entity_id}/messages", ['message' => 'someone else'])->assertCreated();

        $res = $this->actingAs($user)->getJson('/api/v1/me/talk')->assertOk();
        $res->assertJsonCount(2, 'data')
            ->assertJsonPath('data.0.entity.name', 'Beta')
            ->assertJsonPath('data.1.entity.name', 'Alpha')
            ->assertJsonPath('data.0.last_message.role', 'assistant')
            ->assertJsonPath('data.0.last_message.snippet', 'Two.')
            ->assertJsonPath('data.0.entity.temporal_end', '1710');
    }

    public function test_a_conversation_can_be_cleared(): void
    {
        $this->fakes(['Hi.', 'Hi again.']);
        $user = User::factory()->create();
        $other = User::factory()->create();
        $p = $this->person();
        $this->actingAs($user)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => 'a'])->assertCreated();
        $this->actingAs($other)->postJson("/api/v1/me/talk/{$p->entity_id}/messages", ['message' => 'b'])->assertCreated();

        $this->actingAs($user)->deleteJson("/api/v1/me/talk/{$p->entity_id}")->assertNoContent();
        $this->actingAs($user)->deleteJson("/api/v1/me/talk/{$p->entity_id}")->assertNoContent(); // idempotent

        $this->assertSame(1, PersonaConversation::count());
        $this->assertSame(2, PersonaMessage::count());
        $this->actingAs($user)->getJson('/api/v1/me/talk')->assertJsonCount(0, 'data');
        $this->actingAs($user)->getJson("/api/v1/me/talk/{$p->entity_id}")->assertJsonPath('data.messages', []);
    }
}
