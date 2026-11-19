<?php

declare(strict_types=1);

namespace App\Actions\Persona;

use App\Ai\Agents\PersonaSummaryAgent;
use App\Models\PersonaConversation;
use Illuminate\Support\Facades\Log;
use Throwable;

/**
 * Folds turns that left the recent window into the conversation's running
 * summary, so an old chat keeps its thread without a growing prompt. Runs
 * after the response; a failure leaves the summary as it was and is retried
 * on the next message.
 */
class SummarisePersonaConversationAction
{
    public function __invoke(int $conversationId): void
    {
        $conversation = PersonaConversation::with('entity:entity_id,name')->find($conversationId);
        if (! $conversation) {
            return;
        }
        $recent = max(2, (int) config('persona.context.recent_messages', 16));
        $threshold = max(2, (int) config('persona.context.summarise_after', 8));

        $keepFromId = $conversation->messages()->reorder()->orderByDesc('id')->skip($recent - 1)->limit(1)->value('id');
        if ($keepFromId === null) {
            return;
        }
        $older = $conversation->messages()->where('id', '>', $conversation->summarised_until_id)->where('id', '<', $keepFromId)->get();
        if ($older->count() < $threshold) {
            return;
        }

        $name = $conversation->entity->name;
        $transcript = $older->map(fn ($m) => ($m->role === 'user' ? 'Visitor' : $name).': '.$m->content)->implode("\n");
        $previous = $conversation->summary ? "Earlier summary:\n{$conversation->summary}\n\n" : '';
        $limit = (int) config('persona.context.summary_chars', 1800);

        try {
            $response = (new PersonaSummaryAgent(
                "You keep the memory of {$name} for a role-play chat. Summarise the talk below in at most {$limit} characters of plain prose, from {$name}'s point of view, third person is fine. Keep what the visitor said about themselves, topics discussed, promises, and the tone between them. Add nothing that was not said. Reply with the summary only.",
                [],
                config('persona.chat_model'),
                500,
                0.2,
            ))->prompt($previous."New conversation:\n".$transcript, model: config('persona.chat_model'));
            $summary = trim((string) $response->text);
        } catch (Throwable $e) {
            Log::warning('persona.summary_failed', ['conversation' => $conversationId, 'error' => $e->getMessage()]);

            return;
        }
        if ($summary === '') {
            return;
        }
        $conversation->forceFill([
            'summary' => mb_substr($summary, 0, $limit),
            'summarised_until_id' => $older->max('id'),
        ])->save();
    }
}
