/**
 * API barrel. Import the transport (`api`, `getCsrfCookie`) or the typed domain
 * endpoints from here: `import { entitiesInView } from '@/lib/api'`.
 */
export { api, getCsrfCookie } from './client';
export {
  entitiesInView,
  entityList,
  entity,
  entityConnections,
  entityTimeline,
} from './entities';
export { search, searchEntities, highlights, timelineDensity } from './discovery';
export { chronicle, chronicleList, entityChronicles } from './chronicles';
export { historicalPeriods } from './reference';
export {
  fetchEntityGraph,
  fetchChronicleGraph,
  normaliseEntityGraphParams,
  normaliseChronicleGraphParams,
  type EntityGraphParams,
  type ChronicleGraphParams,
} from './graph';
export { mapParams, listParams, type ListOptions } from './params';
