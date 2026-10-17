export type User = {
    id: number;
    name: string;
    email: string;
    avatar?: string;
    email_verified_at: string | null;
    two_factor_enabled?: boolean;
    created_at: string;
    updated_at: string;
    [key: string]: unknown;
};

export type AuthCan = {
    access_admin: boolean;
    review_contributions: boolean;
    manage_users?: boolean;
};

export type Auth = {
    user: User;
    /** Capabilities shared by HandleInertiaRequests (optional on older payloads). */
    can?: AuthCan;
};

export type TwoFactorSetupData = {
    svg: string;
    url: string;
};

export type TwoFactorSecretKey = {
    secretKey: string;
};
