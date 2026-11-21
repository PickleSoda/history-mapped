import axios from 'axios';
import type { InternalAxiosRequestConfig } from 'axios';

/** Methods that only read. Laravel checks the CSRF token on every other one. */
const READ_METHODS = new Set(['get', 'head', 'options']);

/**
 * Whether a request carries the Sanctum XSRF-TOKEN cookie as the X-XSRF-TOKEN
 * header: writes only.
 *
 * The SPA and the API are different origins. A request header outside the
 * browser's short safe list makes such a request "non-simple", and the browser
 * then asks the API for permission first (an OPTIONS preflight). With the token
 * on reads too, almost every GET cost two requests, for visitors and for the
 * crawlers that render our pages (39% of all requests on 2026-11-21). A read
 * needs no token and its only other header, Accept, is on the safe list, so it
 * goes out as one request. Keep it so: no custom header on a GET.
 */
export function sendsXsrfToken(config: InternalAxiosRequestConfig): boolean {
  return !READ_METHODS.has((config.method ?? 'get').toLowerCase());
}

/** Low-level transport. Typed domain endpoints live alongside in this folder. */
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  withCredentials: true,
  // The SPA and API are different origins (:5173 → :8000 in dev), so axios
  // only echoes the Sanctum XSRF-TOKEN cookie as a header when told to, and
  // only an exact `true` tells it (anything else means "same origin only").
  withXSRFToken: sendsXsrfToken,
  headers: {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  },
});

/** Fetch the Sanctum CSRF cookie before making mutating requests. */
export async function getCsrfCookie(): Promise<void> {
  await api.get('/sanctum/csrf-cookie');
}
