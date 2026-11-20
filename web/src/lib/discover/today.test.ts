// @vitest-environment jsdom
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useToday } from './today';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('useToday', () => {
  it('is the local day, and moves on at each midnight', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 10, 20, 23, 59, 30));
    const { result } = renderHook(() => useToday());
    expect(result.current).toBe('2026-11-20');

    act(() => {
      vi.advanceTimersByTime(31_000);
    });
    expect(result.current).toBe('2026-11-21');

    act(() => {
      vi.advanceTimersByTime(24 * 60 * 60_000);
    });
    expect(result.current).toBe('2026-11-22');
  });

  it('catches up when the tab is looked at again after a night asleep', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 10, 20, 12, 0, 0));
    const { result } = renderHook(() => useToday());

    // The clock moved on without a timer firing.
    vi.setSystemTime(new Date(2026, 10, 21, 8, 0, 0));
    expect(result.current).toBe('2026-11-20');
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'));
    });
    expect(result.current).toBe('2026-11-21');

    vi.setSystemTime(new Date(2026, 10, 22, 8, 0, 0));
    act(() => {
      window.dispatchEvent(new Event('focus'));
    });
    expect(result.current).toBe('2026-11-22');
  });

  it('stops listening when nothing reads it', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 10, 20, 12, 0, 0));
    const { unmount } = renderHook(() => useToday());
    expect(vi.getTimerCount()).toBe(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});
