import { renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { documentTitle, metaDescription, useDocumentMeta } from './document-meta';

const description = () =>
  document.head.querySelector<HTMLMetaElement>('meta[name="description"]')?.getAttribute('content') ?? null;

afterEach(() => {
  document.title = '';
  document.head.querySelectorAll('meta[name="description"]').forEach((m) => m.remove());
});

describe('documentTitle', () => {
  it('suffixes the site name', () => {
    expect(documentTitle('Battle of Cannae')).toBe('Battle of Cannae · History Mapped');
    expect(documentTitle('  ')).toBe('History Mapped');
    expect(documentTitle(null)).toBe('History Mapped');
  });
});

describe('metaDescription', () => {
  it('keeps short text and flattens whitespace', () => {
    expect(metaDescription('A  battle\nin 216 BC.')).toBe('A battle in 216 BC.');
  });

  it('cuts long text on a word boundary', () => {
    const out = metaDescription('word '.repeat(60), 40);
    expect(out.length).toBeLessThanOrEqual(40);
    expect(out.endsWith('word…')).toBe(true);
  });
});

describe('useDocumentMeta', () => {
  it('sets the title and description, then restores them', () => {
    document.title = 'History Mapped';
    const { unmount } = renderHook(() =>
      useDocumentMeta({ title: 'Battle of Cannae', description: 'Hannibal encircles a Roman army.' }),
    );
    expect(document.title).toBe('Battle of Cannae · History Mapped');
    expect(description()).toBe('Hannibal encircles a Roman army.');
    unmount();
    expect(document.title).toBe('History Mapped');
    expect(description()).toBeNull();
  });

  it('restores an existing description tag instead of removing it', () => {
    const tag = document.createElement('meta');
    tag.name = 'description';
    tag.content = 'An interactive historical atlas';
    document.head.appendChild(tag);
    const { rerender, unmount } = renderHook((p: { d: string }) => useDocumentMeta({ title: 'X', description: p.d }), {
      initialProps: { d: 'first' },
    });
    expect(description()).toBe('first');
    rerender({ d: 'second' });
    expect(description()).toBe('second');
    unmount();
    expect(description()).toBe('An interactive historical atlas');
  });

  it('leaves the description alone when none is given', () => {
    renderHook(() => useDocumentMeta({ title: 'Browse' }));
    expect(description()).toBeNull();
  });
});
