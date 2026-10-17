import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { AuthCard, FormMessage, SubmitButton, TextField } from '@/components/account/form';
import { safeNext, useAuthActions, useMe } from '@/hooks';
import { errorMessage, fieldErrors } from '@/lib/api';

const FIELDS = ['name', 'email', 'password', 'password_confirmation'];

/** Create an account (`/register?next=…`); signs the new user straight in. */
export function RegisterPage() {
  const [params] = useSearchParams();
  const next = safeNext(params.get('next'));
  const navigate = useNavigate();
  const { me } = useMe();
  const { signUp } = useAuthActions();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');

  if (me) return <Navigate to={next} replace />;

  const errors = fieldErrors(signUp.error);
  const general =
    signUp.error && !FIELDS.some((f) => errors[f]) ? errorMessage(signUp.error) : null;
  const mismatch = confirmation.length > 0 && confirmation !== password;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (mismatch) return;
    signUp.mutate(
      { name, email, password, password_confirmation: confirmation },
      { onSuccess: () => navigate(next, { replace: true }) },
    );
  };

  return (
    <AuthCard
      title="Create an account"
      subtitle="Free. Save what you find and help correct the record."
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <TextField
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoComplete="name"
          maxLength={255}
          required
          autoFocus
          error={errors.name}
        />
        <TextField
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          maxLength={255}
          required
          error={errors.email}
        />
        <TextField
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
          required
          error={errors.password}
          hint="12+ characters, mixing upper and lower case, numbers and symbols."
        />
        <TextField
          label="Confirm password"
          type="password"
          value={confirmation}
          onChange={(e) => setConfirmation(e.target.value)}
          autoComplete="new-password"
          required
          error={mismatch ? 'The passwords don’t match.' : errors.password_confirmation}
        />
        {general && <FormMessage>{general}</FormMessage>}
        <SubmitButton pending={signUp.isPending}>
          {signUp.isPending ? 'Creating account…' : 'Create account'}
        </SubmitButton>
      </form>
      <p className="mt-4 text-center text-[12px] text-muted-foreground">
        Already have an account?{' '}
        <Link
          to={`/login${next !== '/' ? `?next=${encodeURIComponent(next)}` : ''}`}
          className="font-medium text-foreground underline-offset-4 hover:underline"
        >
          Sign in
        </Link>
      </p>
    </AuthCard>
  );
}
