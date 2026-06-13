import { QueryClientProvider } from '@tanstack/react-query';
import { NuqsAdapter } from 'nuqs/adapters/react-router/v7';
import type { ReactNode } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { queryClient } from '@/lib/query/client';

/**
 * App providers. Order matters: nuqs needs the router context, so NuqsAdapter
 * sits inside BrowserRouter. TanStack Query wraps everything.
 */
export function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <NuqsAdapter>{children}</NuqsAdapter>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
