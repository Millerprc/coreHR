// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

/**
 * 根目录转发壳：把 `node scripts/check-antd-usage.mjs` 转到真实实现。
 *
 * 为什么需要这个文件：
 * 真实实现是 `apps/web/scripts/check-antd-usage.mjs`（它按自身位置解析
 * `apps/web` 与 `apps/web/node_modules/antd/es`，因此与当前工作目录无关）。
 * 仓库根的 `scripts/` 下曾有一个 **0 字节** 的同名文件——它会静默 exit 0、
 * 不输出任何内容，在流水线里表现为「AntD 守卫通过」的**假绿灯**。
 * 本壳消除这个歧义：无论从哪个路径调用，得到的都是真实守卫的退出码与输出。
 *
 * 退出码与真实实现完全一致（0 = 通过，1 = 有违规）。
 */
import { spawnSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const realScript = resolve(here, "..", "apps", "web", "scripts", "check-antd-usage.mjs");

const result = spawnSync(process.execPath, [realScript], { stdio: "inherit" });

if (result.error) {
  console.error(`✗ 无法执行 Ant Design 规范守卫：${result.error.message}`);
  console.error(`  目标脚本：${realScript}`);
  process.exit(1);
}

process.exit(result.status ?? 1);
