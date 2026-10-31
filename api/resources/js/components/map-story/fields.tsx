import { Crosshair, X } from 'lucide-react';
import { useState } from 'react';
import type { ReactNode } from 'react';
import { lengthStatus } from '@/lib/map-story-doc';
import type { LngLat } from '@/lib/map-story-doc';
import { cn } from '@/lib/utils';

/** Small, dense controls for the map-story editor (native inputs, admin styling). */
export const inputCls =
    'h-8 w-full min-w-0 rounded-md border border-input bg-background px-2 text-sm shadow-xs outline-none focus-visible:ring-2 focus-visible:ring-ring/40';

/** Set `obj[key]`, or delete it when the value is undefined, '' or null (unless `keepNull`). */
export function setKey(
    obj: Record<string, any>,
    key: string,
    value: unknown,
    keepNull = false,
): void {
    if (value === undefined || value === '' || (value === null && !keepNull)) {
        delete obj[key];
    } else {
        obj[key] = value;
    }
}

export function Field({
    label,
    hint,
    children,
    className,
    issues,
}: {
    label: string;
    hint?: ReactNode;
    children: ReactNode;
    className?: string;
    issues?: string[];
}) {
    return (
        <label className={cn('block min-w-0 space-y-1', className)}>
            <span className="flex items-baseline justify-between gap-2 text-xs font-medium text-muted-foreground">
                <span>{label}</span>
                {hint}
            </span>
            {children}
            <Issues messages={issues} />
        </label>
    );
}

export function Issues({ messages }: { messages?: string[] }) {
    if (!messages || messages.length === 0) {
        return null;
    }

    return (
        <ul className="space-y-0.5 text-xs text-destructive">
            {messages.map((m) => (
                <li key={m}>{m}</li>
            ))}
        </ul>
    );
}

export function Count({
    text,
    limits,
}: {
    text: unknown;
    limits?: [number, number];
}) {
    const status = lengthStatus(text, limits);

    return (
        <span
            className={cn(
                'font-mono text-[10px]',
                status.ok ? 'text-muted-foreground' : 'text-amber-600',
            )}
            title={
                limits
                    ? `Aim for ${limits[0]}–${limits[1]} characters`
                    : undefined
            }
        >
            {status.label}
        </span>
    );
}

export function TextField({
    label,
    value,
    onChange,
    limits,
    rows,
    placeholder,
    issues,
    className,
    disabled,
}: {
    label: string;
    value: unknown;
    onChange: (value: string | undefined) => void;
    limits?: [number, number];
    rows?: number;
    placeholder?: string;
    issues?: string[];
    className?: string;
    disabled?: boolean;
}) {
    const text = typeof value === 'string' ? value : '';

    return (
        <Field
            label={label}
            className={className}
            issues={issues}
            hint={limits ? <Count text={text} limits={limits} /> : undefined}
        >
            {rows ? (
                <textarea
                    className={cn(inputCls, 'h-auto py-1.5 leading-snug')}
                    rows={rows}
                    value={text}
                    placeholder={placeholder}
                    disabled={disabled}
                    onChange={(e) =>
                        onChange(
                            e.target.value === '' ? undefined : e.target.value,
                        )
                    }
                />
            ) : (
                <input
                    className={inputCls}
                    value={text}
                    placeholder={placeholder}
                    disabled={disabled}
                    onChange={(e) =>
                        onChange(
                            e.target.value === '' ? undefined : e.target.value,
                        )
                    }
                />
            )}
        </Field>
    );
}

export function NumberField({
    label,
    value,
    onChange,
    step = 'any',
    issues,
    className,
    placeholder,
}: {
    label: string;
    value: unknown;
    onChange: (value: number | undefined) => void;
    step?: string;
    issues?: string[];
    className?: string;
    placeholder?: string;
}) {
    return (
        <Field label={label} className={className} issues={issues}>
            <input
                type="number"
                className={inputCls}
                step={step}
                placeholder={placeholder}
                value={typeof value === 'number' ? value : ''}
                onChange={(e) =>
                    onChange(
                        e.target.value === ''
                            ? undefined
                            : Number(e.target.value),
                    )
                }
            />
        </Field>
    );
}

export function SelectField({
    label,
    value,
    options,
    onChange,
    empty = '—',
    issues,
    className,
}: {
    label: string;
    value: unknown;
    options: readonly (string | { value: string; label: string })[];
    onChange: (value: string | undefined) => void;
    /** The label of the empty choice; null to offer none. */
    empty?: string | null;
    issues?: string[];
    className?: string;
}) {
    const current = typeof value === 'string' ? value : '';

    return (
        <Field label={label} className={className} issues={issues}>
            <select
                className={inputCls}
                value={current}
                onChange={(e) =>
                    onChange(e.target.value === '' ? undefined : e.target.value)
                }
            >
                {empty !== null && <option value="">{empty}</option>}
                {current !== '' &&
                    !options.some(
                        (o) =>
                            (typeof o === 'string' ? o : o.value) === current,
                    ) && <option value={current}>{current} (unknown)</option>}
                {options.map((o) => {
                    const v = typeof o === 'string' ? o : o.value;

                    return (
                        <option key={v} value={v}>
                            {typeof o === 'string'
                                ? o.replace(/_/g, ' ')
                                : o.label}
                        </option>
                    );
                })}
            </select>
        </Field>
    );
}

export function CheckField({
    label,
    value,
    onChange,
    className,
}: {
    label: string;
    value: unknown;
    onChange: (value: boolean | undefined) => void;
    className?: string;
}) {
    return (
        <label className={cn('flex items-center gap-1.5 text-xs', className)}>
            <input
                type="checkbox"
                checked={value === true}
                onChange={(e) => onChange(e.target.checked ? true : undefined)}
            />
            {label}
        </label>
    );
}

/** A [lon, lat] with a "pick on the preview" button. */
export function PointField({
    label,
    value,
    onChange,
    onPick,
    issues,
    className,
}: {
    label: string;
    value: unknown;
    onChange: (value: LngLat | undefined) => void;
    onPick?: () => void;
    issues?: string[];
    className?: string;
}) {
    const p = Array.isArray(value) ? (value as number[]) : [];
    const set = (i: 0 | 1, raw: string) => {
        const next: [number, number] = [p[0] ?? 0, p[1] ?? 0];
        next[i] = Number(raw);
        onChange(
            raw === '' && i === 0 && p[1] === undefined ? undefined : next,
        );
    };

    return (
        <Field label={label} className={className} issues={issues}>
            <span className="flex gap-1">
                <input
                    type="number"
                    step="any"
                    className={inputCls}
                    placeholder="lon"
                    value={typeof p[0] === 'number' ? p[0] : ''}
                    onChange={(e) => set(0, e.target.value)}
                />
                <input
                    type="number"
                    step="any"
                    className={inputCls}
                    placeholder="lat"
                    value={typeof p[1] === 'number' ? p[1] : ''}
                    onChange={(e) => set(1, e.target.value)}
                />
                {onPick && (
                    <IconButton title="Pick on the map" onClick={onPick}>
                        <Crosshair className="size-3.5" />
                    </IconButton>
                )}
            </span>
        </Field>
    );
}

export function IconButton({
    title,
    onClick,
    children,
    className,
    disabled,
}: {
    title: string;
    onClick: () => void;
    children: ReactNode;
    className?: string;
    disabled?: boolean;
}) {
    return (
        <button
            type="button"
            title={title}
            aria-label={title}
            disabled={disabled}
            onClick={(e) => {
                e.preventDefault();
                onClick();
            }}
            className={cn(
                'inline-flex h-8 shrink-0 items-center justify-center rounded-md border px-2 text-xs hover:bg-muted disabled:opacity-40',
                className,
            )}
        >
            {children}
        </button>
    );
}

export function RemoveButton({
    title,
    onClick,
}: {
    title: string;
    onClick: () => void;
}) {
    return (
        <IconButton
            title={title}
            onClick={onClick}
            className="h-6 border-0 px-1 text-muted-foreground hover:text-destructive"
        >
            <X className="size-3.5" />
        </IconButton>
    );
}

/** A titled block in a tab. */
export function Section({
    title,
    actions,
    children,
    className,
}: {
    title: ReactNode;
    actions?: ReactNode;
    children: ReactNode;
    className?: string;
}) {
    return (
        <section className={cn('space-y-2 rounded-lg border p-3', className)}>
            <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-semibold">{title}</h3>
                {actions && (
                    <div className="flex flex-wrap items-center gap-1">
                        {actions}
                    </div>
                )}
            </div>
            {children}
        </section>
    );
}

/**
 * An id that other parts of the story point at: edited locally and committed
 * on blur or Enter through `onRename` (which rewrites the references), and
 * only when the new id is valid and free.
 */
export function IdField({
    label = 'Id',
    value,
    taken,
    onRename,
    className,
    issues,
}: {
    label?: string;
    value: string;
    taken: string[];
    onRename: (next: string) => void;
    className?: string;
    issues?: string[];
}) {
    const [draft, setDraft] = useState(value);
    const [error, setError] = useState<string | null>(null);
    const [shown, setShown] = useState(value);

    // A rename elsewhere (or an undo) resets the draft.
    if (shown !== value) {
        setShown(value);
        setDraft(value);
        setError(null);
    }

    const commit = () => {
        if (draft === value) {
            setError(null);

            return;
        }

        if (!/^[a-z0-9][a-z0-9-]{0,63}$/.test(draft)) {
            setError('lowercase letters, digits and dashes');

            return;
        }

        if (taken.includes(draft)) {
            setError('already used');

            return;
        }

        setError(null);
        onRename(draft);
    };

    return (
        <Field
            label={label}
            className={className}
            issues={[...(issues ?? []), ...(error ? [error] : [])]}
        >
            <input
                className={cn(inputCls, 'font-mono')}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onBlur={commit}
                onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        commit();
                    }

                    if (e.key === 'Escape') {
                        setDraft(value);
                        setError(null);
                    }
                }}
            />
        </Field>
    );
}

/** A comma-separated list of short strings (e.g. goods). */
export function ListField({
    label,
    value,
    onChange,
    className,
}: {
    label: string;
    value: unknown;
    onChange: (value: string[] | undefined) => void;
    className?: string;
}) {
    const list = Array.isArray(value) ? (value as string[]) : [];
    const joined = list.join(', ');
    const [draft, setDraft] = useState(joined);
    const [shown, setShown] = useState(joined);

    if (shown !== joined) {
        setShown(joined);
        setDraft(joined);
    }

    return (
        <Field label={label} className={className}>
            <input
                className={inputCls}
                value={draft}
                placeholder="comma, separated"
                onChange={(e) => setDraft(e.target.value)}
                onBlur={() => {
                    const next = draft
                        .split(',')
                        .map((s) => s.trim())
                        .filter(Boolean);
                    onChange(next.length === 0 ? undefined : next);
                }}
            />
        </Field>
    );
}
