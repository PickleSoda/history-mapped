import { useEffect, useState } from 'react';
import { renderMermaid } from '@/lib/docs/mermaid';
import { useTheme } from '@/lib/theme';
import { CodeBlock } from './CodeBlock';

/**
 * A ```mermaid fence drawn as a diagram. Mermaid loads on first use; the
 * diagram re-renders with the site theme. If mermaid fails to load or the
 * source does not parse, the fence shows as a plain code block instead.
 */
export function MermaidDiagram({ code }: { code: string }) {
  const theme = useTheme((state) => state.theme);
  // undefined: rendering; null: failed. A previous diagram stays up while a
  // theme change re-renders it.
  const [svg, setSvg] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    renderMermaid(code, theme).then(
      (markup) => !cancelled && setSvg(markup),
      (error: unknown) => {
        if (cancelled) return;
        console.warn('[docs] mermaid diagram failed to render', error);
        setSvg(null);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [code, theme]);

  if (svg === undefined) {
    return (
      <div
        role="status"
        aria-label="Rendering diagram"
        className="my-6 h-40 rounded-lg border bg-muted/40 motion-safe:animate-pulse"
      />
    );
  }
  if (svg === null) return <CodeBlock code={code} language="mermaid" note="Diagram could not be rendered" />;
  return (
    <figure
      className="my-6 overflow-x-auto rounded-lg border bg-card p-4 motion-safe:animate-in motion-safe:fade-in motion-reduce:[&_*]:animate-none! motion-reduce:[&_*]:transition-none! [&_svg]:mx-auto [&_svg]:h-auto"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
