<?php

declare(strict_types=1);

namespace App\Actions\Persona;

use App\Ai\Agents\PersonaAgent;
use App\Exceptions\Persona\PersonaException;
use App\Models\Entity;
use App\Models\PersonaConversation;
use App\Models\PersonaMessage;
use App\Models\User;
use App\Support\Persona\SpeakerEligibility;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Laravel\Ai\Messages\Message;
use Throwable;

/**
 * One turn: the visitor's message in, the person's reply out.
 *
 * Order matters. Checks first (eligibility, daily cap), then the persona and
 * briefing, then the model call. Only when the reply is in hand are the
 * conversation (created on the first message) and both messages written, in
 * one transaction, so a failed call leaves no trace and costs no daily quota.
 * A per-conversation lock stops two replies being written at once.
 */
class SendPersonaMessageAction
{
    public function __construct(
        private readonly EnsurePersonaAction $ensurePersona,
        private readonly GetPersonaBriefingAction $briefing,
        private readonly BuildPersonaPromptAction $prompt,
        private readonly PersonaDailyUsageAction $usage,
    ) {}

    /** @return array{user: PersonaMessage, assistant: PersonaMessage, conversation: PersonaConversation} */
    public function __invoke(User $user, Entity $entity, string $text): array
    {
        $entity->loadMissing('primaryTemporalRange');
        if (! SpeakerEligibility::isTalkable($entity)) {
            throw PersonaException::notTalkable();
        }
        $daily = ($this->usage)($user);
        if ($daily['remaining'] <= 0) {
            throw PersonaException::dailyLimit($daily['limit']);
        }

        $lock = Cache::lock("persona:send:{$user->id}:{$entity->entity_id}", 120);
        if (! $lock->get()) {
            throw PersonaException::busy();
        }

        try {
            $persona = ($this->ensurePersona)($entity);
            $conversation = PersonaConversation::where('user_id', $user->id)->where('entity_id', $entity->entity_id)->first();

            $system = ($this->prompt)(
                $entity,
                $persona,
                ($this->briefing)($entity, $persona->knowledge_year),
                $conversation?->summary,
            );
            $history = $conversation ? $this->recent($conversation) : [];
            $model = config('persona.chat_model');

            try {
                $response = (new PersonaAgent(
                    $system,
                    $history,
                    $model,
                    (int) config('persona.limits.output_tokens', 450),
                ))->prompt($text, model: $model);
                $reply = $this->tidy((string) $response->text);
                if ($reply === '') {
                    throw new \RuntimeException('Empty reply.');
                }
            } catch (Throwable $e) {
                Log::warning('persona.chat_failed', ['entity' => $entity->entity_id, 'user' => $user->id, 'error' => $e->getMessage()]);
                throw PersonaException::providerFailed();
            }

            $result = DB::transaction(function () use ($user, $entity, $text, $reply, $response, $model) {
                $conversation = PersonaConversation::firstOrCreate(['user_id' => $user->id, 'entity_id' => $entity->entity_id]);
                $userMessage = $conversation->messages()->create(['user_id' => $user->id, 'role' => 'user', 'content' => $text]);
                $assistant = $conversation->messages()->create([
                    'user_id' => $user->id,
                    'role' => 'assistant',
                    'content' => $reply,
                    'model' => $model ?: config('ai.providers.'.config('ai.default').'.models.text.default'),
                    'prompt_tokens' => $response->usage->promptTokens ?? null,
                    'completion_tokens' => $response->usage->completionTokens ?? null,
                ]);
                $conversation->forceFill(['last_message_at' => $assistant->created_at])->save();

                return ['user' => $userMessage, 'assistant' => $assistant, 'conversation' => $conversation];
            });
        } finally {
            $lock->release();
        }

        $id = $result['conversation']->id;
        dispatch(fn () => app(SummarisePersonaConversationAction::class)($id))->afterResponse();

        return $result;
    }

    /** @return list<Message> */
    private function recent(PersonaConversation $conversation): array
    {
        $n = max(2, (int) config('persona.context.recent_messages', 16));

        return $conversation->messages()->reorder()->orderByDesc('id')->limit($n)->get(['role', 'content'])
            ->reverse()->map(fn ($m) => new Message($m->role, $m->content))->values()->all();
    }

    /**
     * Stage directions in asterisks ("*leans forward*") are removed, however
     * the model likes them; a reply cut by the token limit ends at its last
     * full sentence.
     */
    private function tidy(string $reply): string
    {
        $reply = preg_replace('/[ \t]*\*[^*\n]{1,160}\*[ \t]*/u', ' ', $reply) ?? $reply;
        $reply = trim(preg_replace("/[ \t]+\n/", "\n", preg_replace("/\n{3,}/", "\n\n", $reply) ?? $reply) ?? $reply);
        if ($reply === '' || preg_match('/[.!?…"”»)\]*]$/u', $reply)) {
            return $reply;
        }
        if (preg_match('/^(.*[.!?…]["”»)]?)\s/su', $reply, $m) && mb_strlen($m[1]) > mb_strlen($reply) * 0.5) {
            return trim($m[1]);
        }

        return $reply;
    }
}
