import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Hasil build disajikan oleh backend/web.py; saat dev, /api diteruskan ke web.py di port 8020
export default defineConfig({
  plugins: [react()],
  build: { outDir: "../backend/web/dist", emptyOutDir: true },
  server: { proxy: { "/api": "http://127.0.0.1:8020" } },
});
