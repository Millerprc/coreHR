// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

/// <reference types="vitest" />
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  // Requirement: D-108 — 构建期烘焙水印文案；未设置时为空串，运行时按授权状态生成。
  define: {
    __COREHR_WATERMARK__: JSON.stringify(process.env.COREHR_WATERMARK ?? ""),
  },
  plugins: [react()],
  server: {
    port: 5173,
    // Requirement: D-117 —— 与 vite.config.ts 保持一致：bind mount 场景下必须轮询监听，
    // 否则宿主机改完源码，dev server 仍服务旧模块（详见 vite.config.ts 的完整说明）。
    watch: {
      usePolling: true,
      interval: 400,
    },
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/health": {
        target: process.env.VITE_API_PROXY_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      input: {
        overview: "index.html",
        business: "business.html",
      },
    },
  },
})
