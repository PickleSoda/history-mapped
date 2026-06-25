<?php

namespace App\Http\Controllers\Admin\Ai;

use App\Ai\ProposalApplier;
use App\Http\Controllers\Controller;
use App\Models\Ai\ProposedChangePart;
use App\Models\Chronicle;
use App\Models\Entity;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\Auth;

class AiProposalController extends Controller
{
    /**
     * Apply a single proposed-change part.
     *
     * The acting user must own the parent ProposedChange (user_id check).
     * Permission gate (entities.write) is applied at the route level.
     */
    public function apply(ProposalApplier $applier, string $change, string $key): JsonResponse
    {
        $part = ProposedChangePart::where('change_id', $change)
            ->where('key', $key)
            ->firstOrFail();

        abort_unless((string) $part->change->user_id === (string) Auth::id(), 403, 'You may only apply your own proposals.');

        $applied = $applier->applyPart($part);

        $isGlobalSession = $part->change->context_type === 'global';

        // For global sessions: no redirect. Return a created_ref link so the chat
        // panel can render the new record as an inline link without navigating away.
        // For scoped sessions (entity/chronicle/create): keep existing redirect_url behavior.
        $redirectUrl = null;
        $createdRef = null;

        if ($isGlobalSession && in_array($applied->tool, ['create_entity', 'create_chronicle'], true)) {
            if ($applied->tool === 'create_entity') {
                $entity = Entity::find($applied->result_id);
                $createdRef = $entity ? [
                    'type' => 'entity',
                    'id' => $applied->result_id,
                    'url' => route('entities.edit', $applied->result_id),
                    'label' => $entity->name,
                ] : null;
            } elseif ($applied->tool === 'create_chronicle') {
                $chronicle = Chronicle::find($applied->result_id);
                $createdRef = $chronicle ? [
                    'type' => 'chronicle',
                    'id' => $applied->result_id,
                    'url' => route('chronicles.edit', $chronicle->slug),
                    'label' => $chronicle->title,
                ] : null;
            }
        } elseif (! $isGlobalSession) {
            $redirectUrl = match ($applied->tool) {
                'create_entity' => route('entities.edit', $applied->result_id),
                'create_chronicle' => route('chronicles.edit', Chronicle::findOrFail($applied->result_id)->slug),
                default => null,
            };
        }

        return response()->json([
            'status' => $applied->status,
            'result_id' => $applied->result_id,
            'redirect_url' => $redirectUrl,
            'created_ref' => $createdRef,
        ]);
    }

    /**
     * Discard a single proposed-change part.
     *
     * The acting user must own the parent ProposedChange.
     */
    public function discard(string $change, string $key): JsonResponse
    {
        $part = ProposedChangePart::where('change_id', $change)
            ->where('key', $key)
            ->firstOrFail();

        abort_unless((string) $part->change->user_id === (string) Auth::id(), 403, 'You may only discard your own proposals.');

        $part->markDiscarded();

        return response()->json(['status' => 'discarded']);
    }
}
