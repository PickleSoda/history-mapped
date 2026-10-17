/** Zod schema for GET /api/v1/me — the signed-in user and what they may do. */
import { z } from 'zod';

const CanSchema = z.object({
  access_admin: z.boolean().catch(false),
  contribute: z.boolean().catch(false),
  review_contributions: z.boolean().catch(false),
});

export const MeSchema = z.object({
  id: z.number(),
  name: z.string(),
  email: z.string(),
  roles: z.array(z.string()).catch([]),
  can: CanSchema.catch({ access_admin: false, contribute: false, review_contributions: false }),
  /** The Inertia admin dashboard on the API host. */
  admin_url: z.string().nullable().catch(null),
});
export type Me = z.infer<typeof MeSchema>;

/** POST /login — `two_factor: true` means a 2FA code is still owed. */
export const LoginResultSchema = z.object({
  two_factor: z.boolean().catch(false),
});
export type LoginResult = z.infer<typeof LoginResultSchema>;
