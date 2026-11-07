// Which interface this browser runs: the rebuilt one ("next") or the original ("classic").
//
// Precedence, highest first:
//   1. `?ui=classic` / `?ui=next` in the URL — also remembered, so a shared link sticks.
//   2. The choice saved in localStorage by the in-app switch.
//   3. The build default: `VITE_UI=classic npm run build` ships the classic UI by default.
//
// Both interfaces are lazy chunks, so the one not chosen is never downloaded.

const KEY = "fadir.ui";
const CHOICES = new Set(["classic", "next"]);

export const BUILD_DEFAULT_UI = import.meta.env.VITE_UI === "classic" ? "classic" : "next";

function readStored() {
  try {
    const value = localStorage.getItem(KEY);
    return CHOICES.has(value) ? value : null;
  } catch {
    return null;
  }
}

function store(value) {
  try {
    localStorage.setItem(KEY, value);
  } catch {
    /* private mode: the choice lasts for this page only */
  }
}

export function resolveUi() {
  const params = new URLSearchParams(window.location.search);
  const requested = params.get("ui");
  if (CHOICES.has(requested)) {
    store(requested);
    params.delete("ui");
    const query = params.toString();
    window.history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`);
    return requested;
  }
  return readStored() ?? BUILD_DEFAULT_UI;
}

/** Persist the choice and reload into it. */
export function switchUi(target) {
  if (!CHOICES.has(target)) return;
  store(target);
  window.location.reload();
}
