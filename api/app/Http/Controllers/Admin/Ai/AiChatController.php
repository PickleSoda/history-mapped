<?php

namespace App\Http\Controllers\Admin\Ai;

use App\Ai\Agents\EntityEditorAgent;
use App\Http\Controllers\Controller;
use App\Models\Entity;
use Illuminate\Http\Request;
use Laravel\Ai\Responses\StreamableAgentResponse;

class AiChatController extends Controller
{
    /**
     * Handle an AI chat request and stream the response using the Vercel data protocol.
     *
     * Supports context_type=entity (EntityEditorAgent).
     * Chronicle agent (Task 9) is not yet available.
     *
     * Conversation resumption: when a conversation_id is supplied the agent uses
     * RemembersConversations::continue() to load prior messages from the conversation
     * store. New conversations are started with forUser() so the store can persist them.
     */
    public function chat(Request $request): StreamableAgentResponse
    {
        $data = $request->validate([
            'context_type' => 'required|in:entity,chronicle',
            'context_id' => 'required|string',
            'prompt' => 'required|string',
            'conversation_id' => 'nullable|string',
        ]);

        $user = $request->user();
        $conversationId = $data['conversation_id'] ?? null;

        $context = [
            'user_id' => (string) $user->id,
            'context_type' => $data['context_type'],
            'context_id' => $data['context_id'],
            'conversation_id' => $conversationId,
        ];

        $agent = match ($data['context_type']) {
            'entity' => new EntityEditorAgent(
                Entity::findOrFail($data['context_id']),
                $user,
                $context,
            ),
            // Chronicle agent will be wired in Task 9.
            'chronicle' => abort(422, 'Chronicle agent not yet available'),
        };

        // Wire conversation persistence via RemembersConversations.
        if ($conversationId !== null) {
            $agent->continue($conversationId, $user);
        } else {
            $agent->forUser($user);
        }

        return $agent->stream($data['prompt'])->usingVercelDataProtocol();
    }
}
