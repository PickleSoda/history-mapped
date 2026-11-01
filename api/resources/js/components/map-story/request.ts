import type { StorySummary } from '@/lib/map-story-doc';

/** JSON requests from the map-story editor (session auth). */
export async function storyRequest<T>(
    url: string,
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    body?: unknown,
    signal?: AbortSignal,
): Promise<{ ok: boolean; status: number; data: T }> {
    // Same-origin requests pass the CSRF check on their own; send the XSRF cookie too, as axios would.
    const xsrf = /(?:^|; )XSRF-TOKEN=([^;]*)/.exec(document.cookie)?.[1];
    const res = await fetch(url, {
        method,
        signal,
        credentials: 'same-origin',
        headers: {
            Accept: 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            ...(body !== undefined
                ? { 'Content-Type': 'application/json' }
                : {}),
            ...(xsrf ? { 'X-XSRF-TOKEN': decodeURIComponent(xsrf) } : {}),
        },
        body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    let data: unknown = null;

    try {
        data = await res.json();
    } catch {
        data = null;
    }

    return { ok: res.ok, status: res.status, data: data as T };
}

/** The editor's view of a save / restore / validate response. */
export type SaveResponse = {
    story?: StorySummary;
    document_json?: string;
    errors: string[];
    warnings: string[];
    message?: string;
};
