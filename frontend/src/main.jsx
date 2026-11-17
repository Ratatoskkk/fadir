import React from "react";
import { createRoot } from "react-dom/client";

const load = () => Promise.all([import("./next/App.jsx"), import("./next/styles/index.css")]);

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
