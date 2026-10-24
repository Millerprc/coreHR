// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

/// <reference types="vitest" />
import { defineConfig } from "vitest/config"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    setupFiles: [
      "./src/test/setup.ts",
      "./src/test/setup-match-media.ts",
    ],
    globals: true,
    // Requirement: D-119 —— 全局用例超时放宽到 45 秒。
    //
    // 为什么：这些是**整页渲染级**的 UI 用例（挂 4 个 AntD 面板、几百个节点），
    // 而 antd 6 的 CSS-in-JS 在 jsdom 里会注入成千上万条样式规则，
    // testing-library 的 getByRole 要为无障碍树逐个调 getComputedStyle ——
    // 单次查询实测要 4.8~5.0 秒（getByText 只需 1 毫秒）。
    // 于是本地 9 秒的用例在 CI runner 上（比本机慢约 1.7 倍）会顶穿原来的 15 秒上限，
    // **随机变红**（2026-10-24 CI 就这样红过一次：LifecycleWorkspace 跑满 15.3 秒超时）。
    //
    // 45 秒是「本地最慢用例的 4 倍」：足够覆盖 runner 抖动，又不至于让真挂死的用例
    // 占满整轮 CI。断言一条没动 —— 真的坏了仍然是断言失败，不是超时失败。
    testTimeout: 45_000,
  },
})
