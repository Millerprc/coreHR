/// <reference types="vitest" />
import { defineConfig } from "vitest/config"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: [
      "./src/test/setup.ts",
      "./src/test/setup-match-media.ts",
    ],
    globals: true,
  },
})
