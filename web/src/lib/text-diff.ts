/**
 * Word-level text diff — the client mirror of the server's `App\Support\TextDiff`,
 * used to preview a suggested edit before it is submitted. The server computes
 * the stored diff; this only has to look the same.
 *
 * Tokens are words (letters / digits / marks / `_`), whitespace runs, and single
 * punctuation characters. The output is merged chunks, `=` unchanged, `-`
 * removed, `+` added, with each change run's deletions before its insertions —
 * so joining `=`/`-` texts gives the base and `=`/`+` texts the proposal (both
 * with line endings normalised to `\n`).
 */

export type DiffOp = '=' | '-' | '+';
export type DiffChunk = readonly [DiffOp, string];

const TOKEN = /\s+|[\p{L}\p{N}\p{M}_]+|[^\s\p{L}\p{N}\p{M}_]/gu;
const WHITESPACE = /^\s+$/u;
const WORD = /[\p{L}\p{N}\p{M}_]+/gu;

/** Above this many LCS cells the middle is shown as one replace (keeps the
 *  preview fast on wholesale rewrites; trimming the shared ends comes first). */
const MAX_CELLS = 2_500_000;

export function tokenize(text: string): string[] {
  return text.match(TOKEN) ?? [];
}

/** Line endings normalised and ends trimmed — "did anything really change". */
export function normaliseText(text: string): string {
  return text.replace(/\r\n?/g, '\n').trim();
}

/** Plain code-unit order (not `localeCompare`), as the server sorts. */
const byCodeUnit = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);

/**
 * Canonical form of a list field (one name per line, e.g. aliases) — mirrors
 * the server's `ContributionFields` exactly: split lines, trim, drop blanks,
 * de-duplicate case-insensitively (first spelling wins), sort by the lowercased
 * name in code-unit order, join with `\n`. Applied to both sides before
 * diffing, so the preview shows only real additions and removals.
 */
export function normaliseList(text: string): string {
  const seen = new Set<string>();
  const items: Array<{ key: string; name: string }> = [];
  for (const line of text.replace(/\r\n?/g, '\n').split('\n')) {
    const name = line.trim();
    const key = name.toLowerCase();
    if (!name || seen.has(key)) continue;
    seen.add(key);
    items.push({ key, name });
  }
  return items
    .sort((a, b) => byCodeUnit(a.key, b.key))
    .map((i) => i.name)
    .join('\n');
}

/** A list field's text from its stored items: trimmed and put in code-unit
 *  order first, as the server does, so de-duplication keeps the same spelling. */
export function listText(items: readonly string[]): string {
  return normaliseList(
    items
      .map((s) => s.trim())
      .sort(byCodeUnit)
      .join('\n'),
  );
}

function lcsOps(a: string[], b: string[]): DiffOp[] {
  const n = a.length;
  const m = b.length;
  if (n === 0) return Array<DiffOp>(m).fill('+');
  if (m === 0) return Array<DiffOp>(n).fill('-');
  if ((n + 1) * (m + 1) > MAX_CELLS) {
    return [...Array<DiffOp>(n).fill('-'), ...Array<DiffOp>(m).fill('+')];
  }
  // dp[i][j] = LCS length of a[i:] and b[j:], flattened row-major.
  const w = m + 1;
  const dp = n < 65_535 && m < 65_535 ? new Uint16Array((n + 1) * w) : new Uint32Array((n + 1) * w);
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i * w + j] =
        a[i] === b[j] ? dp[(i + 1) * w + j + 1] + 1 : Math.max(dp[(i + 1) * w + j], dp[i * w + j + 1]);
    }
  }
  const ops: DiffOp[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      ops.push('=');
      i++;
      j++;
    } else if (dp[(i + 1) * w + j] >= dp[i * w + j + 1]) {
      ops.push('-');
      i++;
    } else {
      ops.push('+');
      j++;
    }
  }
  while (i++ < n) ops.push('-');
  while (j++ < m) ops.push('+');
  return ops;
}

type Segment = { eq: string } | { del: string; ins: string };

/**
 * Fold "whitespace islands" (as the server does): an unchanged whitespace-only
 * run between two changes joins both sides of the surrounding change, so
 * `-a +b = ' ' -c +d` reads as `-'a c' +'b d'` instead of two choppy edits.
 */
function foldIslands(segments: Segment[]): Segment[] {
  const out: Segment[] = [];
  for (let k = 0; k < segments.length; k++) {
    const seg = segments[k];
    const prev = out[out.length - 1];
    const next = segments[k + 1];
    if ('eq' in seg && WHITESPACE.test(seg.eq) && prev && 'del' in prev && next && 'del' in next) {
      prev.del += seg.eq + next.del;
      prev.ins += seg.eq + next.ins;
      k++;
      continue;
    }
    out.push('eq' in seg ? { eq: seg.eq } : { del: seg.del, ins: seg.ins });
  }
  return out;
}

/**
 * Item-level diff of two `\n`-joined lists (mirrors the server's
 * `TextDiff::compute(..., byLine: true)`): items are compared, never the
 * separators, and each `\n` goes to the side that has an earlier item.
 */
export function diffLines(base: string, proposed: string): DiffChunk[] {
  const items = (s: string) => (s ? s.replace(/\r\n?/g, '\n').split('\n') : []);
  const a = items(base);
  const b = items(proposed);
  const out: DiffChunk[] = [];
  const pushOp = (op: DiffOp, text: string) => {
    if (!text) return;
    const last = out[out.length - 1];
    if (last && last[0] === op) out[out.length - 1] = [op, last[1] + text];
    else out.push([op, text]);
  };
  let del = '';
  let ins = '';
  const flush = () => {
    pushOp('-', del);
    pushOp('+', ins);
    del = ins = '';
  };
  let hasOld = false;
  let hasNew = false;
  let i = 0;
  let j = 0;
  for (const op of lcsOps(a, b)) {
    if (op === '-') {
      del += (hasOld ? '\n' : '') + a[i++];
      hasOld = true;
    } else if (op === '+') {
      ins += (hasNew ? '\n' : '') + b[j++];
      hasNew = true;
    } else {
      if (hasOld && !hasNew) del += '\n';
      else if (hasNew && !hasOld) ins += '\n';
      flush();
      pushOp('=', (hasOld && hasNew ? '\n' : '') + a[i]);
      i++;
      j++;
      hasOld = hasNew = true;
    }
  }
  flush();
  return out;
}

/** Diff `base` → `proposed` into merged chunks (line endings normalised).
 *  `byLine` compares whole list items instead — see `diffLines`. */
export function diffWords(base: string, proposed: string, byLine = false): DiffChunk[] {
  if (byLine) return diffLines(base, proposed);
  const a = tokenize(base.replace(/\r\n?/g, '\n'));
  const b = tokenize(proposed.replace(/\r\n?/g, '\n'));

  let start = 0;
  while (start < a.length && start < b.length && a[start] === b[start]) start++;
  let endA = a.length;
  let endB = b.length;
  while (endA > start && endB > start && a[endA - 1] === b[endB - 1]) {
    endA--;
    endB--;
  }

  // Ops → segments: equal runs and change runs (deletions + insertions).
  const segments: Segment[] = [];
  const push = (op: DiffOp, token: string) => {
    const last = segments[segments.length - 1];
    if (op === '=') {
      if (last && 'eq' in last) last.eq += token;
      else segments.push({ eq: token });
    } else {
      const change = last && 'del' in last ? last : { del: '', ins: '' };
      if (change !== last) segments.push(change);
      if (op === '-') change.del += token;
      else change.ins += token;
    }
  };

  a.slice(0, start).forEach((t) => push('=', t));
  let i = start;
  let j = start;
  for (const op of lcsOps(a.slice(start, endA), b.slice(start, endB))) {
    if (op === '=') {
      push('=', a[i]);
      i++;
      j++;
    } else if (op === '-') push('-', a[i++]);
    else push('+', b[j++]);
  }
  a.slice(endA).forEach((t) => push('=', t));

  const out: DiffChunk[] = [];
  for (const seg of foldIslands(segments)) {
    if ('eq' in seg) {
      if (seg.eq) out.push(['=', seg.eq]);
      continue;
    }
    if (seg.del) out.push(['-', seg.del]);
    if (seg.ins) out.push(['+', seg.ins]);
  }
  return out;
}

/** Changed word tokens (letters / digits / marks / `_`) on each side. */
export function diffStats(chunks: readonly DiffChunk[]): { added: number; removed: number } {
  let added = 0;
  let removed = 0;
  for (const [op, text] of chunks) {
    if (op === '=') continue;
    const n = text.match(WORD) ?? [];
    if (op === '+') added += n.length;
    else removed += n.length;
  }
  return { added, removed };
}

/** Rebuild one side from the chunks (`base` = `=`+`-`, `proposed` = `=`+`+`). */
export function applyDiff(chunks: readonly DiffChunk[], side: 'base' | 'proposed'): string {
  const drop: DiffOp = side === 'base' ? '+' : '-';
  return chunks
    .filter(([op]) => op !== drop)
    .map(([, text]) => text)
    .join('');
}
