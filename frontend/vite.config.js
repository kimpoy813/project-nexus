import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../static/goey",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: "toaster.js",
        chunkFileNames: "chunks/[name].js",
        assetFileNames: "toaster.css",
      },
    },
  },
});