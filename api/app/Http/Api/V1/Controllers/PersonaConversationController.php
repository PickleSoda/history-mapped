<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Actions\Persona\ClearPersonaConversationAction;
use App\Actions\Persona\ListPersonaConversationsAction;
use App\Actions\Persona\PersonaDailyUsageAction;
use App\Actions\Persona\SendPersonaMessageAction;
use App\Exceptions\Persona\PersonaException;
use App\Http\Api\V1\Requests\SendPersonaMessageRequest;
use App\Http\Api\V1\Resources\PersonaConversationResource;
use App\Http\Controllers\Controller;
use App\Models\Entity;
use App\Models\EntityPersona;
use App\Models\PersonaConversation;
use App\Models\PersonaMessage;
use App\Support\Persona\SpeakerEligibility;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Response;

/**
 * "Talk with people": the signed-in user's one conversation per person.
 * Thin: the work is in App\Actions\Persona.
 */
class PersonaConversationController extends Controller
{
    /** GET /api/v1/me/talk — the people I have talked with, most recent first. */
    public function index(Request $request, ListPersonaConversationsAction $list, PersonaDailyUsageAction $usage): JsonResponse
    {
        return response()->json([
            'data' => PersonaConversationResource::collection($list($request->user()))->resolve($request),
            'daily' => $usage($request->user()),
        ]);
    }

    /**
     * GET /api/v1/me/talk/{entity} — the conversation with one person, with
     * its messages. Creates nothing: before the first message it is empty.
     */
    public function show(Request $request, Entity $entity, PersonaDailyUsageAction $usage): JsonResponse
    {
        $entity->loadMissing('primaryTemporalRange');
        $conversation = PersonaConversation::where('user_id', $request->user()->id)
            ->where('entity_id', $entity->entity_id)->first();
        $talkable = SpeakerEligibility::isTalkable($entity);
        if (! $conversation && ! $talkable) {
            throw PersonaException::notTalkable();
        }

        $messages = $conversation
            ? $conversation->messages()->get(['id', 'role', 'content', 'created_at'])->map(fn (PersonaMessage $m) => $this->message($m))->all()
            : [];

        return response()->json(['data' => [
            'entity' => PersonaConversationResource::speaker($entity),
            'talkable' => $talkable,
            'knowledge_year' => EntityPersona::where('entity_id', $entity->entity_id)->value('knowledge_year')
                ?? SpeakerEligibility::deathYear($entity),
            'messages' => $messages,
            'daily' => $usage($request->user()),
        ]]);
    }

    /** POST /api/v1/me/talk/{entity}/messages — send a message, get the reply. */
    public function send(
        SendPersonaMessageRequest $request,
        Entity $entity,
        SendPersonaMessageAction $send,
        PersonaDailyUsageAction $usage,
    ): JsonResponse {
        $result = $send($request->user(), $entity, $request->validated('message'));

        return response()->json(['data' => [
            'user_message' => $this->message($result['user']),
            'assistant_message' => $this->message($result['assistant']),
            'daily' => $usage($request->user()),
        ]], 201);
    }

    /** DELETE /api/v1/me/talk/{entity} — forget the conversation. */
    public function destroy(Request $request, Entity $entity, ClearPersonaConversationAction $clear): Response
    {
        $clear($request->user(), $entity);

        return response()->noContent();
    }

    /** @return array<string, mixed> */
    private function message(PersonaMessage $m): array
    {
        return [
            'id' => $m->id,
            'role' => $m->role,
            'content' => $m->content,
            'created_at' => $m->created_at?->toISOString(),
        ];
    }
}
