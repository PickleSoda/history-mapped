<?php

declare(strict_types=1);

namespace App\Actions\User;

use App\Models\User;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\ValidationException;

/**
 * Edit an account from the admin: profile, roles and direct permissions.
 *
 * Guards against locking the panel or escalating privileges:
 * - nobody changes their own roles or permissions here;
 * - only an `admin` grants or revokes the `admin` role;
 * - the last `admin` keeps it.
 * A changed email is no longer verified.
 */
class UpdateUserAction
{
    public const ADMIN_ROLE = 'admin';

    /**
     * @param  array{name: string, email: string, roles: list<string>, permissions: list<string>}  $data
     */
    public function __invoke(User $editor, User $user, array $data): User
    {
        $roles = array_values(array_unique($data['roles']));
        $permissions = array_values(array_unique($data['permissions']));
        $currentRoles = $user->getRoleNames()->all();
        $currentPermissions = $user->getDirectPermissions()->pluck('name')->all();

        $accessChanged = self::differ($roles, $currentRoles) || self::differ($permissions, $currentPermissions);
        if ($accessChanged && $editor->is($user)) {
            throw ValidationException::withMessages(['roles' => 'You cannot change your own roles or permissions.']);
        }

        $wasAdmin = in_array(self::ADMIN_ROLE, $currentRoles, true);
        $willBeAdmin = in_array(self::ADMIN_ROLE, $roles, true);
        if ($wasAdmin !== $willBeAdmin && ! $editor->hasRole(self::ADMIN_ROLE)) {
            throw ValidationException::withMessages(['roles' => 'Only an admin can grant or revoke the admin role.']);
        }
        if ($wasAdmin && ! $willBeAdmin && User::role(self::ADMIN_ROLE)->count() <= 1) {
            throw ValidationException::withMessages(['roles' => 'The last admin cannot lose the admin role.']);
        }

        return DB::transaction(function () use ($user, $data, $roles, $permissions, $accessChanged): User {
            // Fortify lowercases the login email (`lowercase_usernames`), so
            // stored emails must be lowercase or the account cannot sign in.
            $user->fill(['name' => trim($data['name']), 'email' => mb_strtolower(trim($data['email']))]);
            if ($user->isDirty('email')) {
                $user->email_verified_at = null;
            }
            $user->save();

            if ($accessChanged) {
                $user->syncRoles($roles);
                $user->syncPermissions($permissions);
            }

            return $user->refresh();
        });
    }

    /**
     * @param  list<string>  $a
     * @param  list<string>  $b
     */
    private static function differ(array $a, array $b): bool
    {
        sort($a);
        sort($b);

        return $a !== $b;
    }
}
