<?php

declare(strict_types=1);

namespace Tests\Feature\Admin;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

/**
 * Admin user management: list / details / edit, and the access guards.
 */
class UserManagementTest extends TestCase
{
    use RefreshDatabase;

    private User $admin;

    protected function setUp(): void
    {
        parent::setUp();
        $this->admin = $this->userWithRole('admin');
    }

    /** @param  array<string, mixed>  $overrides */
    private function payload(User $user, array $overrides = []): array
    {
        return [
            'name' => $user->name,
            'email' => $user->email,
            'roles' => $user->getRoleNames()->all(),
            'permissions' => $user->getDirectPermissions()->pluck('name')->all(),
            ...$overrides,
        ];
    }

    public function test_only_user_managers_reach_the_pages(): void
    {
        $target = $this->userWithRole('user');

        $this->actingAs($this->userWithRole('moderator'))->get('/users')->assertForbidden();
        $this->actingAs($this->userWithRole('user'))->get("/users/{$target->id}")->assertForbidden();

        $this->actingAs($this->userWithPermissions(['admin.access', 'users.manage']))->get('/users')->assertOk();
        $this->actingAs($this->admin)->get("/users/{$target->id}/edit")->assertOk();
    }

    public function test_index_filters_by_role_and_search(): void
    {
        $this->userWithRole('moderator')->update(['name' => 'Mona Moderator']);
        User::factory()->create(['name' => 'Rolf Roleless']);

        $this->actingAs($this->admin)->get('/users?role=moderator')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('users/index')
                ->has('users.data', 1)
                ->where('users.data.0.name', 'Mona Moderator')
                ->where('users.data.0.roles', ['moderator'])
                ->where('filters.role', 'moderator')
                ->where('no_role_count', 1)
            );

        $this->actingAs($this->admin)->get('/users?role=none')
            ->assertInertia(fn (Assert $page) => $page->has('users.data', 1)->where('users.data.0.name', 'Rolf Roleless'));

        $this->actingAs($this->admin)->get('/users?search=MONA')
            ->assertInertia(fn (Assert $page) => $page->has('users.data', 1));
    }

    public function test_show_lists_access_and_activity(): void
    {
        $user = $this->userWithRole('history_moderator');

        $this->actingAs($this->admin)->get("/users/{$user->id}")
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('users/show')
                ->where('user.roles', ['history_moderator'])
                ->where('effective_permissions', fn ($perms) => collect($perms)->contains('contributions.review'))
                ->where('stats.contributions.pending', 0)
                ->where('is_self', false)
            );

        $this->actingAs($this->admin)->get("/users/{$this->admin->id}")
            ->assertInertia(fn (Assert $page) => $page->where('effective_permissions', 'all')->where('is_self', true));
    }

    public function test_an_admin_updates_profile_roles_and_permissions(): void
    {
        $user = $this->userWithRole('user');
        $user->forceFill(['email_verified_at' => now()])->save();

        $this->actingAs($this->admin)
            ->put("/users/{$user->id}", $this->payload($user, [
                'name' => 'Renamed',
                'email' => 'New.Address@Example.com',
                'roles' => ['moderator'],
                'permissions' => ['geometry.write'],
            ]))
            ->assertRedirect("/users/{$user->id}");

        $user->refresh();
        $this->assertSame('Renamed', $user->name);
        $this->assertSame('new.address@example.com', $user->email);
        $this->assertNull($user->email_verified_at);
        $this->assertSame(['moderator'], $user->getRoleNames()->all());
        $this->assertTrue($user->hasDirectPermission('geometry.write'));
    }

    public function test_nobody_changes_their_own_access(): void
    {
        $this->actingAs($this->admin)
            ->put("/users/{$this->admin->id}", $this->payload($this->admin, ['roles' => ['user']]))
            ->assertSessionHasErrors('roles');
        $this->assertTrue($this->admin->fresh()->hasRole('admin'));

        // Profile fields alone are fine.
        $this->actingAs($this->admin)
            ->put("/users/{$this->admin->id}", $this->payload($this->admin, ['name' => 'Chief']))
            ->assertSessionHasNoErrors();
        $this->assertSame('Chief', $this->admin->fresh()->name);
    }

    public function test_only_admins_grant_or_revoke_admin(): void
    {
        $manager = $this->userWithPermissions(['admin.access', 'users.manage']);
        $user = $this->userWithRole('user');
        $otherAdmin = $this->userWithRole('admin');

        $this->actingAs($manager)
            ->put("/users/{$user->id}", $this->payload($user, ['roles' => ['admin']]))
            ->assertSessionHasErrors('roles');
        $this->actingAs($manager)
            ->put("/users/{$otherAdmin->id}", $this->payload($otherAdmin, ['roles' => []]))
            ->assertSessionHasErrors('roles');

        // Other roles are within a manager's reach.
        $this->actingAs($manager)
            ->put("/users/{$user->id}", $this->payload($user, ['roles' => ['user', 'geo_moderator']]))
            ->assertSessionHasNoErrors();
        $this->assertTrue($user->fresh()->hasRole('geo_moderator'));

        $this->actingAs($this->admin)
            ->put("/users/{$otherAdmin->id}", $this->payload($otherAdmin, ['roles' => ['moderator']]))
            ->assertSessionHasNoErrors();
        $this->assertFalse($otherAdmin->fresh()->hasRole('admin'));
    }

    public function test_unknown_roles_and_duplicate_emails_are_rejected(): void
    {
        $user = $this->userWithRole('user');

        $this->actingAs($this->admin)
            ->put("/users/{$user->id}", $this->payload($user, ['roles' => ['emperor'], 'email' => $this->admin->email]))
            ->assertSessionHasErrors(['roles.0', 'email']);
    }
}
