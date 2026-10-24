// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

/// <reference types="vitest" />
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Requirement: D-117 —— dev server 必须用**轮询**监听文件变化。
    //
    // 为什么：开发时 `apps/web` 是以 bind mount 挂进容器的（见 deploy/compose.yaml 的 web 服务）。
    // Docker Desktop 在 Windows 上的 bind mount **不把宿主机侧的写入以 inotify 事件送进容器**，
    // 于是 chokidar 永远收不到 change 事件，vite 的模块图不会失效：
    // 磁盘上的源码已经是新的，浏览器拿到的却还是十几小时前 transform 过的旧模块，
    // 表现就是「代码改了、页面没变」，而且测试与 tsc 照样全绿（它们每次直接读盘，不依赖监听）。
    // uvicorn --reload 用的是 watchfiles，不受这个问题影响，所以 API 侧能自动生效、前端侧不能。
    //
    // usePolling 改成按 mtime 轮询，不依赖 inotify，宿主机改完几百毫秒内就会热更新。
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
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
  },
})
