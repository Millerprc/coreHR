# coreHR Design System v1

> 状态：`MIGRATION_INPUT / PROPOSED`（方向A/B尚未批准）
> 版本：v0.1-draft
> 日期：2026-08-09
> 适用范围：第零阶段及后续所有 Web 管理端页面

> 权威说明：本文件保留视觉方向与Token候选输入。Ant Design版本策略、页面载体和导航规则以[Ant Design页面与交互载体规范](./antd-page-interaction-standard.md)为准；方向A/B在产品决策人批准前不得作为开发依据。

## 0. 文档目的

本文件定义 coreHR 管理端的整体视觉语言，包含 **design tokens**、**组件使用规则** 和 **两个方向（A / B）对比**。

任何后续页面必须使用本文件定义的 token，不在页面内硬编码颜色、字体、间距。

## 1. 设计原则（不管 A 还是 B 都遵守）

1. **以数据密度为先**：HRIS 不是消费应用，每屏要能展示尽可能多的有效信息
2. **留白服从信息**：宁可在单卡片上紧凑，也不在大屏上散开
3. **状态用颜色 + 文字 + 图标三重表达**：不只用颜色（无障碍要求）
4. **键盘可达**：每个交互必须有焦点环 + 键盘可达
5. **响应式可降级**：主屏 1440px，缩到 1100px 仍可用，再小到 760px 是"可用降级"而不是"完美"
6. **暗色模式必须**——HR 系统 24/7 使用

## 2. Design Tokens

token 命名遵循 antd v6 `ConfigProvider.theme.token` 规范，集成时一一对应。

### 2.1 颜色

| Token 名 | 方向 A（专业企业） | 方向 B（现代 SaaS） | 用途 |
|---|---|---|---|
| `colorPrimary` | `#1B4DFF` | `#8B5CF6` | 主操作按钮、链接、激活态 |
| `colorPrimaryHover` | `#3B6AFF` | `#A78BFA` | 主操作悬停 |
| `colorPrimaryActive` | `#0A2A8C` | `#7C3AED` | 主操作按下 |
| `colorInfo` | `#06B6D4` | `#EC4899` | 信息提示（粉色作为 B 方案差异点）|
| `colorSuccess` | `#10B981` | `#10B981` | 成功状态 |
| `colorWarning` | `#F59E0B` | `#F59E0B` | 警告 |
| `colorError` | `#EF4444` | `#EF4444` | 错误 |
| `colorTextBase` | `#0F172A` | `#0F172A` | 主文字 |
| `colorTextSecondary` | `#475569` | `#4B5563` | 次文字 |
| `colorTextTertiary` | `#94A3B8` | `#9CA3AF` | 辅助文字 |
| `colorBgLayout` | `#F1F5F9` | `#FAFAF9` | 整体背景 |
| `colorBgContainer` | `#FFFFFF` | `#FFFFFF` | 卡片背景 |
| `colorBgElevated` | `#FFFFFF` | `#FFFFFF` | 浮层背景 |
| `colorBorder` | `#E2E8F0` | `#E5E7EB` | 边框 |
| `colorBorderSecondary` | `#F1F5F9` | `#F3F4F6` | 次边框 |

### 2.2 渐变

| 用途 | 方向 A | 方向 B |
|---|---|---|
| 主按钮 / 品牌 | `linear-gradient(135deg, #1B4DFF 0%, #0A2A8C 100%)` | `linear-gradient(135deg, #8B5CF6 0%, #EC4899 100%)` |
| 侧栏 Header | 纯色 `#0F172A` | 纯色 `#FFFFFF` + 边线 |
| 进度条 | `linear-gradient(90deg, #1B4DFF 0%, #06B6D4 100%)` | `linear-gradient(90deg, #8B5CF6 0%, #EC4899 100%)` |
| 登录页背景 | `linear-gradient(135deg, #0A2A8C 0%, #1B4DFF 100%)` | `linear-gradient(135deg, #FAFAF9 0%, #F3E8FF 50%, #FCE7F3 100%)` |

### 2.3 字号

| Token | px | rem | 用途 |
|---|---|---|---|
| `fontSize` | 14 | 0.875 | 正文 |
| `fontSizeSM` | 12 | 0.75 | 辅助 |
| `fontSizeLG` | 16 | 1 | 强调 |
| `fontSizeXL` | 20 | 1.25 | 卡片标题 |
| `fontSizeHeading1` | 28 | 1.75 | 页面主标题 |
| `fontSizeHeading2` | 22 | 1.375 | 区块标题 |
| `fontSizeHeading3` | 18 | 1.125 | 卡片标题 |
| `fontSizeHeading4` | 15 | 0.9375 | 子标题 |

字体优先级（系统栈）：
```
-apple-system, BlinkMacSystemFont, "Segoe UI",
"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei",
sans-serif
```

数字专用（金额、工号、人数）`font-feature-settings: 'tnum' 1;` 启用等宽数字。

### 2.4 间距

8px 基准（不要出现 5px / 7px / 13px 这类 magic number）。

| Token | px | 用途 |
|---|---|---|
| `paddingXS` | 4 | 极小内距 |
| `paddingSM` | 8 | 标签、chip |
| `padding` | 12 | 表单元素 |
| `paddingMD` | 16 | 卡片内距 |
| `paddingLG` | 24 | 区块内距 |
| `paddingXL` | 32 | 页面边距 |
| `marginXS` / `marginSM` / `margin` / `marginLG` | 同上 | |

### 2.5 圆角

| Token | px | 用途 |
|---|---|---|
| `borderRadiusXS` | 4 | 小 tag、badge |
| `borderRadiusSM` | 6 | 输入框 |
| `borderRadius` | 8 | 按钮、小卡片（方向 A 默认）|
| `borderRadiusLG` | 12 | 大卡片、modal |
| `borderRadiusXL` | 16 | 登录页大卡片（方向 B）|
| `borderRadiusRound` | 999 | 头像、tag |

**方向 A 默认圆角偏小**（专业感），**方向 B 默认圆角偏大**（现代感）。

### 2.6 阴影

| Token | 值 | 用途 |
|---|---|---|
| `boxShadow` | `0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.06)` | 卡片 |
| `boxShadowSecondary` | `0 4px 12px rgba(0,0,0,0.08)` | 浮层、下拉 |
| `boxShadowTertiary` | `0 12px 32px rgba(0,0,0,0.12)` | modal、drawer |
| `boxShadowPrimary` | `0 8px 20px rgba(<colorPrimary>, 0.32)` | 主按钮 |

### 2.7 焦点环

所有可交互元素必须有 `focus-visible` 焦点环：

```css
:focus-visible {
  outline: 3px solid <colorPrimary at 16% alpha>;
  outline-offset: 2px;
}
```

## 3. 组件使用规则

### 3.1 按钮

| 场景 | 用法 |
|---|---|
| 主操作（提交、保存、新建） | `<Button type="primary">` |
| 次操作（取消、关闭） | `<Button>` 默认 |
| 危险操作（删除、注销） | `<Button danger>` |
| 链接式操作 | `<Button type="link">` |
| **禁用 button[type=primary] + 文字** | 永远不要，违反无障碍 |
| **3 个以上 primary 按钮同屏** | 拆成 1 primary + N default |

按钮内**不**放图标 + 长文字（最多 3 字 + 图标）。

### 3.2 表单

- 标签在输入框**上方**（不是左侧），响应式时不变
- 必填项**不**用红色星号，改用 `必填` 灰色文字（无障碍更好）
- 错误信息用 `Alert type="error"` 放表单顶部，**不**放每个字段下
- 提交按钮在表单底部右侧，左侧放"取消"

### 3.3 表格

- **禁止斑马纹**（antd 默认关闭）——大表会乱
- 表头必加 `tooltip` 说明列含义
- 操作列固定在右侧，`width: 180px`
- 批量操作顶部加 `Alert` + Checkbox
- 数据 > 100 行必须服务端分页
- 行点击进详情；操作列按钮进编辑

### 3.4 状态色

| 状态 | 主色 | 文字色 | Tag 变体 |
|---|---|---|---|
| 草稿 / 待提交 | `#94A3B8` | `#475569` | `default` |
| 审批中 / 进行中 | `#F59E0B` | `#92400E` | `warning` |
| 已生效 / 启用 | `#10B981` | `#065F46` | `success` |
| 失败 / 异常 | `#EF4444` | `#991B1B` | `error` |
| 已作废 | `#94A3B8` | 文字加 line-through | `default` |

**所有状态都配文字前缀**：`<Tag color="success">已生效</Tag>` 而不是只靠颜色。

### 3.5 数字 / 金额显示

- 数字用等宽（`font-feature-settings: 'tnum' 1;`）
- 金额保留 2 位小数 + 千分位 + 币种符号：`¥ 1,234.56`
- 负数红色：`<span style="color: #EF4444">-¥ 123.45</span>`
- 大数字简化：1000 → 1.0k，10000 → 1.0w

### 3.6 占位 / 加载 / 错误 / 空状态

每个数据视图必须 4 个状态都有：

| 状态 | 组件 | 说明 |
|---|---|---|
| 加载中 | `<Skeleton active paragraph={{ rows: 4 }}>` | 不用 Spinner |
| 空数据 | `<Empty description="暂无数据" />` + 操作按钮 | 给出"为什么空"和"下一步" |
| 错误 | `<Result status="error" title="加载失败" subTitle="..." />` | 必须有"重试"按钮 |
| 成功 | 实际内容 | — |

## 4. 布局

### 4.1 整体

```
┌─────────────────────────────────────────────────┐
│ Sider (220px)  │  Header (60-76px)               │
│  品牌           │   面包屑 / 标题 / 用户头像     │
│  导航菜单       ├─────────────────────────────────┤
│                 │                                 │
│                 │  Content (padding 24px)          │
│                 │   - 页面标题 + 描述              │
│                 │   - 主操作按钮组（右上）         │
│                 │   - 筛选 / 搜索                  │
│                 │   - 数据区（卡片/表格/Tab）     │
│                 │                                 │
└─────────────────────────────────────────────────┘
```

### 4.2 响应式断点

| 断点 | 行为 |
|---|---|
| ≥ 1440px | 全功能 |
| 1100 ~ 1440px | Sider 仍 220px，Content 自适应 |
| 760 ~ 1100px | Sider 折叠为 64px（只图标），Header 精简 |
| < 760px | "可用降级"——Sider 隐藏为抽屉，表格转卡片化布局 |

### 4.3 页面结构模板

```tsx
<PageHeader
  title="组织管理"
  description="维护业务组织树、法人、负责人、BP 等关系"
  actions={[<Button>导出</Button>, <Button type="primary">新建组织</Button>]}
/>
<FilterBar filters={...} onChange={...} />
<Table ... />
```

## 5. 暗色模式

第一阶段后期到第三阶段必须支持。设计 token 已命名 `colorBgLayout` 等，antd 6 切换 `algorithm: darkAlgorithm` 自动派生。

关键原则：
- 不要硬编码颜色 hex，**全部用 token**
- 阴影在暗色下保留但减弱（`0 4px 12px rgba(0,0,0,0.32)`）
- 主按钮在暗色下用稍亮的色（方向 A 用 `#3B6AFF` 替代 `#1B4DFF`）
- 渐变在暗色下保留（不会变得刺眼）

## 6. 国际化

- 所有文字 token 化，未来 i18n 切 token 文件
- 日期格式 `2026-08-09` ISO 8601，业务日期不要写中文
- 货币显示跟随 locale：`¥` / `$` / `€` / `₽`
- 表头对齐按语义：文字左对齐，数字右对齐，状态居中

## 7. 可访问性（a11y）

- 所有交互元素 `aria-label` 或可见文字
- 颜色对比度 ≥ 4.5:1（WCAG AA）
- `prefers-reduced-motion: reduce` 时关闭所有动画（现有 CSS 已实现）
- 键盘焦点环必显示
- 表单错误用 `aria-invalid="true"` + `aria-describedby`

## 8. 与 antd 6 的集成

```tsx
// apps/web/src/main.tsx
import { ConfigProvider, theme } from 'antd'

const themeConfig = {
  // 方向 A
  token: {
    colorPrimary: '#1B4DFF',
    colorInfo: '#06B6D4',
    colorSuccess: '#10B981',
    colorWarning: '#F59E0B',
    colorError: '#EF4444',
    colorTextBase: '#0F172A',
    colorBgLayout: '#F1F5F9',
    borderRadius: 8,
    fontSize: 14,
  },
  algorithm: theme.defaultAlgorithm,
  // 暗色模式切换
  // algorithm: theme.darkAlgorithm,
}

<ConfigProvider theme={themeConfig}>
  <App />
</ConfigProvider>
```

## 9. 方向 A vs 方向 B 选择

| 维度 | A · 专业企业 | B · 现代 SaaS |
|---|---|---|
| 主色 | `#1B4DFF` 蓝 | `#8B5CF6` 紫 |
| 辅色 | `#06B6D4` 青 | `#EC4899` 粉 |
| 圆角 | 8px | 12px |
| 字体 | 偏稳重 | 偏圆润（letter-spacing -0.3）|
| 卡片 | 顶部色条 | 顶部色条 |
| 阴影 | 中等 | 偏柔 |
| 登录页 | 深蓝渐变 | 浅色 + 紫粉晕染 |
| 适合 | 银行/国企/制造 | 互联网/SaaS/外企 |
| HRIS 行业参考 | Workday / 飞书招聘 | BambooHR / Lattice |

## 10. 文件结构（实施阶段）

```
apps/web/src/
├─ theme/
│  ├─ tokens.ts                # 所有 design token 常量
│  ├─ theme-a.ts               # 方向 A ConfigProvider 配置
│  ├─ theme-b.ts               # 方向 B ConfigProvider 配置
│  └─ ThemeProvider.tsx        # 运行时切换
├─ components/                 # 通用 UI 组件
│  ├─ PageHeader.tsx
│  ├─ FilterBar.tsx
│  ├─ StatusTag.tsx
│  └─ StatCard.tsx
└─ styles/
   ├─ reset.css
   └─ typography.css
```

## 11. 评审 & 决策

| 日期 | 动作 | 状态 |
|---|---|---|
| 2026-08-09 | 起草 v0.1，两个方向 A/B 对比 | `Proposed` |
| 待用户 | 选择方向 A 或 B | — |
| 选定后 | 把 token 接入 ConfigProvider，迁移现有页面 | — |
| 选定后 | 补全暗色模式 | — |
