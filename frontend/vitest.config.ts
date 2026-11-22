import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom", globals: true, setupFiles: ["./src/test/setup.ts"],
    // Playwright specs run under `npm run test:e2e`; vitest must not try to load them.
    exclude: ["node_modules/**", "dist/**", "tests/e2e/**"],
  },
});
