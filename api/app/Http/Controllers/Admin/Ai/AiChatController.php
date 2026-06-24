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
use Laravel\Ai\Responses\StreamableAgentResponse;

class AiChatController extends Controller
{
    /**
     * Handle an AI chat request and stream the response using the Vercel data protocol.
     *
     * Supports context_type=entity (EntityEditorAgent) and
     * context_type=chronicle (ChronicleEditorAgent).
     *
     * Conversation resumption: when a conversation_id is supplied the agent uses
     * RemembersConversations::continue() to load prior messages from the conversation
     * store. New conversations are started with forUser() so the store can persist them.
     */
    public function chat(Request $request): StreamableAgentResponse
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

        $context = [
            'user_id' => (string) $user->id,
            'context_type' => $data['context_type'],
            'context_id' => $contextId,
            'conversation_id' => $conversationId,
        ];

        $agent = match (true) {
            $mode === 'create' && $data['context_type'] === 'entity' => new EntityCreatorAgent($user, $context),
            $mode === 'create' && $data['context_type'] === 'chronicle' => new ChronicleCreatorAgent($user, $context),
            $data['context_type'] === 'entity' => new EntityEditorAgent(Entity::findOrFail($contextId), $user, $context),
            $data['context_type'] === 'chronicle' => new ChronicleEditorAgent(Chronicle::findOrFail($contextId), $user, $context),
        };

        // Wire conversation persistence via RemembersConversations.
        if ($conversationId !== null) {
            $agent->continue($conversationId, $user);
        } else {
            $agent->forUser($user);
        }

        return $agent->stream($promptText)->usingVercelDataProtocol();
    }
}
