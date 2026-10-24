// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

/**
 * 源码版权与许可证声明守卫。
 *
 * 目标：公开仓里每一份源文件都必须带 coreHR 的版权声明与许可证指向。
 * 为什么要脚本守卫而不是只靠 Review：本仓库是**公开**的，源码头部声明是
 * 事后追责与品牌归属的唯一逐文件凭据——漏一个文件，那一个文件就等于
 * 没有声明（Requirement: D-108）。
 *
 * 判定规则（两个都要满足，顺序不限）：
 *   1. 文件前 10 行内出现版权行 `Copyright (c) 2026 coreHR`；
 *   2. 文件前 10 行内出现许可证指向 `Sustainable Use License v1.0`。
 *
 * 额外约束（重要）：判定只看**真正的注释行**——去掉缩进后以 `#` 或 `//` 开头。
 * 为什么不能只看「前 10 行内包含该字符串」：本文件自己的说明文字里就写了这
 * 两个字符串，如果按包含判定，任何在文档注释里提到 marker 的文件都会被误判
 * 成「已带头」，守卫会假绿，补写脚本还会把许可证行插进块注释中间。
 *
 * 为什么不用 SPDX-License-Identifier：
 * 本项目采用 Source Available 许可（coreHR Sustainable Use License v1.0），
 * **不是 OSI 开源**，没有对应的 SPDX 标识符；强行套一个 OSI 标识会构成
 * 误导性的声明。许可证指向用自然语言写明，见 LICENSE。
 *
 * 扫描范围：apps/** 与 scripts/** 下的 .py / .ts / .tsx / .js / .jsx / .mjs / .cjs /
 * .sh / .ps1。
 * 为什么覆盖到迁移、测试与运维脚本：这些文件同样会随公开仓分发，法律上与产品
 * 源码同级——漏一个文件，那一个文件在法律上就等于没有声明（Requirement: D-108）。
 * 排除：node_modules、dist、build、__pycache__、coverage 等产物目录（纯目录级排除，
 * 不排除任何源文件名——本仓的 __init__.py 带真实模块 docstring，*.d.ts 是手写环境
 * 声明，*.test.tsx 是公开仓里的测试源码，同样需要带声明）。
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "..");

const SCAN_ROOTS = [
  join(repoRoot, "apps"),
  join(repoRoot, "scripts"),
];

const SOURCE_EXTENSIONS = new Set([
  ".py",
  ".ts",
  ".tsx",
  ".js",
  ".jsx",
  ".mjs",
  ".cjs",
  ".sh",
  ".ps1",
]);

/** 不扫描的产物目录名（目录级排除，不排除任何源文件名）。 */
const EXCLUDED_DIRS = new Set([
  "node_modules",
  "dist",
  "build",
  "__pycache__",
  ".venv",
  "coverage",
  ".vite",
]);

/** 版权行必须包含的片段。 */
const COPYRIGHT_MARKER = "Copyright (c) 2026 coreHR";
/** 许可证指向必须包含的片段。 */
const LICENSE_MARKER = "Sustainable Use License v1.0";
/** 在文件前 N 行内查找。 */
const HEADER_SCAN_LINES = 10;

function walk(dir, acc = []) {
  let entries;
  try {
    entries = readdirSync(dir);
  } catch {
    return acc;
  }
  for (const entry of entries) {
    const full = join(dir, entry);
    let st;
    try {
      st = statSync(full);
    } catch {
      continue;
    }
    if (st.isDirectory()) {
      if (EXCLUDED_DIRS.has(entry)) {
        continue;
      }
      walk(full, acc);
    } else if (st.isFile()) {
      acc.push(full);
    }
  }
  return acc;
}

function isSourceFile(file) {
  const name = file.split(/[\\/]/).pop();
  if (!name) return false;
  for (const ext of SOURCE_EXTENSIONS) {
    if (name.endsWith(ext)) return true;
  }
  return false;
}

/**
 * 是否是「真正的注释行」。
 * 头部声明必须以 `#` 或 `//` 开头（允许前导缩进）。
 * 为什么不按「包含字符串」判定：文档注释里提到 marker 的行不是声明，
 * 按包含判定会假绿，并让补写脚本把许可证行插进块注释中间。
 */
function isHeaderComment(line) {
  const trimmed = line.trimStart();
  return trimmed.startsWith("#") || trimmed.startsWith("//");
}

/**
 * 在前 limit 行内找出「不在块注释里」且带 marker 的声明行下标；找不到返回 -1。
 * 为什么要排除块注释内部：块注释里的行即使以 `//` 开头也不是声明，
 * 而且补写脚本按这个下标插入会破坏注释结构。
 * 本函数是 scripts/apply-license-header.mjs 的同名实现的镜像，
 * 两者必须保持一致——守卫认的，补写脚本就一定写得出。
 */
function findHeaderIndex(lines, marker, limit) {
  let inBlock = false;
  const end = Math.min(limit, lines.length);
  for (let i = 0; i < end; i += 1) {
    const line = lines[i];
    const opensBlock = line.includes("/*");
    const closesBlock = line.includes("*/");
    if (inBlock) {
      if (closesBlock) inBlock = false;
      continue;
    }
    if (isHeaderComment(line) && line.includes(marker)) return i;
    if (opensBlock && !closesBlock) inBlock = true;
  }
  return -1;
}

function findFiles() {
  const files = [];
  for (const root of SCAN_ROOTS) {
    for (const file of walk(root)) {
      if (isSourceFile(file)) files.push(file);
    }
  }
  return files.sort();
}

const failures = [];
const files = findFiles();

if (files.length === 0) {
  console.error("✗ 许可证声明守卫未通过\n");
  console.error("扫描范围内没有找到任何源文件——扫描根路径可能不对，守卫失灵。");
  process.exit(1);
}

let missingCopyright = 0;
let missingLicense = 0;

for (const file of files) {
  const rel = relative(repoRoot, file).split("\\").join("/");
  const text = readFileSync(file, "utf8");
  const lines = text.split(/\r?\n/);
  const hasCopyright = findHeaderIndex(lines, COPYRIGHT_MARKER, HEADER_SCAN_LINES) >= 0;
  const hasLicense = findHeaderIndex(lines, LICENSE_MARKER, HEADER_SCAN_LINES) >= 0;

  if (!hasCopyright) {
    missingCopyright += 1;
    failures.push(`  ${rel}  缺少版权声明（需在前 ${HEADER_SCAN_LINES} 行内出现「${COPYRIGHT_MARKER}」）`);
  }
  if (!hasLicense) {
    missingLicense += 1;
    failures.push(`  ${rel}  缺少许可证指向（需在前 ${HEADER_SCAN_LINES} 行内出现「${LICENSE_MARKER}」）`);
  }
}

if (failures.length > 0) {
  console.error("✗ 许可证声明守卫未通过\n");
  console.error(
    `发现 ${files.length} 个源文件中 ${missingCopyright} 个缺版权声明、${missingLicense} 个缺许可证指向：`,
  );
  console.error(failures.join("\n"));
  console.error("\n文件头模板：");
  console.error("  Python:  # Copyright (c) 2026 coreHR 项目贡献者");
  console.error("           # 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。");
  console.error("  TS/TSX: // Copyright (c) 2026 coreHR 项目贡献者");
  console.error("           // 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。");
  process.exit(1);
}

console.log(
  `✓ 许可证声明守卫通过（扫描 ${files.length} 个源文件，${SCAN_ROOTS.length} 个源码根，0 处违规）`,
);
