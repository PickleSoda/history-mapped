<?php

declare(strict_types=1);

namespace App\Http\Controllers\Admin;

use App\Actions\Contribution\DescribeContributionTargetsAction;
use App\Actions\User\UpdateUserAction;
use App\Enums\ContributionStatus;
use App\Http\Controllers\Controller;
use App\Http\Requests\Admin\UpdateUserRequest;
use App\Models\Contribution;
use App\Models\User;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;
use Spatie\Permission\Models\Permission;
use Spatie\Permission\Models\Role;

/**
 * Admin user management: list with role filter, details, and editing of the
 * profile, roles and direct permissions (guards in UpdateUserAction).
 */
class UserController extends Controller
{
    public function index(Request $request): Response
    {
        $role = (string) $request->query('role', '');
        $search = trim((string) $request->query('search', ''));

        $users = User::query()
            ->with('roles:id,name')
            ->withCount('contributions')
            ->when($role === 'none', fn ($q) => $q->whereDoesntHave('roles'))
            ->when($role !== '' && $role !== 'none', fn ($q) => $q->whereHas('roles', fn ($r) => $r->where('name', $role)))
            ->when($search !== '', function ($q) use ($search) {
                $like = '%'.addcslashes(mb_strtolower($search), '%_\\').'%';
                $q->where(fn ($w) => $w->whereRaw('lower(name) like ?', [$like])->orWhereRaw('lower(email) like ?', [$like]));
            })
            ->orderBy('name')
            ->orderBy('id')
            ->paginate(25)
            ->withQueryString();

        return Inertia::render('users/index', [
            'users' => $users->through(fn (User $u) => self::row($u)),
            'filters' => ['role' => $role, 'search' => $search],
            'roles' => Role::query()->withCount('users')->orderBy('name')->get()
                ->map(fn (Role $r) => ['name' => $r->name, 'users_count' => $r->users_count])->values(),
            'no_role_count' => User::query()->whereDoesntHave('roles')->count(),
        ]);
    }

    public function show(Request $request, User $user, DescribeContributionTargetsAction $describe): Response
    {
        $user->load('roles:id,name')->loadCount(['contributions', 'stars', 'savedFolders']);

        $byStatus = $user->contributions()->toBase()
            ->selectRaw('status, count(*) as n')->groupBy('status')->pluck('n', 'status');
        $recent = $user->contributions()->latest()->orderByDesc('id')->limit(10)->get();
        $info = $describe($recent);

        return Inertia::render('users/show', [
            'user' => [...self::row($user), 'updated_at' => $user->updated_at?->toISOString()],
            'direct_permissions' => $user->getDirectPermissions()->pluck('name')->sort()->values(),
            'effective_permissions' => $user->hasRole(UpdateUserAction::ADMIN_ROLE)
                ? 'all'
                : $user->getAllPermissions()->pluck('name')->sort()->values(),
            'stats' => [
                'stars' => $user->stars_count,
                'folders' => $user->saved_folders_count,
                'contributions' => collect(ContributionStatus::cases())
                    ->mapWithKeys(fn (ContributionStatus $s) => [$s->value => (int) ($byStatus[$s->value] ?? 0)]),
            ],
            'recent_contributions' => $recent->map(fn (Contribution $c) => [
                'id' => $c->id,
                'target_type' => $c->target_type->value,
                'field' => $c->field,
                'target_label' => $info[DescribeContributionTargetsAction::key($c)]['label'] ?? 'Removed record',
                'status' => $c->status->value,
                'created_at' => $c->created_at?->toISOString(),
            ])->values(),
            'is_self' => $request->user()->is($user),
        ]);
    }

    public function edit(Request $request, User $user): Response
    {
        return Inertia::render('users/edit', [
            'user' => $user->only(['id', 'name', 'email']),
            'roles' => $user->getRoleNames()->values(),
            'permissions' => $user->getDirectPermissions()->pluck('name')->values(),
            'available_roles' => Role::query()->with('permissions:id,name')->orderBy('name')->get()
                ->map(fn (Role $r) => [
                    'name' => $r->name,
                    'permissions' => $r->permissions->pluck('name')->sort()->values(),
                ])->values(),
            'available_permissions' => Permission::query()->orderBy('name')->pluck('name'),
            'is_self' => $request->user()->is($user),
            'can_assign_admin' => $request->user()->hasRole(UpdateUserAction::ADMIN_ROLE),
        ]);
    }

    public function update(UpdateUserRequest $request, User $user, UpdateUserAction $update): RedirectResponse
    {
        $update($request->user(), $user, $request->validated());

        return to_route('users.show', $user);
    }

    /** @return array<string, mixed> */
    private static function row(User $u): array
    {
        return [
            'id' => $u->id,
            'name' => $u->name,
            'email' => $u->email,
            'roles' => $u->roles->pluck('name')->sort()->values()->all(),
            'email_verified_at' => $u->email_verified_at?->toISOString(),
            'two_factor_enabled' => $u->two_factor_confirmed_at !== null,
            'contributions_count' => (int) ($u->contributions_count ?? 0),
            'created_at' => $u->created_at?->toISOString(),
        ];
    }
}
