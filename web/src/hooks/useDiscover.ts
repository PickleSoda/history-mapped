import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { dailyQuest, forYou, meanwhile, onThisDay } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';
import { retryUnlessClientError } from './useCollections';

const HOUR = 60 * 60_000;

/** What the atlas has for this month and day (`date`: a local YYYY-MM-DD, see `dayKey`). */
export function useOnThisDay(date: string) {
  return useQuery({
    queryKey: qk.onThisDay(date),
    queryFn: ({ signal }) => onThisDay(date, signal),
    staleTime: HOUR,
    retry: retryUnlessClientError,
  });
}

/**
 * What was going on in each world region in `year`; null turns it off. The
 * last answer stays on screen while the next year loads (the sidebar follows
 * the timeline).
 */
export function useMeanwhile(year: number | null) {
  return useQuery({
    queryKey: qk.meanwhile(year ?? 0),
    queryFn: ({ signal }) => meanwhile(year as number, signal),
    enabled: year !== null,
    staleTime: HOUR,
    placeholderData: keepPreviousData,
    retry: retryUnlessClientError,
  });
}

/** The day's expedition (`date`: a local YYYY-MM-DD). The same for everyone that day. */
export function useDailyQuest(date: string) {
  return useQuery({
    queryKey: qk.dailyQuest(date),
    queryFn: ({ signal }) => dailyQuest(date, signal),
    staleTime: Infinity,
    retry: retryUnlessClientError,
  });
}

/** Suggestions from the entity ids this browser opened lately (most recent first); none, no request. */
export function useForYou(ids: string[]) {
  return useQuery({
    queryKey: qk.forYou(ids),
    queryFn: ({ signal }) => forYou(ids, signal),
    enabled: ids.length > 0,
    staleTime: 10 * 60_000,
    placeholderData: keepPreviousData,
    retry: retryUnlessClientError,
  });
}
