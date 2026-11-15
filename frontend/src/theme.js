// Light/dark follows the system until the user overrides it. The override is stored only
// while it differs from the system, so toggling back hands control to the system again;
// a stored value is never dropped just because the system later comes to match it.
// index.html applies the same rule before first paint.

const KEY = "fadir.theme";
const lightQuery = window.matchMedia("(prefers-color-scheme: light)");

const valid = (v) => (v === "light" || v === "dark" ? v : null);

function read() {
  try { return valid(localStorage.getItem(KEY)); } catch { return null; }
}

let override = read();

export const systemTheme = () => (lightQuery.matches ? "light" : "dark");

/** Paints the current choice: data-theme for our CSS, the meta for native UI. */
function apply() {
  const theme = override ?? systemTheme();
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="color-scheme"]')?.setAttribute("content", override ?? "light dark");
  return theme;
}

export const currentTheme = apply;

/** Switches to the opposite of what is on screen and returns the new theme. */
export function toggleTheme() {
  const next = (override ?? systemTheme()) === "dark" ? "light" : "dark";
  override = next === systemTheme() ? null : next;
  try {
    if (override) localStorage.setItem(KEY, override);
    else localStorage.removeItem(KEY);
  } catch {
    /* private mode: the choice holds for this page only */
  }
  return apply();
}

/** Calls onChange with the theme when the system scheme or another tab changes it. */
export function watchTheme(onChange) {
  const onSystem = () => onChange(apply());
  const onStorage = (e) => {
    if (e.key !== KEY && e.key !== null) return;
    override = read();
    onChange(apply());
  };
  lightQuery.addEventListener("change", onSystem);
  window.addEventListener("storage", onStorage);
  return () => {
    lightQuery.removeEventListener("change", onSystem);
    window.removeEventListener("storage", onStorage);
  };
}
