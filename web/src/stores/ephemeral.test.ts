import { describe, it, expect, afterEach } from 'vitest';
import { useEphemeralStore } from './ephemeral';

afterEach(() => useEphemeralStore.getState().setTimelineExpanded(false));

describe('timelineExpanded slice', () => {
  it('defaults to false', () => {
    expect(useEphemeralStore.getState().timelineExpanded).toBe(false);
  });
  it('is updated by setTimelineExpanded', () => {
    useEphemeralStore.getState().setTimelineExpanded(true);
    expect(useEphemeralStore.getState().timelineExpanded).toBe(true);
  });
});
