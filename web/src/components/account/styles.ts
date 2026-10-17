/** Shared class strings for the account popups (menu, popover, dialog). */

/** Floating surface for menus and popovers. Fades in/out; instant under
 *  prefers-reduced-motion. */
export const POPUP =
  'origin-[var(--transform-origin)] rounded-xl border bg-popover p-1.5 text-popover-foreground shadow-lg outline-none transition-[opacity,scale] duration-150 data-[ending-style]:scale-95 data-[ending-style]:opacity-0 data-[starting-style]:scale-95 data-[starting-style]:opacity-0 motion-reduce:transition-none';

/** A row in a menu / popover list. */
export const MENU_ITEM =
  'flex w-full cursor-default select-none items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px] outline-none data-[highlighted]:bg-muted hover:bg-muted focus-visible:bg-muted';

/** Text input / textarea. */
export const FIELD =
  'w-full rounded-lg border bg-background px-3 py-2 text-[13px] outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-invalid:border-destructive';

/** Folder colour swatches (picked at create/rename). */
export const FOLDER_COLORS = ['#b4532a', '#2f6f8f', '#5b7a3a', '#8a4f9e', '#b08a1e', '#6b6b6b'] as const;
