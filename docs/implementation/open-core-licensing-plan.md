# coreHR 开源发布与模块级授权实施计划

> 状态：实施计划（已定案，可推翻项见 §12）
> 日期：2026-10-24
> 关联决策：**D-108**（Open Core 形态与离线签名模块级授权）
> 关联 ADR：docs/adr/ADR-0008-open-core-and-commercial-licensing.md（Wave 1 同批新建）
> 计划来源：2026-10-24 产品决策人提供的实施计划原文

## Summary

**目标**：把 coreHR 从「一份完整源码直接摊在 GitHub 上」改成 **Open Core + 离线签名模块级授权** 的形态。公开仓让人看得见全部功能、模型、契约、UI 与文档；核心业务引擎不公开；客户取得你签发的 License Token 后才解锁对应模块的写能力；无授权时系统进入只读演示模式（功能全可浏览，写操作禁用并提示需要授权）。

**范围**：仓库法律层（LICENSE/NOTICE/版权头）、授权 SDK（后端）、License Token 签发工具（私有）、只读演示模式、前端授权徽标与水印、公开仓与私有实现包的拆分方案、PRD/ADR 同步修订、测试与验收。不包含：在线支付、会员体系、License Center 的完整商业化运维、远程托管 API 路线。

**四个已确认的关键决策**（来自本轮问卷）：

| 决策 | 选定 | 影响 |
|---|---|---|
| 保护强度 | 单仓公开 + 私有实现包 | 公开仓只放骨架与契约；引擎实现在私有包，公开仓里没有可运行的核心实现 |
| 授权模块 | 考勤 / 生命周期 / 流程引擎 / 数据治理导入引擎（"全选"） | 这四个模块的写能力需要授权；Workforce Core 与绩效默认作为免费层 |
| Token 验证 | 离线 Ed25519 签名为准 + 在线通道作为可选的续期/吊销 | 私钥离线保管，公钥内置；不依赖你的服务器存活 |
| 未授权表现 | 只读演示模式 | 全部功能可浏览，所有写操作禁用并给出明确授权指引 |

**三处按推荐定案的补充决策**（详见 §12）：许可证采用**自研 n8n SUSL 风格**（明确非 OSI 开源，BSL 1.1 与双许可制写入 ADR 备选方案）；私有核心以**进程内私有包**交付而非拆独立 RPC 进程（安全收益相近、工程代价差一个数量级）；公开仓**保留完整前端**。

**与两份外部建议的关系**：两份建议与本方案**同源**——三层保护、Open Core、Ed25519 离线验签、Token 不保护公开源码、私有组件才是关键，四条主干判断完全一致，没有冲突。本计划吸收了它们补充的四点——**Community/Developer/Commercial 三级版本**、**Source Available 许可证路线（n8n SUSL / BSL 1.1）**、**独立的 `corehr-license` 签发工具项目**、**第三方依赖协议兼容性核对**；并按 coreHR 自身现状做了五处修正（见「与两份外部建议的对照与合并结论」一节）。

---

## 1. 现状核查（已验证事实，非推测）

### 1.1 远端仓库状态

- 远端实际仓库是 `https://github.com/Millerprc/coreHR`（**已公开**，`private: false`，`visibility: public`），本地 `origin` 写的是 `https://github.com/Millerprc/HRIS.git`，GitHub 靠重命名做了跳转。**remote URL 与实际仓库名不一致，需要统一**，否则以后推错仓。
- 无 `LICENSE` 文件（GitHub API 返回 `license: null`）。仓库里也没有任何 LICENSE/NOTICE/COPYING 文件。
- 最后推送 `2026-08-15T04:12:58Z`，早于本地的 2026-08-18 rebaseline，因此公开的是**较旧快照**。
- `stars: 0 / forks: 0 / watchers: 0 / open_issues: 0`。**实际泄漏面极小**——说明现在动手，损失还很小。
- 历史提交中**从未提交过** `.env`、`.pem`、`.key`、`secrets/`；当前仅跟踪 `.env.example` 与 `deploy/business.env.example` 两个示例文件。凭据泄漏风险为零，无需历史清洗。

### 1.2 代码结构与授权切入点（coreHR 自有事实）

- 单一模块化单体，Python 3.13 / FastAPI 0.118 / SQLAlchemy 2.0 / PostgreSQL 16 / React 19 / Ant Design 6.5.2。
- **两个应用入口**：`hris.main:app`（12 个 endpoint，`deploy/compose.yaml:50`）与 `hris.business_main:app`（162 个 endpoint，`deploy/compose.business.yaml:10`）。
- **现有认证链路**：`hris/modules/platform/dependencies.py`
  - `get_current_session` → Bearer token 查 `UserSession.token_hash`，返回 `(UserAccount, UserSession)`。
  - `require_permissions` / `require_permission` / `require_any_permission` 三个 FastAPI 依赖工厂。
  - `business_router.py:39-49` 已经示范了 **router 级挂依赖** 的写法：`business_router.include_router(workflow_configuration_router, prefix="/api/v1", dependencies=[Depends(require_permission("LIFECYCLE_ADMIN"))])`。授权门禁直接复用这个模式即可。
- **现有模块注册表**：`/api/v1/system/modules`（`hris/modules/system/api.py:48`）已经返回 `ModuleStatus(code=..., available_capabilities=..., available_endpoints=...)`，是天然的"功能清单"出口，授权信息可以并入这里或独立成 `/api/v1/license`。
- **前端入口**：`apps/web/src/business/navigation.ts` 定义 14 个 workspace 与 permission 映射；`AppShell.tsx` 按 permission 过滤侧栏；`client.ts` 提供 `getModules(token)`；`BusinessApp.tsx` 是登录流程。
- **构建注入点**：`apps/web/vite.business.config.ts` 目前没有 `define` 块，构建期烘焙水印要新增。
- **依赖**：`cryptography==49.0.0` 已在生产依赖里 → Ed25519 签发与验签**不需要引入新依赖**。`httpx` 同样已在，用于可选的在线通道。

### 1.3 现有架构语言（授权分层的现成词汇）

`docs/review/platform-kernel-architecture-fit-review-2026-08-18.md` 与 `docs/01-foundation/16-coreHR产品总体PRD.md` 已定义：

- **Platform Kernel**（必装）：身份、权限、审计、配置字典、任务、Outbox、模块注册、消息端口、观测。
- **Workforce Core**（必装业务底座）：人员、组织、雇佣、任职、编制、快照、人事事件。
- **业务套件**：Recruitment / Workflow / Contract / Attendance / Payroll / ESS / Integration。

这套分层**直接就是授权分层的天然骨架**，不需要另造一套模块划分。

### 1.4 与 PRD 的现存冲突（必须先解决，否则与项目自身纪律冲突）

- PRD §3.2 第 24 行：「企业规模、部署档位和**商业服务方式不得成为阉割开源业务功能的理由**」。
- PRD §4.2：「企业人数仅作为选型参考，**不作为功能开关或许可限制**」。
- PRD §18 待决问题 **PROD-Q001**：「coreHR 采用的开源许可证、贡献者协议和第三方依赖准入规则」——正是本计划要回答的问题。

本计划引入模块级商业授权，与上述两条**直接抵触**。项目纪律要求用 ADR 6 段式记录并同步修订 PRD，否则代码与文档不一致会直接被 Review 打回。

---

## 2. 目标架构

```text
┌──────────────────────────── 公开仓 Millerprc/coreHR ────────────────────────────┐
│  完整 UI（React + AntD）· 完整 API 契约（FastAPI routers + schemas）           │
│  完整数据模型 + Alembic 迁移链 · Platform Kernel 实现 · 文档 · 骨架 Demo 引擎     │
│  LICENSE (SUSL 风格) · 源码版权头 · 内置 License 公钥表                          │
└──────────────────────────────────────┬───────────────────────────────────────────┘
                                       │ 运行时依赖（pip 私有源 / 私有包 / submodule）
                                       ▼
┌──────────────────── 私有实现包 coreHR-enterprise（不公开） ────────────────────┐
│  workflow 引擎（状态机/选路/调度）· attendance 引擎（规则/排班/假勤/日月报）      │
│  lifecycle 引擎（招聘/合同/人事事件）· governance 引擎（导入校验/快照导出）        │
│  workforce 计算内核（生效日期求解/编制占用/快照）                                 │
└──────────────────────────────────────┬───────────────────────────────────────────┘
                                       │ 授权判定
                                       ▼
┌──────────────── License Center（私有，可选在线） ───────────────────────────────┐
│  签发 CLI `corehr-license`（离线，私钥在你自己机器）                             │
│  可选：续期 / 吊销 / 状态查询服务（默认不启用，coreHR 离线可用）                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 核心不变量

1. **公开仓里不存在任何"能独立算出业务结果"的代码**。Demo 实现只提供直通数据库的读取和显式的"需要授权"拒绝，不含规则求解。
2. **Token 只判定使用权，不判定所有权**。核心实现不公开是保护来源，Token 是使用权来源。两者缺一不可。
3. **授权判定只有一个收口点**：`hris/core/licensing/`。任何模块不得自己实现一套授权逻辑。
4. **离线优先**。没有任何在线依赖是系统可用的前提。

### 2.2 公开 / 私有边界表

| 域 | 公开仓内容 | 私有包内容 |
|---|---|---|
| Platform Kernel | 全部（身份/权限/审计/字典/编号/消息/配置） | — |
| 通用基础设施 | `core/`（config、database、errors、middleware、concurrency） | — |
| 数据模型 | 全部 ORM 模型 + Alembic 全链迁移 | — |
| API 契约 | 全部 routers + pydantic schemas（OpenAPI 可读） | — |
| 前端 | 全部（完整 UI，AntD 6.5.2 原生交互） | — |
| Workflow | routers / schemas / Demo 引擎（状态机判定抛 LICENSE_REQUIRED） | `state_machine` / `transitions` / `conditions` / `actions` / `scheduler` / `notifier` |
| Attendance | routers / schemas / Demo 引擎 | 规则版本、班次、排班求解、打卡幂等、假勤余额、日报月报计算、期间冻结 |
| Lifecycle | routers / schemas / Demo 引擎 | 招聘/应聘/Offer 转换、合同版本与续签解除、人事事件生效与回退 |
| Governance | routers / schemas / 模板下载 | 预校验、逐行拒绝报告、幂等执行、有效快照导出 |
| Workforce | routers / schemas / 简单 CRUD 读 | 生效日期求解、编制占用、快照计算、批量变更 |
| Performance | routers / schemas | OKR 计算逻辑 |
| 人员敏感字段 | `core/personnel_security.py` **保留公开** | — |
| License 公钥 | 内置公钥表（`kids` 多 key 并存，支持轮换） | 私钥（永不进仓库） |

> 人员敏感字段保护机制**故意保留公开**：它是安全机制而非商业能力，公开反而建立信任；若后续要转为私有，按同一套 Protocol 机制处理即可，不影响其他设计。

---

## 3. 与两份外部建议的对照与合并结论

两份建议的**主干判断与本方案完全同源**：三层保护（架构隔离 / 许可证兜底 / Token 授权）、Open Core 形态、Ed25519 非对称离线验签、Token 不保护公开源码、私有组件才是关键、按模块粒度授权。四条判断无冲突，可放心按本设计推进。

| 建议条目 | 采纳情况 | 说明 |
|---|---|---|
| Open Core 模式、Token 不保护公开源码、私有组件才是关键 | **完全采纳** | 本方案骨架，与实测结论一致 |
| Ed25519 + 本地离线验证（参考 Keygen / PermitCore 离线方案） | **完全采纳** | `cryptography` 已在生产依赖里，零新增依赖 |
| 按模块粒度授权（`features` 字段逐项放行） | **完全采纳** | 落进 `entitlements`（比扁平 `features` 更精确：区分 read / write） |
| 公开仓 = 控制面（API / CLI / Web UI / SDK / 文档 / 部署配置），私有仓 = 核心实现 | **完全采纳** | 对应本计划 §2.2 边界表 |
| 独立 License Generator CLI | **采纳** | 独立项目 `corehr-license`，可复用到 coreHR 之外的产品 |
| 公共 License SDK 统一判定 | **采纳** | `hris/core/licensing/`，全仓唯一授权逻辑入口 |
| 源码头部版权声明 | **采纳** | 配 `scripts/check-license-header.mjs` 门禁（复用 `check-antd-usage.mjs` 模式） |
| 清理提交历史凭据 | **采纳但已无必要** | 实测历史干净（从未提交过 `.env`/`.pem`/`.key`），无需 filter-repo/BFG |
| 私有核心通过**稳定客户端**调用，而不是直接 import 实现模块 | **采纳思想，形态不同** | 见下方「两处实质差异」 |
| 许可证采用 Source Available（n8n SUSL / BSL 1.1 / 双许可） | **采纳** | 定案为自研 SUSL 风格，BSL 1.1 与「公开层 Apache-2.0 + 私有层商业许可」记入 ADR 备选方案 |
| 三级版本 Community / Developer / Commercial | **采纳并强化** | 落进 Token 的 `tier` 字段，Community 级**带写能力白名单**（§5.2），不是简单三等分 |
| 核心服务只返回结果，不返回策略内部细节（错误信息也不能泄露） | **采纳** | 已写入 §7.1 的授权错误约束 |
| `machine_code` 绑定机器 | **采纳** | 落进 payload 的 `deployment_binding` 字段（可选，默认不启用） |
| 定期在线心跳 | **不采纳为必需** | 与 PRD §4.2「离线私有化」冲突。改为可选在线通道，且不可达时**不降级授权状态**（§9.3） |
| 最高保护模块可考虑托管为远程 API | **暂不纳入** | 与 coreHR「私有化离线、不绑定云厂商」的 PRD 原则冲突；记入未决决策 |

### 3.1 两处实质差异与取舍

**差异 1：私有核心的交付形态 —— 进程内私有包（本计划） vs 独立进程 RPC 服务（第三份建议）**

| | 进程内私有包（本计划） | 独立进程 RPC 服务（第三份建议） |
|---|---|---|
| 私有实现存在哪 | 客户环境里的私有 wheel / 私有源安装 | 客户环境里的独立服务进程 |
| 公开仓怎么调 | `resolve_engine()` 工厂 + Protocol（同进程 import） | `private_core_client.py` 走 HTTP/RPC |
| 安全收益 | 核心代码不在公开仓 → 拿不到实现 | 同左；额外阻止「拿到 wheel 的人改 wheel」 |
| 工程代价 | 低：只在 service 边界抽 Protocol | 高：进程间通信、序列化、事务边界跨进程、Alembic 迁移归属、部署与运维复杂度、性能损耗 |
| 与 coreHR 现状的契合 | 高：模块化单体，PRD 明确「默认在同一代码仓库和模块化单体内交付」 | 低：等于把一个模块化单体拆成微服务，与 PRD §6「套件边界描述的是产品责任，不要求当前立即拆成独立进程」抵触 |

**取舍结论：采用进程内私有包。** 理由是两份形态的**安全收益差距很小**（私有实现不发布这一点已经达成，而私有 wheel 只发给已授权客户，改它属于违反许可证而非核心风险），但**工程代价差距很大**。第三份建议的核心洞察——"验证必须发生在私有实现内部，而不是公开客户端里"——在本方案里已经成立：`DemoAttendanceEngine` 的写方法只能拒绝，无法返回真实业务结果，因为规则求解代码根本不在公开仓。攻击者能改的只有"拒绝"这一段，改完也只是拿不到真结果。

**保留的升级路径**：若将来某个模块需要最高保护（例如考勤引擎被反向），可**只针对该单一模块**升级为独立 RPC 服务（`hris/contracts/<domain>.py` 的 Protocol 已经把接口定义与实现分离，替换实现不影响调用方）。本期不做。

**差异 2：许可证具体形态 —— 自研 SUSL 风格（本计划定案） vs BSL 1.1（第三份建议）**

两者同属「Source Available + Commercial License」族，法律效果接近。选自研 SUSL 风格的三个理由：
1. **n8n 的实践已被验证**：它是同类产品里商业化最成功的形态之一，且明确标注"非 OSI 开源"，避免了社区口径争议。
2. **BSL 1.1 的"变更日自动转 Apache-2.0"与"4 年后强制开放"**，对一个仍在快速演进、核心引擎在私有手里的产品是**自伤**——等于给自己设了一个必须公开商业代码的倒计时。SUSL 风格可以自定义条款而不带强制转开源条款。
3. 自研文本可以把**模块级授权与只读演示模式**直接写进许可证条款，与本产品的实际形态对齐，而不是套一个通用模板。

BSL 1.1 与「公开层 Apache-2.0 + 私有层商业许可」双轨制写入 ADR-0008 的**备选方案**章节（每个含优/缺/不采用原因），符合项目 ADR 6 段式规范。

### 3.2 五处按 coreHR 实况做的修正

1. **不新建授权模块划分**——直接复用 PRD 已定义的 Kernel / Workforce Core / 业务套件分层，避免两套词汇打架。
2. **只读模式的收口点定在引擎边界**而非逐个 HTTP 方法。Wave 2 拆包后，私有引擎的写方法与 Demo 引擎的拒绝方法在同一处；逐个方法加标注容易漏且难审计，引擎边界是天然收口。
3. **Demo 读路径必须与商业版读路径共用同一查询代码**，只把「规则求解」抽走。否则社区版读出来的数和商业版不一样，直接摧毁信任。这是本方案最容易被低估的风险（§11 风险 2）。
4. **PRD 与 ADR 必须同步修订**，否则 Wave 1 的代码一落地就与 PRD §3.2 / §4.2 冲突。
5. **不引入在线心跳为必需**——coreHR 明确支持私有化离线部署，任何"必须连到厂商服务器才能用"的机制都会直接否掉企业客户。

---

## 4. 实施分阶段

每个 Wave 独立可交付、可回滚、可验收。

### Wave 0 — 法律层止血（优先，零业务风险）

**为什么最先做**：仓库已公开但**没有 LICENSE**。无 LICENSE 时 GitHub 虽不授予使用许可，但"看得到、fork 得走"的事实已经存在，而事后追责唯一的凭据就是 LICENSE 与版权声明。这一步成本最低、防追溯价值最高。

| # | 动作 | 文件 |
|---|---|---|
| 0.1 | 起草 `LICENSE`【**已定案**】：自研「coreHR Sustainable Use License v1.0」，参照 n8n 的 SUSL 风格（允许查看/学习/修改/非商业自用/贡献；限制未经授权的商业使用、白标转售、托管售卖；保留商标与署名权；明确模块级商业授权经 License Token 授予）。**必须声明"非 OSI 开源"**。BSL 1.1 与「公开层 Apache-2.0 + 私有层商业许可」写入 ADR-0008 备选方案章节 | `LICENSE`（新建） |
| 0.2 | 第三方依赖协议清单与结论 | `NOTICE`（新建） |
| 0.3 | 贡献者协议 | `CONTRIBUTING.md`（新建） |
| 0.4 | 源码头部版权声明 + 门禁脚本（照抄 `scripts/check-antd-usage.mjs` 的检查模式） | `scripts/check-license-header.mjs`（新建） |
| 0.5 | `.gitignore` 增加私钥与授权文件规则：`*.lic`、`*.license.json`、`signing/`、`*.pem`、`*.key`（后两类已有，需确认 `.lic` 未被 `*.key` 覆盖） | `.gitignore` |
| 0.6 | README 增加「授权与商业使用」章节：社区版能做什么、商业版解锁什么、如何申请 | `README.md` |
| 0.7 | 仓库描述与 topics 调整（GitHub 侧操作） | 仓库设置 |

**依赖协议核对结论（Wave 0.2 的实质内容）**：alembic(MIT)、cryptography(Apache-2.0 OR BSD-3)、fastapi(MIT)、httpx(BSD-3)、psycopg(LGPL-3.0)、pydantic(MIT)、pydantic-settings(MIT)、redis(MIT)、SQLAlchemy(MIT)、uvicorn(BSD-3)、react(MIT)、antd(MIT)、vite(MIT)、vitest(MIT)、typescript(Apache-2.0)。
**结论：无 GPL 传染性依赖，允许闭源商用分发。** 唯一弱 copyleft 是 psycopg(LGPL-3.0)，以服务端/二进制形式使用不触发强制开源义务。cryptography 为双许可，商用分发时保留其一即可。

**验收**：
- `LICENSE`、`NOTICE`、`CONTRIBUTING.md` 存在且内容与本计划一致。
- `node scripts/check-license-header.mjs` 对 `apps/**` 源码全绿；故意去掉一个文件头时必须报红。
- `git ls-files` 中无 `*.lic` / 私钥文件。
- `scripts/check-business-portable.ps1` 仍然全绿（Wave 0 不触碰运行逻辑）。

---

### Wave 1 — 授权 SDK + 只读演示模式（可独立交付，不依赖拆包）

#### 1) 后端：新增 `apps/api/src/hris/core/licensing/`

| 文件 | 职责 |
|---|---|
| `types.py` | `LicenseEntitlements`（模块 → read/write）、`LicenseStatus`、`LicenseTier` 枚举、`VerificationResult` |
| `token.py` | token 编解码与 Ed25519 验签。格式 `coreHR.<b64url(header)>.<b64url(payload)>.<b64url(sig)>`；header `{alg:"EdDSA", typ:"corehr-license-v1", kid}`；payload 见 §5.1 |
| `keys.py` | 内置公钥表 `{kid: base64 raw pubkey}`，支持 `COREHR_LICENSE_PUBLIC_KEYS` 环境变量覆盖（供轮换期临时替换）；验签失败一律 `LICENSE_INVALID_SIGNATURE` |
| `store.py` | 授权事实的 DB 持久化（只存 token 摘要，不存明文） |
| `service.py` | `LicenseService`：读取当前授权、激活 token、计算有效 entitlements、过期判定 |
| `guard.py` | `require_licensed_write(module)` / `require_licensed_read(module)` 两个 FastAPI 依赖工厂，风格对齐 `platform/dependencies.py` 的 `require_permission` |
| `errors.py` | `LicenseRequiredError` → 统一错误响应 `403 / code=LICENSE_REQUIRED`，`details` 给出缺失模块名与申请指引 |
| `server.py` | 可选在线通道客户端（httpx），仅在 `COREHR_LICENSE_SERVER_URL` 存在时启用 |

#### 2) 后端：数据模型与迁移

- 在 `hris/modules/platform/models.py` 增加 `LicenseRegistration`（见 §6 表结构）。
- 新增 Alembic 迁移，`down_revision` **必须接当前 head `f2b000000001`**，用 `alembic heads` 验证唯一 head。
  > ⚠️ 本项目迁移链是完整单链，**按文件名排序 ≠ 链顺序**（历史上出现过 `f1b000000001` 的 down_revision 是 `f3a000000004`）。必须先跑 `alembic heads` 拿真实 head 再写 revision，不要猜。

#### 3) 后端：API

| 方法 | 路径 | 权限 | 用途 |
|---|---|---|---|
| GET | `/api/v1/license` | 登录即可 | 当前授权状态：tier、licensee、entitlements、expires_at、是否只读模式 |
| POST | `/api/v1/license/activate` | `*`（主管理员） | 粘贴/提交 Token 激活，返回激活结果与授权范围 |
| POST | `/api/v1/license/deactivate` | `*` | 停用当前授权（回落到只读演示模式） |

挂载在 `hris/modules/platform/license_api.py`，由 `business_router` include，与现有 `/api/v1/auth` 风格一致。

#### 4) 后端：只读拦截（三道，见 §7.2）

#### 5) 前端

| 文件 | 改动 |
|---|---|
| `apps/web/src/business/features/license/LicenseBadge.tsx`（新建） | **顶栏最右端**的描边小徽标：未授权 → 「未授权 · 只读演示」；已授权 → 「某某科技 · Commercial · 至 2027-10-24」。按你一贯偏好放顶栏、带描边、一眼可见，不放页脚 |
| `apps/web/src/business/features/license/LicenseWorkspace.tsx`（新建） | 「授权管理」工作区：查看当前状态与授权范围、粘贴 Token 激活、停用 |
| `apps/web/src/business/features/license/LicenseBanner.tsx`（新建） | 模块被锁时的明确说明面板（不伪造业务表单——沿用 `AppShell.tsx:149` 已有的「不显示假功能或占位业务表单」纪律） |
| `apps/web/src/business/navigation.ts` | `workspaces` 增加 `license` 项；给授权模块的项加 `licensedModule` 字段与锁标标记 |
| `apps/web/src/business/AppShell.tsx` | Header 右侧插徽标；被锁模块菜单**保留可见**、带锁图标 + Tooltip「需要 XX 模块授权」 |
| `apps/web/src/business/client.ts` | `getLicense` / `activateLicense` / `deactivateLicense` |
| `apps/web/src/business/business.css` | 水印层 `.corehr-watermark`（`pointer-events: none`，斜向重复低透明度文本，置于内容区底层） |
| `apps/web/vite.business.config.ts` | 新增 `define: { __COREHR_WATERMARK__: JSON.stringify(process.env.COREHR_WATERMARK ?? "") }`，支持构建期烘焙水印 |
| `apps/web/src/business/types.ts` | `LicenseStatus` 等类型 |

#### 6) 签发工具（**私有仓，不进公开仓**）

独立项目 `corehr-license`：

```text
corehr-license issue --licensee "某某科技有限公司" --licensee-short "某某科技" \
    --tier commercial --entitlements workforce:rw,workflow:r,attendance:r \
    --not-before 2026-10-24 --expires 2027-10-24 --out corp.lic
corehr-license inspect corp.lic          # 本地验签与摘要
corehr-license revoke --license-id LIC-2026-000123   # 写吊销清单，供在线通道
```

- 私钥来源：`COREHR_LICENSE_SIGNING_KEY` 环境变量，或 `~/.corehr/signing/ed25519.pem`。**私钥永不进任何仓库**，且要在两处 `.gitignore` 同时设防（公开仓 + 私有包仓）。
- 私钥生成用 `cryptography` 的 Ed25519，**不要用 `RandomNumberGenerator.Fill`**（Windows PS 5.1 会静默产生全零弱密钥，须用 `RandomNumberGenerator::Create()` + `GetBytes()`）。

#### 7) 文档同步（与 Wave 1 同批，不可延后）

| 文件 | 改动 |
|---|---|
| `docs/adr/ADR-0008-open-core-and-commercial-licensing.md`（新建） | 6 段式：背景 → 决策（编号）→ 备选方案（各含优/缺/不采用原因）→ 影响（正面/代价/风险与缓解）→ 验证证据 → 复审条件 |
| `docs/01-foundation/03-项目决策.md` | 新增 **D-108**：采用 Open Core 形态与离线签名模块级授权，社区版只读演示，商业版按模块授权 |
| `docs/01-foundation/16-coreHR产品总体PRD.md` | 修订 §3.2 第 24 行与 §4.2，使"商业服务方式不得阉割开源功能"限定为"不阉割已承诺开源的能力"，并明确"企业人数不作为运行时功能开关"与授权的关系；PROD-Q001 标记为已决并指向 ADR-0008 |
| `docs/01-foundation/99-待确认问题.md` | 关闭 PROD-Q001 |
| `docs/adr/README.md` | 补 ADR-0008 条目 |

> 代码注释引用规范：授权相关代码统一写 `// Requirement: D-108 — ...`（对齐项目既有 D-067 / D-091 / D-100 的引用纪律）。

**Wave 1 验收标准**：

1. 无 Token 时：登录成功；`GET /api/v1/attendance/rule-sets` 返回 200 且有数据；`POST /api/v1/attendance/rule-sets` 返回 403 且 `code=LICENSE_REQUIRED`、`details` 含缺失模块名。
2. 顶栏出现「未授权 · 只读演示」描边徽标；内容区出现水印；侧栏「考勤管理」可见但带锁标。
3. 激活有效 Token 后：同样的 POST 返回 201；徽标显示「某某科技 · Commercial · 至 2027-10-24」；`GET /api/v1/license` 返回完整 entitlements。
4. 篡改 Token 任一字节 → 激活返回 400 `LICENSE_INVALID_SIGNATURE`；过期 Token → 激活成功但状态为 expired → 仍保持只读。
5. DB 中只存 token 摘要（断言 `token_digest` 非明文）。
6. 测试规模：pytest 新增 ≥ 12 条（含签名往返、篡改、过期、只读拦截、激活幂等、并发激活冲突），vitest 新增 ≥ 6 条（徽标文案、锁定菜单可见性、授权页提交）；`scripts/check-business-portable.ps1` 全绿且现有 40+ 集成测试零回归。

---

### Wave 2 — 拆包：把核心引擎搬进私有包（价值最大的一步）

#### 拆包机制（对现有代码侵入最小的做法）

在公开仓定义 **Protocol 契约层**，私有包提供实现，公开仓保留 Demo 实现：

```text
apps/api/src/hris/contracts/<domain>.py        # 公开：Protocol + 契约 DTO
apps/api/src/hris/modules/<domain>/engine.py   # 公开：resolve_engine() 工厂
apps/api/src/hris/modules/<domain>/demo_engine.py  # 公开：直通 DB 的读 + 写操作拒绝
```

```python
# engine.py（公开）
def resolve_engine() -> AttendanceEngine:
    try:
        from corehr_enterprise.attendance import EnterpriseAttendanceEngine
        return EnterpriseAttendanceEngine(session)
    except ImportError:
        return DemoAttendanceEngine(session)   # 公开壳
```

`DemoAttendanceEngine` 的写方法统一抛 `LicenseRequiredError`；读方法**直接查数据库**返回真实行，不做规则求解。

#### 拆分波次（按商业价值与重写难度排序）

| 波次 | 目标模块 | 理由 |
|---|---|---|
| 2a | **workflow 引擎** | 状态机 + 选路是最难自行重写、最有商业价值的部分 |
| 2b | **attendance 引擎** | 规则/排班/假勤余额/月报冻结，业务复杂度最高 |
| 2c | **lifecycle + governance** | 招聘/合同/人事事件；导入校验引擎客户痛感强 |
| 2d | **workforce 计算内核** | 生效日期求解、编制占用、快照、批量变更 |

每个波次独立完成：抽 Protocol → 写 Demo 实现 → 私有包写真实现 → 切流 → 回归。

#### 拆包守则（必须遵守，否则商业边界失守）

1. **公开仓里不得残留可独立算出业务结果的代码**。用架构测试守卫。
2. **Demo 读路径与私有实现读路径共用同一查询代码**，只把"规则求解"抽走。否则社区版与商业版读出的数不一致 → 信任崩塌（最高风险项）。
3. **不按目录切，按能力切**。私有包暴露的是能力（"算日考勤"），不是整个目录。
4. 私有包走 **pip 私有源或私有 git submodule**；Docker 镜像构建时从私有源安装，公开仓的 CI 不依赖私有源（只跑壳的测试）。

**Wave 2 验收标准**（以 2a workflow 为例）：

1. 只 clone 公开仓 → `docker compose up` 正常起、UI 完整、读接口可用、写接口返回 `LICENSE_REQUIRED`。
2. 架构测试 `apps/api/tests/test_architecture_no_private_engine.py` 扫描公开仓源码，断言不含私有实现符号（如状态机判定函数名），故意塞入一个符号时必须报红。
3. 装入私有包后，写接口返回正确业务结果，且与拆包前行为完全一致（现有 workflow 集成测试全绿）。

---

### Wave 3 — 仓库重组 + 可选在线通道

#### 3a) 仓库分离

推荐路径（保留历史、公开仓干净无历史包袱）：

| 仓库 | 可见性 | 内容 | 操作 |
|---|---|---|---|
| `Millerprc/coreHR`（现有） | → **私有** | 全部历史与当前实现 | 改名 `Millerprc/coreHR-enterprise`，或保持私有并在 README 标注内部/客户交付 |
| `Millerprc/coreHR`（公开新建） | 公开 | 拆包后的骨架 + 契约 + UI + 文档 + LICENSE | 需一个**未被占用的名字**（现名已被私有仓占用）→ 建议 `Millerprc/coreHR-community` 或 `Millerprc/openhr-core` |

同时统一本地 remote：`git remote set-url origin <新的公开仓 URL>`，并加第二个 remote 指向私有仓（`private`），避免以后推错。

> **注意**：仓库一旦被人 clone 就无法收回。当前 0 fork / 0 watcher，实际泄漏面极小；现在转私有基本无损失。转私有后 GitHub 对非授权者返回 404，这本身也是一层效果。

#### 3b) 可选 License Center（在线通道）

只有当需要远程吊销或集中统计时才建。最小实现：

- `GET /v1/licenses/{license_id}/status` → `{revoked, checked_at, next_token?}`
- 吊销由 `corehr-license revoke` 写本地清单并同步到该服务。
- coreHR 侧：`COREHR_LICENSE_SERVER_URL` 未配置 → 纯离线，**不发起任何外部请求**；配置了 → 后台任务定期拉取，**不阻塞启动**。
- 网络不可达 → 沿用最后一次已知状态（见 §9.3 降级矩阵）。
- 明确不纳入：在线签发、支付、会员、计费。

**Wave 3 验收**：公开仓 clone 后不含任何私有实现符号；私有仓可完整构建并产出正确业务结果；授权吊销在配置在线通道时 24h 内生效，断网时不影响运行。

---

## 5. 授权模型细节

### 5.1 License Token 规格

```text
coreHR.<b64url(header)>.<b64url(payload)>.<b64url(ed25519_signature)>
```

```jsonc
// header
{ "alg": "EdDSA", "typ": "corehr-license-v1", "kid": "k1" }

// payload
{
  "v": 1,
  "license_id": "LIC-2026-000123",
  "licensee": "某某科技有限公司",
  "licensee_short": "某某科技",
  "tier": "community | developer | commercial",
  "entitlements": {
    "workforce":   { "read": true,  "write": true  },
    "workflow":    { "read": true,  "write": false },
    "attendance":  { "read": true,  "write": false },
    "lifecycle":   { "read": true,  "write": false },
    "governance":  { "read": true,  "write": false },
    "performance": { "read": true,  "write": false }
  },
  "issued_at":   "2026-10-24T06:00:00Z",
  "not_before":  "2026-10-24T00:00:00Z",
  "expires_at":  "2027-10-24T00:00:00Z",
  "seat_limit":  5000,              // 合同条款，不做运行时功能裁剪（见 §5.2）
  "deployment_binding": null,       // 可选：绑定部署指纹
  "issuer": "coreHR",
  "nonce": "<随机>"
}
```

设计要点：

- **签名覆盖 header + payload**，任一字节被改即验签失败。
- **签名算法固定 Ed25519**（`cryptography` 已依赖），不用 JWT 的 HS256（对称＝公钥可伪造，泄露即全线失守）。
- **只存 token 摘要**（sha256）入库，明文 token 只在激活请求里出现一次。
- **公钥表支持多 kid 并存**，支持轮换期（新的 kid 加入，旧的到期移除）。

### 5.2 三级版本

| 版本 | 获取方式 | 写能力 | 说明 |
|---|---|---|---|
| **Community** | 免费，自助 | 全部模块写禁用，**只读演示模式** | 完整 UI + 完整读路径，看得到全部功能与真实界面效果 |
| **Developer** | 免费申请，短有效期 | 限定模块写能力（如仅 workforce + workflow 写） | 便于开发者真实联调与贡献 |
| **Commercial** | 商业合同 | 按合同模块授权 + 完整支持 | 含私有包交付、部署支持、升级服务 |

`seat_limit` 仅作为**合同条款与签发元数据**记录，**不做运行时功能裁剪**——这既是与 PRD §4.2「企业人数不作为功能开关或许可限制」保持一致的做法，也避免把系统做成"按人头收费"这种最招人烦的形态。

### 5.3 授权状态的判定优先级

```text
1. 没有注册任何授权           → 只读演示模式
2. 注册了但 not_before 未到    → 只读演示模式（状态 not_yet_valid）
3. 注册了但 expires_at 已过    → 只读演示模式（状态 expired）
4. 在线通道明确返回 revoked   → 只读演示模式（状态 revoked，立即生效）
5. 否则                        → 按 entitlements 逐模块判定 read / write
```

---

## 6. 数据模型

```python
class LicenseRegistration(Base):
    __tablename__ = "license_registrations"
    id:                Mapped[uuid.UUID]  # pk, default uuid4
    license_id:        Mapped[str]       # unique, index
    licensee:          Mapped[str]
    licensee_short:    Mapped[str]
    tier:              Mapped[str]       # community | developer | commercial
    entitlements:      Mapped[dict]      # JSONB: {module: {read, write}}
    token_digest:      Mapped[str]       # sha256(明文 token)，不存明文
    issued_at:         Mapped[datetime]
    not_before:        Mapped[datetime]
    expires_at:        Mapped[datetime]
    seat_limit:        Mapped[int | None]
    status:            Mapped[str]       # active | expired | revoked | superseded | not_yet_valid
    source:            Mapped[str]       # env | file | admin
    activated_at:      Mapped[datetime]
    activated_by:      Mapped[str]       # 用户名
    revoked_at:        Mapped[datetime | None]
```

- **在线通道缓存**放 Redis（`license:server:{license_id}`，带 TTL），DB 只记 `last_sync_at` 供审计。
- **激活是写操作** → 必须走审计（复用现有 `hris/modules/platform/audit_service.py`），审计 payload **不得包含 token 明文**。
- 迁移接在当前 head 之后，`alembic heads` 必须唯一。

---

## 7. 只读演示模式的实现

### 7.1 语义定义

| 能力 | 未授权时 |
|---|---|
| 登录、导航、页面渲染、文档 | 可用 |
| 读接口（列表/详情/查询） | 可用，返回数据库真实行 |
| 读接口中的**规则求解类**结果（生效日期当前任职、编制占用、日考勤汇总、流程下一步预测） | 返回明确的「需要授权」标记，不返回假数据 |
| 写接口（新建/修改/删除/审批/导入/导出报表等有副作用的操作） | 403 `LICENSE_REQUIRED`，`details` 说明缺失模块与申请方式 |
| 审计与操作日志 | 可读（授权动作本身要被审计） |

> 「不伪造业务数据」沿用项目既有纪律（`AppShell.tsx:149` 的 PendingWorkspace 明确"当前不会显示假功能或占位业务表单"）。

**授权错误的信息边界**：403 响应只给出**缺失的模块名 + 申请方式 + 当前授权 tier**，**不得泄露业务策略细节**（不说明"你的规则应该怎么算""这条路径缺哪个字段校验"）。否则未授权方可以通过反复试错反推私有引擎的行为，等于把核心实现逐步还原出来。这条对公开接口同样适用：`details` 只放 `{module, required, tier, contact_hint}`。

### 7.2 三道拦截

**第一道：引擎边界（Wave 2 后为主力）**
私有引擎写方法在 Demo 实现里直接抛 `LicenseRequiredError`。天然收口、不会漏。

**第二道：路由级默认拒写（Wave 1 的主力，零侵入）**
沿用 `business_router.py` 已有的 router 级依赖模式：

```python
business_router.include_router(
    attendance_configuration_router,
    prefix="/api/v1",
    dependencies=[
        Depends(require_permission("ATTENDANCE_ADMIN")),
        Depends(require_licensed_write("attendance")),
    ],
)
```

`require_licensed_write(module)` 的语义：请求方法为 `POST/PUT/PATCH/DELETE` → 需要 `entitlements[module].write`；`GET/HEAD/OPTIONS` → 放行。
**例外**：少数查询型 POST（若有）必须**显式登记白名单**并在代码注释里写明理由，禁止"默认放行"。

**第三道：服务层显式标注（高价值路径）**
对关键写路径（审批执行、期间冻结、导入执行、敏感字段 reveal）在 service 方法首行显式 `await ensure_write_allowed("attendance")`。这层是审计与可读性保障。

### 7.3 性能

授权状态查询不能每次都打 DB：
- 进程内 LRU 缓存，TTL 5 秒；
- Redis 共享缓存，TTL 30 秒（多副本部署时避免各自回源）；
- 授权变更（激活/停用/吊销）**主动失效**进程内与 Redis 缓存。

---

## 8. 端到端流程

### 8.1 签发（你，离线）

```text
corehr-license issue --licensee "某某科技" --tier commercial \
    --entitlements workforce:rw,attendance:rw --expires 2027-10-24 --out corp.lic
  → 用 ~/.corehr/signing/ed25519.pem 私钥 Ed25519 签名
  → 输出 corp.lic（= coreHR.<h>.<p>.<s>）
  → 通过任意渠道交付客户（邮件/IM，不入库、不进仓库）
```

### 8.2 激活（客户）

```text
管理员 → 前端「授权管理」页 → 粘贴 Token → POST /api/v1/license/activate
  → 后端验签（Ed25519，公钥内置）→ 校验 not_before/expires_at → 计算 entitlements
  → 写 license_registrations（只存 digest）+ 审计（不含明文）
  → 失效缓存 → 返回授权范围
```

### 8.3 运行期判定

```text
每个受保护请求
  → require_licensed_write(module)
  → LicenseService.current_entitlements()
      → DB/Redis 缓存命中？ → 用
      → 未命中？ → 查 DB（必要时查在线通道）→ 写缓存
  → entitlements[module].write ? 放行 : 抛 403 LICENSE_REQUIRED
```

### 8.4 前端呈现

```text
登录成功 → GET /api/v1/license
  → 顶栏徽标：已授权显示「licensee_short · Tier · 至 expires_at」
              未授权显示「未授权 · 只读演示」
  → 侧栏：被锁模块可见 + 锁标 + Tooltip
  → 内容区：水印层（未授权显示「coreHR · 未授权演示」；已授权显示「coreHR · licensee_short · license_id」）
  → 点击被锁模块 → LicenseBanner 说明如何申请
```

---

## 9. 状态、并发、失败与恢复

### 9.1 状态机

```text
(none) ──activate(valid)──▶ active ──expire(now>expires_at)──▶ expired
                                │                                    │
                                ├──deactivate──▶ (none)              │
                                └──revoke(inline)──▶ revoked ◀────────┘（吊销优先于一切）
```

- `expired` / `revoked` / `not_yet_valid` / `(none)` **一律等价于只读演示模式**。
- 过期不自动删除注册记录，保留审计链。

### 9.2 并发

| 场景 | 处理 |
|---|---|
| 同一 license_id 并发激活 | `license_id` 唯一索引 → 冲突方返回 409 或按"后激活覆盖前激活"处理（推荐后者，并记 `superseded`），**不产生双活** |
| 多副本同时激活 | DB 唯一约束 + 事务，保证全局单一有效注册 |
| 授权状态缓存过期瞬间的写请求 | 允许最多 5 秒的旧缓存（fail-open 于授权判定，但**仅限已授权状态**；吊销走 Redis 主动失效 + 在线通道，立即生效） |
| 读缓存一致性 | 授权状态用「进程内 LRU + Redis」两级，写操作前统一读 Redis（TTL 30s），关键路径读 DB |

### 9.3 失败与降级矩阵

| 故障 | 行为 |
|---|---|
| Token 格式非法 | 激活返回 400 `LICENSE_INVALID_TOKEN`，**不影响系统运行** |
| 签名不匹配 | 激活返回 400 `LICENSE_INVALID_SIGNATURE` |
| Token 过期 | 激活**允许**（记录为 expired），系统进入只读 |
| `license_registrations` 表不存在（迁移未跑） | licensing 模块降级为「无授权 → 只读」，**不影响服务启动**。⚠️ 这条必须实现，否则一次迁移失败 = 整个系统起不来 |
| 内置公钥缺失 / 配置损坏 | 激活一律拒绝（fail-closed on activation），系统仍可只读运行 |
| 在线通道不可达 | 沿用最后一次已知状态；**不把授权降级为未授权**（避免网络抖动误伤客户）；超过宽限期（7 天）仍沿用并在 UI 标注「授权状态同步已过期」 |
| 在线通道明确返回 `revoked: true` | **立即**进入只读模式，不等宽限期 |
| Redis 不可用 | 回落到进程内 LRU + 直查 DB |
| 私钥泄露 | 轮换 kid：新增 kid 签发新 Token → 移除旧 kid → 旧 Token 全部失效。⚠️ 旧 kid 移除前需留重叠期，且已激活的旧 Token 需重新签发（记入运维手册） |

### 9.4 恢复

- 授权服务不可用时的重启用：授权状态完全由本地 DB + 缓存决定，**不依赖任何远端**即可恢复服务。
- 客户丢失 Token：重新签发（新 license_id 或同 id 新 Token），旧 Token 可按需吊销。
- 客户换机 / 重装：激活是幂等的，同 license_id 重新激活覆盖旧记录，不产生冲突。

---

## 10. 测试与验收

### 10.1 后端 pytest（新增）

| 文件 | 覆盖 |
|---|---|
| `apps/api/tests/test_license_token.py` | 编解码往返、签名验证、篡改任一字节验签失败、错误 alg 拒绝、过期 / not_before 判定、公钥 kid 轮换 |
| `apps/api/tests/test_license_guard.py` | `require_licensed_write` 的方法语义、白名单例外、缺模块时的 403 与 `details` 内容 |
| `apps/api/tests/integration/test_license_api.py` | 激活、重复激活、并发激活冲突、停用、只读模式下写 403 读 200、审计不含 token 明文、DB 只存 digest |
| `apps/api/tests/integration/test_architecture_no_private_engine.py` | 公开仓源码不含私有实现符号（Wave 2 起启用，故意塞入符号必须报红） |

沿用项目既有纪律：断言带 `response.text`；合成数据可识别（`licensee` 用 `Synthetic Licensee`）；`get_settings.cache_clear()` 在 env 变更测试后必须调用；`/api/v1/license` 的写操作要有副作用断言（查 DB）。

### 10.2 前端 vitest（新增）

| 文件 | 覆盖 |
|---|---|
| `apps/web/src/business/features/license/LicenseBadge.test.tsx` | 未授权 / 已授权两种文案、顶栏位置（`by-role` / `by-label-text` 查询，禁止 test-id） |
| `apps/web/src/business/features/license/LicenseWorkspace.test.tsx` | 粘贴 Token 提交、错误提示、状态展示 |
| `apps/web/src/business/navigation.test.ts`（扩写） | 被锁模块**仍然可见**、锁标存在 |

### 10.3 门禁

- `scripts/check-business-portable.ps1` 全绿（现有 40+ 集成测试零回归）。
- `node scripts/check-license-header.mjs` 全绿。
- `npm run test:run` 全绿。

### 10.4 人工验收脚本

1. 无 Token 启动 → 登录 → 逐个走 14 个 workspace → 确认**全部可进入且可读**，写操作均提示"需要授权"，顶栏徽标与水印可见。
2. 激活有效 Token → 确认授权模块写成功、徽标切换、非授权模块仍锁。
3. 停用 → 回到只读。
4. 篡改 Token → 激活被拒。
5. 断网 + 在线通道配置 → 确认授权状态不受影响。

---

## 11. 风险

| # | 风险 | 等级 | 缓解 |
|---|---|---|---|
| 1 | **PRD 与代码冲突**：现有 PRD §3.2 / §4.2 明文禁止商业授权阉割功能 | 高 | Wave 1 同批修订 PRD §3.2、§4.2、PROD-Q001，并写 ADR-0008 + D-108。**先改文档再改代码** |
| 2 | **Demo 读路径与商业版结果不一致** → 社区版看到的数据和商业版对不上，信任崩塌 | 高 | 拆包守则 2：只抽走"规则求解"，查询代码共用；每个 wave 加对比测试（同一数据集，Demo 与 Enterprise 读出的行必须一致） |
| 3 | **已公开的历史无法收回** | 中 | 现实泄漏面极小（0 fork / 0 watcher，且是旧快照）；以 LICENSE + 版权头作为追责依据；Wave 3 转私有 + 新建干净公开仓 |
| 4 | **只读拦截漏点**：查询型 POST 被误拦，或写路径漏标 | 中 | router 级默认拒写 + 显式白名单 + service 层标注；加一条"全量路由权限/授权覆盖守卫"测试（仿照现有 `test_permission_code_coverage.py`），保证每个写路由都有归属声明 |
| 5 | **拆包工作量大**（6 个域 × Protocol + Demo + 私有实现） | 中 | 分 4 个 wave，每个 wave 独立可交付可回滚；每 wave 只动一个域 |
| 6 | **授权判定进入热路径拖慢性能** | 低 | 两级缓存（进程内 5s + Redis 30s），授权变更主动失效 |
| 7 | **私钥管理事故** | 低 | 私钥永不入仓（两处 .gitignore + CI 守卫扫描）、离线保管、kid 轮换流程写进运维手册 |
| 8 | **在线通道成为单点** | 低 | 默认不启用；不可达不降级授权状态；宽限期 7 天 |
| 9 | **远程托管 API 路线与 PRD「私有化离线」冲突** | 低 | 本期不纳入，记入未决决策 |
| 10 | **社区版写全禁用导致贡献者无法联调** | 低 | Developer 级提供短效、限定模块的写能力，开发者可自助申请 |

---

## 12. 决策定案（按推荐定案，可随时推翻）

两份外部建议与本方案同源，无冲突。下列各项**按推荐定案**；其中标注「可推翻」的项，你随时可以一句话改回来。

| # | 决策点 | 定案 | 说明 |
|---|---|---|---|
| 1 | LICENSE 具体条款形态 | **自研「coreHR Sustainable Use License v1.0」**（n8n SUSL 风格），明确声明非 OSI 开源 | BSL 1.1 与「公开层 Apache-2.0 + 私有层商业许可」写入 ADR-0008 备选方案（各含优/缺/不采用原因）。可推翻 |
| 2 | 只读演示模式的粒度 | **全局**：无有效授权时所有写操作禁用（不限模块） | 与你选的「全部功能可浏览，所有写操作禁用」直接一致。授权后按 `entitlements` 逐模块放行写能力 |
| 3 | Workforce Core / 绩效 是否进写授权清单 | **不进**，作为免费层；但其实现仍在私有包 | 社区版仍可读 Workforce 与绩效数据；写能力随全局只读模式禁用，Developer 级可放开 |
| 4 | 私有核心交付形态 | **进程内私有包**（pip 私有源 wheel），不拆独立 RPC 进程 | 安全收益与 RPC 形态近乎相同，工程代价差一个数量级。保留「单模块升级为 RPC 服务」的后路（§3.1） |
| 5 | 公开仓最终名字 | 私有仓 `coreHR-enterprise` + 公开仓 `coreHR-community`（现名 `coreHR` 已被现有仓占用） | 可推翻。需你在 GitHub 侧亲自操作（建仓/改名/改可见性） |
| 6 | 是否现在就做在线 License Center | **不做**，Wave 3 可选 | 离线已完全满足私有化部署需求 |
| 7 | 公开仓是否保留完整前端 | **保留完整前端** | 完整 UI 是「能看到功能都有」的最好载体，也是招贡献者的入口 |
| 8 | 私有包发布方式 | **pip 私有源**（版本化、可离线 wheel、可校验哈希） | git submodule 作为备选（简单但易碎） |
| 9 | 是否把某个模块升级为独立 RPC 服务 | **不做** | 记入未决，随时可对单一模块启用 |

---

## 13. 执行约束与须知

- **本次仅产出计划，未修改任何仓库文件，未改动 Git 状态。** 本文档是本次唯一的写入。
- **本计划文档在仓库中的落位**：Wave 0 开工时，把本文档整理为 `docs/implementation/open-core-licensing-plan.md` 提交进仓库（当前会话的 artifacts 路径是临时位置，不能作为长期依据）。同时在 `docs/01-foundation/16-coreHR产品总体PRD.md` 的文档入口清单里补上链接，与项目既有的「文档入口」索引方式一致。
- 后续实施阶段的写入范围：Wave 0 涉及 `LICENSE`/`NOTICE`/`CONTRIBUTING.md`/`scripts/check-license-header.mjs`/`.gitignore`/`README.md`；Wave 1 涉及 `apps/api/src/hris/core/licensing/`、`apps/api/src/hris/modules/platform/license_api.py`、`apps/api/src/hris/modules/platform/models.py`、新迁移、`apps/api/src/hris/api/business_router.py`、`apps/web/src/business/**`、`apps/web/vite.business.config.ts`、`docs/**`。私有包与 `corehr-license` 工具在**独立私有仓**实施，不进本仓。
- **需要你在 GitHub 侧亲自操作的**：仓库可见性变更、仓库改名/新建、topics 与描述。AI 侧不代为执行账户级变更。
- **不得提交的**：私钥、License 明文 token、`deploy/.env`（已被 .gitignore 忽略）、任何真实人员数据。
- **测试纪律**沿用项目既有规范：断言带 `response.text`、合成数据可识别、`get_settings.cache_clear()` 必调、门禁脚本 `scripts/check-business-portable.ps1` 必须全绿才算完成。
- **Windows 环境注意**：生成 Ed25519 私钥时**不要**用 `RandomNumberGenerator.Fill`（PS 5.1 会静默产生全零弱密钥），须用 `RandomNumberGenerator::Create()` + `GetBytes()`。
- **迁移链注意**：新迁移的 `down_revision` 必须取自 `alembic heads` 的真实输出，不可按文件名排序推断。

---

## 14. 建议的落地顺序（把风险降到最低）

```text
第 1 步（半天）：Wave 0 —— LICENSE + 版权头 + NOTICE。不碰任何运行逻辑，可独立发布。
第 2 步（1 周）：Wave 1 —— 授权 SDK + 只读演示模式 + 前端徽标水印。
                 同时完成 PRD 修订 + ADR-0008 + D-108（必须同批）。
                 此时即便核心实现仍在公开仓，授权框架已经能跑、能演示、能签发。
第 3 步（按 wave）：Wave 2 —— 拆包。2a workflow → 2b attendance → 2c lifecycle+governance → 2d workforce。
                 每拆一个域，公开仓的商业价值就少一分、私有包就多一分。
第 4 步（可选）：Wave 3 —— 仓库分离 + 在线 License Center。
```

**为什么 Wave 3a 不放最前面**：当前 0 fork / 0 watcher、公开的还是旧快照，实际泄漏面极小；而且公开仓一旦发布再撤下，会在社区侧留下"撤回过"的负面印象。先把授权框架和拆包做完，再一次性以干净的骨架发布，是更稳的节奏。若你希望在拆包前就止血，只需先执行 Wave 3a 的一半（把现仓设为 private），不需要等 Wave 2 完成。
