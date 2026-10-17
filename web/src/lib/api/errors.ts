/** Reading Laravel error responses (422 validation, 429 throttle, …). */
import { isAxiosError } from 'axios';

/** HTTP status of a failed request, or null for network / non-axios errors. */
export function errorStatus(error: unknown): number | null {
  return isAxiosError(error) ? (error.response?.status ?? null) : null;
}

/** Field → first message from a 422 `errors` bag (empty when not a 422). */
export function fieldErrors(error: unknown): Record<string, string> {
  if (!isAxiosError(error) || error.response?.status !== 422) return {};
  const bag = (error.response.data as { errors?: Record<string, string[] | string> })?.errors;
  if (!bag || typeof bag !== 'object') return {};
  const out: Record<string, string> = {};
  for (const [field, messages] of Object.entries(bag)) {
    const first = Array.isArray(messages) ? messages[0] : messages;
    if (typeof first === 'string') out[field] = first;
  }
  return out;
}

/** One human sentence for a failed request. */
export function errorMessage(error: unknown, fallback = 'Something went wrong. Please try again.'): string {
  if (!isAxiosError(error)) return fallback;
  const status = error.response?.status;
  if (!error.response) return 'Could not reach the server. Check your connection.';
  if (status === 419) return 'Your session expired. Reload the page and try again.';
  if (status === 429) return 'Too many attempts. Wait a minute and try again.';
  if (status === 403) return 'You don’t have permission to do that.';
  const message = (error.response.data as { message?: unknown })?.message;
  return typeof message === 'string' && message ? message : fallback;
}
