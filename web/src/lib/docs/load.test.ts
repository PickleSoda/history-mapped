import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import Markdown from 'react-markdown';
import rehypeSlug from 'rehype-slug';
import remarkGfm from 'remark-gfm';
import { describe, expect, it } from 'vitest';
import { DOC_PAGES } from '@/content/docs/manifest';
import { tocFromMarkdown } from './docs';
import { bundledDocPaths, loadDoc } from './load';

// `web` has no @types/node, so node:fs comes in untyped through a variable
// specifier and gets this minimal signature.
const FS_MODULE = 'node:fs';
const fs = (await import(/* @vite-ignore */ FS_MODULE)) as {
  existsSync(path: URL): boolean;
  readFileSync(path: URL, encoding: 'utf8'): string;
};
// The base goes through a variable: Vite rewrites `new URL(…, import.meta.url)` as an asset import.
const HERE = import.meta.url;
const repoFile = (path: string) => new URL(`../../../../${path}`, HERE);

describe('published doc sources', () => {
  it('exist on disk for every manifest entry', () => {
    const missing = DOC_PAGES.filter((page) => !fs.existsSync(repoFile(page.path))).map((page) => page.path);
    expect(missing).toEqual([]);
  });

  it('are bundled for exactly the manifest paths', () => {
    expect([...bundledDocPaths()].sort()).toEqual(DOC_PAGES.map((page) => page.path).sort());
  });

  it('load by slug with the file contents, title and toc', async () => {
    const doc = await loadDoc('tags');
    expect(doc?.entry.path).toBe('docs/architecture/tags.md');
    expect(doc?.markdown).toBe(fs.readFileSync(repoFile('docs/architecture/tags.md'), 'utf8'));
    expect(doc?.title).toBe('Tags: finding chronicles and entities');
    expect(doc?.toc.length).toBeGreaterThan(0);
  });

  it('load the index at the default slug and nothing for an unknown one', async () => {
    expect((await loadDoc('index'))?.entry.path).toBe('docs/README.md');
    expect(await loadDoc('no-such-page')).toBeNull();
  });
});

/** H2 / H3 as the real renderer (react-markdown + GFM + rehype-slug) outputs them. */
function renderedHeadings(markdown: string) {
  const html = renderToStaticMarkup(
    createElement(Markdown, { remarkPlugins: [remarkGfm], rehypePlugins: [rehypeSlug] }, markdown),
  );
  const container = document.createElement('div');
  container.innerHTML = html;
  return [...container.querySelectorAll('h2, h3')].map((el) => ({
    id: el.id,
    text: el.textContent?.trim(),
    depth: Number(el.tagName[1]),
  }));
}

describe('table of contents matches the rendered headings', () => {
  it.each(DOC_PAGES.map((page) => [page.slug, page.path]))('%s', (_slug, path) => {
    const markdown = fs.readFileSync(repoFile(path), 'utf8');
    expect(tocFromMarkdown(markdown)).toEqual(renderedHeadings(markdown));
  });

  it('for inline markup, escapes, duplicates and fences', () => {
    const markdown = [
      '# Notes',
      '## Notes',
      '### The `web/` app ##',
      '## [Tags](tags.md) and **bold**, *em*, ~~struck~~',
      '## entity_type and __strong__ and _em_',
      '## `**literal**` \\*escaped\\* Fish &amp; chips',
      '```bash',
      '## not a heading',
      '```',
      '1. step',
      '   ```sh',
      '   ## nor this',
      '   ```',
      '## Notes',
    ].join('\n');
    expect(tocFromMarkdown(markdown)).toEqual(renderedHeadings(markdown));
  });
});
