import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

const configuredControlPort = Number(process.env.VITE_CONTROL_PORT);
const controlPort =
  Number.isInteger(configuredControlPort) && configuredControlPort > 0
    ? configuredControlPort
    : 56000;

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      "/api": `http://127.0.0.1:${controlPort}`,
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    target: "es2020",
  },
});
