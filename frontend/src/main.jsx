import React from "react";
import { createRoot } from "react-dom/client";
import { resolveUi } from "./ui.js";

const ui = resolveUi();
document.documentElement.dataset.ui = ui;

// Each interface brings its own global stylesheet, so only the chosen one is loaded.
const load =
  ui === "classic"
    ? () => Promise.all([import("./classic/App.jsx"), import("./classic/styles.css")])
    : () => Promise.all([import("./next/App.jsx"), import("./next/styles/index.css")]);

const RELOADED = "fadir.chunk-reload";

load().then(([{ default: App }]) => {
  try { sessionStorage.removeItem(RELOADED); } catch { /* private mode */ }
  createRoot(document.getElementById("root")).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}).catch((error) => {
  // A deploy removed the bundles an older shell names: one reload fetches the new shell.
  // Only once, and only where the attempt can be remembered, so it can never loop.
  let retry = false;
  try {
    retry = sessionStorage.getItem(RELOADED) !== "1";
    sessionStorage.setItem(RELOADED, "1");
  } catch { /* storage blocked: no reload */ }
  if (retry) window.location.reload();
  else throw error;
});
