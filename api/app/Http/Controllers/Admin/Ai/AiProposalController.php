<?php

namespace App\Http\Controllers\Admin\Ai;

use App\Ai\ProposalApplier;
use App\Http\Controllers\Controller;
use App\Models\Ai\ProposedChangePart;
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

        return response()->json([
            'status' => $applied->status,
            'result_id' => $applied->result_id,
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
