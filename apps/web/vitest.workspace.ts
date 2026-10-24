import { defineWorkspace } from "vitest/config"

export default defineWorkspace([
  {
    extends: "./vitest.config.ts",
    test: {
      name: "corehr-web",
      // Requirement: CHECKPOINT-001 — 检查点必须覆盖全部前端测试，禁止仅运行登录冒烟用例。
      include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    },
  },
])
