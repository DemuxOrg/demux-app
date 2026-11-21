// Builds the kit into one IIFE script + one stylesheet that backend/app/agent/shell.py
// inlines into every v2 app (frontend/theme.md §10.3). The iframe allows no network, so
// nothing may be split into chunks or loaded at runtime.
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  build: {
    outDir: "../backend/app/agent/kit",
    emptyOutDir: true,
    cssCodeSplit: false,
    minify: true,
    sourcemap: false,
    lib: {
      entry: "src/index.tsx",
      formats: ["iife"],
      name: "DemuxKit",
      fileName: () => "kit.js",
      cssFileName: "kit",
    },
    rollupOptions: { output: { inlineDynamicImports: true } },
  },
});
