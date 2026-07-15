import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Relative base so the built assets load whether served from FastAPI at "/"
// or opened from the filesystem inside the Tauri bundle.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    target: "es2020",
  },
  server: {
    port: 5173,
    // Dev-only proxy so `npm run dev` can talk to the Python backend
    // without CORS while iterating on the UI.
    proxy: {
      "/api": "http://127.0.0.1:8377",
      "/health": "http://127.0.0.1:8377",
    },
  },
});
