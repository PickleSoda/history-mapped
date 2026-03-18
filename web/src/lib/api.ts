import axios from 'axios';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  withCredentials: true,
  headers: {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  },
});

/**
 * Fetch the Sanctum CSRF cookie before making mutating requests.
 */
export async function getCsrfCookie(): Promise<void> {
  await api.get('/sanctum/csrf-cookie');
}
