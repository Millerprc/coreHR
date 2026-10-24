// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

/**
 * 源码版权头批量写入脚本（幂等）。
 *
 * 目标：给公开仓里的每一份源文件补上 coreHR 的版权声明与许可证指向，
 * 与 scripts/check-license-header.mjs 的判定规则严格对齐——守卫认，
 * 本脚本就一定写得出；守卫不认，本脚本就会补。
 *
 * 为什么要有这个脚本：版权头是**逐文件**的凭据，手工加必然漏。
 * 而漏一个文件，那一个文件在法律上就等于没有声明。
 *
 * 幂等保证（重复跑不产生任何变化）：
 *   1. 文件前 10 行内已同时出现版权行与许可证指向 → 直接跳过；
 *   2. 只缺其中一行 → 在已有那一行旁边补上缺失的那一行（不重复插入已有的）；
 *   3. 两行都缺 → 在文件顶部插入完整的两行头部 + 一个空行。
 * 判定的 10 行窗口与守卫一致，因此「跑完之后守卫必然转绿」。
 *
 * 「声明行」的判定：必须是**真正的注释行**（去缩进后以 `#` 或 `//` 开头），
 * 且不在成对的块注释内部。文档注释里提到 marker 的文字不算声明——
 * 否则守卫会假绿，本脚本会把许可证行插进块注释中间（已实测踩过）。
 *
 * 用法：
 *   node scripts/apply-license-header.mjs                    # 写入 apps/** 与 scripts/** 下的所有源文件
 *   node scripts/apply-license-header.mjs --dry-run          # 预演，不写盘
 *   node scripts/apply-license-header.mjs --root <目录>       # 只处理指定目录（可重复）
 *   node scripts/apply-license-header.mjs --verbose           # 列出全部改动文件
 *
 * 保真性：原文件的换行风格（CRLF / LF）、UTF-8 BOM、行内内容一律不动，
 * 只在顶部插入注释行。
 */
import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, extname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "..");

/** 默认扫描根，与守卫脚本保持一致。 */
const DEFAULT_ROOTS = [
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

const COPYRIGHT_MARKER = "Copyright (c) 2026 coreHR";
const LICENSE_MARKER = "Sustainable Use License v1.0";

const COPYRIGHT_TEXT = "Copyright (c) 2026 coreHR 项目贡献者";
const LICENSE_TEXT =
  "许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。";

/** 在文件前 N 行内查找，与守卫脚本的 HEADER_SCAN_LINES 一致。 */
const HEADER_SCAN_LINES = 10;

/** 注释前缀：Python / Shell / PowerShell 用 #，TS / JS 用 //。 */
const COMMENT_PREFIX = {
  ".py": "#",
  ".sh": "#",
  ".ps1": "#",
  ".ts": "//",
  ".tsx": "//",
  ".js": "//",
  ".jsx": "//",
  ".mjs": "//",
  ".cjs": "//",
};

const MAX_LISTED = 30;

// ── 命令行参数 ──────────────────────────────────────────────────────────
function parseArgs(argv) {
  const opts = { dryRun: false, verbose: false, roots: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--dry-run" || arg === "-n") {
      opts.dryRun = true;
    } else if (arg === "--verbose" || arg === "-v") {
      opts.verbose = true;
    } else if (arg === "--root") {
      const value = argv[i + 1];
      if (!value) {
        console.error("✗ --root 需要一个目录参数");
        process.exit(1);
      }
      opts.roots.push(resolve(repoRoot, value));
      i += 1;
    } else if (arg === "--help" || arg === "-h") {
      console.log(
        [
          "用法：node scripts/apply-license-header.mjs [选项]",
          "",
          "  --dry-run, -n     预演：只报告将发生的改动，不写盘",
          "  --root <目录>     只处理指定目录（相对仓库根目录，可重复）",
          "  --verbose, -v     列出全部改动文件（默认最多列 30 条）",
          "  --help, -h        显示本帮助",
        ].join("\n"),
      );
      process.exit(0);
    } else {
      console.error(`✗ 无法识别的参数：${arg}（用 --help 查看用法）`);
      process.exit(1);
    }
  }
  if (opts.roots.length === 0) {
    opts.roots = DEFAULT_ROOTS;
  }
  return opts;
}

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
      if (EXCLUDED_DIRS.has(entry)) continue;
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

function findFiles(roots) {
  const files = [];
  for (const root of roots) {
    for (const file of walk(root)) {
      if (isSourceFile(file)) files.push(file);
    }
  }
  return files.sort();
}

/**
 * 顶部必须留在头部注释之前的内容。
 * Python：shebang 与编码声明必须在文件最前面；
 * Shell：shebang 必须在第 1 行；
 * JS/TS："use strict" 指令要放在指令序列（directive prologue）里，
 * 插在它前面虽然合法，但会破坏 ESLint strict 规则与部分工具链的预期。
 */
function reservedHeadCount(lines, ext) {
  let idx = 0;
  if (idx < lines.length && lines[idx].startsWith("#!")) idx += 1;
  if (ext === ".py") {
    if (idx < lines.length && /^\s*#.*coding[:=]\s*[-\w.]+/.test(lines[idx])) idx += 1;
  } else if (idx < lines.length && /^\s*["']use strict["']\s*;?\s*$/.test(lines[idx])) {
    idx += 1;
  }
  return idx;
}

/** 在已有头部旁边补一行（不重复插入已有的那一行）。 */
function insertBeside(lines, atIndex, newLine) {
  const next = [...lines];
  next.splice(atIndex, 0, newLine);
  return next;
}

/** 在指定位置插入完整两行头部 + 必要的空行分隔。 */
function insertHeader(lines, atIndex, copyrightLine, licenseLine) {
  const before = lines.slice(0, atIndex);
  const after = lines.slice(atIndex);
  const block = [];
  if (before.length > 0 && before[before.length - 1].trim() !== "") {
    block.push("");
  }
  block.push(copyrightLine, licenseLine);
  if (after.length === 0 || after[0].trim() !== "") {
    block.push("");
  }
  return [...before, ...block, ...after];
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
 * 本函数是 scripts/check-license-header.mjs 的同名实现的镜像，
 * 两者必须保持一致——守卫认的，本脚本就一定写得出。
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

/**
 * 处理单个文件。
 * @returns {{changed: boolean, action: string}} action 用于报告：skipped / filled / inserted
 */
function processFile(file, opts) {
  const raw = readFileSync(file);
  const hasBom = raw.length >= 3 && raw[0] === 0xef && raw[1] === 0xbb && raw[2] === 0xbf;
  const body = hasBom ? raw.subarray(3) : raw;
  const text = body.toString("utf8");
  const eol = text.includes("\r\n") ? "\r\n" : "\n";
  const lines = text.split(/\r?\n/);

  const copyrightAt = findHeaderIndex(lines, COPYRIGHT_MARKER, HEADER_SCAN_LINES);
  const licenseAt = findHeaderIndex(lines, LICENSE_MARKER, HEADER_SCAN_LINES);

  if (copyrightAt >= 0 && licenseAt >= 0) {
    return { changed: false, action: "skipped" };
  }

  const ext = extname(file);
  const prefix = COMMENT_PREFIX[ext] ?? "//";
  const copyrightLine = `${prefix} ${COPYRIGHT_TEXT}`;
  const licenseLine = `${prefix} ${LICENSE_TEXT}`;

  let next;
  let action;
  if (copyrightAt >= 0) {
    // 只缺许可证行 → 补在版权行后面。
    next = insertBeside(lines, copyrightAt + 1, licenseLine);
    action = "filled";
  } else if (licenseAt >= 0) {
    // 只缺版权行 → 补在许可证行前面，保持「版权在前、许可证在后」的既定顺序。
    next = insertBeside(lines, licenseAt, copyrightLine);
    action = "filled";
  } else {
    const at = reservedHeadCount(lines, ext);
    next = insertHeader(lines, at, copyrightLine, licenseLine);
    action = "inserted";
  }

  if (opts.dryRun) {
    return { changed: true, action };
  }

  const out = Buffer.concat([
    ...(hasBom ? [Buffer.from([0xef, 0xbb, 0xbf])] : []),
    Buffer.from(next.join(eol), "utf8"),
  ]);
  writeFileSync(file, out);
  return { changed: true, action };
}

// ── 主流程 ──────────────────────────────────────────────────────────────
const opts = parseArgs(process.argv.slice(2));
const files = findFiles(opts.roots);

if (files.length === 0) {
  console.error("✗ 版权头写入脚本未执行\n");
  console.error("扫描范围内没有找到任何源文件——扫描根路径可能不对，脚本空转。");
  process.exit(1);
}

const changed = [];
let skipped = 0;

for (const file of files) {
  const result = processFile(file, opts);
  if (result.changed) {
    changed.push({ file: relative(repoRoot, file).split("\\").join("/"), action: result.action });
  } else {
    skipped += 1;
  }
}

const listed = opts.verbose ? changed : changed.slice(0, MAX_LISTED);
for (const item of listed) {
  console.log(`  ${item.action === "filled" ? "补齐" : "插入"} ${item.file}`);
}
if (listed.length < changed.length) {
  console.log(`  …… 另有 ${changed.length - listed.length} 个文件（用 --verbose 查看全部）`);
}

if (opts.dryRun) {
  console.log(
    `\n✓ 预演完成：将写入 ${changed.length} 个文件的版权头，跳过 ${skipped} 个已带声明的文件（未写入任何文件）`,
  );
} else {
  console.log(
    `\n✓ 已写入 ${changed.length} 个文件的版权头，跳过 ${skipped} 个已带声明的文件`,
  );
}
