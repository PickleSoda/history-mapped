/** Small form building blocks for the account pages. */
import { useId } from 'react';
import type { InputHTMLAttributes, ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { FIELD } from './styles';

/** Labelled input with its validation message. */
export function TextField({
  label,
  error,
  hint,
  className,
  ...input
}: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string; hint?: ReactNode }) {
  const id = useId();
  const errorId = `${id}-error`;
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1.5 block text-[12px] font-medium">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        className={cn(FIELD, 'h-10')}
        {...input}
      />
      {error ? (
        <p id={errorId} className="mt-1 text-[12px] text-destructive">
          {error}
        </p>
      ) : (
        hint && <p className="mt-1 text-[12px] text-muted-foreground">{hint}</p>
      )}
    </div>
  );
}

export function SubmitButton({ pending, children }: { pending?: boolean; children: ReactNode }) {
  return (
    <button
      type="submit"
      disabled={pending}
      className="inline-flex h-10 w-full items-center justify-center rounded-lg bg-primary px-4 text-[13px] font-medium text-primary-foreground transition-colors hover:bg-primary/85 disabled:opacity-50"
    >
      {children}
    </button>
  );
}

/** A form-level message (not tied to one field). */
export function FormMessage({ tone = 'error', children }: { tone?: 'error' | 'info'; children: ReactNode }) {
  return (
    <p
      role={tone === 'error' ? 'alert' : 'status'}
      className={cn(
        'rounded-lg border px-3 py-2 text-[12.5px]',
        tone === 'error'
          ? 'border-destructive/30 bg-destructive/10 text-destructive'
          : 'bg-muted/50 text-foreground/80',
      )}
    >
      {children}
    </p>
  );
}

/** The centred card the sign-in / register forms sit in. */
export function AuthCard({ title, subtitle, children }: { title: string; subtitle?: ReactNode; children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-sm pt-4 md:pt-10">
      <h1 className="font-heading text-[30px] font-semibold leading-tight tracking-tight">{title}</h1>
      {subtitle && <p className="mt-2 text-[13px] text-muted-foreground">{subtitle}</p>}
      <div className="mt-6 rounded-xl border bg-card p-5 shadow-xs">{children}</div>
    </div>
  );
}
