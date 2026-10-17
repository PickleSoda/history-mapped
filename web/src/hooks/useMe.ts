import { useQuery } from '@tanstack/react-query';
import { useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { me } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';

/** The signed-in user (`me` null = guest). One GET /me per session; a 401 is
 *  a guest, not an error, so it is never retried. */
export function useMe() {
  const query = useQuery({
    queryKey: qk.me(),
    queryFn: ({ signal }) => me(signal),
    staleTime: 5 * 60_000,
    retry: false,
  });
  return { ...query, me: query.data ?? null };
}

/** A safe in-app `next` target: a same-origin path, never `//host` (nor
 *  `/\host`, which URL parsing treats the same). */
export function safeNext(next: string | null | undefined, fallback = '/'): string {
  return next && /^\/(?![/\\])/.test(next) ? next : fallback;
}

/** Send a guest to sign in, coming back to where they are now. */
export function useLoginRedirect() {
  const navigate = useNavigate();
  const location = useLocation();
  return useCallback(() => {
    const here = `${location.pathname}${location.search}`;
    navigate(`/login?next=${encodeURIComponent(here)}`);
  }, [navigate, location.pathname, location.search]);
}
