import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { myContributions, submitContribution, withdrawContribution } from '@/lib/api';
import type { ContributionInput, MyContributionsParams } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';
import { useMe } from './useMe';

/** A page of the user's own submissions. */
export function useMyContributions(params: MyContributionsParams) {
  const { me } = useMe();
  return useQuery({
    queryKey: qk.myContributions(params),
    queryFn: ({ signal }) => myContributions(params, signal),
    enabled: me != null,
    placeholderData: keepPreviousData,
  });
}

export function useSubmitContribution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: ContributionInput) => submitContribution(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.contributions() }),
  });
}

export function useWithdrawContribution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => withdrawContribution(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.contributions() }),
  });
}
