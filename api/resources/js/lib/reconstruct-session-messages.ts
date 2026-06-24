import type { UIMessage } from 'ai';
import { parseProposal } from '@/components/ai/proposal-card';

export type SessionMessage = {
    id: string;
    role: string;
    content: string | null;
    tool_results?: Array<{ id: string; result: unknown }> | unknown;
    created_at: string | null;
};

export type SessionProposal = {
    proposal_id: string;
    parts: Array<{
        key: string;
        tool: string;
        human_diff: { summary: string };
        status?: 'pending' | 'applied' | 'discarded';
        result_id?: string | null;
    }>;
};

export type SessionShowPayload = {
    messages: SessionMessage[];
    proposals: SessionProposal[];
};

type ProposalStatus = 'pending' | 'applied' | 'discarded';

/**
 * Reconstruct a session's stored messages into the UIMessage[] shape the chat
 * panel renders. Assistant tool results are parsed back into Proposal objects
 * (via parseProposal) and surfaced as `dynamic-tool` output-available parts, with
 * each proposal's per-part status merged from the `proposals[]` audit list so the
 * replayed ProposalCards render applied/discarded locked and pending actionable.
 */
export function reconstructSessionMessages(payload: SessionShowPayload): UIMessage[] {
    // Build lookup: proposal_id -> (part key -> {status, result_id})
    const statusByProposal = new Map<string, Map<string, { status?: ProposalStatus; result_id?: string | null }>>();

    for (const p of payload.proposals ?? []) {
        const byKey = new Map<string, { status?: ProposalStatus; result_id?: string | null }>();

        for (const part of p.parts) {
            byKey.set(part.key, { status: part.status as ProposalStatus | undefined, result_id: part.result_id });
        }

        statusByProposal.set(p.proposal_id, byKey);
    }

    return (payload.messages ?? []).map((msg, i): UIMessage => {
        const parts: UIMessage['parts'] = [];

        if (msg.content) {
            parts.push({ type: 'text', text: msg.content } as UIMessage['parts'][number]);
        }

        const toolResults = Array.isArray(msg.tool_results) ? msg.tool_results : [];
        (toolResults as Array<{ id?: string; result?: unknown }>).forEach((tr, j) => {
            const proposal = parseProposal(tr.result);

            if (!proposal) {
                return;
            }

            const byKey = statusByProposal.get(proposal.proposal_id);

            if (byKey) {
                proposal.parts = proposal.parts.map((pt) => {
                    const stored = byKey.get(pt.key);

                    return stored ? { ...pt, status: stored.status, result_id: stored.result_id } : pt;
                });
            }

            parts.push({
                type: 'dynamic-tool',
                toolName: 'proposal',
                toolCallId: tr.id ?? `tr-${i}-${j}`,
                state: 'output-available',
                output: proposal,
            } as UIMessage['parts'][number]);
        });

        return {
            id: msg.id,
            role: msg.role === 'user' ? 'user' : 'assistant',
            parts,
        };
    });
}
