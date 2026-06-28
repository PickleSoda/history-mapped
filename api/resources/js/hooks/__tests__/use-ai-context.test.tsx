// @vitest-environment jsdom
import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';

import { useAiContext } from '@/hooks/use-ai-context';

// ── Mock @inertiajs/react ─────────────────────────────────────────────────────

const mockUsePage = vi.fn();

vi.mock('@inertiajs/react', () => ({
    usePage: () => mockUsePage(),
}));

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('useAiContext', () => {
    it('returns null when ai_context prop is not present', () => {
        mockUsePage.mockReturnValue({ props: {} });

        const { result } = renderHook(() => useAiContext());

        expect(result.current).toBeNull();
    });

    it('returns null when ai_context prop is undefined', () => {
        mockUsePage.mockReturnValue({ props: { ai_context: undefined } });

        const { result } = renderHook(() => useAiContext());

        expect(result.current).toBeNull();
    });

    it('returns entity context when ai_context has entity type', () => {
        mockUsePage.mockReturnValue({
            props: { ai_context: { type: 'entity', id: '42' } },
        });

        const { result } = renderHook(() => useAiContext());

        expect(result.current).toEqual({
            type: 'entity',
            id: '42',
            mode: 'edit',
        });
    });

    it('returns chronicle context when ai_context has chronicle type', () => {
        mockUsePage.mockReturnValue({
            props: {
                ai_context: { type: 'chronicle', id: 'chronicle-7' },
            },
        });

        const { result } = renderHook(() => useAiContext());

        expect(result.current).toEqual({
            type: 'chronicle',
            id: 'chronicle-7',
            mode: 'edit',
        });
    });

    it('returns null for an unknown type', () => {
        mockUsePage.mockReturnValue({
            props: { ai_context: { type: 'user', id: '1' } },
        });

        const { result } = renderHook(() => useAiContext());

        expect(result.current).toBeNull();
    });

    it('returns null when id is missing or not a string in edit mode', () => {
        mockUsePage.mockReturnValue({
            props: { ai_context: { type: 'entity', id: 99 } },
        });

        const { result } = renderHook(() => useAiContext());

        expect(result.current).toBeNull();
    });

    it('returns create-mode context with null id when mode is create', () => {
        mockUsePage.mockReturnValue({
            props: { ai_context: { type: 'entity', id: null, mode: 'create' } },
        });

        const { result } = renderHook(() => useAiContext());

        expect(result.current).toEqual({
            type: 'entity',
            id: null,
            mode: 'create',
        });
    });

    it('returns create-mode context for chronicle type with null id', () => {
        mockUsePage.mockReturnValue({
            props: {
                ai_context: { type: 'chronicle', id: null, mode: 'create' },
            },
        });

        const { result } = renderHook(() => useAiContext());

        expect(result.current).toEqual({
            type: 'chronicle',
            id: null,
            mode: 'create',
        });
    });

    it('defaults mode to edit when mode field is absent', () => {
        mockUsePage.mockReturnValue({
            props: { ai_context: { type: 'entity', id: 'abc' } },
        });

        const { result } = renderHook(() => useAiContext());

        expect(result.current?.mode).toBe('edit');
    });

    it('returns null for unknown type even in create mode', () => {
        mockUsePage.mockReturnValue({
            props: { ai_context: { type: 'user', id: null, mode: 'create' } },
        });

        const { result } = renderHook(() => useAiContext());

        expect(result.current).toBeNull();
    });
});
