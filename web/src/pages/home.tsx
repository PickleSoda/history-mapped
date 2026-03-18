import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';

export default function Home() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get('/api/v1/health').then((r) => r.data),
  });

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-gray-900">WikiGlobe</h1>
        <p className="mt-2 text-gray-600">Customer-facing SPA</p>
        <div className="mt-6 rounded-lg border bg-white p-4 text-sm text-gray-500">
          {health.isLoading && <span>Checking API...</span>}
          {health.isError && (
            <span className="text-red-500">API unreachable</span>
          )}
          {health.isSuccess && (
            <span className="text-green-600">
              API status: {health.data.status}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
