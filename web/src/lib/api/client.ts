import axios from 'axios';

/** Low-level transport. Typed domain endpoints live alongside in this folder. */
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  withCredentials: true,
  // The SPA and API are different origins (:5173 → :8000 in dev), so axios
  // only echoes the Sanctum XSRF-TOKEN cookie as a header when told to.
  withXSRFToken: true,
  headers: {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  },
});

/** Fetch the Sanctum CSRF cookie before making mutating requests. */
export async function getCsrfCookie(): Promise<void> {
  await api.get('/sanctum/csrf-cookie');
}
