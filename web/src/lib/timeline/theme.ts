/**
 * Canvas-safe theme helpers for the timeline. timescope draws on a `<canvas>`,
 * where `var(--…)` does not resolve and oklch() tokens are unreliable — so we
 * derive plain hex from the active light/dark theme instead.
 */

/** The app's sans family (Geist), matching the rest of the UI. */
export const APP_FONT_FAMILY = "'Geist Variable', sans-serif";

/** True when the dark theme class is active on <html>. */
export function isDarkTheme(): boolean {
  return (
    typeof document !== 'undefined' &&
    document.documentElement.classList.contains('dark')
  );
}

/** Readable text colour for canvas labels in the active theme. */
export function labelTextColor(): string {
  return isDarkTheme() ? '#fafafa' : '#0a0a0a';
}

/** Contrasting outline colour so labels stay legible over coloured spans. */
export function labelOutlineColor(): string {
  return isDarkTheme() ? '#0a0a0a' : '#ffffff';
}

/** Muted colour for time-axis tick labels (approximates --muted-foreground). */
export function axisLabelColor(): string {
  return isDarkTheme() ? '#a3a3a3' : '#737373';
}

/** Subtle colour for the axis line and ticks (approximates --border). */
export function axisLineColor(): string {
  return isDarkTheme() ? '#3f3f3f' : '#d4d4d4';
}
