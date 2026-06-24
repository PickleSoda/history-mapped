<?php

namespace App\Http\Controllers\Admin\Ai;

use App\Http\Controllers\Controller;
use App\Models\Chronicle;
use App\Models\Entity;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Laravel\Ai\Models\Conversation;

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
