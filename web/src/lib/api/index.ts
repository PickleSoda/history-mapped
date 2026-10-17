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
export {
  me,
  login,
  twoFactorChallenge,
  register,
  logout,
  forgotPassword,
  type LoginInput,
  type RegisterInput,
} from './auth';
export {
  starKeys,
  stars,
  star,
  unstar,
  folders,
  createFolder,
  updateFolder,
  deleteFolder,
  addToFolder,
  removeFromFolder,
  type StarListParams,
  type FolderInput,
} from './saved';
export {
  submitContribution,
  myContributions,
  withdrawContribution,
  type ContributionInput,
  type MyContributionsParams,
} from './contributions';
export { errorMessage, errorStatus, fieldErrors } from './errors';
