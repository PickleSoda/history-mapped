<?php

namespace App\Http\Controllers\Admin\Ai;

use App\Http\Controllers\Controller;
use App\Models\Ai\ProposedChange;
use App\Models\Chronicle;
use App\Models\Entity;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Laravel\Ai\Models\Conversation;
use Laravel\Ai\Models\ConversationMessage;

class AiSessionController extends Controller
{
    /**
     * List the current user's sessions, newest first.
     * Optional ?context_type=&context_id= narrows to one bound record.
     */
    public function index(Request $request): JsonResponse
    {
        $data = $request->validate([
            'context_type' => 'nullable|in:entity,chronicle,global',
            'context_id' => 'nullable|string',
        ]);

        $query = Conversation::query()
            ->where('user_id', $request->user()->id)
            ->orderByDesc('updated_at');

        if (! empty($data['context_type'])) {
            $query->where('context_type', $data['context_type']);
        }

        if (! empty($data['context_id'])) {
            $query->where('context_id', $data['context_id']);
        }

        $sessions = $query->get()->map(fn (Conversation $c) => [
            'id' => $c->id,
            'kind' => $c->context_type,
            'context_id' => $c->context_id,
            'context_label' => $this->contextLabel($c->context_type, $c->context_id),
            'title' => $c->title,
            'updated_at' => optional($c->updated_at)->toIso8601String(),
        ])->all();

        return response()->json(['data' => $sessions]);
    }

    /**
     * Return replay payload: session, ordered messages, and staged proposals.
     */
    public function show(Request $request, string $conversation): JsonResponse
    {
        $session = Conversation::find($conversation);

        if ($session === null) {
            abort(404);
        }

        if ((string) $session->user_id !== (string) $request->user()->id) {
            abort(403);
        }

        $messages = ConversationMessage::query()
            ->where('conversation_id', $session->id)
            ->orderBy('created_at')
            ->get()
            ->map(fn (ConversationMessage $m) => [
                'id' => $m->id,
                'role' => $m->role,
                'content' => $m->content,
                'tool_calls' => $m->tool_calls,     // array (model cast)
                'tool_results' => $m->tool_results, // array (model cast)
                'created_at' => optional($m->created_at)->toIso8601String(),
            ])->all();

        $proposals = ProposedChange::with('parts')
            ->where('conversation_id', $session->id)
            ->get()
            ->map(fn (ProposedChange $change) => [
                'proposal_id' => $change->id,
                'parts' => $change->parts->map(fn ($p) => [
                    'key' => $p->key,
                    'tool' => $p->tool,
                    'human_diff' => $p->human_diff,
                    'status' => $p->status,
                    'result_id' => $p->result_id,
                ])->all(),
            ])->all();

        return response()->json([
            'session' => [
                'id' => $session->id,
                'kind' => $session->context_type,
                'context_id' => $session->context_id,
                'context_label' => $this->contextLabel($session->context_type, $session->context_id),
                'title' => $session->title,
            ],
            'messages' => $messages,
            'proposals' => $proposals,
        ]);
    }

    /**
     * Human label for a session's bound context (e.g. "Entity: Rome").
     */
    public function contextLabel(?string $type, ?string $id): string
    {
        if ($type === 'global') {
            return 'Global';
        }

        if ($id === null || $id === 'create') {
            return $type === 'chronicle' ? 'New chronicle' : 'New entity';
        }

        if ($type === 'entity') {
            return 'Entity: '.(Entity::find($id)?->name ?? $id);
        }

        if ($type === 'chronicle') {
            return 'Chronicle: '.(Chronicle::find($id)?->title ?? $id);
        }

        return $id;
    }
}
