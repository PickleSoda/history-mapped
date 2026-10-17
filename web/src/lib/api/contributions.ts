/** Suggested text edits: submit, list my own, withdraw. */
import { ContributionListSchema, ContributionSchema } from '@/lib/schemas/contribution';
import type {
  Contribution,
  ContributionList,
  ContributionStatus,
  ContributionTargetType,
} from '@/lib/schemas/contribution';
import { api, getCsrfCookie } from './client';

const unwrap = (data: unknown) => (data as { data?: unknown }).data ?? data;

export interface ContributionInput {
  target_type: ContributionTargetType;
  target_id: string;
  field: string;
  proposed_text: string;
  note?: string | null;
}

/** POST /contributions — queued for staff review. */
export async function submitContribution(input: ContributionInput): Promise<Contribution> {
  await getCsrfCookie();
  const { data } = await api.post('/api/v1/contributions', input);
  return ContributionSchema.parse(unwrap(data));
}

export interface MyContributionsParams {
  status?: ContributionStatus | null;
  page?: number;
}

/** GET /me/contributions — the user's own submissions, newest first. */
export async function myContributions(
  params: MyContributionsParams,
  signal?: AbortSignal,
): Promise<ContributionList> {
  const { data } = await api.get('/api/v1/me/contributions', {
    signal,
    params: { status: params.status ?? undefined, page: params.page ?? 1 },
  });
  return ContributionListSchema.parse(data);
}

/** POST /me/contributions/{id}/withdraw — only while pending. */
export async function withdrawContribution(id: number): Promise<Contribution> {
  await getCsrfCookie();
  const { data } = await api.post(`/api/v1/me/contributions/${id}/withdraw`);
  return ContributionSchema.parse(unwrap(data));
}
