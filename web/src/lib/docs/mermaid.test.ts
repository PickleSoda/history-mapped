import mermaid from 'mermaid';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderMermaid } from './mermaid';

vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn(async () => ({ svg: '<svg></svg>' })),
  },
}));

/** The config passed to the last mermaid.initialize call. */
function lastConfig() {
  return vi.mocked(mermaid.initialize).mock.lastCall?.[0];
}

describe('renderMermaid', () => {
  beforeEach(() => {
    vi.mocked(mermaid.initialize).mockClear();
  });

  it('returns the rendered SVG', async () => {
    await expect(renderMermaid('flowchart TB\n  A --> B', 'light')).resolves.toBe('<svg></svg>');
  });

  // The base theme derives its other colours (ER table rows, note text, the
  // mindmap and timeline scale) from themeVariables.darkMode. With only the
  // top-level flag, dark pages got near-white ER rows under light text.
  it('derives the dark palette from themeVariables.darkMode', async () => {
    await renderMermaid('erDiagram\n  a ||--o{ b : has', 'dark');
    const themeVariables = lastConfig()?.themeVariables;
    expect(themeVariables?.darkMode).toBe(true);
    expect(themeVariables?.noteTextColor).toBe('#faf9f6');
    expect(themeVariables?.cScale0).toBe('#c0b496');
  });

  it('keeps the light palette light', async () => {
    await renderMermaid('erDiagram\n  a ||--o{ b : has', 'light');
    expect(lastConfig()?.themeVariables?.darkMode).toBe(false);
  });
});
