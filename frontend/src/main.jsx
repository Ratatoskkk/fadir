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

load().then(([{ default: App }]) => {
  createRoot(document.getElementById("root")).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
});
