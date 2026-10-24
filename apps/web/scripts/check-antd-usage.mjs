// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

/**
 * Ant Design 版本合规守卫。
 *
 * 目标：所有页面统一使用 Ant Design 最新版（当前锁定 6.5.2）规范，
 * 不允许继续使用 antd 6 中已标记 @deprecated 的属性。
 *
 * 为什么要脚本守卫而不是只靠 tsc：
 * antd 6 里相当一部分旧属性**仍然可以被 TypeScript 通过**（它们还留在类型里，
 * 只是标了 @deprecated）。例如 Alert.message / Alert.onClose / destroyOnClose /
 * dropdownRender / visible / onVisibleChange 都是「类型合法但已废弃」——
 * tsc 抓不到，只有读 antd 源码才能发现。
 *
 * 判定精度（重要）：
 * 按属性名全局扫描会误报——同一个名字在不同组件上可能一废弃一有效。
 * 例如 `maxCount` 在 antd 6 里是 AvatarGroup 的废弃属性，但 Select.maxCount
 * 是合法新属性。因此本守卫**按组件作用域判定**：
 *   1. 从 antd/es/index.d.ts 解析「导出名 → 组件目录」；
 *   2. 逐组件目录解析该组件自己 d.ts 里的 @deprecated 属性；
 *   3. 扫描 src 下的 tsx，按 JSX 标签名匹配，只在该组件自己的废弃集合里命中才报错。
 * 这样组件 A 的废弃属性不会牵连组件 B 的同名合法属性。
 *
 * 两类废弃要分开查（Requirement: D-090）：
 *   A. 属性级废弃：组件还在，但某个 prop 废弃了 → 读 d.ts 的 @deprecated。
 *   B. 组件级废弃：组件本身整个废弃，下个大版本移除 → 只能读组件的 js 实现。
 * B 类在 antd 6.5.2 上就是 List / BackTop——它们的 d.ts 里**没有** @deprecated，
 * 只在 js 里挂了 Deprecated.displayName 与 devUseWarning 警告，
 * 所以只看 d.ts 的旧机制对它们完全失明。
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(here, "..");
const srcRoot = join(webRoot, "src");
const antdEsm = join(webRoot, "node_modules", "antd", "es");

/**
 * 通用属性名豁免表。
 *
 * antd 的 @deprecated 覆盖 165 个属性，其中相当一部分是**通用词**
 * （type / label / children / color / content / description / dataSource /
 * width / layout / position / onSelect / split …）。这些词在别的组件
 * （甚至原生标签）上语义完全不同。按组件作用域判定后通用词误报已经大幅减少，
 * 但仍有少数同名不同义的场景，这些整体豁免。
 */
const EXCLUDED_PROPS = new Set([
  "children",
  "color",
  "content",
  "dataSource",
  "description",
  "label",
  "layout",
  "position",
  "split",
  "type",
  "width",
]);

function walk(dir, predicate, acc = []) {
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
      walk(full, predicate, acc);
    } else if (predicate(full)) {
      acc.push(full);
    }
  }
  return acc;
}

/** 解析 antd/es/index.d.ts，得到「导出组件名 → 组件目录名」。 */
function collectComponentDirs() {
  const indexFile = join(antdEsm, "index.d.ts");
  const text = readFileSync(indexFile, "utf8");
  const map = new Map();
  // export { default as X } from './y';
  const re = /export\s*\{[^}]*?default\s+as\s+([A-Za-z0-9_]+)[^}]*?\}\s*from\s*['"]\.\/([^'"]+)['"]/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    map.set(m[1], m[2]);
  }
  return map;
}

/** 解析单个组件目录下所有 @deprecated 属性，返回 { 属性名 -> 替代写法 }。 */
function collectDeprecatedPropsOf(dir) {
  const result = new Map();
  const files = walk(join(antdEsm, dir), (f) => f.endsWith(".d.ts"));
  const blockRe =
    /\/\*\*[\s\S]{0,600}?@deprecated[\s\S]{0,600}?\*\/\s*(?:readonly\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\??\s*:/g;
  const useRe = /use\s+`([a-zA-Z_][a-zA-Z0-9_.]*)`/;
  for (const file of files) {
    const text = readFileSync(file, "utf8");
    let match;
    while ((match = blockRe.exec(text)) !== null) {
      const prop = match[1];
      if (EXCLUDED_PROPS.has(prop)) continue;
      if (result.has(prop)) continue;
      const useMatch = useRe.exec(match[0]);
      result.set(prop, useMatch ? useMatch[1] : "");
    }
  }
  return result;
}

function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * 收集文件里的普通字符串字面量（跳过模板字符串）。
 * 用来在 js 实现里找「组件级废弃提示」这种带文案的长字符串。
 */
function collectStringLiterals(text) {
  const literals = [];
  const re = /'((?:[^'\\\n]|\\.)*)'|"((?:[^"\\\n]|\\.)*)"/g;
  let match;
  while ((match = re.exec(text)) !== null) {
    literals.push(match[1] !== undefined ? match[1] : match[2]);
  }
  return literals;
}

/**
 * 识别「整体废弃」的 antd 组件（组件本身废弃，而不是组件的某个属性废弃）。
 *
 * 为什么不能靠 d.ts 的 @deprecated：
 * antd 对整体废弃的组件**故意不在类型声明里标 @deprecated**——标了 tsc 就会直接报错，
 * 开发者根本编译不过。它只在组件自己的 js 实现里挂 Deprecated.displayName 与
 * devUseWarning 警告。所以属性级那套「解析 d.ts」的机制对组件级废弃天然失明。
 *
 * 判定信号（按可靠性排序，全部来自 antd 源码，不硬编码组件名）：
 *   1. displayName = 'Deprecated.<X>'：antd 对整体废弃组件的统一标记，最可靠。
 *   2. warning.deprecated(false, '<X>', '<替代品>')：废弃主体就是组件自己。
 *   3. warning(<false>, 'deprecated', '<提到 X 的组件级废弃提示>') 且同文件有 devUseWarning('<X>')。
 * antd 升级后新废弃的组件会自动被这三类信号捕获。
 *
 * @returns Map<组件名, 替代写法>（替代写法取自 antd 源码，可能为空串）
 */
function collectDeprecatedComponents(componentDirs) {
  const deprecated = new Map();
  for (const [name, dir] of componentDirs) {
    const files = walk(join(antdEsm, dir), (f) => f.endsWith(".js"));
    if (files.length === 0) continue;
    const escaped = escapeRegExp(name);
    // 信号 1：displayName = 'Deprecated.<X>'
    const displayNameRe = new RegExp(`displayName\\s*=\\s*['"]Deprecated\\.${escaped}['"]`);
    // 信号 2：warning.deprecated(false, '<X>', '<替代品>')
    const selfDeprecatedRe = new RegExp(
      `\\.deprecated\\(\\s*false\\s*,\\s*['"\`]${escaped}['"\`]\\s*,`,
    );
    for (const file of files) {
      const text = readFileSync(file, "utf8");
      let found = displayNameRe.test(text);
      let replacement = "";
      const selfMatch = selfDeprecatedRe.exec(text);
      if (selfMatch) {
        found = true;
        const tail = text.slice(selfMatch.index + selfMatch[0].length);
        const next = /^\s*['"`]([^'"`]+)['"`]/.exec(tail);
        replacement = next ? next[1] : "";
      }
      if (!found) {
        // 信号 3：组件自己挂 devUseWarning('<X>')，且文件里有「废弃主体就是 <X> 本身」的文案。
        // 文案必须把组件名整体点出来（`X` 或 "X component"），
        // 否则 ConfigProvider.SizeContext 这类「子属性废弃」会被误判成组件废弃。
        const ownsWarning =
          text.includes(`devUseWarning('${name}')`) || text.includes(`devUseWarning("${name}")`);
        if (ownsWarning) {
          const mentioned = collectStringLiterals(text).find(
            (literal) =>
              /deprecated/i.test(literal) &&
              (literal.includes(`\`${name}\``) || literal.includes(`${name} component`)),
          );
          if (mentioned) found = true;
        }
      }
      if (found) {
        deprecated.set(name, replacement);
        break;
      }
    }
  }
  return deprecated;
}

/**
 * 自检：全量扫描 antd/es 里所有 `Deprecated.displayName` 标记，
 * 确认「被 antd 标记为整体废弃、且是 antd 导出组件」的组件都被上面的检测捕获。
 * 检测逻辑一旦失灵（正则写错、目录解析漏项）这里会立刻报红，
 * 保证组件级检查不是空转。
 */
function crossCheckDeprecatedComponents(componentDirs, detected) {
  const exportNames = new Set(componentDirs.keys());
  const missing = [];
  for (const file of walk(antdEsm, (f) => f.endsWith(".js"))) {
    const text = readFileSync(file, "utf8");
    const re = /displayName\s*=\s*['"]Deprecated\.([A-Za-z0-9_.]+)['"]/g;
    let match;
    while ((match = re.exec(text)) !== null) {
      const name = match[1];
      if (!exportNames.has(name) || detected.has(name)) continue;
      missing.push({ name, file: relative(webRoot, file) });
    }
  }
  return missing;
}

/**
 * 扫描 JSX 开始标签。
 *
 * 不能用简单正则：属性值里的箭头函数 `() =>` 含 `>`，正则会在那里提前截断标签，
 * 导致后半段的属性被漏检（假绿）。这里用深度感知的扫描器：
 * 跟踪 {} / [] 深度并跳过字符串字面量，直到深度归零的 `>` 才是标签结束。
 */
function findJsxTags(text) {
  const tags = [];
  const openRe = /<([A-Z][A-Za-z0-9_]*)/g;
  let m;
  while ((m = openRe.exec(text)) !== null) {
    const name = m[1];
    let i = m.index + m[0].length;
    let depth = 0;
    while (i < text.length) {
      const ch = text[i];
      if (ch === "'" || ch === '"' || ch === "`") {
        const quote = ch;
        i += 1;
        while (i < text.length && text[i] !== quote) {
          if (text[i] === "\\") i += 1;
          i += 1;
        }
        i += 1;
        continue;
      }
      if (ch === "{" || ch === "[") {
        depth += 1;
      } else if (ch === "}" || ch === "]") {
        depth -= 1;
      } else if (ch === ">" && depth <= 0) {
        break;
      }
      i += 1;
    }
    if (i >= text.length) break;
    tags.push({
      name,
      body: text.slice(m.index + m[0].length, i),
      start: m.index,
      bodyStart: m.index + m[0].length,
    });
    openRe.lastIndex = i;
  }
  return tags;
}

/**
 * 扫描 src 下的 tsx，按 JSX 标签名判定属性是否废弃。
 * 只匹配大写开头的标签（React 组件），原生标签（div/span/button…）不参与。
 */
function findUsages(componentDeprecated) {
  const files = walk(srcRoot, (f) => f.endsWith(".tsx"));
  const hits = [];
  const attrRe = /(?:^|\s)([a-zA-Z_][a-zA-Z0-9_]*)\s*=/g;
  for (const file of files) {
    const text = readFileSync(file, "utf8");
    for (const tag of findJsxTags(text)) {
      const deprecated = componentDeprecated.get(tag.name);
      if (!deprecated || deprecated.size === 0) continue;
      let attr;
      attrRe.lastIndex = 0;
      while ((attr = attrRe.exec(tag.body)) !== null) {
        const prop = attr[1];
        if (!deprecated.has(prop)) continue;
        const line = text.slice(0, tag.bodyStart + attr.index).split(/\r?\n/).length;
        hits.push({
          file: relative(webRoot, file),
          line,
          component: tag.name,
          prop,
          replacement: deprecated.get(prop) ?? "",
          text: text.split(/\r?\n/)[line - 1]?.trim() ?? "",
        });
      }
    }
  }
  return hits;
}

function readAntdVersion() {
  const pkg = JSON.parse(readFileSync(join(webRoot, "package.json"), "utf8"));
  const installed = JSON.parse(
    readFileSync(join(webRoot, "node_modules", "antd", "package.json"), "utf8"),
  );
  return { declared: pkg.dependencies?.antd, installed: installed.version };
}

/**
 * 扫描 src 下的 tsx，找出「整体废弃组件」的使用点。
 *
 * 两条都要查：
 *   1. 从 "antd" 具名导入废弃组件——哪怕没写 JSX，光是导入就说明在用；
 *   2. JSX 标签 <X> 与成员形式 <X.Y> 使用废弃组件。
 *      只有当该文件确实从 "antd" 导入了同名符号时才判定，
 *      避免把仓库自己定义的同名组件误伤。
 *
 * JSX 标签复用 findJsxTags（它能正确处理属性值里含 `>` 的情况），
 * 不自己写脆弱的正则。
 */
function findDeprecatedComponentUsages(deprecatedComponents) {
  const files = walk(srcRoot, (f) => f.endsWith(".tsx"));
  const hits = [];
  const importRe = /import\s+(type\s+)?\{([^}]*)\}\s*from\s*['"]antd['"]/g;
  const lineOf = (text, offset) => text.slice(0, offset).split(/\r?\n/).length;
  const lineText = (text, offset) =>
    text.split(/\r?\n/)[lineOf(text, offset) - 1]?.trim() ?? "";
  for (const file of files) {
    const text = readFileSync(file, "utf8");
    // 该文件从 "antd" 具名导入的符号 → 字符偏移
    const imported = new Map();
    importRe.lastIndex = 0;
    let match;
    while ((match = importRe.exec(text)) !== null) {
      if (match[1]) continue; // import type { ... } 是纯类型导入，不构成运行时用法
      const bodyStart = match.index + match[0].indexOf(match[2]);
      for (const part of match[2].split(",")) {
        const raw = part.trim();
        if (!raw) continue;
        const name = raw.split(/\s+as\s+/)[0].trim();
        if (!name || imported.has(name)) continue;
        imported.set(name, bodyStart + match[2].indexOf(raw));
      }
    }
    for (const [name, offset] of imported) {
      if (!deprecatedComponents.has(name)) continue;
      hits.push({
        kind: "import",
        file: relative(webRoot, file),
        line: lineOf(text, offset),
        component: name,
        text: lineText(text, offset),
      });
    }
    for (const tag of findJsxTags(text)) {
      const name = tag.name;
      if (!deprecatedComponents.has(name)) continue;
      if (!imported.has(name)) continue; // 不是从 antd 导入的同名符号，不判定
      hits.push({
        kind: "jsx",
        file: relative(webRoot, file),
        line: lineOf(text, tag.start),
        component: name,
        member: tag.body.startsWith("."),
        text: lineText(text, tag.start),
      });
    }
  }
  return hits;
}

const failures = [];

// ── 1. antd 版本一致性 ────────────────────────────────────────────────
const { declared, installed } = readAntdVersion();
if (declared !== installed) {
  failures.push(`antd 版本不一致：package.json 声明 ${declared}，node_modules 实际 ${installed}`);
}

// ── 2. 按组件作用域扫描废弃属性 ────────────────────────────────────────
const componentDirs = collectComponentDirs();
const componentDeprecated = new Map();
let deprecatedTotal = 0;
for (const [name, dir] of componentDirs) {
  const props = collectDeprecatedPropsOf(dir);
  if (props.size > 0) {
    componentDeprecated.set(name, props);
    deprecatedTotal += props.size;
  }
}

const hits = findUsages(componentDeprecated);

if (hits.length > 0) {
  failures.push(`发现 ${hits.length} 处 antd 已废弃属性用法（antd ${installed}）：`);
  for (const hit of hits) {
    const hint = hit.replacement
      ? `请改用 \`${hit.replacement}\``
      : "请查 antd 6 迁移说明";
    failures.push(
      `  ${hit.file}:${hit.line}  <${hit.component} \`${hit.prop}\`> 已废弃，${hint}`,
    );
    failures.push(`      ${hit.text}`);
  }
}

// ── 3. 组件级废弃：组件本身已整体废弃，下个大版本移除 ────────────────────
// Requirement: D-090 — AntD 废弃属性不允许保留，守卫阻断。
// 组件整体废弃同理不允许保留：它在 antd 里不标 @deprecated（标了 tsc 就会红），
// 只会静悄悄地打出 devUseWarning，直到下个大版本被移除时才炸。
const deprecatedComponents = collectDeprecatedComponents(componentDirs);

const missingDeprecated = crossCheckDeprecatedComponents(componentDirs, deprecatedComponents);
if (missingDeprecated.length > 0) {
  failures.push(
    `组件级废弃检测失灵：antd 源码里有 ${missingDeprecated.length} 个整体废弃组件未被识别`,
  );
  for (const item of missingDeprecated) {
    failures.push(`  ${item.file}  <${item.name}> 带 Deprecated.displayName 但未识别`);
  }
}

const componentHits = findDeprecatedComponentUsages(deprecatedComponents);

if (componentHits.length > 0) {
  const files = new Set(componentHits.map((hit) => hit.file));
  failures.push(
    `发现 ${componentHits.length} 处 antd 已整体废弃组件用法（antd ${installed}，涉及 ${files.size} 个文件）：`,
  );
  for (const hit of componentHits) {
    const replacement = deprecatedComponents.get(hit.component);
    const hint = replacement
      ? `请改用 \`${replacement}\``
      : "请改用非废弃的等价实现（语义化 HTML 或 antd 6 其他组件）";
    const usage =
      hit.kind === "import"
        ? `从 "antd" 具名导入已整体废弃组件 <${hit.component}>`
        : `JSX 使用已整体废弃组件 <${hit.component}${hit.member ? ".*" : ""}>`;
    failures.push(
      `  ${hit.file}:${hit.line}  ${usage}：该组件在 antd ${installed} 已整体废弃，下个大版本移除，${hint}`,
    );
    failures.push(`      ${hit.text}`);
  }
}

if (failures.length > 0) {
  console.error("✗ Ant Design 规范守卫未通过\n");
  console.error(failures.join("\n"));
  process.exit(1);
}

console.log(
  `✓ Ant Design 规范守卫通过（antd ${installed}，覆盖 ${componentDeprecated.size} 个组件 / ${deprecatedTotal} 个废弃属性定义 / ${deprecatedComponents.size} 个整体废弃组件（${[...deprecatedComponents.keys()].join("、") || "无"}），0 处违规）`,
);
