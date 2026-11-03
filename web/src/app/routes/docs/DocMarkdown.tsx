/**
 * Markdown → the docs page body: GFM (tables, task lists, strikethrough,
 * autolinks), heading ids from rehype-slug with hover anchors, links rewritten
 * for the site, code blocks, and ```mermaid fences drawn as diagrams.
 * Raw HTML in the markdown is shown as text, never injected.
 */
import { createElement, memo, useMemo } from 'react';
import type { ComponentPropsWithoutRef } from 'react';
import Markdown from 'react-markdown';
import type { Components, ExtraProps } from 'react-markdown';
import { Link } from 'react-router-dom';
import rehypeSlug from 'rehype-slug';
import remarkGfm from 'remark-gfm';
import { rewriteDocImage, rewriteDocLink } from '@/lib/docs/docs';
import { cn } from '@/lib/utils';
import { CodeBlock } from './CodeBlock';
import { MermaidDiagram } from './MermaidDiagram';

const REMARK_PLUGINS = [remarkGfm];
const REHYPE_PLUGINS = [rehypeSlug];

/** The bits of a hast node the renderer reads (hast types are not a direct dependency). */
interface HastNode {
  type: string;
  tagName?: string;
  value?: string;
  properties?: Record<string, unknown>;
  children?: HastNode[];
}

function hastText(node: HastNode): string {
  if (node.type === 'text') return node.value ?? '';
  return (node.children ?? []).map(hastText).join('');
}

/** Element props without react-markdown's `node`, ready to spread onto the DOM. */
function domProps<P extends ExtraProps>(props: P): Omit<P, 'node'> {
  const rest = { ...props };
  delete rest.node;
  return rest;
}

type HeadingTag = 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';

const HEADING_CLASS: Record<HeadingTag, string> = {
  h1: 'mb-6 text-balance text-3xl font-semibold leading-tight tracking-tight md:text-4xl',
  h2: 'mt-12 mb-4 border-b pb-2 text-2xl font-semibold tracking-tight',
  h3: 'mt-8 mb-3 text-xl font-semibold',
  h4: 'mt-6 mb-2 text-base font-semibold',
  h5: 'mt-6 mb-2 text-sm font-semibold',
  h6: 'mt-6 mb-2 text-sm font-semibold text-muted-foreground',
};

function heading(tag: HeadingTag) {
  return function Heading(props: ComponentPropsWithoutRef<HeadingTag> & ExtraProps) {
    const { id, children, className, ...rest } = domProps(props);
    return createElement(
      tag,
      {
        ...rest,
        id,
        className: cn(
          'group scroll-mt-[calc(var(--site-header-height,0px)+1.5rem)]',
          HEADING_CLASS[tag],
          className,
        ),
      },
      children,
      id && tag !== 'h1' ? (
        <a
          href={`#${id}`}
          aria-label="Link to this section"
          className="ml-2 font-sans font-normal text-muted-foreground no-underline opacity-0 transition-opacity group-hover:opacity-100 motion-reduce:transition-none focus-visible:opacity-100"
        >
          #
        </a>
      ) : null,
    );
  };
}

function external(href: string): boolean {
  return /^https?:\/\//i.test(href);
}

function components(path: string): Components {
  return {
    h1: heading('h1'),
    h2: heading('h2'),
    h3: heading('h3'),
    h4: heading('h4'),
    h5: heading('h5'),
    h6: heading('h6'),
    p: (props) => <p {...domProps(props)} className="my-4" />,
    a(props) {
      const { href, children, ...rest } = domProps(props);
      const target = rewriteDocLink(href, path);
      const className = 'font-medium underline decoration-ring underline-offset-4 hover:decoration-foreground';
      if (target?.startsWith('/') && !target.startsWith('//')) {
        return (
          <Link {...rest} to={target} className={className}>
            {children}
          </Link>
        );
      }
      return (
        <a
          {...rest}
          href={target}
          className={className}
          {...(target && external(target) ? { target: '_blank', rel: 'noreferrer' } : {})}
        >
          {children}
        </a>
      );
    },
    img(props) {
      const { src, alt, ...rest } = domProps(props);
      return (
        <img
          {...rest}
          src={typeof src === 'string' ? rewriteDocImage(src, path) : undefined}
          alt={alt ?? ''}
          loading="lazy"
          className="my-4 h-auto max-w-full rounded-lg"
        />
      );
    },
    ul: ({ className, ...props }) => (
      <ul
        {...domProps(props)}
        className={cn(
          'my-4 ml-6 list-disc space-y-1.5 marker:text-muted-foreground [&_ol]:my-1.5 [&_ul]:my-1.5',
          className === 'contains-task-list' && 'ml-1 list-none',
        )}
      />
    ),
    ol: ({ className, ...props }) => (
      <ol
        {...domProps(props)}
        className={cn(
          'my-4 ml-6 list-decimal space-y-1.5 marker:text-muted-foreground [&_ol]:my-1.5 [&_ul]:my-1.5',
          className === 'contains-task-list' && 'ml-1 list-none',
        )}
      />
    ),
    li: (props) => <li {...domProps(props)} className="pl-1" />,
    input: (props) => <input {...domProps(props)} className="mr-2 align-middle accent-foreground" />,
    blockquote: (props) => (
      <blockquote {...domProps(props)} className="my-5 border-l-2 border-ring pl-4 text-muted-foreground [&>p]:my-2" />
    ),
    hr: (props) => <hr {...domProps(props)} className="my-10 border-border" />,
    strong: (props) => <strong {...domProps(props)} className="font-semibold text-foreground" />,
    table: (props) => (
      <div className="my-6 overflow-x-auto rounded-lg border">
        <table
          {...domProps(props)}
          className="w-full border-collapse text-sm [&_tbody_tr:last-child>td]:border-b-0"
        />
      </div>
    ),
    thead: (props) => <thead {...domProps(props)} className="bg-muted/60" />,
    th: (props) => (
      <th {...domProps(props)} className="border-b px-3 py-2 text-left font-semibold whitespace-nowrap" />
    ),
    td: (props) => <td {...domProps(props)} className="border-b px-3 py-2 align-top" />,
    // Inline code only: fenced blocks are rendered whole by `pre` below.
    code: (props) => (
      <code {...domProps(props)} className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[0.85em] wrap-anywhere" />
    ),
    pre({ node }) {
      const code = (node as HastNode | undefined)?.children?.find(
        (child) => child.type === 'element' && child.tagName === 'code',
      );
      const classes = code?.properties?.className;
      const language = (Array.isArray(classes) ? classes.map(String) : [])
        .find((name) => name.startsWith('language-'))
        ?.slice('language-'.length);
      // mdast-util-to-hast appends a newline to every code block.
      const text = code ? hastText(code).replace(/\n$/, '') : '';
      if (language === 'mermaid') return <MermaidDiagram code={text} />;
      return <CodeBlock code={text} language={language} />;
    },
  };
}

/**
 * Renders one doc; `path` (repo-relative) anchors its relative links. Memoised
 * with stable components so a parent re-render never remounts the body (and
 * its diagrams).
 */
export const DocMarkdown = memo(function DocMarkdown({ markdown, path }: { markdown: string; path: string }) {
  const rendered = useMemo(() => components(path), [path]);
  return (
    <div className="text-[15px] leading-7 break-words text-foreground/90 md:text-base [&>:first-child]:mt-0">
      <Markdown remarkPlugins={REMARK_PLUGINS} rehypePlugins={REHYPE_PLUGINS} components={rendered}>
        {markdown}
      </Markdown>
    </div>
  );
});
