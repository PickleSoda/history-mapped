import { describe, expect, it } from 'vitest';
import { DOC_PAGES, DOCS_INDEX_SLUG } from '@/content/docs/manifest';
import {
  docNeighbours,
  docPath,
  docSections,
  docTitle,
  findDoc,
  githubEditUrl,
  headingText,
  resolveRepoPath,
  rewriteDocImage,
  rewriteDocLink,
  tocFromMarkdown,
} from './docs';
import { formatDocumentTitle } from './document-meta';

const BLOB = 'https://github.com/PickleSoda/history-mapped/blob/main/';
const TREE = 'https://github.com/PickleSoda/history-mapped/tree/main/';

describe('docs manifest', () => {
  it('has unique slugs and unique paths', () => {
    const slugs = DOC_PAGES.map((page) => page.slug);
    const paths = DOC_PAGES.map((page) => page.path);
    expect(new Set(slugs).size).toBe(slugs.length);
    expect(new Set(paths).size).toBe(paths.length);
  });

  it('uses URL-safe slugs and repo-relative markdown paths under docs/', () => {
    for (const page of DOC_PAGES) {
      expect(page.slug).toMatch(/^[a-z0-9]+(?:-[a-z0-9]+)*$/);
      expect(page.path).toMatch(/^docs\/[\w./-]+\.md$/);
      expect(page.title.length).toBeGreaterThan(0);
      expect(page.description.length).toBeGreaterThan(20);
    }
  });

  it('serves docs/README.md as the index page', () => {
    expect(findDoc(undefined)?.path).toBe('docs/README.md');
    expect(findDoc(DOCS_INDEX_SLUG)?.path).toBe('docs/README.md');
  });

  it('never publishes runbooks, plans or the archive', () => {
    for (const page of DOC_PAGES) {
      expect(page.path).not.toMatch(/runbook|\/plans\/|\/archive\/|\/superpowers\/|\/reference\//);
    }
  });
});

describe('manifest lookups', () => {
  it('builds site paths, with the index at /docs', () => {
    expect(docPath(DOCS_INDEX_SLUG)).toBe('/docs');
    expect(docPath('tags')).toBe('/docs/tags');
  });

  it('returns undefined for unknown slugs', () => {
    expect(findDoc('no-such-page')).toBeUndefined();
  });

  it('groups pages by section in manifest order and drops empty sections', () => {
    const groups = docSections();
    expect(groups.map((group) => group.section.id)).toEqual(['overview', 'architecture', 'data-model', 'guides']);
    expect(groups.flatMap((group) => group.pages)).toHaveLength(DOC_PAGES.length);
  });

  it('links previous and next pages across sections', () => {
    expect(docNeighbours(DOCS_INDEX_SLUG)).toEqual({ prev: undefined, next: findDoc('system-overview') });
    expect(docNeighbours('frontend-app').prev?.slug).toBe('system-overview');
    expect(docNeighbours('map-story-authoring').next).toBeUndefined();
    expect(docNeighbours('no-such-page')).toEqual({});
  });

  it('points Edit on GitHub at the source file', () => {
    expect(githubEditUrl('docs/architecture/tags.md')).toBe(
      'https://github.com/PickleSoda/history-mapped/edit/main/docs/architecture/tags.md',
    );
  });
});

describe('resolveRepoPath', () => {
  it('resolves against the directory of the source file', () => {
    expect(resolveRepoPath('docs/README.md', 'architecture/tags.md')).toBe('docs/architecture/tags.md');
    expect(resolveRepoPath('docs/architecture/tags.md', './entity-images.md')).toBe('docs/architecture/entity-images.md');
    expect(resolveRepoPath('docs/architecture/tags.md', '../../api/app/Models/Entity.php')).toBe(
      'api/app/Models/Entity.php',
    );
  });

  it('keeps a trailing slash and refuses to climb above the repo root', () => {
    expect(resolveRepoPath('docs/README.md', 'archive/')).toBe('docs/archive/');
    expect(resolveRepoPath('docs/README.md', '../../outside.md')).toBeNull();
  });
});

describe('rewriteDocLink', () => {
  it('sends links to published docs to their /docs page, keeping the anchor', () => {
    expect(rewriteDocLink('architecture/tags.md', 'docs/README.md')).toBe('/docs/tags');
    expect(rewriteDocLink('architecture/tags.md#storage', 'docs/README.md')).toBe('/docs/tags#storage');
    expect(rewriteDocLink('./entity-images.md', 'docs/architecture/tags.md')).toBe('/docs/entity-images');
    expect(rewriteDocLink('../README.md#folder-guide', 'docs/architecture/tags.md')).toBe('/docs#folder-guide');
    expect(rewriteDocLink('tags.md?plain=1#facets', 'docs/architecture/frontend-app.md')).toBe('/docs/tags#facets');
  });

  it('sends other relative repo links to the file on GitHub', () => {
    expect(rewriteDocLink('plans/STATUS.md', 'docs/README.md')).toBe(`${BLOB}docs/plans/STATUS.md`);
    expect(rewriteDocLink('../README.md', 'docs/README.md')).toBe(`${BLOB}README.md`);
    expect(rewriteDocLink('../pipeline/README.md#usage', 'docs/README.md')).toBe(`${BLOB}pipeline/README.md#usage`);
    expect(rewriteDocLink('README.md', 'docs/architecture/tags.md')).toBe(`${BLOB}docs/architecture/README.md`);
    expect(rewriteDocLink('../superpowers/specs/x-design.md', 'docs/architecture/frontend-app.md')).toBe(
      `${BLOB}docs/superpowers/specs/x-design.md`,
    );
    expect(rewriteDocLink('file%20name.md', 'docs/README.md')).toBe(`${BLOB}docs/file%20name.md`);
  });

  it('links directories to the GitHub tree view', () => {
    expect(rewriteDocLink('archive/', 'docs/README.md')).toBe(`${TREE}docs/archive/`);
  });

  it('leaves absolute links, in-page anchors and unresolvable links alone', () => {
    for (const href of ['https://example.org/a.md', 'mailto:team@example.org', '#storage', '/browse', '//cdn.example.org/x']) {
      expect(rewriteDocLink(href, 'docs/README.md')).toBe(href);
    }
    expect(rewriteDocLink('../../outside.md', 'docs/README.md')).toBe('../../outside.md');
    expect(rewriteDocLink(undefined, 'docs/README.md')).toBeUndefined();
    expect(rewriteDocLink('', 'docs/README.md')).toBe('');
  });

  it('loads relative images from GitHub raw', () => {
    expect(rewriteDocImage('img/map.png', 'docs/architecture/tags.md')).toBe(
      'https://raw.githubusercontent.com/PickleSoda/history-mapped/main/docs/architecture/img/map.png',
    );
    expect(rewriteDocImage('https://example.org/a.png', 'docs/README.md')).toBe('https://example.org/a.png');
  });
});

describe('headings', () => {
  it('reduces inline markdown to the rendered text', () => {
    expect(headingText('The `web/` app')).toBe('The web/ app');
    expect(headingText('[Tags](tags.md) and **bold** and *em*')).toBe('Tags and bold and em');
    expect(headingText('entity_type and __strong__ and _em_')).toBe('entity_type and strong and em');
    expect(headingText('`**not bold**` \\*escaped\\* ~~gone~~')).toBe('**not bold** *escaped* gone');
    expect(headingText('Fish &amp; chips')).toBe('Fish & chips');
  });

  it('takes the title from the first H1', () => {
    expect(docTitle('Intro\n\n# The `web/` app\n\n# Second')).toBe('The web/ app');
    expect(docTitle('## Only an H2')).toBeNull();
  });

  it('lists H2 and H3 with rehype-slug ids, counting every heading for duplicates', () => {
    const markdown = [
      '# Notes',
      '## Notes',
      'text',
      '### The `web/` app ##',
      '#### Deep',
      '## Notes',
      '```bash',
      '# not a heading',
      '## nor this',
      '```',
      '    ## indented code, not a heading',
      '## entity_type values',
    ].join('\n');
    expect(tocFromMarkdown(markdown)).toEqual([
      { id: 'notes-1', text: 'Notes', depth: 2 },
      { id: 'the-web-app', text: 'The web/ app', depth: 3 },
      { id: 'notes-2', text: 'Notes', depth: 2 },
      { id: 'entity_type-values', text: 'entity_type values', depth: 2 },
    ]);
  });

  it('skips tilde fences and fences nested in list items', () => {
    const markdown = ['~~~', '## no', '~~~', '1. step', '   ```sh', '   ## no', '   ```', '## Yes'].join('\n');
    expect(tocFromMarkdown(markdown)).toEqual([{ id: 'yes', text: 'Yes', depth: 2 }]);
  });
});

describe('formatDocumentTitle', () => {
  it('appends the site name', () => {
    expect(formatDocumentTitle('Tags')).toBe('Tags · History Mapped');
    expect(formatDocumentTitle(null)).toBe('History Mapped');
  });
});
