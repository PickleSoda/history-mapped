/**
 * Session auth against Fortify's JSON endpoints (Sanctum cookie / stateful SPA).
 * Every mutation first fetches the CSRF cookie; the session cookie is set by
 * the API host.
 */
import { LoginResultSchema, MeSchema } from '@/lib/schemas/auth';
import type { LoginResult, Me } from '@/lib/schemas/auth';
import { api, getCsrfCookie } from './client';
import { errorStatus } from './errors';

/** GET /api/v1/me — the signed-in user, or null for a guest (401). */
export async function me(signal?: AbortSignal): Promise<Me | null> {
  try {
    const { data } = await api.get('/api/v1/me', { signal });
    return MeSchema.parse((data as { data?: unknown }).data ?? data);
  } catch (error) {
    if (errorStatus(error) === 401) return null;
    throw error;
  }
}

export interface LoginInput {
  email: string;
  password: string;
  remember?: boolean;
}

/** POST /login. `two_factor: true` → follow up with `twoFactorChallenge`. */
export async function login(input: LoginInput): Promise<LoginResult> {
  await getCsrfCookie();
  const { data } = await api.post('/login', input);
  return LoginResultSchema.parse(data ?? {});
}

/** POST /two-factor-challenge with either a TOTP code or a recovery code. */
export async function twoFactorChallenge(
  input: { code: string } | { recovery_code: string },
): Promise<void> {
  await getCsrfCookie();
  await api.post('/two-factor-challenge', input);
}

export interface RegisterInput {
  name: string;
  email: string;
  password: string;
  password_confirmation: string;
}

/** POST /register — signs the new user in. */
export async function register(input: RegisterInput): Promise<void> {
  await getCsrfCookie();
  await api.post('/register', input);
}

export async function logout(): Promise<void> {
  await getCsrfCookie();
  await api.post('/logout');
}

/** POST /forgot-password — emails a reset link; returns the status message. */
export async function forgotPassword(email: string): Promise<string | null> {
  await getCsrfCookie();
  const { data } = await api.post('/forgot-password', { email });
  const message = (data as { message?: unknown } | undefined)?.message;
  return typeof message === 'string' ? message : null;
}
