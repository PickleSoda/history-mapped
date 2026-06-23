/** Hook inventory barrel (spec §5). Components read the app through these. */

// URL-state
export { useViewport } from './useViewport';
export { useTimeState } from './useTimeState';
export { useFilters } from './useFilters';
export { useSelection } from './useSelection';
export { useSearchQuery } from './useSearchQuery';
export { useChronicleNav } from './useChronicleNav';
export { useView } from './useView';

// Derived
export { useScope } from './useScope';
export { useNavTrail, useNavTrailSync } from './useNavTrail';

// Server-cache
export { useEntitiesInView } from './useEntitiesInView';
export { useEntityList } from './useEntityList';
export { useEntity, useEntityConnections } from './useEntity';
export { useEntityGeometries } from './useEntityGeometries';
export { useSearch, useHighlights, useTimelineDensity } from './useDiscovery';
export { useEntitySearch } from './useEntitySearch';
export { useChronicle } from './useChronicle';
export { useChronicleList } from './useChronicleList';
export { useEntityChronicles } from './useEntityChronicles';
export { usePrefetchEntity } from './usePrefetchEntity';
export { useHistoricalPeriods } from './useHistoricalPeriods';

// Ephemeral / imperative
export {
  useMapInstance,
  useLiveScrub,
  useHover,
  useSheet,
  useCommandPalette,
} from './ephemeral';
export { useMapFocus } from './useMapFocus';

// Sheet logic
export { useSheetContent } from './useSheetContent';
export { useSheetSelectionSync } from './useSheetSelectionSync';

// Responsive
export { useMediaQuery, useIsMobile } from './useMediaQuery';
