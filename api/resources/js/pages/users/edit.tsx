import { Head, Link, useForm } from '@inertiajs/react';
import { ArrowLeft, Lock } from 'lucide-react';
import type { FormEvent } from 'react';
import InputError from '@/components/input-error';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { roleLabel, sortRoles } from '@/components/user-badges';
import AppLayout from '@/layouts/app-layout';
import { permissionsFromRoles, toggleName } from '@/lib/user-admin';
import type { BreadcrumbItem, UserEditForm, UserEditProps } from '@/types';

export default function UserEdit({
    user,
    roles,
    permissions,
    available_roles,
    available_permissions,
    is_self,
    can_assign_admin,
}: UserEditProps) {
    const form = useForm<UserEditForm>({
        name: user.name,
        email: user.email,
        roles,
        permissions,
    });
    const errors = form.errors as Partial<Record<string, string>>;
    // Array items fail as `roles.0`; show those under the list too.
    const listError = (key: string) =>
        errors[key] ??
        Object.entries(errors).find(([k]) => k.startsWith(`${key}.`))?.[1];
    const viaRoles = permissionsFromRoles(available_roles, form.data.roles);
    const orderedRoles = sortRoles(available_roles.map((r) => r.name)).map(
        (name) => available_roles.find((r) => r.name === name)!,
    );

    const breadcrumbs: BreadcrumbItem[] = [
        { title: 'Dashboard', href: '/dashboard' },
        { title: 'Users', href: '/users' },
        { title: user.name, href: `/users/${user.id}` },
        { title: 'Edit', href: `/users/${user.id}/edit` },
    ];

    const submit = (e: FormEvent) => {
        e.preventDefault();
        form.put(`/users/${user.id}`, { preserveScroll: true });
    };

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title={`Edit ${user.name}`} />

            <form
                onSubmit={submit}
                className="flex max-w-3xl flex-col gap-4 p-4"
            >
                <Link
                    href={`/users/${user.id}`}
                    className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
                >
                    <ArrowLeft className="size-4" />
                    Back to {user.name}
                </Link>

                <h1 className="text-2xl font-bold tracking-tight">
                    Edit {user.name}
                </h1>

                {/* Profile */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Profile</CardTitle>
                        <CardDescription>
                            Changing the email marks it as unverified.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="grid gap-4 sm:grid-cols-2">
                        <div className="grid gap-2">
                            <Label htmlFor="name">Name</Label>
                            <Input
                                id="name"
                                value={form.data.name}
                                onChange={(e) =>
                                    form.setData('name', e.target.value)
                                }
                                required
                                maxLength={255}
                                aria-invalid={errors.name ? true : undefined}
                            />
                            <InputError message={errors.name} />
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="email">Email</Label>
                            <Input
                                id="email"
                                type="email"
                                value={form.data.email}
                                onChange={(e) =>
                                    form.setData('email', e.target.value)
                                }
                                required
                                maxLength={255}
                                aria-invalid={errors.email ? true : undefined}
                            />
                            <InputError message={errors.email} />
                        </div>
                    </CardContent>
                </Card>

                {is_self && (
                    <Alert>
                        <Lock />
                        <AlertDescription>
                            You can’t change your own roles or permissions — ask
                            another administrator.
                        </AlertDescription>
                    </Alert>
                )}

                {/* Roles */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Roles</CardTitle>
                        <CardDescription>
                            Roles bundle permissions. Admin is a super-user and
                            passes every check.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <fieldset
                            disabled={is_self}
                            className="flex flex-col gap-3 disabled:opacity-60"
                        >
                            <legend className="sr-only">Roles</legend>
                            {orderedRoles.map((role) => {
                                const id = `role-${role.name}`;
                                const locked =
                                    is_self ||
                                    (role.name === 'admin' &&
                                        !can_assign_admin);

                                return (
                                    <div
                                        key={role.name}
                                        className="flex items-start gap-2.5"
                                    >
                                        <Checkbox
                                            id={id}
                                            checked={form.data.roles.includes(
                                                role.name,
                                            )}
                                            disabled={locked}
                                            onCheckedChange={(v) =>
                                                form.setData(
                                                    'roles',
                                                    toggleName(
                                                        form.data.roles,
                                                        role.name,
                                                        v === true,
                                                    ),
                                                )
                                            }
                                        />
                                        <div className="grid gap-0.5">
                                            <Label htmlFor={id}>
                                                {roleLabel(role.name)}
                                            </Label>
                                            <p className="text-xs text-muted-foreground">
                                                {role.name === 'admin'
                                                    ? can_assign_admin
                                                        ? 'Everything.'
                                                        : 'Everything. Only an admin can grant or revoke this role.'
                                                    : role.permissions.length >
                                                        0
                                                      ? role.permissions.join(
                                                            ', ',
                                                        )
                                                      : 'No permissions.'}
                                            </p>
                                        </div>
                                    </div>
                                );
                            })}
                        </fieldset>
                        <InputError
                            message={listError('roles')}
                            className="mt-3"
                        />
                    </CardContent>
                </Card>

                {/* Direct permissions */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">
                            Direct permissions
                        </CardTitle>
                        <CardDescription>
                            Granted on top of the roles above. Roles usually
                            cover what you need — use these for one-off access.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <fieldset
                            disabled={is_self}
                            className="grid gap-3 disabled:opacity-60 sm:grid-cols-2"
                        >
                            <legend className="sr-only">
                                Direct permissions
                            </legend>
                            {available_permissions.map((permission) => {
                                const id = `permission-${permission}`;

                                return (
                                    <div
                                        key={permission}
                                        className="flex items-start gap-2.5"
                                    >
                                        <Checkbox
                                            id={id}
                                            checked={form.data.permissions.includes(
                                                permission,
                                            )}
                                            disabled={is_self}
                                            onCheckedChange={(v) =>
                                                form.setData(
                                                    'permissions',
                                                    toggleName(
                                                        form.data.permissions,
                                                        permission,
                                                        v === true,
                                                    ),
                                                )
                                            }
                                        />
                                        <div className="grid gap-0.5">
                                            <Label
                                                htmlFor={id}
                                                className="font-mono text-xs"
                                            >
                                                {permission}
                                            </Label>
                                            {viaRoles.has(permission) && (
                                                <p className="text-xs text-muted-foreground">
                                                    Already granted by a role
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </fieldset>
                        <InputError
                            message={listError('permissions')}
                            className="mt-3"
                        />
                    </CardContent>
                </Card>

                <div className="flex gap-2">
                    <Button type="submit" disabled={form.processing}>
                        Save changes
                    </Button>
                    <Button variant="outline" asChild>
                        <Link href={`/users/${user.id}`}>Cancel</Link>
                    </Button>
                </div>
            </form>
        </AppLayout>
    );
}
