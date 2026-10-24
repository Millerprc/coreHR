// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

// Requirement: D-108 — 构建期烘焙的水印文案。
// 由 vite.business.config.ts 的 define 注入（环境变量 COREHR_WATERMARK）；
// 未注入时为 undefined，运行时回落到按授权状态生成的文案。
declare const __COREHR_WATERMARK__: string | undefined
