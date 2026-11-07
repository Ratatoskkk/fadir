import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import mockApi from "./mock/mockApi.js";

// The dev server proxies /api to the FastAPI app on loopback (SPEC §1).
// `vite --mode mock` (npm run dev:mock) serves a synthetic in-memory API instead, so the
// interface can be developed without the backend. The mock never reaches a build.
export default defineConfig(({ mode }) => ({
  plugins: [react(), ...(mode === "mock" ? [mockApi()] : [])],
  server: {
    port: 5173,
    strictPort: true,
    proxy: mode === "mock" ? undefined : {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
}));
