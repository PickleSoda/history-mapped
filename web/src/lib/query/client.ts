import { QueryClient } from '@tanstack/react-query';

/**
 * Historical data is immutable, so we cache hard. Per-query overrides bump
 * `staleTime` to Infinity for entity detail and chronicles.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60_000,
      gcTime: 30 * 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});
