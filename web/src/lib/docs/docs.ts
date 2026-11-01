/**
 * Pure helpers for the docs pages (spec 2026-11-01 public site, D5): manifest
 * lookups, link rewriting, and title / table-of-contents extraction from the
 * markdown source. No React, no loading: see `load.ts` for that.
 */
import GithubSlugger from 'github-slugger';
import { DOC_PAGES, DOC_SECTIONS, DOCS_INDEX_SLUG } from '@/content/docs/manifest';
import type { DocEntry, DocSection } from '@/content/docs/manifest';

export const GITHUB_REPO_URL = 'https://github.com/PickleSoda/history-mapped';
const GITHUB_BRANCH = 'main';

/* ── Manifest lookups ─────────────────────────────────────────────────────── */

/** The manifest entry for a slug (no slug = the index page). */
export function findDoc(slug: string | undefined): DocEntry | undefined {
  const key = slug ?? DOCS_INDEX_SLUG;
  return DOC_PAGES.find((page) => page.slug === key);
}

/** The manifest entry whose source is `path` (repo-relative). */
export function findDocByPath(path: string): DocEntry | undefined {
  return DOC_PAGES.find((page) => page.path === path);
}

/** Site path of a doc page: `/docs` for the index, `/docs/<slug>` otherwise. */
export function docPath(slug: string): string {
  return slug === DOCS_INDEX_SLUG ? '/docs' : `/docs/${slug}`;
}

/** Sections in order with their pages; sections without pages are left out. */
export function docSections(): { section: DocSection; pages: DocEntry[] }[] {
  return DOC_SECTIONS.map((section) => ({
    section,
    pages: DOC_PAGES.filter((page) => page.section === section.id),
  })).filter((group) => group.pages.length > 0);
}

/** Previous / next page in reading order (sections in order, then pages). */
export function docNeighbours(slug: string): { prev?: DocEntry; next?: DocEntry } {
  const ordered = docSections().flatMap((group) => group.pages);
  const index = ordered.findIndex((page) => page.slug === slug);
  if (index === -1) return {};
  return { prev: ordered[index - 1], next: ordered[index + 1] };
}

/** The file on GitHub (`blob`, or `tree` for a directory path ending in `/`). */
export function githubUrl(path: string, hash = ''): string {
  const kind = path === '' || path.endsWith('/') ? 'tree' : 'blob';
  return `${GITHUB_REPO_URL}/${kind}/${GITHUB_BRANCH}/${path}${hash}`;
}

/** GitHub's editor for a source file ("Edit on GitHub"). */
export function githubEditUrl(path: string): string {
  return `${GITHUB_REPO_URL}/edit/${GITHUB_BRANCH}/${path}`;
}

/** Raw file URL, for images referenced relatively from a doc. */
export function githubRawUrl(path: string): string {
  return `https://raw.githubusercontent.com/PickleSoda/history-mapped/${GITHUB_BRANCH}/${path}`;
}

/* ── Links ────────────────────────────────────────────────────────────────── */

const SCHEME = /^[a-z][a-z\d+.-]*:/i;

/** True for links that leave the docs untouched: schemes, `//host`, `/path`, `#anchor`. */
function isAbsolute(href: string): boolean {
  return SCHEME.test(href) || href.startsWith('/') || href.startsWith('#');
}

/**
 * Resolve `target` against the directory of `fromPath` (both repo-relative,
 * POSIX). Returns null when the result would climb above the repo root.
 * A trailing slash (a directory link) is kept.
 */
export function resolveRepoPath(fromPath: string, target: string): string | null {
  const segments = fromPath.split('/').slice(0, -1);
  const parts = target.split('/');
  for (const [i, part] of parts.entries()) {
    if (part === '' || part === '.') {
      // `a//b` and `./a`: nothing to do. A trailing '' marks a directory.
      if (i === parts.length - 1 && part === '' && parts.length > 1) segments.push('');
      continue;
    }
    if (part === '..') {
      if (segments.length === 0) return null;
      segments.pop();
      continue;
    }
    segments.push(part);
  }
  return segments.join('/');
}

function safeDecode(value: string): string {
  try {
    return decodeURI(value);
  } catch {
    return value;
  }
}

/**
 * Rewrite a link found in the doc at `fromPath` (repo-relative):
 * a relative link to a published doc → `/docs/<slug>` (anchor kept); any other
 * relative link → the file on GitHub; absolute links and `#anchors` untouched.
 */
export function rewriteDocLink(href: string | undefined, fromPath: string): string | undefined {
  if (!href || isAbsolute(href)) return href;
  const hashAt = href.indexOf('#');
  const hash = hashAt === -1 ? '' : href.slice(hashAt);
  const beforeHash = hashAt === -1 ? href : href.slice(0, hashAt);
  const queryAt = beforeHash.indexOf('?');
  const target = queryAt === -1 ? beforeHash : beforeHash.slice(0, queryAt);

  const resolved = resolveRepoPath(fromPath, safeDecode(target));
  if (resolved === null) return href;
  const doc = findDocByPath(resolved);
  if (doc) return `${docPath(doc.slug)}${hash}`;
  return githubUrl(encodeURI(resolved), hash);
}

/** Image sources: relative ones load from GitHub's raw host. */
export function rewriteDocImage(src: string | undefined, fromPath: string): string | undefined {
  if (!src || isAbsolute(src)) return src;
  const resolved = resolveRepoPath(fromPath, safeDecode(src.split(/[?#]/)[0]));
  return resolved === null ? src : githubRawUrl(encodeURI(resolved));
}

/* ── Headings: title and table of contents ────────────────────────────────── */

export interface TocItem {
  /** The heading's `id`, as rehype-slug assigns it. */
  id: string;
  /** Plain heading text. */
  text: string;
  depth: 2 | 3;
}

interface Heading {
  depth: number;
  text: string;
}

const FENCE = /^\s*(`{3,}|~{3,})/;
const ATX = /^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$/;
const ENTITIES: Record<string, string> = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' };

function decodeEntities(text: string): string {
  return text.replace(/&(#x[\da-f]+|#\d+|[a-z]+);/gi, (match, name: string) => {
    if (name[0] === '#') {
      const code = name[1] === 'x' || name[1] === 'X' ? parseInt(name.slice(2), 16) : parseInt(name.slice(1), 10);
      return Number.isFinite(code) ? String.fromCodePoint(code) : match;
    }
    return ENTITIES[name.toLowerCase()] ?? match;
  });
}

/** Inline markdown (outside code spans) → the text it renders. */
function plainInline(text: string): string {
  // Backslash-escaped punctuation is literal: park it so no rule below sees it.
  const escaped: string[] = [];
  const parked = text.replace(/\\([!-/:-@[-`{-~])/g, (_match, char: string) => {
    escaped.push(char);
    return `\uE000${escaped.length - 1}\uE001`;
  });
  const plain = decodeEntities(
    parked
      // Images keep their alt text, links their label (inline and reference).
      .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
      .replace(/!\[([^\]]*)\]\[[^\]]*\]/g, '$1')
      .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
      .replace(/\[([^\]]*)\]\[[^\]]*\]/g, '$1')
      // Autolinks: <https://…> renders the URL.
      .replace(/<((?:https?|mailto):[^>\s]+)>/gi, '$1')
      // Emphasis and strikethrough delimiters. `_` only at word boundaries
      // (intraword underscores are literal in CommonMark).
      .replace(/(\*\*|__)(?=\S)([\s\S]*?\S)\1/g, '$2')
      .replace(/\*(?=\S)([^*]*?\S)\*/g, '$1')
      .replace(/(^|[^\p{L}\p{N}_])_(?=\S)([^_]*?\S)_(?![\p{L}\p{N}_])/gu, '$1$2')
      .replace(/~~?(?=\S)([^~]*?\S)~~?/g, '$1'),
  );
  return plain.replace(/\uE000(\d+)\uE001/g, (_match, index: string) => escaped[Number(index)]);
}

/** A heading's markdown → its rendered text (code spans kept verbatim). */
export function headingText(markdown: string): string {
  let out = '';
  let rest = markdown;
  const codeSpan = /(`+)([\s\S]*?[^`])\1(?!`)/;
  for (let match = codeSpan.exec(rest); match; match = codeSpan.exec(rest)) {
    out += plainInline(rest.slice(0, match.index));
    let code = match[2].replace(/\n/g, ' ');
    if (code.length > 2 && code.startsWith(' ') && code.endsWith(' ') && code.trim() !== '') code = code.slice(1, -1);
    out += code;
    rest = rest.slice(match.index + match[0].length);
  }
  return (out + plainInline(rest)).trim();
}

/** ATX headings outside fenced code blocks, in document order. */
function headings(markdown: string): Heading[] {
  const found: Heading[] = [];
  let fence: string | null = null;
  for (const line of markdown.split(/\r?\n/)) {
    const fenceMatch = FENCE.exec(line);
    if (fence) {
      if (fenceMatch && fenceMatch[1][0] === fence[0] && fenceMatch[1].length >= fence.length && line.trim() === fenceMatch[1]) {
        fence = null;
      }
      continue;
    }
    if (fenceMatch) {
      fence = fenceMatch[1];
      continue;
    }
    const atx = ATX.exec(line);
    if (!atx) continue;
    // A closing sequence (` ##`) is not part of the heading.
    const content = (atx[2] ?? '').replace(/(^|[ \t]+)#+$/, '');
    found.push({ depth: atx[1].length, text: headingText(content) });
  }
  return found;
}

/** The first H1's text, or null when the doc has none. */
export function docTitle(markdown: string): string | null {
  return headings(markdown).find((heading) => heading.depth === 1)?.text ?? null;
}

/**
 * H2 and H3 headings with the ids rehype-slug gives them: every heading
 * (H1–H6) goes through one github-slugger in document order, so repeated
 * titles get the same `-1`, `-2` suffixes as in the rendered page.
 */
export function tocFromMarkdown(markdown: string): TocItem[] {
  const slugger = new GithubSlugger();
  const items: TocItem[] = [];
  for (const heading of headings(markdown)) {
    const id = slugger.slug(heading.text);
    if (heading.depth === 2 || heading.depth === 3) items.push({ id, text: heading.text, depth: heading.depth });
  }
  return items;
}
