# Moka People × coreHR 功能缺口对照与补活路线

> 生成日期：2026-08-20（原始盘点） / **2026-10-24 复核更新**
> Moka 侧数据来源：Moka People 生产构建 `20261022-1930-c4dc3-release`（前端 bundle 静态还原 + 已登录会话 UI 核对）
> coreHR 侧数据来源：`apps/api/src/hris/modules/**`、`apps/api/alembic/versions/**`、`apps/web/src/business/**` 全量代码盘点
> 采集方法与可复现脚本见 `tmp/moka-recon/`

> **2026-10-24 复核说明**：本文档的结论基于 2026-08-20 的代码盘点。2026-10-24 对核心条目做了逐项复验，**已修正 1 条过时结论（汇报关系「无写入路径」）**，并新增 §3.12「Moka 五项功能复刻对照」记录本轮复刻的语义决策与在建状态。语义决策条目见 `docs/01-foundation/03-项目决策.md` §8.5（D-102 ~ D-107），实现层依据见 `docs/review/moka-5-feature-decisions-2026-10-24.md`。

---

## 0. 结论

**能补，但不是"补 66 个文件"那么简单。**

> **2026-10-24 进展快照（本轮）**
>
> | 维度 | 8 月 20 日盘点 | 10 月 24 日现状 |
> |---|---|---|
> | 数据库表 | 72 | **91**（新增人员修正版本、审批流转历史、消息内核、假期发放批次、排班类型/草稿/换班、授权登记、后台任务表等） |
> | Alembic 迁移 | 16 | **32**（单链、单根、单头，head = `f2r000000001`） |
> | 汇报关系 | 死模型 | **已全通**（POST/GET/DELETE + 双 Tab + 生效区间） |
> | 审批动作 | 只有同意/驳回 | **8 个动作各自独立入口** + 显式状态机 + 只追加流转历史（D-095 红线落地） |
> | 假期余额 | 有账户有流水 | 账户/流水**本来就是真余额**；本轮补**发假明细 + 时点余额 + 计提骨架** |
> | 排班 | 只有班次与排班结果 | 本轮补**排班类型 + 草稿发布 + 换班 + 批量排班 + 规则集版本化修复** |
> | 历史组织架构 | 未开放时点查询 | 本轮开放 **`as_of` 时点切片**（D-103） |
> | 历史花名册 | 无 | 本轮建**时点花名册**（D-102） |
> | 兼岗 | 挂在 employment 级 | 本轮改为 **person 级权威载体**（D-104） |
> | Pencil 画板 | 6 张 | **13 张**（新增员工档案编辑态/修正态、历史花名册、新建兼岗 Modal、组织架构查看日期、考勤发假明细与排班管理、消息中心铃铛与 Drawer） |
>
> **仍未解决、且本轮明确不做的**：请假不走审批流（需 BPMS 定稿后接入）、薪酬/绩效/报表三大空白、企业规则输入（假期计提与排班规则取值）、信息健康度（D-101 DEFERRED）。
>
> **收工实测（2026-10-24 晚，主 agent 独立复跑）**
>
> | 门禁 | 结果 |
> |---|---|
> | 后端 `alembic upgrade head` + `alembic check` | **零漂移**（32 条迁移，单根单头无分支，head = `f2r000000001`） |
> | 后端 `pytest`（**公开仓模式**，不装私有包） | **357 passed / 20 skipped**（全量 377 条；skip = 流程写路径用例，装上私有包才跑） |
> | 后端 `pytest`（**装私有包模式**） | **373 passed / 4 skipped**（同一批 377 条，16 条由 skip 转 pass） |
> | 前端 `check-antd-usage.mjs` | **0 处违规**（antd 6.5.2 / 45 组件 / 201 废弃属性） |
> | 前端 `npx tsc -b` | **exit 0** |
> | 前端 `npm run test:run` | **35 文件 / 115 测试全绿** |
> | 版权头守卫 `check-license-header.mjs` | **375 个源文件 0 违规**（补写脚本幂等：0 变更） |
> | 私有实现防误发守卫 `check-private-package-isolation.mjs` | **三闸全过**（已跟踪文件 364 个，私有实现 0 个；已做过真实红→绿验证） |
>
> **本轮新增的四块**：①考勤 7 类高风险动作拆独立权限码（16 个端点）；②一阶段组织编制 3 条 P0（初始化导入整批不入库 / 事件生效前复校 / 组织编码避让）；③Kernel 后台任务框架（任务表 + 独立 Worker + 退避重试 + 管理查询与手动重试，首批接入导入执行）；④Open Core Wave 2a 流程引擎拆包（私有包 + AST 架构守卫红绿验证）。
>
> **本轮晚间追加（2026-10-24 20:00 之后）**：①**考勤冻结成为硬闸**（D-113）——冻结账期禁止补录打卡（409 `ATTENDANCE_PERIOD_FROZEN`），业务日按业务时区折算，幂等命中优先于冻结；②**正式签发公钥替换占位公钥**（D-114）+ 离线签发工具（仓库外）；③**私有实现防误发三闸**（`.gitignore` + 仓库守卫 + CI）；④**零 CI → 最小 CI 护栏**（迁移单链单头 + 漂移检查 + 用例 + 前端类型/用例/构建 + 三道仓库守卫）；⑤**读路径索引三件套**（D-115：待办 `(assignee_ref, status, created_at)`、审计 `action`/`object_type`、打卡 `(employment_id, punched_at)`）。
>
> **本轮深夜追加（2026-10-24 20:00 之后，D-116）**：⑥**批量考勤计算从「逐人单选」改为「范围三态 + 后台任务」** —— 原契约是「一次算一个人」，200 人企业要点 200 次；现在默认**全员**，可切「指定人员 / 排除人员」，一次提交覆盖整个范围，日报与月报**都走后台任务**（Worker 执行 + 2 秒轮询 + 提交时冻结预检 + 单人失败保存点隔离 + 长任务续租）。既有单人端点**完全保留**，批量是新增路径。
>
> **收工实测（2026-10-24 深夜，主 agent 独立复跑）**
>
> | 门禁 | 结果 |
> |---|---|
> | 后端 `alembic upgrade head` + `alembic check` | **零漂移**（32 条迁移，单根单头，head = `f2r000000001`） |
> | 后端 `pytest`（**公开仓模式**，不装私有包） | **372 passed / 20 skipped**（全量 392 条；较上轮 +15 = D-116 新增批量计算用例，无回归） |
> | 后端 `pytest`（**装私有包模式**） | **388 passed / 4 skipped**（同一批 392 条，16 条由 skip 转 pass） |
> | 前端 `check-antd-usage.mjs` | **0 处违规**（antd 6.5.2 / 45 组件 / 201 废弃属性） |
> | 前端 `npx tsc -b` | **exit 0** |
> | 前端 `npm run test:run` | **36 文件 / 118 测试全绿**（较上轮 +1 文件 / +3 测试 = `ReportPanel.test.tsx`） |
> | 版权头守卫 `check-license-header.mjs` | **378 个源文件 0 违规**（较上轮 +3 = 2 个前端新文件 + 1 个后端新测试） |
> | 私有实现防误发守卫 `check-private-package-isolation.mjs` | **三闸全过**（已跟踪文件 364 个，私有实现 0 个） |
> | 端到端实跑 | 向演示库投真实批量任务 → Worker `claimed=1` → 任务 `succeeded`，result 统计正确（验证后已清理测试任务行） |
>
> **一句话**：Moka 差距最大的仍是「可配置性深度」与「三大套件」（薪酬/绩效/报表）；本轮把**功能结构**层面的五项缺口补齐了，剩下的是**企业输入**与**平台内核**两类非本轮可解的活。

三句话：

1. **coreHR 的地基是扎实的**——组织主数据、编制、异动事件模型、审批流引擎（已支持条件分支 + 会签/或签）、假勤账本、审计与导入治理，这几块设计水平明显高于普通自研 HR 系统。

   但覆盖率要说实话，三个口径（都按 `nav-menu.txt` 可核）：
   - **按可见菜单叶子项计**（202 项）：coreHR 覆盖约 15 项 ≈ **8%**
   - **按业务功能菜单计**（剔除设置下 60+ 项纯配置，约 65 项）：coreHR 覆盖约 15 项 ≈ **23%**
   - **按一级业务域计**（12 个）：**6 个有实质实现**（工作台/人事/组织/入职/假勤/审批）+ **3 个部分**（报表/基础应用/我的团队）+ **3 个完全空白**（薪酬/绩效/人才星图）

   落差最大的不是"少"，而是**深**：Moka 279 个菜单项里 **161 条路由集中在 `/setting`**（占全站路由的 40%），说明成熟 HR SaaS 的产品深度主要在**可配置性**——而这恰好是 coreHR 完全没有的维度。
2. **最大的三块空白是「薪酬」「绩效」「报表/BI」**——Moka 在这三块有 47 + 28 + 11 条路由，coreHR **一张表都没有**。这不是"再写几个接口"的量级，是三个完整套件。
3. **但有一块"小而致命"的空白被低估了：审批引擎缺 6 个基础能力**（撤回、超时升级、代理审批、抄送、催办、加签）。Moka 的入职/转正/调岗/离职/请假/加班**全部挂在这套引擎上**。coreHR 现在的请假是"管理员直接 PATCH 置 approved"（`apps/web/src/business/features/attendance/LeavePanel.tsx:154`）——**这意味着 coreHR 现在还不能真正上线跑流程**。

**建议补活顺序**：Wave 1（把已有壳变活）→ Wave 2（补审批引擎底座）→ Wave 3（入职全流程，当前焦点）→ Wave 4（假勤补全）→ Wave 5（报表）→ Wave 6（薪酬）→ Wave 7（绩效）→ Wave 8（设置/集成/ESS）。

**给"猛猛补"的建议**：Wave 1 + Wave 2 加起来约 2 周，是"让 coreHR 从能演示变成能上线"的最小投入。薪酬和绩效可以延后到第四五阶段（16 号 PRD 里本来就把它们排在后面）。

---

## 1. Moka 功能蓝图（一手证据）

### 1.1 采集方法（可复现）

Moka 的前端是 webpack SPA，**静态资源匿名可访问**（`https://static-core.mokahr.com/`）。因此不需要逐页点 UI 就能拿到完整结构：

| 步骤 | 产物 | 规模 |
|---|---|---|
| `GET https://core.mokahr.com/` 取 HTML | `window.__MOKA_INIT__`（版本号/资源 origin）+ script/prefetch 清单 | — |
| 下载 `assets/moka-people.*.js`（主包） | 路由表 + 导航配置 + API 路径 + 中文文案 | 5.04 MB |
| 正则抽 `path:"..."` + `a.e("chunk")` | **React Router 全量路由 → chunk 映射** | **396 条** |
| 正则抽 `{url:"...",name:"..."|U("..."),authorityKey:"..."}` | **全站导航菜单树（含中文名 + 权限码）** | **279 项** |
| 正则抽 `"/api/..."` | **后端微服务 API 全貌** | **1507 条** |
| 抽 chunk→contenthash 映射 + 批量下载页面 chunk | 页面级字段/枚举/按钮文案 | 691 个 chunk |
| REA 静态分析（`rea analyze-javascript-application`） | 证据化的功能图谱 | 见 §6 |

**踩过的坑**（复用时注意）：
- webpack 的 chunk-map **key 是裸标识符，不带引号**（`p__staffManage__roster__index:"ea29..."`）。用 `"name":"hash"` 匹配会漏掉 90%。
- **同一 chunk 名对应多个 hash**（多套构建共存）。必须收集全部候选 hash 逐个探测 200，不能取第一个。
- `Get-Content` 在 PS 5.1 读无 BOM 的 UTF-8 会按 GBK 解码 → 中文全乱码，必须显式 `-Encoding UTF8`。

### 1.2 导航树（279 项节选，按业务域）

**工作台**（`/dashboard`）：工作台 · 数据看板 · Eva（AI 人事伙伴）· 任务中心 · 通知 · 待入职

**我的团队**（`/myTeam`）— 外部人员

**招聘**（`app.mokahr.com` ATS 外链）

**人事**（`/staffManage`）
| 二级菜单 | 路由 | 权限码 |
|---|---|---|
| 员工花名册 | `/staffManage/roster` | `staffManager_roster` |
| 信息健康度 | `/staffManage/informationHealth` | `auth_000562` |
| 试用期管理 | `/staffManage/probation` | `staffManager_formal_look` |
| 异动管理 | `/staffManage/jobChange` | `staffManager_transfer` |
| 合同管理 | `/staffManage/contract` | `contract` |
| 兼岗管理 | `/staffManage/staffList/6` | `auth_000042` |
| 项目组人员 | `/staffManage/projectTeamMembers` | `auth_12146` |
| 员工人力明细 | `/staffManage/manpower` | `hr_auth_12193` |
| └ 部门 / 成本中心 / 项目组 人力明细 | `/manpower/{department,costCenter,projectTeam}` | — |
| 离职管理 | `/staffManage/departure` | `auth_000626` |

**组织**（`/organization`）
| 二级菜单 | 路由 |
|---|---|
| 部门 | `/organization/structure/list` |
| 编制（+导入编制） | `/organization/headCountManage` |
| 成本中心 | `/organization/costCenter` |
| 项目组 | `/organization/projectTeam` |
| 组织架构（可视化图） | `/organization/graph` |
| 组织架构调整（方案 / 历史） | `/organization/adjustment{,/schemeForm,/schemeForm/history,/sheet}` |
| 汇报关系（管理 / 图） | `/organization/report/{manage,graph}` |
| **职务** | `/organization/position`（`organization_positionManage`） |
| **职位** | `/organization/jobPosition`（`organization_duty`） |
| 招聘需求 | `/organization/recruitment` |

> 注意：「职务」和「职位」是**两个独立菜单**。coreHR 把 `job_catalog` 做成「编制管理」里的一个 Tab，Moka 是拆开的。

**入职**（`/onboarding`）：入职人员（发起入职）· 入职任务

**假勤**（`/holiday`）
出勤记录：出勤月报 · 出勤日报 · 请假记录 · 加班记录 · 出差记录 · 外出记录 · 打卡记录 · 补卡记录
排班管理：排班管理 · 换班记录
假期账户：当前余额 · 发假明细
设置侧：`/setting/holiday/*` **22 条路由**（异常考勤规则/状态、考勤机、打卡方式、考勤统计、请假规则、加班规则、清零规则、排班规则、连排规则、假期日历、假期通知、人脸、班次管理、月报与月报字段…）

**薪酬**（`/salaryManage`）**47 条路由**：预算制定 · 预算分析 · 薪资档案 · 薪酬核算（薪资准备：社保公积金/其他薪资项目/在线编辑/数据导入/录入考勤结果/截止上月个税累计/专项附加扣除累计）· 数据对比 · 解析 Excel · 调整结果 · 复杂计薪 · 多人协作 · 发工资单 · 银企直联 · 成本分摊结果 · 批量调薪 · 人员报送（纳税人员报送/减员报送）· 个税申报（明细/专项附加扣除）· 在线缴款 · 报税主体管理 · 减除费用确认 · 参保档案 · 参保月报

**绩效**（`/perf`）**28 条路由**：目标跟进 · 目标地图 · 绩效待办（员工绩效/组织绩效）· 绩效活动/活动详情（异常/申诉/被考核人/评分表）· 评估方案 · 模板管理 · 报告配置 · 批量任务 · 目标类型

**基础应用**（`/baseApplication`）：数据填报 · 签署中心

**审批**（`/workflow`）

**报表中心**（`/biReport`）：主页 · 模板库 · 数据源 · 自定义看板

**人才星图**（`/aiTalent`，Moka 2026 新增）：概览 · 人才画像 · 岗位画像 · 反馈管理

**AI 识人**（`/aiRecognizes`）— 简历解析

**设置**（`/setting`）**161 条路由**，8 大子域：
- 基础设置：功能设置（人事/组织/绩效/工作台待办）、组合字段设置
- 人事设置：员工信息设置（个人信息/任职信息/兼岗信息/履历信息/培训信息/合同信息/招聘信息/所属成本中心/所属项目组/其他信息）· 信息健康度规则 · 事件原因 · 合同设置 · 工号管理 · 规则设置 · 政策制度 · 试用期设置（评价规则/等级规则/考核模板/转正方案/结果方案）· 智能标签管理
- 入职设置：入职计划设置 · 任务设置 · 通知设置 · 欢迎信 · 信息采集 · 入职信息设置
- 审批设置：流程设计器（创建审批/创建表单/创建信息/测试流程）
- 组织设置：编制方案 · 法人公司 · 工作地点 · 职级管理 · 部门信息设置（基础信息/组织职责）· 成本中心信息设置 · 项目组信息设置 · 编制信息设置 · 职务管理（职务类别/职务族/职务字段）· 成本信息 · 成本职责
- 权限：账号管理 · 角色管理（授权设置）
- 假勤设置 / 绩效设置 / 薪酬设置 / 社保设置 / 企业安全（水印·隐私政策）· 外部接口 · 任务中心 · 第三方（电子签/银企直连/实名认证/身份证识别/Eva 计费）· 操作日志

### 1.3 后端微服务全景（1507 个 API，按前缀）

| 前缀 | 数量 | 域 |
|---|---|---|
| `/api/core/*` | 239 | 核心（员工档案等） |
| `/api/organization/*` | 234 | 组织 |
| `/api/perf/*` | 179 | 绩效 |
| `/api/salary/*` | 171 | 薪酬 |
| `/api/abs/*` + `/api/absence/*` | 177 | 假勤（考勤/请假/加班/排班/班次/补卡/外勤/差旅/假期余额/时区） |
| `/api/onboarding/*` | 85 | 入职 |
| `/api/personnel/*` | 81 | 人事异动 |
| `/api/mobile/*` | 57 | 移动端 |
| `/api/workflow/*` + `/api/workflowplatform/*` | 69 | 审批 |
| `/api/universal/*` | 53 | 通用 |
| `/api/common/*` | 41 | 公共 |
| `/api/outer/*` | 19 | 外部 |
| `/api/welfare/*` | 18 | 福利 |
| `/api/authorization/*` | 17 | 权限 |
| `/api/esign/*` | 16 | **电子签** |
| `/api/aggregate/*` | 16 | 聚合 |
| `/api/oapi/*` | 10 | **开放平台 API** |
| `/api/absence-statistics/*` | 8 | 假勤统计 |
| `/api/gateway/*` | 3 | 网关 |
| `/api/chatbot/*` | 1 | AI |

> `/api/esign/*` 与 `/api/oapi/*` 的存在说明 Moka 把**电子签**和**开放平台**当作一等公民，不是后加的边角。

---

## 2. coreHR 现状（代码盘点摘要）

| 维度 | 数量 | 说明 |
|---|---|---|
| 后端模块 | 5（platform / workforce / workflow / attendance / system） | — |
| 数据库表 | **72** | 16 条 Alembic 迁移 |
| Endpoint | 164（其中 162 可达） | `workforce/api.py` 的 2 个是死代码 |
| 前端 workspace | 11（`positions` 标记 `available: false`，实际不可达） | — |
| 前端 feature 目录 | 7 | — |
| 测试 | 后端 11 文件 / 前端 23 文件 | **后端无 endpoint 级集成测试** |

**做得好的地方**（别在补活时推翻）：
- 组织主数据是**生效日期化 + 版本化**模型（`organizations` / `organization_versions` / `organization_events` / `organization_cost_allocations` / `revenue_targets`…），比 Moka 的"直接改部门表"更严谨。
- `hr_events` 事件模型统一承载 9 种人事事件（`ONBOARDING`/`CONFIRMATION`/`TERMINATION`/`WITHDRAWAL`/`EMPLOYMENT_CORRECTION`/`TRANSFER`/`CONCURRENT_ASSIGNMENT`/`SECONDMENT`/`END_ASSIGNMENT`），带 `idempotency_key` + `request_checksum` + `before/planned/actual_payload` 三段式。
- 审批引擎**已支持条件分支**（算子 `eq/ne/in/not_in/gt/gte/lt/lte/exists/not_exists`，条件组 `all|any`，默认连线，多路命中报 `WORKFLOW_ROUTE_AMBIGUOUS`）+ **会签/或签**。
- 敏感字段（AESGCM 加密 + HMAC 检索摘要 + `reveal`/`expire` 显式授权）这一层做得比 Moka 细。

---

## 3. 对照表：Moka 有 / coreHR 缺

图例：✅ 已实现 ｜ ⚠️ 部分/有壳无流程 ｜ ❌ 完全没有

### 3.1 组织（Moka 21 路由 / coreHR 最完整的一块）

| Moka 功能 | 路由 | coreHR | 证据 / 差距 |
|---|---|---|---|
| 部门（树·详情·版本·生效日） | `/organization/structure/list` | ✅ | `organization_api.py:110-220`；`OrganizationWorkspace.tsx` + `OrganizationDetailWorkspace.tsx` |
| 编制（计划·规则·冻结·快照） | `/organization/headCountManage` | ⚠️ | `HeadcountWorkspace.tsx` 5 Tab；**Moka 有导入编制/编制方案两层** |
| 成本中心 | `/organization/costCenter` | ⚠️ | 有 `cost_centers` 表 + CRUD（`organization_api.py:324`），**无独立前端页** |
| 项目组 | `/organization/projectTeam` | ❌ | 无表无接口 |
| **组织架构可视化图** | `/organization/graph` | ❌ | coreHR 只有表格树，无图 |
| **组织架构调整（方案→校验→提交→生效→历史）** | `/organization/adjustment{,/schemeForm,/schemeForm/history}` | ⚠️ | 有 `organization_versions` + `organization_events`（**单次**变更），**无"调整方案"实体、无多步变更打包、无历史版本浏览页** |
| **汇报关系（管理 + 图）** | `/organization/report/{manage,graph}` | ✅ | **2026-10-24 复验：已全通**。`reporting_relations` 具备 POST / GET / DELETE 与 `effective_at` / `effective_to` 生效区间，前端 `ReportingWorkspace.tsx` 双 Tab（关系管理 / 关系图），实线与虚线各自独立成环（D-093）。本文档原结论「有定义无任何写入路径」**已过时，作废** |
| 职务 | `/organization/position` | ⚠️ | 后端 `job_catalog` 完整，前端藏在编制 Tab |
| **职位** | `/organization/jobPosition` | ❌ | `navigation.ts:44-48` `available:false`，且 `workspaceFromHash` 会回落 dashboard → **灰入口但完全不可达** |
| 招聘需求 | `/organization/recruitment` | ⚠️ | `RecruitmentWorkspace.tsx` 仅需求 CRUD；无渠道/面试/Offer 审批 |
| 部门信息设置 / 组织职责 / 成本中心信息设置 / 职务类别·族·字段 | `/setting/org/*` | ❌ | 设置模块整体缺失 |

### 3.2 入职（Moka 6 路由 + 6 条设置路由 / coreHR 当前焦点）

| Moka 功能 | coreHR | 证据 / 差距 |
|---|---|---|
| 入职人员列表（全部/待入职/已入职/已取消） | ⚠️ | 有 `hr_events` `ONBOARDING` + 应聘转录用，**无入职人员列表页** |
| **入职任务** | ❌ | grep `onboarding_task|checklist|入职清单` 零匹配 |
| **信息采集** | ❌ | 无 |
| **电子签署 / 签署状态** | ❌ | 无（`/api/esign/*` 对应的能力完全没有） |
| 批量发起入职 | ❌ | 无 |
| **入职计划设置 / 任务设置 / 通知设置 / 欢迎信 / 入职信息设置** | ❌ | `/setting/onboarding/*` 全无 |
| 报到流程审批 | ⚠️ | 审批引擎可发起，但业务对象**只支持 `hr_event`**（`workflow/extended_service.py:1356-1357`） |

> **入职是 Moka 与 coreHR 差距最大的业务域之一**：Moka 的入职 = 清单 + 任务 + 信息采集 + 电子签 + 欢迎信 + 通知 + 审批；coreHR 的入职 = 一个 `ONBOARDING` 事件。当前 input pack 03「入职流程图与审批规则」要补的正是这块。

### 3.3 人事（19 路由）

| Moka 功能 | coreHR | 证据 / 差距 |
|---|---|---|
| 员工花名册 | ✅ | `PeopleWorkspace.tsx` + `PersonnelSubrecordsPanel.tsx`（4 Tab + 7 类子记录） |
| **信息健康度** | ❌ | 无字段完整度治理、无缺失项提醒、无整改。**Moka 实为「信息采集+催办+审核」闭环**（见 §3.11） |
| 试用期管理（含考核详情 + 转正方案） | ⚠️ | 只有 `CONFIRMATION` 事件；**无试用期考核表、无评价规则/等级规则/考核模板** |
| 异动管理 | ✅ | `TRANSFER`/`SECONDMENT`/`CONCURRENT_ASSIGNMENT`/`END_ASSIGNMENT` 全有。**但无「批量异动」**（Moka 有批量异动 + 异动导入 + 草稿/继续编辑/放弃/自动撤销，见 §3.11） |
| 合同管理 | ⚠️ | CRUD + 到期提醒 + 变更续签解除；**附件/电子签章/合同模板全是 `metadata_payload` 自由 JSON** |
| 兼岗管理 | ⚠️ | 有 `CONCURRENT_ASSIGNMENT` 事件，但载体挂在 **employment 级**（`EmploymentAssignment.relation_type='concurrent'`），与规范 `05-*.md:172` 要求的 **person 级**不符；person 级的 `organization_person_relations` 字段齐全却**无任何写入路径**（死模型）。**2026-10-24 按 D-104 裁定：person 级为唯一权威载体**，employment 级保留任职类型语义、不再兼作兼岗载体 |
| **项目组人员** | ❌ | 无 |
| **员工人力明细（部门/成本中心/项目组三视角）** | ⚠️ | 只有 `headcount-results` 一个统计端点 |
| 离职管理 | ✅ | `TERMINATION` 事件 + `end_reason_code` |
| **签署中心** | ❌ | 无 |
| 历史花名册 | ⚠️ | **2026-10-24 复验**：8/9 张相关表已生效日期化（`employments` / `employment_assignments` / `reporting_relations` / `organization_person_relations` 等），`persons` 本身未版本化。缺的是**对外查询层**（按任意历史时点查当时的人员、组织与任职）。本轮按 D-102 补时点花名册，人员字段的时点值复用「人员修正版本」切片，不新建第二套人员版本表 |

### 3.4 假勤（19 路由 + 22 条设置路由）

| Moka 功能 | coreHR | 证据 / 差距 |
|---|---|---|
| 请假记录 | ⚠️ | 有 `leave_requests` + 余额账本 + 销假，**但不走审批流**（`LeavePanel.tsx:154`） |
| 出勤日报 / 月报 | ✅ | `attendance/extended_api.py:447-499`（单人）；**2026-10-24 深夜补批量路径**（D-116）：`POST /api/v1/attendance/calculation-tasks` 范围三态 + 后台任务，200 人规模不再逐人点 |
| 打卡记录 | ✅ | `attendance_punches`（幂等） |
| 排班管理 | ⚠️ | **2026-10-24 复验**：已有 `shifts`（班次）+ `schedule_assignments`（排班结果，UNIQUE employment+date）+ `GET /schedules`；缺轮班 / 弹性 / 自由班等排班类型、排班草稿与发布、月度发布、批量排班。另有真实缺陷：`shifts.rule_set_id` 指向**非版本化**规则集，旧班次会静默跟随新规则。本轮按 D-107 补骨架 |
| **加班记录 / 加班规则** | ❌ | 无 |
| **出差记录 / 外出记录 / 补卡记录** | ❌ | 无 |
| **换班记录** | ❌ | 本轮按 D-107 补 `schedule_swaps`（换班双方、原/新班次、日期、状态） |
| 假期账户 / 当前余额 / **发假明细** | ⚠️ | **2026-10-24 复验**：账户与不可变流水**已是一等实体**（`leave_balance_accounts` + `leave_balance_transactions`，`balance_before/after` 恒等 CHECK），`LeaveBalancePanel` 读的是**真余额**不是接口层汇总。真正缺的是「发假明细」（额度规则 / 发放批次）、自动计提调度器与**时点余额查询**。本轮按 D-107 补；`leave_types` 按 D-077 不做版本化，需要版本化的是**发假额度规则** |
| 异常考勤规则/状态、考勤机、打卡方式、考勤统计、请假规则、清零规则、假期日历、假期通知、人脸、班次管理、连排规则 | ❌ | `/setting/holiday/*` 22 条路由几乎全无 |

### 3.5 薪酬（Moka 47 + 15 设置路由 / coreHR **零**）

coreHR 全库仅有 4 个外键字段 `payroll_legal_entity_id` / `social_insurance_legal_entity_id` / `tax_legal_entity_id`（`workforce/models.py:630-641`），**无 `payroll` 模块目录、无表、无 endpoint**。

Moka 有：薪资档案 / 预算制定 / 预算分析 / 薪酬核算（8 个准备步骤）/ 复杂计薪 / 成本分摊 / 批量调薪 / 工资单 / 银企直联 / 纳税人员报送 / 个税申报 / 在线缴款 / 报税主体管理 / 参保档案 / 参保月报 / 减除费用确认。

**这是最大的单一空白，也是工作量最大的一块**（Moka 用 171 个 API 承载）。

### 3.6 绩效（Moka 28 + 9 设置路由 / coreHR **零**）

coreHR 的 11 个 workspace 里**没有绩效**。Moka 有：目标地图 / 目标跟进 / 绩效活动（员工+组织）/ 活动详情（异常/申诉/被考核人/评分表）/ 评估方案 / 模板管理 / 报告配置 / 批量任务 / 强制分布 / 绩效等级 / 目标库 / 目标类型。

**注意**：Moka 走的是「目标+持续跟进」路线，不是纯年度考核。coreHR 若补，建议对齐这条路线（`hr_events` 的事件模型天然适合承载"目标-跟进-评估"三段）。

### 3.7 报表与 BI（Moka `/biReport` + `/collabReporting` 6 + `/customLanding` 6 / coreHR 5 个端点）

| Moka 功能 | coreHR |
|---|---|
| BI 报表中心（模板库 / 数据源 / 自定义看板） | ❌ |
| **多人协作报表搭建器**（表单设置 → 自定义规则 → 任务汇总三步向导） | ❌ |
| 自定义落地页（月报/看板） | ❌ |
| 编制 vs 实际人数结果 | ✅ `GET /workforce/headcount-results` |
| 考勤日报 / 月报 | ✅ |
| 主数据 CSV 导出 | ✅（8 类） |
| **人数趋势 / 离职率 / 编制达成率 / 异动分析** | ❌ |

> coreHR 工作台的 5 个数字是**前端并发调 5 个 list 接口取 `length` 拼出来的**（`AppShell.tsx:70-82`），不是统计接口。且"编制月度版本"标题统计的其实是**计划条数**而非人数（`AppShell.tsx:76,100`）。

### 3.8 审批引擎（Moka `/workflow` + `/setting/approve/*`）

| 能力 | coreHR | 证据 |
|---|---|---|
| 流程定义 / 版本 / 发布 | ✅ | `workflow/api.py:29` + `extended_api.py:378` |
| 条件分支（9 算子 + all/any + 默认连线） | ✅ | `workflow/conditions.py:40-101` |
| 会签 / 或签 | ✅ | `workflow/schemas.py:62` |
| 驳回 | ⚠️ | 驳回即终止整条实例，**不支持退回上一节点/重投**（`extended_service.py:1324-1330`） |
| **撤回** | ❌ | `workflow_tasks` 无撤回状态；grep `撤回|withdraw` 仅命中招聘阶段 |
| **超时升级** | ❌ | `workflow_tasks` 无 `due_at`/`escalate_to`；grep `超时|escalat` 零匹配 |
| **代理/委托审批** | ❌ | grep `代理|delegat|proxy` 零匹配 |
| **抄送 CC** | ❌ | 无 |
| **催办/提醒** | ❌ | 无 |
| **加签/转办** | ❠️ | `workflow_tasks` 有 `decided_by`，但无转办动作 |
| **图形化流程设计器** | ❌ | 前端只有表格 + JSON 定义表单 |
| **业务对象联动** | ⚠️ | 只支持 `business_object_type == "hr_event"`，请假/合同挂不上 |

### 3.9 权限与治理

| Moka 功能 | coreHR |
|---|---|
| 角色管理 + 授权设置 | ❌ 只读（`GET /roles`） |
| **数据范围（行级/组织范围）权限** | ❌ `permissions` 只有 `code`/`name`/`module_code` |
| **字段级权限** | ❌ |
| **操作日志查询/导出** | ❌ `audit_logs` **只写不读** |
| **工号规则管理 / 组合字段设置 / 智能标签** | ❌ |
| **外部接口（开放平台）** | ❌ `outbox_events` 只写不读，无发布器 |
| **第三方：电子签/银企直连/实名认证/身份证识别** | ❌ |

### 3.10 其他

| Moka 功能 | coreHR |
|---|---|
| 员工自助 ESS（移动端·我的团队·我的薪酬·请假申请） | ❌ D-006 明确第一阶段不做 |
| 人才星图（AI 人才画像/岗位画像/反馈） | ❌ 但 **`person_labels` 表已建好**（`workforce/models.py:351`），**有表无任何读写路径**——可以直接启用 |
| AI 识人（简历解析）/ Eva 人事伙伴 | ❌ |
| 政策制度 / 欢迎信 | ❌ |
| 福利 `welfare` | ❌ |
| 培训 | ❌（外链） |

---

## 3.11 页面级功能点还原（211 个页面 chunk 的中文功能词）

从 211 个 `p__*` 页面 chunk 里抽出的中文字段（去重后 8483 行，按 83 个业务域聚合），是**比菜单名更细一层的证据**。下面 8 条是 coreHR 完全没做、但补起来路径清晰的能力：

### ① 信息健康度 = 「信息采集 + 催办 + 审核」闭环，不是评分看板

还原出的功能词：*采集频率 · 采集字段 · 适用范围 · 采集状态 · 不发起信息采集 · 立即发送 · 发送时间 · 截止日期 · 修改截止日期 · 已截止信息采集 · 已开启信息采集 · 采集中 · 审核中 · 催办 / 将催办 · 催办成功 · 周期性更新 · 单次更新 · 支持自动发起采集任务 · 关注员工的信息健康度 · 人员明细 · 人正在采集信息 · 信息健康度规则 · 更多规则设置 · 暂无符合条件的信息健康度*

> **这意味着 coreHR 缺的不是一个"信息完整度评分页"，而是一整套「向员工下发采集任务 → 员工填报 → HR 催办 → 审核关闭」的机制**——而这套机制**入职模块（信息采集）也要用**。做一次，两处受益。

### ② 组织架构调整 = 方案级工作流，不是单次改部门

还原出的功能词：*添加调整方案 · 方案名称 · 方案状态 · 调整范围 · 变更范围 · 创建人 · 生效日期 · 开始时间 / 结束时间 · 编辑方案 · 提交 · 历史提交 · 转交调整方案 / 将方案转交给 · 撤销 · 删除调整方案 · 操作日志 · 查看规则 · 变更部门信息 · 变更部门职责 · 变更上级部门 · 变更员工到该部门 · 变更员工 · 变更兼岗 · 变更编制计划 · 变更启用中的部门 · 变更前 / 变更后 · 变更前上级部门 / 变更后上级部门 · 编制周期 · 编制数据存在问题 · 拆解编制数已超过上级同周期的拆解编制数 · 拆解编制数已大于计划编制数 · 不变更的不填写*

> coreHR 现在的 `organization_versions` + `organization_events` 是**单次变更**；Moka 是**「方案」把多步变更打包 → 校验（编制拆解规则）→ 提交 → 生效 → 历史版本**。coreHR 的编制数据模型足以支撑校验，但缺"方案"这一层实体。

### ③ 员工人力明细 = 周期性「人力填报」+ 成本分摊规则

还原出的功能词：*人力填报规则 · 人力规则 · 填报周期 · 每月 / 每三个月 / 每半年 / 每一年 · 发起时机 · 系统会在指定时间首次发起填报 · 后续每半年都会发起填报 · 后续每年都会发起填报 · 如当月无对应日期则按当月最晚日期发送 · 发起填报 · 工作年月 · 默认分摊规则 · 编辑默认分摊规则 · 分摊比例之和需等于 100 · 部门分摊比例 · 成本分摊时按异动后部门归属 · 按异动生效日期折算归属 · 编辑人力明细 · 请手动计算*

> coreHR 有 `headcount_plans`（计划）和 `organization_cost_allocations`（分摊），**但缺「填报」这个动作**——没有"每月自动发起一次人力填报、HR 填实际人数"的循环。Moka 用 `headcount_snapshots` 的等价物承接结果。

### ④ 批量异动（coreHR 完全没有）

还原出的功能词：*批量异动 · 异动导入 · 导入数据 · 开始导入 · 异动内容 · 获取字段映射信息失败 · 您有一条编辑中的批量异动 · 重新编辑 · 请放弃草稿 / 放弃 · 已生效 / 待生效 / 审批中 / 已通过 / 已拒绝 / 已撤销 · 自动撤销 · 查看流程 · 您提交的批量异动审批被驳回 · 请填写飞书多维表URL*

> coreHR 的异动只能**逐条**建 `hr_events`。Moka 支持批量异动 + 导入 + 草稿 + 批量审批 + 自动撤销。批量异动是 HR 的高频刚需（年度调岗、批量转正）。

### ⑤ 入职任务 = 带责任人和到期日的任务引擎

还原出的功能词：*设置入职任务 · 入职计划 · 关联的入职计划 · 全部入职计划 · 全部新员工 · 任务负责人 · 全部任务负责人 · 调整负责人 / 请指定新的负责人 · 调整截止时间 / 请指定新的截止日期 · 任务到期日 · 分配日 · 到期日 · 开始日期 / 结束日期 · 未完成 · 已完成 · 催办任务 · 催办成功 · 查看所有已过期任务 · 角色 · 这里会显示所有入职任务*

> 与 coreHR 的 0 实现形成鲜明对比——**Wave 3 的核心就是这个**。

### ⑥ 审批的「撤销」是四种场景，不是一种

还原出的功能词：*发起人通过后撤销 · 发起人中途撤销 · 管理员通过后撤销 · 管理员中途撤销 · 撤销原因 · 催办 / 催办内容 / 部分催办请先勾选 / 点击将催办当前列表的全部审批 · 导出Excel中按流程名称分Sheet聚合 / 基于当前页面的筛选结果 / 建议调整筛选条件分批导出*

> **coreHR 的审批引擎连"撤销"都没有**（grep `撤回|withdraw` 零命中）。Moka 把它做成了四种明确语义 —— 这直接印证 Wave 2 的 2.2/2.6 是硬需求。
> 另外 Moka 的**批量催办**和**按流程分 Sheet 导出**也是 coreHR 空白。

### ⑦ Moka 的审批类型清单（coreHR 只有 hr_event 一种能挂流程）

还原出的业务审批类型：*补卡 · 出差 · 调薪 · 定薪 · 发薪 · 个人信息修改 · 加班 · 合同 · 换班 · 离职 · 离职办理 · 结束兼岗*

> coreHR 的 `workflow_instances.business_object_type` **只支持 `hr_event`**（`workflow/extended_service.py:1356-1357`）。上表 12 种里，coreHR 只能挂 3 种（转正/调岗/离职），其余 9 种要么没有对应业务，要么没有流程。

### ⑧ 薪酬核算的「薪资准备」是 8 个独立步骤

还原出的步骤词：*社保公积金 · 其他薪资项目录入 · 在线编辑 · 数据导入 · 录入考勤结果 · 截止上月个税累计 · 专项附加扣除累计*

> Moka 的算薪不是"一个算薪按钮"，而是**8 个准备步骤按序解锁**。coreHR 若补薪酬，建议直接照这个骨架设计流程状态机，避免做成"一个表单提交完事"。

---

## 3.12 Moka 五项功能复刻对照（2026-10-24）

> 对应产品决策人指令：「有些moka的功能，你了解完，跟项目比较一下复刻过来，融合一起」——历史花名册 / 历史组织架构 / 汇报关系兼岗 / 假期账户与余额 / 各类排班。
> 语义决策：`docs/01-foundation/03-项目决策.md` §8.5（D-102 ~ D-107）。实现层依据、迁移编号分配与文件所有权矩阵：`docs/review/moka-5-feature-decisions-2026-10-24.md`。

### 总览

| # | Moka 功能 | Moka 路由 | 复刻前 coreHR | 本轮结论 | 决策 | 落地状态（2026-10-24 收工） |
|---|---|---|---|---|---|---|
| 1 | 历史花名册 | `/staffManage/roster` | ⚠️ 底层已区间化，查询层缺失 | 补**对外时点查询**，不新建人员版本表 | D-102 | ✅ 已落地，8 条用例 |
| 2 | 历史组织架构 | `/organization/adjustment/history` | ⚠️ 模型完全就位，API 主动 422 | 开放 `as_of` 参数渲染时点树，**不建独立页面** | D-103 | ✅ 已落地，5 条用例；画板 `vg2Mm` 已补 |
| 3 | 汇报关系 + 兼岗 | `/organization/report/{manage,graph}`、`/staffManage/staffList/6` | ✅ 汇报关系已全通 / ⚠️ 兼岗载体错位 | 只补**兼岗**（person 级载体） | D-104 | ✅ 已落地，11 + 3 条用例；**职务存 note JSON 是残留债** |
| 4 | 假期账户与余额 | `/holiday` 当前余额 + 发假明细 | ⚠️ 余额是真的，缺发假明细 | 补发假明细 + 时点余额 + 计提骨架 | D-107 | ✅ 已落地，6 条用例 |
| 5 | 各类排班 | `/holiday` 排班管理 + 换班记录 | ⚠️ 只有班次与排班结果 | 补排班类型 + 草稿发布 + 换班 + 批量 | D-107 | ✅ 已落地，7 条用例 |

### ① 历史花名册（D-102）

**Moka 侧**：`/staffManage/roster` 可按任意时点回看当时的员工名册与当时的员工信息。

**coreHR 现状**：8/9 张名册相关表已生效日期化，**唯独 `persons` 没有版本化**（`workforce/models.py:324-348`）。可复用的区间查询实现已在 `extended_service.py:1343-1372`（`_count_people`）。

**结论**：允许查任意历史时点；时点上的组织 / 雇佣 / 任职取自区间化表，**人员字段的时点值复用「人员修正版本」按生效日期切片**——不新建第二套人员版本表。

> **必须如实呈现的限制**：历史花名册的「字段级历史」精度取决于修正记录覆盖率。没被修正过的人，其时点姓名/证件等于当前值。**这不是完整的历史回放**，界面上不得暗示是某年的完整档案快照。

### ② 历史组织架构（D-103）

**Moka 侧**：组织架构调整有「方案 / 历史」两层。

**coreHR 现状**：模型**完全就位**——`organization_versions` 区间化 + `organization_events` 生效事件。缺的只有一层：`organization_service.py:498-521` 的 `get_current_tree` 把日期写死为 `business_date()`，且 `organization_api.py:133-138` 主动返回 422 `CURRENT_TREE_ONLY`。

**结论**：在**既有**组织架构页与组织详情内增加 `as_of` 参数渲染时点树；**不建设独立的待生效组织事件页面**（D-059 字面保持不变）。D-013 仍有效 ⇒ **只允许查看当前与历史时点，未来时点返回 422**。

### ③ 汇报关系与兼岗（D-104）

**汇报关系**：**已全通**，本文档 §3.1 的旧结论作废（见上）。

**兼岗**：差距不在功能有无，而在**载体层级**。

| 载体 | 字段 | 问题 |
|---|---|---|
| employment 级 | `EmploymentAssignment.relation_type='concurrent'` | 把兼岗绑在某段雇佣关系上，换雇佣 / 再入职会丢兼岗 |
| person 级 | `organization_person_relations`（含生效起止） | 字段齐全，但**无任何写入路径**，是死模型 |

**结论**：person 级为兼岗唯一权威载体（符合 `05-*.md:172` 与 D-026）。不改 `EmploymentAssignment.relation_type` 的任职类型语义；改 HR 事件 `CONCURRENT_ASSIGNMENT` 的执行器，审批通过后写 person 级；employment 级既有行留作历史记录，读取端不再以其为兼岗来源。

### ④ 假期账户与余额（D-107）

**必须先纠正一个常见误判**：coreHR 的假期余额**不是接口层汇总**。`leave_balance_accounts` + `leave_balance_transactions` 已是一等实体，且有 `balance_before/after` 恒等 CHECK（`attendance/models.py:159-241`），`LeaveBalancePanel` 读的是真余额。

**真正的差距**是 Moka 的「发假明细」：

| Moka 能力 | 本轮 |
|---|---|
| 当前余额 | ✅ 已有 |
| 时点余额查询 | 本轮补（按流水累加到 `as_of`） |
| 发假额度规则 | 本轮补**字段容器**，取值留空待企业输入 |
| 发放批次 + 发放明细 | 本轮补 |
| 自动计提调度器 | 本轮补**可配置开关 + 调度骨架**，默认关闭、不挂应用启动路径 |
| 假期类型版本化 | **不做** —— D-077：基础资料未明确含生效日期则不维护有效期历史版本。版本化的是发假额度规则 |

**残留差距（本轮明确不做）**：**请假不走审批流**（`LeavePanel.tsx` 直接 PATCH `status=approved`）。这需要 BPMS 引擎定稿后把请假挂上流程，属跨域改造。

### ⑤ 各类排班（D-107）

**Moka 侧**：排班管理 + 换班记录 + 22 条 `/setting/holiday/*` 配置路由。

**coreHR 现状**：只有 `shifts`（班次）+ `schedule_assignments`（排班结果）+ `GET /schedules`。另有**真实缺陷**：`shifts.rule_set_id` 指向非版本化规则集，旧班次会静默跟随新规则。

**本轮**：排班类型（固定班 / 轮班 / 弹性 / 自由）+ 草稿与发布（月度发布）+ 换班记录 + 批量排班（上限 1000，对齐 D-097）+ 规则集版本化修复。**轮班周期、弹性窗口、同日多班次的取值一律留空**，等 `docs/input-packs/07-attendance-rule-input.md` §4.1/§4.2/§4.5 的企业输入。

### 落地状态（2026-10-24 收工实测）

五项复刻全部落地并通过自动化验证。以下是**实测终态**，不是计划：

| 项 | 落地位置 | 验证 |
|---|---|---|
| ① 历史花名册 | `apps/api/src/hris/modules/workforce/historical_roster_api.py` + `historical_roster_service.py`；前端 `features/workforce/HistoricalRosterWorkspace.tsx` | `test_historical_roster_api.py` **8 passed** |
| ② 历史组织架构 | `apps/api/src/hris/modules/workforce/organization_service.py`（`get_current_tree(effective_at)` 参数化）+ `organization_api.py`（`as_of`）；前端 `features/organization/view-date.ts` + 两页 | `test_organization_tree_as_of_api.py` **5 passed**（组织域合计 12） |
| ③ 兼岗（person 级） | `apps/api/src/hris/modules/workforce/concurrent_positions_api.py` + `concurrent_positions_service.py`；前端 `features/workforce/ConcurrentPositionPanel.tsx`；**HR 事件执行器改写** `modules/workflow/extended_service.py` | `test_concurrent_positions_api.py` **11 passed** + `test_hr_event_concurrent_position_api.py` **3 passed** |
| ④ 假期发假明细 | `apps/api/src/hris/modules/attendance/grant_service.py` + `grant_schemas.py` + `accrual_scheduler.py`；前端 `features/attendance/LeaveGrantPanel.tsx` | `test_leave_grant_api.py` **6 passed** |
| ⑤ 各类排班 | `apps/api/src/hris/modules/attendance/schedule_service.py` + `schedule_schemas.py`；前端 `features/attendance/ScheduleManagementPanel.tsx` | `test_schedule_management_api.py` **7 passed** |

**迁移链**：本轮新增 `f2h`（人员修正版本）→ `f2i`（审批流转）→ `f2j`（消息引擎）→ `f2k`（假期发假）→ `f2l`（排班）→ `f2m`（授权登记，Open Core 方案），共 **27 条迁移、单根单头无分支**，`alembic check` 零漂移。
**历史花名册与兼岗最终都未新增迁移**——前者复用既有区间化表与 `person_field_versions`，后者复用既有 `organization_person_relations`，因此 `f2n` 这个预留编号**未被占用**（`f2n` 现为兼岗 `job_id` 真列的候选号，见 `open-items-2026-10-24.md` A19）。

**本轮 5 个复刻 worker 均未访问 Moka**，全部实现来自本地决策文档与代码库；未复制对方代码、商标、图标或整页视觉。

### 工程约束（并行开发的防冲突约定）

- **迁移链是单链**，新迁移的 `down_revision` 必须指向上一条已分配编号：`f2h`（人员修正）→ `f2i`（审批流转）→ `f2j`（消息引擎）→ `f2k`（假期）→ `f2l`（排班）→ `f2m`（授权登记）。跳号或并行分叉都会让 `alembic check` 报漂移。**编号必须由主 agent 统一分配，并跑 `alembic heads` 取真实 head，不得按文件名排序推断**（本项目历史上出现过文件名顺序与链顺序不一致）。
- **新模型必须放进已被 `shared/db/models.py` 导入的模块**（`attendance/models.py` / `workforce/models.py` / `workflow/models.py`），否则不会进 `Base.metadata`；并行任务期间任何 worker 都不得改 `shared/db/models.py`，由主 agent 统一合并。
- **不新建 router 模块**，新端点加到既有 router 所属文件；`business_router.py` 与 `navigation.ts` 由主 agent 统一改。（例外：消息引擎作为**平台内核基础服务**（D-100 / ADR-0006），其路由独立注册在 `business_main.py`，并附 `Requirement: D-100` 说明。）

---

## 4. 分级补活路线

### Wave 1 — 把已有的壳变活（约 3–5 天，几乎零新增表）

> 目标：不写新表，只补页面/接口，让已存在的能力可被看见、可被用。

| # | 事项 | 依据 |
|---|---|---|
| 1.1 | **开放职位管理 workspace** | 后端 `/api/v1/workforce/jobs` 完整，前端 `available:false` → 改导航 + 建页面即可（ORG-AUD-008） |
| 1.2 | **成本中心独立页面** | `cost_centers` CRUD 已有，塞进编制 Tab 是信息架构问题 |
| 1.3 | **兼岗管理 / 异动管理独立页** | `hr_events` 事件齐全，只是没有专属列表页 |
| 1.4 | **汇报关系** | `reporting_relations` 表在但**没有写入路径** → 补 1 个 service 方法 + 1 个页面即可（ORG-AUD-001 类） |
| 1.5 | **信息健康度** | Moka 有规则 + 评分 + 整改；coreHR 可基于现有字段必填性做一个轻量版（字段完整率 + 缺失清单 + 导出）。**这是高价值低成本** |
| 1.6 | **启用 `person_labels`** | 表已建好，加读写路径 + 标签页，等于白捡一个"人才标签"模块 |
| 1.7 | **审计日志查询页** | `audit_logs` 只写不读 → 加 1 个查询端点 + 页面（合规必需） |
| 1.8 | **权限模型从扁平升级** | `permissions` 加 `resource`/`action`/`scope` 三维 + 角色 CRUD + 数据范围过滤（这会牵动全站，属 Wave 2 的前置，单独放 Wave 1.8 只做**表结构 + 兼容读取**） |
| 1.9 | **组织架构可视化图** | 有组织树数据，画一张树图成本很低，Moka 有专门的 `/organization/graph` |
| 1.10 | **批量异动**（导入 + 草稿 + 批量审批 + 自动撤销） | 复用现有 `hr_events` 幂等模型，只加"批次"实体；HR 高频刚需 |
| 1.11 | **人力填报**（周期性发起 → 填实际人数 → 出快照） | `headcount_plans` + `headcount_snapshots` 已有，只缺"填报"这个动作与周期规则 |
| 1.12 | **组织架构调整方案**（多步变更打包 + 编制拆解校验 + 历史版本） | 在 `organization_versions` / `organization_events` 之上加"方案"层；编制校验规则 coreHR 的数据模型已够 |

### Wave 2 — 审批引擎底座（约 1.5–2 周，**优先级最高**）

> 理由：Moka 的入职/转正/调岗/离职/请假/加班全部挂在这套引擎上。coreHR 现在的流程能力撑不起"能上线的 HR 系统"。
> 这一波做完后，Wave 3+ 的每个业务流才有落地方式。

| # | 事项 | 涉及 |
|---|---|---|
| 2.1 | 任务状态机扩展：`withdrawn` / `transferred` / `escalated` / `cc` | `workflow_tasks` 表 + `workflow/schemas.py` |
| 2.2 | **撤回**（发起人可在流程未结束前撤回） | 端点 + 状态流转 + 业务对象回滚联动 |
| 2.3 | **超时升级**（`due_at` + `escalate_to` + 后台扫描） | 需要后台任务，见 2.8 |
| 2.4 | **代理/委托审批**（休假/出差时委托） | `workflow_tasks` 加 `original_assignee_ref` + 代理规则表 |
| 2.5 | **抄送 CC** | 新表 `workflow_cc_records` |
| 2.6 | **催办** | 依赖 2.8 通知通道 |
| 2.7 | **驳回后可退回上一节点 / 重投** | `extended_service.py:1324-1330` 改造 |
| 2.8 | **后台任务/调度器** | 全库 grep `celery|arq|apscheduler|cron` **零匹配**。`hr_events/process`、`contracts/process-statuses` 现在靠前端按钮手工触发——这是硬伤 |
| 2.9 | **通知通道**（站内信 + 邮件） | 全库 grep `notification|notify|webhook|wecom` **零匹配**；`outbox_events` 只写不读 |
| 2.10 | **业务对象联动放开** | `_finish_workflow_business_object` 目前只认 `hr_event`，请假/合同挂不上 |
| 2.11 | 图形化流程设计器 | 前端画布（Moka `/setting/approve/createFlow`） |

### Wave 3 — 入职全流程（约 2–3 周，**当前焦点，input pack 03**）

| # | 事项 |
|---|---|
| 3.1 | 入职计划模板（可复用模板 + 实例化） |
| 3.2 | 入职任务清单（任务项、责任人、截止时间、状态） |
| 3.3 | 信息采集（员工自助填表 + 字段映射 + 校验） |
| 3.4 | 电子签署（对接 `/api/esign` 类能力或自建签署记录） |
| 3.5 | 欢迎信 / 通知模板 |
| 3.6 | 入职人员列表页 + 批量发起 |
| 3.7 | 入职流程图与审批规则落地（依赖 Wave 2） |

### Wave 4 — 假勤补全（约 2 周）

加班类型 + 加班规则 / 出差 / 外出 / 补卡申请 / 换班 / 发假明细 / 排班发布流程 / 异常考勤规则与状态 / 请假接审批流（依赖 Wave 2.10）。

### Wave 5 — 报表与 BI（约 2–3 周）

统计 API（人数趋势/离职率/编制达成率/异动分析）→ 自定义看板 → BI 模板库 + 数据源 → 多人协作报表搭建器 → Excel/透视导出。

### Wave 6 — 薪酬（约 6–8 周，最大）

薪资结构与薪资档案 → 算薪引擎 → 工资条 → 社保公积金 → 个税 → 成本分摊 → 预算 → 调薪 → 银企直联。**建议沿用 Moka 的"薪资准备八步"作为首个里程碑**。

### Wave 7 — 绩效（约 4 周）

目标库/目标类型 → 目标地图 → 绩效活动 → 评分表 → 结果与强制分布 → 报告与申诉。

### Wave 8 — 设置与集成（约 3 周）

权限模型完整化（角色 CRUD / 数据范围 / 字段权限）→ 组织设置全套 → 入职设置 → 假勤设置 → 薪酬/绩效设置 → 开放平台 API（`outbox_events` 发布器 + webhook）→ 第三方（电子签/银企直连/实名认证）。

---

## 5. 必须先修的 3 个"不看代码看不出来"的问题

| # | 问题 | 证据 | 影响 |
|---|---|---|---|
| **B-1** | **默认部署入口只暴露 12/162 个 endpoint** | `apps/api/Dockerfile:25` 和 `deploy/compose.yaml:50` 都跑 `hris.main:app`（只 include system + workflow/api + attendance/api = 12 个）；完整业务 API 在 `hris.business_main:app`（162 个），只有 `deploy/compose.business.yaml:10` 用它 | **用默认 compose 起的服务，业务 API 全都不在**。这会导致"重启后发现接口 404" |
| **B-2** | **`workforce/api.py` 的 2 个 endpoint 是死代码** | `apps/api/src/hris/modules/workforce/api.py:15,32`；全库无 `from hris.modules.workforce.api import` | `POST/GET /workforce/organizations` 从未挂载 |
| **B-3** | **`GET /api/v1/system/modules` 硬编码 3 个模块，且声称 `uat_ready` 的同时写着"正式流程图与审批人规则未到位"** | `apps/api/src/hris/modules/system/api.py:48-118` | 自相矛盾，UAT 时会被直接质疑 |

> **B-1 特别提醒**：你这次要重启项目——重启前先确认用的是 `compose.business.yaml` 还是 `compose.yaml`。用后者的话，业务接口全是 404。

---

## 6. REA 逆向分析说明

本次用 `rea` (Reverse Engineer Anything, v6.4.0) 做静态还原：

- `rea doctor` / `rea mcp doctor --json` → server healthy，170 tools / 6 prompts 全部就位，版本与目录摘要一致。
- 宿主（Mavis Code）**未把 rea 的 MCP 工具注入到会话工具表**（`tool_search` 对 rea 零命中），因此改用 **REA CLI 直调**完成数据获取。
- `rea analyze-web-bundle` 需要 loopback CDP endpoint；本机 Electron 未开 `--remote-debugging-port`，`list-browser-targets` 不可用 → 改为「下载 bundle → 本地静态分析」路径。
- `rea analyze-javascript-application <dir>` **跑通**（exit 0，77 MB Evidence）：

| 项 | 值 |
|---|---|
| `evidence_id` | `ev_6065b9d40bf7643e99d1b839c6e21152ffaf457e7f129a25fcb6cb0842c2755e` |
| `root_artifact_sha256` | `aca4b4c2fd97e335d665f91cee2b02eff38c564e24a6542d142a3819db1657e3` |
| 解析的 JS 源文件 | **275** |
| 物理图谱 | 3254 nodes / 9427 edges |
| 语义图谱 | **19822 nodes / 39085 relations** |
| fingerprints / unknowns / evidence_contexts | 509 / 9898 / 791 |
| 完整性冲突 | **0** |
| limitations | 551 条 |

**REA 自己给出的限制（必须一并记住，否则会误读）**：
- *"Graph coverage is incomplete; unavailable facts remain explicit and must not be read as absence."* —— 图覆盖不完整，**"没分析出来"不等于"不存在"**。
- *"JavaScript and HTML were parsed as inert text; bundle bootstrap code was never executed."* —— 纯静态解析，**从未执行**，因此运行时才有的行为（动态路由、权限过滤）不在图里。
- 大量 `"Expanded application relationships ... exceed the parent's result budget"` —— 关系展开被预算截断。

> **因此本文档的 Moka 侧结论分两个来源，权重不同**：
> ① **菜单树 / 路由表 / API 路径 / 页面中文字段** —— 直接从 bundle 与已登录 UI 提取，**可逐条复核**（见 §7 产物索引）；
> ② **REA 语义图谱** —— 作为**独立交叉验证**与**证据包**，不单独用来断言"某功能存在"。
> 两者一致的部分（菜单、路由）已在 §1 给出；不一致时以 ① 为准。

Evidence 文件：`tmp/rea-out/rea-moka-analysis.json`（77 MB）、`tmp/rea-out/rea-summary.txt`、`tmp/rea-out/rea-fingerprints.json`、`tmp/rea-out/rea-nodes.json`。

---

## 7. 产物索引

| 文件 | 内容 |
|---|---|
| `tmp/moka-recon/moka-vs-corehr-feature-gap.md` | **本文档** |
| `tmp/moka-recon/routes-clean.txt` | Moka 396 条路由（干净的 URL 列表） |
| `tmp/moka-recon/route-table.txt` | 路由 → chunk 映射（含 src 公共 chunk） |
| `tmp/moka-recon/nav-menu.txt` | **Moka 279 项导航菜单**（url / 中文名 / authorityKey / HIDDEN·EXT 标记） |
| `tmp/moka-recon/nav-raw.txt` | 导航配置原始片段 |
| `tmp/moka-recon/api-paths.txt` | Moka 1507 条 API 路径 |
| `tmp/moka-recon/chunk-hashmap.txt` | chunk → contenthash 映射（479 条） |
| `tmp/moka-recon/async/` | **已下载的 271 个 Moka 页面 chunk（6.1 MB）** |
| `tmp/moka-recon/async-manifest.txt` | chunk 文件清单 + 体积 |
| `tmp/moka-recon/page-features.txt` | **逐页面中文字段还原（211 个页面 chunk / 9139 行）** |
| `tmp/moka-recon/domain-vocabulary.txt` | 按 83 个业务域聚合的功能词表（8483 行） |
| `tmp/moka-recon/zh-strings.txt` | 7923 条中文 UI 文案（按出现频次） |
| `tmp/moka-recon/src-tokens.txt` | 源码路径 token |
| `tmp/rea-out/rea-moka-analysis.json` | **REA Evidence（77 MB）** |
| `tmp/rea-out/rea-summary.txt` | REA 语义图谱摘要 + limitations |
| `tmp/rea-out/rea-fingerprints.json` | 509 个函数级 fingerprint |
| `tmp/rea-out/rea-nodes.json` | 19822 个语义节点 |

### 可复现脚本

| 脚本 | 作用 |
|---|---|
| `tmp/moka-recon/fetch-core-chunks.ps1` | chunk 批量下载（**多 hash 候选回退**是必需的） |
| `tmp/moka-recon/parse-nav.ps1` | 导航树解析（url / 中文名 / authorityKey） |
| `tmp/moka-recon/extract-page-features.ps1` | 逐页面中文功能词提取 + 域聚合 |
| `tmp/rea-out/extract_rea_semantic.py` | REA Evidence → 语义图谱摘要 |

---

## 8. 数据来源与合规声明

- Moka 侧仅采集**功能结构**（路由 / 菜单 / API 路径 / 字段名），**未复制任何代码、品牌资产或 UI 资源**，符合 `docs/design/antd-page-interaction-standard.md` 对外部产品的约束。
- 采集过程中登录态由用户在浏览器侧自行完成，**未读取或存储任何凭据**。
- 本文档**不包含 Moka 租户的真实人员信息**（姓名、企业名、部门负责人等一律未记录）。
- coreHR 侧结论均以**文件路径 / 行号 / 表名**为证，可逐条复核。
