// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

/**
 * 私有实现防误发守卫（发布通道自检）。
 *
 * 背景：coreHR 走 Open Core（Requirement: D-108）。商业逻辑放在**私有包**
 * `packages/corehr-enterprise/`，公开仓只留契约与读路径。私有包一旦随公开仓
 * 分发，商业保护就形同虚设 —— 而且这种事故在 GitHub 上是**不可逆**的
 * （即使后来删掉提交，历史仍在、已被克隆的副本仍在）。
 *
 * 所以这里用三道闸：
 *   1. 根 `.gitignore` 必须覆盖 `packages/`（挡住 `git add -A`）；
 *   2. git **已跟踪**文件里不得出现 `packages/` 或私有包名的任何路径
 *      （挡住「先 commit 再补救」——那时已经晚了）；
 *   3. 打包发布物时用 `git archive`（只含已跟踪内容）并在打包后**复核内容**。
 *
 * 为什么这个守卫跑在**宿���/CI runner** 而不是容器里：它要读 git 的已跟踪文件
 * 清单，而镜像里没有 git（`corehr-api` / `corehr-web` 都不带）。它属于仓库
 * 卫生检查，不属于代码检查，不需要进容器。
 *
 * 守则：**守卫必须先证明自己抓得住**（红绿自检），否则容易退化成「永远绿」的摆设。
 *
 * 用法：
 *   node scripts/check-private-package-isolation.mjs                 # 只做检查
 *   node scripts/check-private-package-isolation.mjs --archive <dir>  # 检查 + 打发布包
 */

import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "..");

/** 私有实现所在目录（相对仓库根）。 */
const PRIVATE_DIR = "packages";

/** 私有包的包名片段 —— 任何路径里出现它都视为私有实现。 */
const PRIVATE_NAME_MARKERS = ["corehr-enterprise", "corehr_enterprise"];

/** 私有包仓库自己的忽略规则里必须有的密钥防漏项。 */
const PRIVATE_GITIGNORE_REQUIRED = ["*.pem", "*.key"];

function fail(message) {
  console.error(`\n[私有实现防误发守卫] 失败：${message}\n`);
  process.exit(1);
}

function git(args) {
  try {
    return execFileSync("git", args, {
      cwd: repoRoot,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    }).trim();
  } catch (error) {
    fail(
      `无法执行 git ${args.join(" ")}（退出码 ${error.status ?? "?"}）。\n` +
        `        本守卫需要 git 可用；容器镜像里没有 git，请在宿主或 CI runner 上运行。\n` +
        `        stderr：${String(error.stderr ?? "").trim()}`,
    );
  }
  return "";
}

/**
 * 从一份「已跟踪文件清单」里找出私有实现路径。
 *
 * 抽成纯函数是为了能做红绿自检 —— 守卫本身必须证明能抓到。
 */
export function findPrivatePaths(trackedPaths) {
  const hits = [];
  for (const path of trackedPaths) {
    const normalized = path.replace(/\\/g, "/");
    const segments = normalized.split("/");
    if (segments[0] === PRIVATE_DIR) {
      hits.push({ path: normalized, reason: `位于私有目录 ${PRIVATE_DIR}/` });
      continue;
    }
    const marker = PRIVATE_NAME_MARKERS.find((m) => normalized.includes(m));
    if (marker) {
      hits.push({ path: normalized, reason: `路径含私有包名 "${marker}"` });
    }
  }
  return hits;
}

/**
 * 判断根 `.gitignore` 是否覆盖了私有目录。
 *
 * 判定口径：存在一条非注释行，去掉行尾斜杠与前导斜杠后等于 `packages`，
 * 或以 `packages/` 开头（通配写法，如 `packages/**`）。
 */
export function gitignoreCoversPrivateDir(gitignoreText) {
  for (const raw of gitignoreText.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const trimmed = line.replace(/^\//, "").replace(/\/$/, "");
    if (trimmed === PRIVATE_DIR) return true;
    if (trimmed.startsWith(`${PRIVATE_DIR}/`)) return true;
  }
  return false;
}

function main() {
  const argv = process.argv.slice(2);
  const archiveIndex = argv.indexOf("--archive");
  const archiveDir = archiveIndex >= 0 ? argv[archiveIndex + 1] : null;

  console.log("[私有实现防误发守卫] 开始检查…");

  // ---- 红绿自检：守卫必须先证明自己抓得住 ------------------------------
  const selfTestHit = findPrivatePaths([
    "apps/api/src/hris/modules/workflow/engine.py",
    "packages/corehr-enterprise/src/corehr_enterprise/workflow/engine.py",
  ]);
  if (selfTestHit.length !== 1 || !selfTestHit[0].path.startsWith(PRIVATE_DIR)) {
    fail("红绿自检失败：探测器没能抓到伪造的私有路径，守卫不可信，已中止。");
  }
  if (findPrivatePaths(["apps/api/src/hris/core/licensing/keys.py"]).length !== 0) {
    fail("红绿自检失败：探测器把公开文件误判成私有实现，已中止。");
  }
  if (!gitignoreCoversPrivateDir("packages/\n")) {
    fail("红绿自检失败：`.gitignore` 覆盖判定失效，已中止。");
  }
  if (gitignoreCoversPrivateDir("# packages/\nnode_modules/\n")) {
    fail("红绿自检失败：`.gitignore` 覆盖判定把注释行当成规则，已中止。");
  }
  console.log("  · 红绿自检通过（探测器既能抓私有路径，也不会误伤公开文件）");

  // ---- 闸 1：根 .gitignore 必须覆盖私有目录 -----------------------------
  const gitignorePath = join(repoRoot, ".gitignore");
  if (!existsSync(gitignorePath)) {
    fail("找不到根 .gitignore。");
  }
  const gitignoreText = readFileSync(gitignorePath, "utf8");
  if (!gitignoreCoversPrivateDir(gitignoreText)) {
    fail(
      `根 .gitignore 没有覆盖 "${PRIVATE_DIR}/"。\n` +
        `        没有这条规则，一次 \`git add -A\` 就会把私有实现提交进公开仓。\n` +
        `        请在 .gitignore 里加一行：\n` +
        `            ${PRIVATE_DIR}/\n`,
    );
  }
  console.log(`  · 闸 1 通过：根 .gitignore 覆盖了 ${PRIVATE_DIR}/`);

  // ---- 闸 2：已跟踪文件里不得有私有实现 --------------------------------
  const trackedRaw = git(["ls-files"]);
  const tracked = trackedRaw ? trackedRaw.split(/\r?\n/).filter(Boolean) : [];
  const hits = findPrivatePaths(tracked);
  if (hits.length > 0) {
    fail(
      "git 已跟踪文件里出现了私有实现路径：\n" +
        hits.map((h) => `        ${h.path}  —— ${h.reason}`).join("\n") +
        "\n\n" +
        "        这些内容已经进入提交历史。**立刻执行**（未 push 时）：\n" +
        "            git rm -r --cached <路径>\n" +
        "            git commit --amend --no-edit\n" +
        "        如果已经 push 过，历史无法真正抹掉，只能视为已泄露并重做该部分实现。",
    );
  }
  console.log(`  · 闸 2 通过：已跟踪文件 ${tracked.length} 个，其中私有实现 0 个`);

  // ---- 闸 3（可选）：打包并复核发布物 ------------------------------------
  if (archiveDir) {
    const outDir = resolve(repoRoot, archiveDir);
    mkdirSync(outDir, { recursive: true });
    const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    const archivePath = join(outDir, `corehr-public-${stamp}.tar.gz`);

    const head = git(["rev-parse", "--short", "HEAD"]);
    git(["archive", "--format=tar.gz", `-o`, archivePath, "HEAD"]);
    console.log(`  · 已打包发布物：${relative(repoRoot, archivePath)}（HEAD ${head}）`);

    // 复核：发布物里不得出现私有目录
    const listing = execFileSync("tar", ["-tzf", archivePath], { encoding: "utf8" });
    const entries = listing.split(/\r?\n/).filter(Boolean);
    const badEntries = findPrivatePaths(entries);
    if (badEntries.length > 0) {
      fail(
        "发布物里出现了私有实现路径：\n" +
          badEntries.map((h) => `        ${h.path}`).join("\n"),
      );
    }

    const digest = createHash("sha256")
      .update(readFileSync(archivePath))
      .digest("hex");
    writeFileSync(
      join(outDir, "SHA256SUMS.txt"),
      `${digest}  ${archivePath.split(/[\\/]/).pop()}\n`,
      "utf8",
    );
    console.log(`  · 闸 3 通过：发布物 ${entries.length} 个条目，私有实现 0 个`);
    console.log(`  · sha256 = ${digest}`);
    console.log(`  · 校验和文件：${relative(repoRoot, join(outDir, "SHA256SUMS.txt"))}`);
  }

  // ---- 提示：本地私有包状态 ---------------------------------------------
  const privateDir = join(repoRoot, PRIVATE_DIR);
  if (existsSync(privateDir)) {
    console.log(
      `\n  · 提示：本地存在私有包目录 ${PRIVATE_DIR}/（未被 git 跟踪，符合预期）。\n` +
        "        它不在版本控制里，请确保在离线备份里有副本 ——\n" +
        "        它是商业资产的**唯一**一份实现副本。",
    );
    const privateGitignore = join(privateDir, "corehr-enterprise", ".gitignore");
    if (existsSync(privateGitignore)) {
      const text = readFileSync(privateGitignore, "utf8");
      const missing = PRIVATE_GITIGNORE_REQUIRED.filter(
        (rule) => !text.split(/\r?\n/).some((l) => l.trim() === rule),
      );
      if (missing.length > 0) {
        console.log(
          `  · 提示：私有包 .gitignore 缺少密钥防漏项：${missing.join(", ")}`,
        );
      }
    }
  }

  console.log("[私有实现防误发守卫] 全部通过。\n");
}

if (import.meta.url === `file://${process.argv[1]}` || process.argv[1]?.endsWith("check-private-package-isolation.mjs")) {
  main();
}
