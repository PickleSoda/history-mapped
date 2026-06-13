/**
 * API barrel. Import the transport (`api`, `getCsrfCookie`) or the typed domain
 * endpoints from here: `import { entitiesInView } from '@/lib/api'`.
 */
export { api, getCsrfCookie } from './client';
export { entitiesInView, entityList, entity, entityConnections } from './entities';
export { search, highlights, timelineDensity } from './discovery';
export { chronicle, chronicleList, entityChronicles } from './chronicles';
export { mapParams, listParams, type ListOptions } from './params';
