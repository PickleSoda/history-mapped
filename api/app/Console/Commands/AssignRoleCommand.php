<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Models\User;
use Illuminate\Console\Command;
use Spatie\Permission\Models\Role;

class AssignRoleCommand extends Command
{
    protected $signature = 'user:role
        {email : The email of the user}
        {role : The role name (admin, moderator, geo_moderator, history_moderator, user)}
        {--remove : Remove the role instead of assigning it}';

    protected $description = 'Assign or remove a role for a user (RBAC).';

    public function handle(): int
    {
        $email = (string) $this->argument('email');
        $role = (string) $this->argument('role');

        $user = User::where('email', $email)->first();
        if ($user === null) {
            $this->error("No user found with email [{$email}].");

            return self::FAILURE;
        }

        if (Role::where('name', $role)->doesntExist()) {
            $available = Role::query()->pluck('name')->implode(', ');
            $this->error("Role [{$role}] does not exist. Available roles: {$available}");

            return self::FAILURE;
        }

        if ($this->option('remove')) {
            $user->removeRole($role);
            $this->info("Removed role [{$role}] from {$email}.");
        } else {
            $user->assignRole($role);
            $this->info("Assigned role [{$role}] to {$email}.");
        }

        $this->line('Current roles: '.$user->getRoleNames()->implode(', '));

        return self::SUCCESS;
    }
}
