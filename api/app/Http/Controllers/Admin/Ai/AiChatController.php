<?php

namespace App\Http\Controllers\Admin\Ai;

use App\Ai\Agents\ChronicleCreatorAgent;
use App\Ai\Agents\ChronicleEditorAgent;
use App\Ai\Agents\EntityCreatorAgent;
use App\Ai\Agents\EntityEditorAgent;
use App\Http\Controllers\Controller;
use App\Models\Chronicle;
use App\Models\Entity;
use Illuminate\Http\Request;
use Illuminate\Support\Str;
use Laravel\Ai\Models\Conversation;
use Symfony\Component\HttpFoundation\Response;

class AiChatController extends Controller
{
    /**
     * Handle an AI chat request and stream the response using the Vercel data protocol.
     *
     * In edit mode (the default) it routes context_type=entity to EntityEditorAgent
     * and context_type=chronicle to ChronicleEditorAgent, binding to the record at
     * context_id. In create mode (mode=create) it routes to EntityCreatorAgent /
     * ChronicleCreatorAgent with no bound record, staging proposals under the
     * sentinel context_id='create'.
     *
     * Conversation resumption: when a conversation_id is supplied the agent uses
     * RemembersConversations::continue() to load prior messages from the conversation
     * store. For a new session, a UUID is minted and the bound record is resolved
     * (findOrFail) before the session row is created, so an invalid context_id aborts
     * with 404 without leaving a phantom row. The new conversation id is returned in
     * the X-Conversation-Id response header, and the agent always continues via
     * continue() so the SDK persists messages under the pre-created id.
     */
    public function chat(Request $request): Response
    {
        $data = $request->validate([
            'context_type' => 'required|in:entity,chronicle',
            'context_id' => 'nullable|string',
            'mode' => 'nullable|in:edit,create',
            // v3 @ai-sdk/react sends `messages` array; legacy/test callers may send `prompt`.
            'prompt' => 'nullable|string',
            'messages' => 'nullable|array',
            'conversation_id' => 'nullable|string',
        ]);

        // Derive the prompt text from either the legacy `prompt` field or the
        // v3 UIMessage array (take the last user message and join its text parts).
        $promptText = null;

        if (! empty($data['prompt'])) {
            $promptText = $data['prompt'];
        } elseif (! empty($data['messages'])) {
            $userMessages = array_filter(
                $data['messages'],
                fn ($m) => isset($m['role']) && $m['role'] === 'user',
            );

            $lastUser = end($userMessages);

            if ($lastUser !== false) {
                // v3 UIMessage: parts: [{type:'text', text:'...'}]
                if (! empty($lastUser['parts']) && is_array($lastUser['parts'])) {
                    $textParts = array_filter(
                        $lastUser['parts'],
                        fn ($p) => isset($p['type']) && $p['type'] === 'text',
                    );
                    $texts = array_map(fn ($p) => $p['text'] ?? '', $textParts);
                    $promptText = implode('', $texts);
                }

                // Fallback: plain `content` string (some SDK versions)
                if (empty($promptText) && isset($lastUser['content']) && is_string($lastUser['content'])) {
                    $promptText = $lastUser['content'];
                }
            }
        }

        if (empty($promptText)) {
            abort(422, 'Could not extract a user message from the request. Provide `prompt` or a non-empty `messages` array with at least one user message containing text parts.');
        }

        $user = $request->user();
        $conversationId = $data['conversation_id'] ?? null;
        $mode = $data['mode'] ?? 'edit';

        if ($mode === 'edit' && empty($data['context_id'])) {
            abort(422, 'context_id is required in edit mode.');
        }

        $contextId = $mode === 'create' ? 'create' : $data['context_id'];

        // Resolve the session (agent_conversations row). Either continue one the
        // user owns, or mint a UUID for a new session. For new sessions we resolve
        // the bound record BEFORE creating the row so an invalid context_id aborts
        // with 404 without leaving a phantom session in the store.
        $isNewSession = false;

        if ($conversationId !== null) {
            $conversation = Conversation::find($conversationId);

            if ($conversation === null) {
                abort(404, 'Unknown conversation.');
            }

            if ((string) $conversation->user_id !== (string) $user->id) {
                abort(403, 'You do not own this conversation.');
            }
        } else {
            $conversationId = (string) Str::uuid7();
            $isNewSession = true;
        }

        $context = [
            'user_id' => (string) $user->id,
            'context_type' => $data['context_type'],
            'context_id' => $contextId,
            'conversation_id' => $conversationId,
        ];

        // Build the agent (and resolve the bound record via findOrFail). This may
        // abort with 404 before we create any row — intentional for the new-session
        // path so bad context_id values leave no phantom rows behind.
        // Guard: PostgreSQL UUID columns reject non-UUID strings at the driver level
        // (PDOException) before Eloquent can convert that to a ModelNotFoundException.
        // Pre-check the format so we always get a clean 404 for unresolvable ids.
        if ($mode === 'edit' && ! Str::isUuid($contextId)) {
            abort(404, 'Record not found.');
        }

        $agent = match (true) {
            $mode === 'create' && $data['context_type'] === 'entity' => new EntityCreatorAgent($user, $context),
            $mode === 'create' && $data['context_type'] === 'chronicle' => new ChronicleCreatorAgent($user, $context),
            $data['context_type'] === 'entity' => new EntityEditorAgent(Entity::findOrFail($contextId), $user, $context),
            $data['context_type'] === 'chronicle' => new ChronicleEditorAgent(Chronicle::findOrFail($contextId), $user, $context),
        };

        // Now that the bound record is confirmed valid, create the session row for
        // new sessions so proposals and message persistence are tied to a real,
        // listable session from the first message.
        if ($isNewSession) {
            Conversation::create([
                'id' => $conversationId,
                'user_id' => $user->id,
                'title' => Str::limit($promptText, 60, ''),
                'context_type' => $data['context_type'],
                'context_id' => $contextId,
            ]);
        }

        // continue() makes the SDK persist messages under our pre-created id
        // instead of generating its own.
        $agent->continue($conversationId, $user);

        $response = $agent->stream($promptText)->usingVercelDataProtocol()->toResponse($request);
        $response->headers->set('X-Conversation-Id', $conversationId);

        return $response;
    }
}
