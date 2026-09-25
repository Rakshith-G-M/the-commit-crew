/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// CampusIQ frontend (M8).
// Dev server proxies /api to the FastAPI backend so the browser only ever
// talks to the product API (never the raw JSON artefacts).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000",
        ws: true,
      },
    },
  },
  preview: {
    port: 4173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000",
        ws: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    include: ["src/**/*.test.{ts,tsx}"],
  },
});