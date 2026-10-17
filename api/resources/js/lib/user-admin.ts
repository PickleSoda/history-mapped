/** Pure helpers for the admin user edit form. */

/** Add or remove `name` from a list of names, keeping it duplicate-free. */
export function toggleName(
    list: string[],
    name: string,
    checked: boolean,
): string[] {
    const without = list.filter((n) => n !== name);

    return checked ? [...without, name] : without;
}

/** Every permission the selected roles grant, so direct grants can say so. */
export function permissionsFromRoles(
    availableRoles: { name: string; permissions: string[] }[],
    selected: string[],
): Set<string> {
    const granted = new Set<string>();

    for (const role of availableRoles) {
        if (selected.includes(role.name)) {
            role.permissions.forEach((p) => granted.add(p));
        }
    }

    return granted;
}
