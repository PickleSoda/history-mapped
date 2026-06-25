// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { reconstructSessionMessages } from '../reconstruct-session-messages';

describe('reconstructSessionMessages', () => {
    it('builds text + proposal parts and merges per-part status', () => {
        const proposalJson = JSON.stringify({
            proposal_id: 'prop-1',
            parts: [{ key: 'entity', tool: 'create_entity', human_diff: { summary: 'Create Rome' } }],
        });

        const messages = reconstructSessionMessages({
            messages: [
                { id: 'm1', role: 'user', content: 'make rome', tool_results: [], created_at: null },
                {
                    id: 'm2', role: 'assistant', content: 'Proposing.',
                    tool_results: [{ id: 'call-1', result: proposalJson }],
                    created_at: null,
                },
            ],
            proposals: [
                { proposal_id: 'prop-1', parts: [{ key: 'entity', tool: 'create_entity', human_diff: { summary: 'Create Rome' }, status: 'applied', result_id: 'e-9' }] },
            ],
        });

        // user message
        expect(messages[0]).toMatchObject({ id: 'm1', role: 'user' });
        expect(messages[0].parts[0]).toMatchObject({ type: 'text', text: 'make rome' });

        // assistant message: text + proposal part
        expect(messages[1]).toMatchObject({ id: 'm2', role: 'assistant' });
        const parts = messages[1].parts;
        expect(parts[0]).toMatchObject({ type: 'text', text: 'Proposing.' });
        const toolPart = parts[1] as { type: string; state: string; output: { proposal_id: string; parts: Array<{ key: string; status?: string }> } };
        expect(toolPart.type).toBe('dynamic-tool');
        expect(toolPart.state).toBe('output-available');
        expect(toolPart.output.proposal_id).toBe('prop-1');
        // status merged from proposals[]
        expect(toolPart.output.parts[0].status).toBe('applied');
    });

    it('omits the text part when assistant content is empty and handles no tool_results', () => {
        const messages = reconstructSessionMessages({
            messages: [{ id: 'm1', role: 'assistant', content: '', tool_results: [], created_at: null }],
            proposals: [],
        });
        expect(messages[0].parts).toHaveLength(0);
    });
});
