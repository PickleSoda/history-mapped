import { Outlet } from 'react-router-dom';

/** `/docs` frame: sidebar + page (spec D5). Skeleton; track C replaces it. */
export function DocsLayout() {
  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8">
      <Outlet />
    </div>
  );
}
