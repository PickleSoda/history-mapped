/** A fenced code block: optional language label, horizontal scroll, no highlighting. */
export function CodeBlock({ code, language, note }: { code: string; language?: string; note?: string }) {
  const label = [language, note].filter(Boolean).join(' · ');
  return (
    <div className="my-5 overflow-hidden rounded-lg border bg-muted/40">
      {label && (
        <div className="border-b px-4 py-1.5 font-mono text-[11px] tracking-wide text-muted-foreground">{label}</div>
      )}
      <pre className="overflow-x-auto p-4 font-mono text-[13px] leading-6">
        <code className={language ? `language-${language}` : undefined}>{code}</code>
      </pre>
    </div>
  );
}
