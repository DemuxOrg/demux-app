// Builds the studio runtime (src/studio.tsx) into one IIFE script that
// backend/app/agent/shell.py inlines into every v3 app. No CSS: v3 apps bring their own
// look (Tailwind's browser build, copied by scripts/finish.mjs, styles their classes).
// Runs after the kit build, into the same folder, so it must not empty it.
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  build: {
    outDir: "../backend/app/agent/kit",
    emptyOutDir: false,
    minify: true,
    sourcemap: false,
    lib: {
      entry: "src/studio.tsx",
      formats: ["iife"],
      name: "DemuxStudio",
      fileName: () => "studio.js",
    },
    rollupOptions: { output: { inlineDynamicImports: true } },
  },
});
