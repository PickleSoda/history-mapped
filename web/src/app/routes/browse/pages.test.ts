// @vitest-environment jsdom
/**
 * Smoke renders of the four browse pages against fixture payloads (stubbed
 * transport, no network): real data renders, unknown tags and sets show the
 * not-found state, and endpoints that 404 (not deployed yet) leave calm
 * notices instead of crashing the page.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, configure, render, screen } from '@testing-library/react';
import { AxiosError } from 'axios';
import type { AxiosResponse } from 'axios';
import { createElement } from 'react';
import type { ComponentType } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '@/lib/api/client';
import {
  chronicleRow,
  collectionDetailPayload,
  collectionListPayload,
  entityRow,
  mapStoryListPayload,
  tagRow,
} from '@/lib/schemas/collection.fixtures';
import { BrowseFacetPage } from './BrowseFacetPage';
import { BrowseIndexPage } from './BrowseIndexPage';
import { CollectionPage } from './CollectionPage';
import { StoriesPage } from './StoriesPage';

// A full parallel run is slow under jsdom; the default 1s wait can flake.
configure({ asyncUtilTimeout: 15_000 });

const meta = { current_page: 1, last_page: 1, per_page: 50, total: 1 };

const tags = {
  data: [
    tagRow,
    { ...tagRow, slug: 'asia', name: 'Asia', facet: 'region', start_year: null, end_year: null },
    { ...tagRow, slug: 'china', name: 'China', facet: 'region', parent: 'asia', start_year: null, end_year: null },
    { ...tagRow, slug: 'polity', name: 'Empire or dynasty', facet: 'type', entity_count: 0 },
  ],
  facets: [],
};

function notFound(): never {
  throw new AxiosError('Not Found', 'ERR_BAD_REQUEST', undefined, undefined, {
    status: 404,
    statusText: 'Not Found',
    data: { message: 'Not Found' },
    headers: {},
    config: {},
  } as AxiosResponse);
}

/** Route the stubbed GETs; `missing` lists endpoints that 404. */
function stubApi(missing: string[] = []) {
  vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
    if (missing.some((m) => url.startsWith(m))) notFound();
    if (url === '/api/v1/tags') return { data: tags };
    if (url === '/api/v1/chronicles') return { data: { data: [chronicleRow], meta } };
    if (url === '/api/v1/entities') return { data: { data: [entityRow], meta } };
    if (url === '/api/v1/collections') return { data: collectionListPayload };
    if (url === '/api/v1/collections/the-roman-world') return { data: collectionDetailPayload };
    if (url === '/api/v1/map-stories') return { data: mapStoryListPayload };
    notFound();
  });
}

function renderAt(path: string, pattern: string, page: ComponentType) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    createElement(
      QueryClientProvider,
      { client },
      createElement(
        MemoryRouter,
        { initialEntries: [path] },
        createElement(Routes, null, createElement(Route, { path: pattern, element: createElement(page) })),
      ),
    ),
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// The first render pays for importing the hook barrel; give it room on a busy machine.
describe('browse pages', { timeout: 30_000 }, () => {
  it('index: sets, facet grids, chronicles and battle maps', async () => {
    stubApi();
    renderAt('/browse', '/browse', BrowseIndexPage);
    expect(await screen.findByRole('link', { name: 'The Roman world' })).toHaveProperty(
      'pathname',
      '/browse/collections/the-roman-world',
    );
    // The era card and the chronicle card's tag chip both link to the era page.
    const era = await screen.findAllByRole('link', { name: /Classical Era/ });
    expect(era.every((a) => a.getAttribute('href') === '/browse/era/classical')).toBe(true);
    expect(await screen.findByRole('link', { name: 'China' })).toHaveProperty('pathname', '/browse/region/china');
    expect(await screen.findByRole('link', { name: 'The Roman World' })).toHaveProperty(
      'pathname',
      '/chronicles/the-roman-world',
    );
    const cannae = await screen.findByRole('link', { name: 'Battle of Cannae' });
    expect(cannae.getAttribute('href')).toBe('/app?story=battle-of-cannae');
    expect(document.title).toBe('Browse · History Mapped');
  });

  it('index: stays calm when the new endpoints 404', async () => {
    stubApi(['/api/v1/collections', '/api/v1/map-stories']);
    renderAt('/browse', '/browse', BrowseIndexPage);
    expect(await screen.findByText('The first curated sets are on their way.')).toBeTruthy();
    expect(await screen.findByText(/battle-map index is on its way/)).toBeTruthy();
    expect((await screen.findAllByRole('link', { name: /Classical Era/ })).length).toBeGreaterThan(0);
  });

  it('facet page: header, chronicles and entities with globe links', async () => {
    stubApi();
    renderAt('/browse/region/asia', '/browse/:facet/:tag', BrowseFacetPage);
    expect(await screen.findByRole('heading', { level: 1, name: 'Asia' })).toBeTruthy();
    expect(await screen.findByRole('link', { name: /China/ })).toHaveProperty('pathname', '/browse/region/china');
    expect(await screen.findByRole('link', { name: 'Roman Empire' })).toHaveProperty(
      'pathname',
      `/entities/${entityRow.id}`,
    );
    const globe = screen.getAllByRole('link', { name: /Open on the globe/ }).map((a) => a.getAttribute('href'));
    expect(globe).toEqual(['/app?chron=the-roman-world', `/app?sel=${entityRow.id}&full=1`]);
    expect(document.title).toBe('Asia · History Mapped');
  });

  it('facet page: an unknown tag is not found', async () => {
    stubApi();
    renderAt('/browse/era/atlantis', '/browse/:facet/:tag', BrowseFacetPage);
    expect(await screen.findByRole('heading', { level: 1, name: 'Nothing is filed under that tag' })).toBeTruthy();
  });

  it('collection: items in the author’s order with notes', async () => {
    stubApi();
    renderAt('/browse/collections/the-roman-world', '/browse/collections/:slug', CollectionPage);
    expect(await screen.findByRole('heading', { level: 1, name: 'The Roman world' })).toBeTruthy();
    const items = await screen.findAllByLabelText(/^Item \d$/);
    expect(items.map((i) => i.textContent)).toEqual(['1', '2', '3', '4']);
    expect(screen.getByText('Start here.')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Wikipedia' }).getAttribute('target')).toBe('_blank');
    expect(document.title).toBe('The Roman world · History Mapped');
  });

  it('collection: an unknown set is not found', async () => {
    stubApi();
    renderAt('/browse/collections/nope', '/browse/collections/:slug', CollectionPage);
    expect(await screen.findByRole('heading', { level: 1, name: 'No such curated set' })).toBeTruthy();
  });

  it('stories: cards link to the globe and to the entity', async () => {
    stubApi();
    renderAt('/browse/stories', '/browse/stories', StoriesPage);
    expect((await screen.findByRole('link', { name: 'Siege of Alesia' })).getAttribute('href')).toBe(
      '/app?story=siege-of-alesia',
    );
    expect(screen.getByRole('link', { name: 'Read about Battle of Cannae' }).getAttribute('href')).toBe(
      `/entities/${mapStoryListPayload.data[0].entity?.id}`,
    );
    expect(screen.getByRole('button', { name: /Sieges/ })).toBeTruthy();
  });
});
