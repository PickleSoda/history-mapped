import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { AuthCard, FormMessage, SubmitButton, TextField } from '@/components/account/form';
import { safeNext, useAuthActions, useMe } from '@/hooks';
import { errorMessage, fieldErrors } from '@/lib/api';

type Mode = 'login' | 'two_factor' | 'forgot';

/** One message for a failed mutation, unless a field already shows it. */
function formError(error: unknown, shownFields: string[]): string | null {
  if (!error) return null;
  const fields = fieldErrors(error);
  return shownFields.some((f) => fields[f]) ? null : errorMessage(error);
}

/**
 * Sign in (`/login?next=…`): email + password, then — for accounts with
 * two-factor auth — a code step. Also hosts "forgot password", which emails a
 * reset link.
 */
export function LoginPage() {
  const [params] = useSearchParams();
  const next = safeNext(params.get('next'));
  const navigate = useNavigate();
  const { me } = useMe();
  const { signIn, twoFactor, resetLink } = useAuthActions();

  const [mode, setMode] = useState<Mode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(true);
  const [code, setCode] = useState('');
  const [recovery, setRecovery] = useState(false);

  if (me && mode !== 'two_factor') return <Navigate to={next} replace />;

  const onLogin = (e: FormEvent) => {
    e.preventDefault();
    signIn.mutate(
      { email, password, remember },
      {
        onSuccess: (result) => {
          if (result.two_factor) setMode('two_factor');
          else navigate(next, { replace: true });
        },
      },
    );
  };

  const onTwoFactor = (e: FormEvent) => {
    e.preventDefault();
    const value = code.trim();
    twoFactor.mutate(recovery ? { recovery_code: value } : { code: value.replace(/\s/g, '') }, {
      onSuccess: () => navigate(next, { replace: true }),
    });
  };

  const onForgot = (e: FormEvent) => {
    e.preventDefault();
    resetLink.mutate(email);
  };

  if (mode === 'two_factor') {
    const errors = fieldErrors(twoFactor.error);
    const field = recovery ? 'recovery_code' : 'code';
    return (
      <AuthCard
        title="Two-factor check"
        subtitle={
          recovery
            ? 'Enter one of your emergency recovery codes.'
            : 'Enter the 6-digit code from your authenticator app.'
        }
      >
        <form onSubmit={onTwoFactor} className="space-y-4">
          <TextField
            key={field}
            label={recovery ? 'Recovery code' : 'Authentication code'}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            inputMode={recovery ? 'text' : 'numeric'}
            autoComplete="one-time-code"
            required
            autoFocus
            error={errors[field]}
          />
          {formError(twoFactor.error, [field]) && (
            <FormMessage>{formError(twoFactor.error, [field])}</FormMessage>
          )}
          <SubmitButton pending={twoFactor.isPending}>
            {twoFactor.isPending ? 'Checking…' : 'Continue'}
          </SubmitButton>
          <button
            type="button"
            onClick={() => {
              setRecovery((v) => !v);
              setCode('');
              twoFactor.reset();
            }}
            className="w-full text-center text-[12px] text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            {recovery ? 'Use an authentication code instead' : 'Use a recovery code instead'}
          </button>
        </form>
      </AuthCard>
    );
  }

  if (mode === 'forgot') {
    const errors = fieldErrors(resetLink.error);
    return (
      <AuthCard title="Reset your password" subtitle="We’ll email you a link to choose a new one.">
        <form onSubmit={onForgot} className="space-y-4">
          <TextField
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
            autoFocus
            error={errors.email}
          />
          {resetLink.isSuccess && (
            <FormMessage tone="info">
              {resetLink.data ?? 'If that address has an account, a reset link is on its way.'}
            </FormMessage>
          )}
          {formError(resetLink.error, ['email']) && (
            <FormMessage>{formError(resetLink.error, ['email'])}</FormMessage>
          )}
          <SubmitButton pending={resetLink.isPending}>
            {resetLink.isPending ? 'Sending…' : 'Email me a reset link'}
          </SubmitButton>
          <button
            type="button"
            onClick={() => setMode('login')}
            className="w-full text-center text-[12px] text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            Back to sign in
          </button>
        </form>
      </AuthCard>
    );
  }

  const errors = fieldErrors(signIn.error);
  return (
    <AuthCard
      title="Sign in"
      subtitle="Star places and chronicles, file them into folders, and suggest corrections."
    >
      <form onSubmit={onLogin} className="space-y-4">
        <TextField
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          required
          autoFocus
          error={errors.email}
        />
        <TextField
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          required
          error={errors.password}
        />
        <div className="flex items-center justify-between gap-3 text-[12px]">
          <label className="inline-flex items-center gap-2 text-muted-foreground">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="size-3.5 accent-foreground"
            />
            Keep me signed in
          </label>
          <button
            type="button"
            onClick={() => setMode('forgot')}
            className="text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            Forgot password?
          </button>
        </div>
        {formError(signIn.error, ['email', 'password']) && (
          <FormMessage>{formError(signIn.error, ['email', 'password'])}</FormMessage>
        )}
        <SubmitButton pending={signIn.isPending}>{signIn.isPending ? 'Signing in…' : 'Sign in'}</SubmitButton>
      </form>
      <p className="mt-4 text-center text-[12px] text-muted-foreground">
        New here?{' '}
        <Link
          to={`/register${next !== '/' ? `?next=${encodeURIComponent(next)}` : ''}`}
          className="font-medium text-foreground underline-offset-4 hover:underline"
        >
          Create an account
        </Link>
      </p>
    </AuthCard>
  );
}
