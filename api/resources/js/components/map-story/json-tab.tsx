import { useEffect, useState } from 'react';
import { useStoryEditor } from './editor-context';

/**
 * The whole document as JSON, for anything the form does not cover. Valid
 * JSON replaces the draft as you type; while it does not parse, the error
 * shows and the other tabs stay locked (`onParseError`).
 */
export function JsonTab({
    onParseError,
}: {
    onParseError: (error: string | null) => void;
}) {
    const { doc, replace } = useStoryEditor();
    const [text, setText] = useState(() => JSON.stringify(doc, null, 2));
    const [error, setError] = useState<string | null>(null);

    useEffect(() => () => onParseError(null), [onParseError]);

    return (
        <div className="space-y-2">
            <p className="text-xs text-muted-foreground">
                The authored document (schema in
                docs/implementation-docs/map-story-authoring.md). Resolved ids
                (entity_id beside a Q-id, chronicle_id, entry_id) are added when
                you save.
            </p>
            {error && (
                <p className="rounded border border-destructive/40 bg-destructive/5 px-2 py-1 font-mono text-xs text-destructive">
                    {error}
                </p>
            )}
            <textarea
                className="h-[calc(100vh-17rem)] min-h-96 w-full resize-y rounded-md border bg-background p-2 font-mono text-xs leading-snug outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
                spellCheck={false}
                value={text}
                onChange={(e) => {
                    setText(e.target.value);

                    try {
                        const parsed = JSON.parse(e.target.value);

                        if (
                            !parsed ||
                            typeof parsed !== 'object' ||
                            Array.isArray(parsed)
                        ) {
                            throw new Error(
                                'the document must be a JSON object',
                            );
                        }

                        setError(null);
                        onParseError(null);
                        replace(parsed);
                    } catch (err) {
                        const message =
                            err instanceof Error ? err.message : String(err);
                        setError(message);
                        onParseError(message);
                    }
                }}
            />
        </div>
    );
}
