import { useMutation, useQueryClient } from '@tanstack/react-query';
import { forgotPassword, login, logout, register, twoFactorChallenge } from '@/lib/api';
import type { LoginInput, RegisterInput } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';

/**
 * Sign in / register / sign out. Signing in refetches everything personal
 * (profile, stars, folders, contributions); signing out drops it from the
 * cache so the next user never sees the last one's data.
 */
export function useAuthActions() {
  const qc = useQueryClient();
  const refreshPersonal = () => qc.invalidateQueries({ queryKey: qk.personal() });

  const signIn = useMutation({
    mutationFn: (input: LoginInput) => login(input),
    onSuccess: (result) => {
      if (!result.two_factor) return refreshPersonal();
    },
  });

  const twoFactor = useMutation({
    mutationFn: (input: { code: string } | { recovery_code: string }) => twoFactorChallenge(input),
    onSuccess: refreshPersonal,
  });

  const signUp = useMutation({
    mutationFn: (input: RegisterInput) => register(input),
    onSuccess: refreshPersonal,
  });

  const signOut = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      qc.removeQueries({ queryKey: qk.personal() });
      qc.setQueryData(qk.me(), null);
    },
    // A failed sign-out (expired session, …) — ask the server who we are.
    onError: () => qc.invalidateQueries({ queryKey: qk.me() }),
  });

  const resetLink = useMutation({ mutationFn: (email: string) => forgotPassword(email) });

  return { signIn, twoFactor, signUp, signOut, resetLink };
}
