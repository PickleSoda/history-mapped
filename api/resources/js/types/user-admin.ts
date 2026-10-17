/**
 * Admin user management (users.manage) as served to the users/* pages.
 * Contract: docs/superpowers/specs/2026-10-18-user-accounts-saved-contributions-design.md §7.
 */
import type {
    ContributionStatus,
    ContributionTargetType,
} from './contribution';
import type { PaginatedData } from './entity';

export type UserRow = {
    id: number;
    name: string;
    email: string;
    roles: string[];
    email_verified_at: string | null;
    two_factor_enabled: boolean;
    contributions_count: number;
    created_at: string;
};

export type PaginatedUsers = PaginatedData<UserRow>;

export type UserFilters = {
    /** A role name, `none` (no role at all), or '' for every user. */
    role: string;
    search: string;
};

export type UsersIndexProps = {
    users: PaginatedUsers;
    filters: UserFilters;
    roles: { name: string; users_count: number }[];
    no_role_count: number;
};

export type UserRecentContribution = {
    id: number;
    target_type: ContributionTargetType;
    field: string;
    target_label: string;
    status: ContributionStatus;
    created_at: string;
};

export type UserShowProps = {
    user: UserRow & { updated_at: string };
    direct_permissions: string[];
    /** Every permission the user holds, or 'all' for the admin super-user. */
    effective_permissions: string[] | 'all';
    stats: {
        stars: number;
        folders: number;
        contributions: Record<ContributionStatus, number>;
    };
    recent_contributions: UserRecentContribution[];
    is_self: boolean;
};

export type UserEditProps = {
    user: { id: number; name: string; email: string };
    /** The user's current role names. */
    roles: string[];
    /** The user's current direct permission names. */
    permissions: string[];
    available_roles: { name: string; permissions: string[] }[];
    available_permissions: string[];
    is_self: boolean;
    can_assign_admin: boolean;
};

export type UserEditForm = {
    name: string;
    email: string;
    roles: string[];
    permissions: string[];
};
