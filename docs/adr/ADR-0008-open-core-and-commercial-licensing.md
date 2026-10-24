# ADR-0008 Open Core 形态与离线签名模块级授权

> 状态：Accepted
> 日期：2026-10-24
> 决策人：Miller（已拍板：四条关键决策 + 三处补充决策）、Mavis
> 关联任务：D-108；`docs/implementation/open-core-licensing-plan.md`；PRD §3.2 / §4.2 / PROD-Q001
> 关联记录：[项目决策 D-108](../01-foundation/03-项目决策.md)；PRD 待确认项 PROD-Q001 已由此关闭

## 背景

本 ADR 回答的是项目一直挂着的待决问题 **PROD-Q001**：「coreHR 采用的开源许可证、贡献者协议和第三方依赖准入规则」，以及一个更前置的问题：coreHR 的**源码以什么形态对外发布**。

2026-10-24 产品决策人拍板，把 coreHR 从「一份完整源码直接摊在 GitHub 上」改为 **Open Core + 离线签名模块级授权**。本 ADR 记录该决策及其边界，不重复实施细节（实施细节见 `docs/implementation/open-core-licensing-plan.md`，共 706 行）。

### 一、现有 PRD 与本决策直接抵触，必须先解决

| PRD 位置 | 原文（修订前） | 冲突点 |
|---|---|---|
| §2 产品定位（「普惠」条目，第 24 行） | 「企业规模、部署档位和商业服务方式不得成为阉割开源业务功能的理由」 | 与「模块级商业授权」直接抵触。**注意**：该句实际位于 §2，不是 §3.2（§3.2 为「当前非目标」清单）；本 ADR 按实际位置记录 |
| §4.2 产品交付原则（修订前第 72 行） | 「企业人数仅作为选型参考，不作为功能开关或许可限制」 | 需要明确它约束的是**运行时功能开关**，不否定**合同条款层的授权** |
| §20 待产品决策人确认 · PROD-Q001（修订前第 463 行） | 「coreHR 采用的开源许可证、贡献者协议和第三方依赖准入规则」 | 正是本 ADR 要回答的问题 |

按项目纪律（ADR 6 段式 + 决策日志 + PRD 同步），Wave 1 的授权代码落地前必须先把这三处改完，否则代码与文档不一致会被 Review 直接打回。PRD 修订与本 ADR 同批提交。

### 二、仓库已公开，且没有 LICENSE（实测事实）

2026-10-24 实测 `https://api.github.com/repos/Millerprc/coreHR` 返回：

- `private: false`、`visibility: "public"` —— **仓库对所有人公开**。
- `license: null` —— **GitHub 侧没有任何许可证声明**；已提交 HEAD 树中不存在 `LICENSE` / `NOTICE` / `COPYING` / `CONTRIBUTING.md`。本地工作区的这三个法律文件由并行的 Wave 0 任务新建，**尚未提交、尚未推送**，因此公开渠道至今没有许可证。
- `stargazers_count: 0`、`forks_count: 0`、`watchers_count: 0`、`open_issues_count: 0`。
- `pushed_at: 2026-08-15T04:12:58Z` —— 公开的是**旧快照**，早于本地 2026-08-18 rebaseline。
- 本地 `origin` 写的是 `https://github.com/Millerprc/HRIS.git`，与实际仓库名 `Millerprc/coreHR` 不一致（GitHub 靠重定向跳转）。remote URL 需要统一，否则以后会推错仓。

**无 LICENSE 时的法律事实**：GitHub 不授予任何使用许可，但「看得到、fork 得走」的事实已经存在，而事后追责唯一的凭据就是 LICENSE 与源码版权声明。这是最便宜、零业务风险的一步止血。

### 三、实际泄漏面很小，现在动手损失有限

0 fork / 0 watcher / 0 star，且公开的是旧快照；历史提交中从未出现过 `.env` / `.pem` / `.key` / `secrets/`，当前仅跟踪 `.env.example` 与 `deploy/business.env.example` 两个示例文件。**凭据泄漏风险为零，无需历史清洗**（不需要 filter-repo / BFG）。

### 四、Token 保护不了已公开的源码——真正的保护来源是私有实现

这是本决策的技术核心，必须写清楚，否则容易得出错误结论：

- **Token 只判定使用权，不判定所有权。** 一份完整源码一旦公开，任何 Token 机制都拦不住第三方自行 fork 自建。
- **保护来源是「核心业务引擎实现不公开」。** Token 的作用是在「拿到私有包」之后再叠加一层合同约束与可撤销性。
- coreHR 当前的问题正在于：workflow / attendance / lifecycle / governance / workforce 的引擎实现**全部在公开仓里**，此时加多少 Token 校验都没有保护价值。

因此本决策的骨架是**单仓公开 + 私有实现包**：公开仓保留完整 UI、完整 API 契约、完整数据模型与迁移链、Platform Kernel 实现与文档；核心业务引擎实现搬进不公开的私有包。公开仓保留 Demo 实现，但 Demo 实现**只做直通数据库的读取与显式的「需要授权」拒绝，不含任何规则求解**。

### 五、现有工程条件已具备，落地代价可控

- 现有认证链路已示范 **router 级挂依赖** 的写法（`hris/api/business_router.py:39-49`），授权门禁可复用同一模式，零侵入。
- 现有模块注册表 `/api/v1/system/modules`（`hris/modules/system/api.py:49`）已返回 `ModuleStatus(code=..., available_capabilities=..., available_endpoints=...)`，是天然的「功能清单」出口，授权信息可以并入这里或独立成 `/api/v1/license`。
- `cryptography==49.0.0` 已在生产依赖里 → Ed25519 签发与验签**零新增依赖**；`httpx==0.28.1` 同样已在，可用于可选在线通道。
- PRD 已定义的 Kernel / Workforce Core / 业务套件分层，**直接就是授权分层的天然骨架**，不需要另造一套模块划分词汇。

## 决策

本 ADR 的决策项编号为 **D-108.1 ~ D-108.9**，是项目决策 **D-108** 的细化拆分，供 `docs/01-foundation/03-项目决策.md` 的 D-108 条目引用。

### 四条关键决策（2026-10-24 产品决策人问卷确认，不得推翻）

- **D-108.1 保护强度＝单仓公开 + 私有实现包。** 公开仓只放骨架与契约，引擎实现在私有包（不公开）。公开仓里**不存在任何能独立算出业务结果的代码**。
- **D-108.2 授权模块＝考勤 / 生命周期 / 流程引擎 / 数据治理导入引擎（「全选」）。** 这四个模块的**写能力**需要授权；**Workforce Core 与绩效默认作为免费层**（社区版可读，其实现仍在私有包）。
- **D-108.3 Token 验证＝离线 Ed25519 签名为准 + 在线通道作为可选的续期/吊销。** 私钥离线保管，公钥内置于产品；**不依赖厂商服务器存活**，离线优先是硬约束。
- **D-108.4 未授权表现＝只读演示模式。** 功能全部可浏览、所有写操作禁用并给出明确的授权指引；**不伪造业务数据**，未授权时不返回占位结果。

### 三处补充决策（实施计划 §12 按推荐定案）

- **D-108.5 许可证形态＝自研「coreHR Sustainable Use License v1.0」（n8n SUSL 风格），明确声明非 OSI 开源。** 允许查看、学习、修改、非商业自用与贡献；限制未经授权的商业使用、白标转售与托管售卖；保留商标与署名权；写明模块级商业授权经 License Token 授予。BSL 1.1 与「公开层 Apache-2.0 + 私有层商业许可」双轨制**写入本 ADR 备选方案**（各含优/缺/未采用原因）。
- **D-108.6 私有核心交付形态＝进程内私有包**（pip 私有源 wheel），**不拆独立 RPC 进程**。公开仓定义 Protocol 契约层 + `resolve_engine()` 工厂，私有包提供实现；安全收益与 RPC 形态近乎相同，工程代价差一个数量级。保留「仅针对单一模块升级为独立 RPC 服务」的后路。
- **D-108.7 公开仓保留完整前端。** 完整 UI 是「能看到功能都有」的最好载体，也是招贡献者的入口；只锁写能力，不裁界面。

### 其余已定案事项（实施计划 §12）

- **D-108.8 只读演示模式的粒度＝全局。** 无有效授权时所有写操作禁用（不限模块）；授权后按 `entitlements` 逐模块放行写能力。授权状态分级为 community / developer / commercial，developer 级提供短有效期、限定模块的写能力，供贡献者真实联调。
- **D-108.9 私有包发布方式＝pip 私有源**（版本化、可离线 wheel、可校验哈希），git submodule 作为备选；**本期不建在线 License Center**（离线已满足私有化部署需求），在线通道留作可选；**不把任何模块升级为独立 RPC 服务**（记入未决，随时可对单一模块启用）。

### 不变量（实施层面的硬约束）

1. 公开仓内不存在可独立算出业务结果的代码；Demo 实现只提供直通数据库的读取与显式拒绝。
2. 授权判定只有一个收口点（`hris/core/licensing/`），任何模块不得自建授权逻辑。
3. 没有任何在线依赖是系统可用的前提；在线通道不可达时**不降级授权状态**。
4. Demo 读路径与商业版读路径**共用同一查询代码**，只把「规则求解」抽走——否则社区版与商业版读出的数不一致，信任直接崩塌。
5. 授权错误的响应只给缺失模块名、申请方式与当前 tier，**不得泄露业务策略细节**。

## 备选方案

### BSL 1.1（Business Source License 1.1）

- 优点：条款成熟、有大量先例；「变更日自动转 Apache-2.0」提供明确的社区回流预期；法务审阅成本低于自研文本。
- 缺点：**「变更日后自动转为 Apache-2.0」与「最长 N 年后强制开放」等于给自己设了一个必须公开商业代码的倒计时**，对一个仍在快速演进、核心引擎在私有手里的产品是自伤；无法把「模块级授权 + 只读演示模式」写进条款，与实际产品形态对不齐。
- 未采用原因：强制转开源条款与「核心引擎长期不公开」的资产策略直接冲突。自研 SUSL 风格可以自定义条款而不带强制转开源义务，且 n8n 的同类形态已被市场验证。

### 「公开层 Apache-2.0 + 私有层商业许可」双轨制

- 优点：公开层是标准 OSI 许可证，社区接受度最高、贡献者法律顾虑最小；私有层用商业许可，两者互不干扰。
- 缺点：**公开层一旦声明 Apache-2.0 就等于对公开层全部代码作出不可撤销的授权**——若后续发现某些引擎实现混在公开层，无法收回；且「公开层/私有层」的双重许可叙述容易被社区理解为「把核心藏起来的同时仍声称 Apache-2.0」，对品牌不利；条款复杂度高于单一许可证。
- 未采用原因：coreHR 的公开层与私有层边界会随 Wave 2 拆包进度持续移动，双许可的追溯义务跟着移动，成本不可控。单一份自研 SUSL 风格许可证可以把模块级授权与只读演示写进同一份文本。

### 私有核心做成独立 RPC 服务（独立进程）

- 优点：额外阻止「拿到 wheel 的人改 wheel」；跨语言实现与独立扩缩容成为可能；私有实现的进程边界天然形成隔离。
- 缺点：进程间通信、序列化、**事务边界跨进程**、Alembic 迁移归属、部署与运维复杂度、性能损耗全面上升；等于把一个模块化单体拆成微服务，与 PRD §6（`16-coreHR产品总体PRD.md:162`）「套件边界描述的是产品责任，不要求当前立即拆成独立进程」抵触。
- 未采用原因：安全收益差距很小——私有实现不发布这一点已经达成，而私有 wheel 只发给已授权客户，改它属于违反许可证而非核心风险；但工程代价差距很大。Protocol 契约层已经把接口定义与实现分离，将来仅对单一模块升级为 RPC 服务不影响调用方。

### 最高保护模块托管为远程 API

- 优点：核心实现永不落地客户环境，保护强度最高；可同时实现集中计费与集中吊销。
- 缺点：与 coreHR「私有化离线部署、不把依赖某一云厂商作为运行前提」的 PRD 原则正面冲突；网络成为可用性前提，直接否掉一批企业客户；客户数据出境与合规成本高。
- 未采用原因：本期不纳入，记入未决。离线 Ed25519 + 私有包已能满足当前商业目标。

### 纯 OSI 开源，不加任何授权机制

- 优点：贡献者门槛最低、社区传播最顺；无任何授权代码与运维负担；与 PRD 原有「开源」表述完全一致，不需要修订任何文档。
- 缺点：**当前全部引擎实现都在公开仓，一旦纯开源发布即等于永久放弃核心资产**，之后无法收回（仓库一旦被人 clone 就无法收回）；无法对已进入交付链路的客户做差异化交付。
- 未采用原因：这与「把核心业务引擎作为可收费资产」的长期目标不相容，且本决策的时点条件非常有利——仓库已公开但 0 fork / 0 watcher、且公开的是旧快照，此时保护成本最低。

## 影响

### 正面

- 核心资产（四个引擎模块 + workforce 计算内核）从公开仓撤出后，可支撑按模块的商业授权与差异化交付。
- 授权框架可独立先落地：Wave 1 完成后即使核心实现仍在公开仓，授权框架已经能跑、能演示、能签发。
- 零新增生产依赖（`cryptography` 已在），离线可用，不引入云厂商绑定。
- 公开层仍然「看得到全部功能」：完整 UI、完整 API 契约、完整数据模型与迁移链、完整文档，对开发者与潜在客户的说服力不降。
- 社区版只读演示不阉割已承诺开源的能力——只是把**规则求解**这一层收进私有包，读路径共用，数值口径一致。

### 代价

- **PRD 需要修订**（§2「普惠」条目与 §3.2、§4.2、PROD-Q001），本 ADR 与 PRD 修订是同一批交付。PRD §2 首句仍以「开源、可自托管」描述产品定位，其中「开源」需按最终许可证文本（Source Available／非 OSI 开源）再校准一次——该措辞属 Wave 0 法律层文案范畴，随 `LICENSE` 落盘时一并处理，不在本 ADR 的同步修订范围内。
- 引入授权 SDK、只读拦截、License 注册表与新迁移、`/api/v1/license` 系列端点、前端徽标与水印，以及一批新的测试与门禁。
- Wave 2 拆包是**分 4 个波次、每个域都要抽 Protocol + 写 Demo 实现 + 私有包写真实现 + 切流 + 回归**的持续工作量。
- 私有包交付与 pip 私有源、离线 wheel 的分发与校验成为新的运维面。
- 社区贡献者在无 Token 时无法直接写数据，需要 Developer 级通道兜底。

### 风险与缓解

| # | 风险 | 缓解 |
|---|---|---|
| 1 | **PRD 与代码冲突**：PRD 明文禁止商业授权阉割功能 | Wave 1 同批修订 PRD §2/§3.2/§4.2 与 PROD-Q001，并写本 ADR + D-108；**先改文档再改代码** |
| 2 | **Demo 读路径与商业版结果不一致** → 社区版数据与商业版对不上，信任崩塌 | 只抽走「规则求解」，查询代码共用；每个拆包波次加对比测试（同一数据集，Demo 与 Enterprise 读出的行必须一致） |
| 3 | **已公开的历史无法收回** | 现实泄漏面极小（0 fork / 0 watcher，旧快照）；以 LICENSE + 源码版权头作为追责依据；Wave 3 转私有 + 新建干净公开仓 |
| 4 | **只读拦截漏点**（查询型 POST 被误拦、写路径漏标） | router 级默认拒写 + 显式白名单 + service 层标注；加「写路由授权覆盖守卫」测试，保证每个写路由都有归属声明 |
| 5 | **授权判定进入热路径拖慢性能** | 两级缓存（进程内 LRU 5s + Redis 30s），授权变更主动失效 |
| 6 | **私钥管理事故** | 私钥永不入仓（两处 `.gitignore` + CI 守卫扫描）、离线保管、`kid` 轮换流程写进运维手册 |
| 7 | **在线通道成为单点** | 默认不启用；不可达不降级授权状态；宽限期 7 天 |
| 8 | **远程托管 API 路线与 PRD「私有化离线」冲突** | 本期不纳入，记入未决 |

## 落地情况（2026-10-24）

| 决策 | 落地位置 / 状态 |
|---|---|
| Wave 0 法律层 | `LICENSE` / `NOTICE` / `CONTRIBUTING.md` / 源码版权头门禁 —— 由并行的 Wave 0 任务在本地工作区落盘（未提交、未推送）；远端仓库仍无许可证声明。**版权头已全量刷入本地 347 个源文件**（`apps/**` + `scripts/**`，扩展名 `.py/.ts/.tsx/.js/.jsx/.mjs/.cjs/.sh/.ps1`），守卫 `scripts/check-license-header.mjs` 与幂等补写脚本 `scripts/apply-license-header.mjs` 均已接入 `scripts/check-business-portable.ps1` / `.sh` |
| Wave 1 授权 SDK | `apps/api/src/hris/core/licensing/`（`types` / `token` / `keys` / `store` / `service` / `guard` / `errors` / `server`）+ `hris/modules/platform/license_api.py` + 新迁移 + 前端 `features/license/` —— 本 ADR 与之同批 |
| Wave 2 拆包 | **2a（流程引擎）已落地**：公开侧新增 `hris/contracts/workflow.py`（`WorkflowEngine` Protocol + 契约 DTO + 公开词表）、`hris/modules/workflow/{queries,catalog,demo_engine,engine}.py`；私有包 `packages/corehr-enterprise/`（11 个文件，承载 32 个私有实现符号：条件求值、状态机与动作规格、引擎推进、流转/通知/调度）；`deploy/compose.enterprise.yaml` 为可选 overlay（base `compose.yaml` 未改）。架构守卫 `tests/test_architecture_no_private_engine.py` 用 **AST 扫描**（非文本匹配）断言公开仓不残留私有符号，已做**红绿验证**（塞探针必报红）。公开仓模式：写方法统一 403 `LICENSE_REQUIRED`，读接口返回真实数据；装私有包后写方法恢复。**2b attendance / 2c lifecycle+governance / 2d workforce 计算内核未开工** |
| Wave 3 仓库分离 | 现有仓转私有（保留历史）+ 新建干净公开仓；可选在线 License Center —— GitHub 侧账户级操作**由产品决策人亲自执行**。**私有包剔除风险已在本轮闭环**（见下一行），Wave 3 剩下的只是账户级动作 |
| **私有实现防误发（本轮补齐）** | 此前 `packages/` **既未被 git 跟踪、也未被 `.gitignore` 排除** —— 一次 `git add -A` 就会把商业实现提交进公开仓，而这类泄露在 GitHub 上**不可逆**。本轮补三道防线：① 根 `.gitignore` 加入 `packages/`（私有实现不进版本控制）；② `scripts/check-private-package-isolation.mjs` 三闸守卫（`.gitignore` 必须覆盖 → git 已跟踪文件里不得出现私有路径 → 打包后复核发布物内容），带**红绿自检**，并已做过一次真实的「强制加入索引 → 守卫报红 → 撤销 → 恢复绿」验证；③ CI（`.github/workflows/ci.yml`）跑该守卫并断言检出结果不含 `packages/`。**签发工具直接落在仓库外**（`C:\Users\83289\.corehr\tools\`），不存在误分发可能 |
| **签发公钥与私钥（D-114）** | 内置占位公钥已替换为**正式签发公钥**（`BUILTIN_PUBLIC_KEYS["k1"]`）。私钥在本机生成、**永不进仓库**、ACL 收紧到当前用户 + SYSTEM；**待产品决策人转移到离线保管并轮换**（已登记进待确认清单 D6）。轮换机制不变：新增 `k2` 与 `k1` 并存，`COREHR_LICENSE_PUBLIC_KEYS` 与内置表是合并关系，旧 Token 不会因轮换当天失效 |
| 文档同步 | 本 ADR + D-108 + PRD §2/§3.2/§4.2/PROD-Q001 + `docs/adr/README.md` + `00-正式文档目录.md` —— 与 Wave 1 同批 |

> 仓库最终命名：私有仓 `coreHR-enterprise` + 公开仓 `coreHR-community`（实施计划 §12 决策 5）。**注意现名 `coreHR` 已被现有仓库占用**，新建公开仓必须另取未被占用的名字；该操作为 GitHub 账户级变更，不在本 ADR 的实施范围内。

## 验证证据

均为 2026-10-24 在本机与公开 API 上实测，可复现。

- **仓库公开状态**：`GET https://api.github.com/repos/Millerprc/coreHR` → `"private": false`、`"visibility": "public"`、`"license": null`、`"stargazers_count": 0`、`"forks_count": 0`、`"watchers_count": 0`、`"open_issues_count": 0`、`"created_at": "2026-07-31T07:11:48Z"`、`"pushed_at": "2026-08-15T04:12:58Z"`、`"default_branch": "main"`。
- **remote URL 不一致**：`git remote -v` → `origin https://github.com/Millerprc/HRIS.git (fetch/push)`，与实际仓库名 `Millerprc/coreHR` 不一致，需统一。
- **无 LICENSE（以远端为准）**：`GET https://api.github.com/repos/Millerprc/coreHR` → `"license": null`；`git ls-tree --name-only HEAD` → 无 `LICENSE` / `NOTICE` / `COPYING` / `CONTRIBUTING` 命中；`git ls-files -- LICENSE NOTICE COPYING CONTRIBUTING.md` → 空。**结论：公开渠道至今没有许可证声明**（本地工作区已有 Wave 0 新建的 `LICENSE` / `NOTICE` / `CONTRIBUTING.md`，但未提交未推送，不改变该结论）。
- **零新增依赖（Ed25519）**：`apps/api/pyproject.toml:12` → `"cryptography==49.0.0"` 已在生产依赖；`:14` → `"httpx==0.28.1"` 已在（供可选在线通道）。签发与验签无需新增任何包。
- **第三方依赖协议核对结论**：`alembic 1.14.0`(MIT)、`cryptography 49.0.0`(Apache-2.0 OR BSD-3-Clause)、`fastapi 0.118.0`(MIT)、`httpx 0.28.1`(BSD-3)、`psycopg[binary] 3.2.3`(LGPL-3.0)、`pydantic 2.10.3`(MIT)、`pydantic-settings 2.7.0`(MIT)、`redis 5.2.1`(MIT)、`SQLAlchemy 2.0.36`(MIT)、`uvicorn 0.32.1`(BSD-3)、`pytest 8.3.4` / `pytest-asyncio 0.25.0`(MIT)；前端 `react 19.2.0`(MIT)、`antd 6.5.2`(MIT)、`vite 6.4.3`(MIT)、`vitest 3.2.7`(MIT)、`typescript 5.9.3`(Apache-2.0)、`@vitejs/plugin-react 4.7.0`(MIT)。**结论：无 GPL 传染性依赖，允许闭源商用分发**；唯一弱 copyleft 是 `psycopg`(LGPL-3.0)，以客户端库 + 服务端部署形态使用，不触发强制开源义务；`cryptography` 双许可，商用分发保留其一即可。该核对结论已落盘为仓库根 `NOTICE` §四（2026-10-24 核对），与本 ADR 一致。
- **功能清单出口已存在**：`apps/api/src/hris/modules/system/api.py:49` → `"/api/v1/system/modules"`，返回 `ModuleStatus(code=..., available_capabilities=..., available_endpoints=...)`（`:11` 导入、`:55` / `:76` / `:97` 构造），可作为授权功能清单的既有出口。
- **router 级挂依赖的现成写法**：`apps/api/src/hris/api/business_router.py:27-29` 起为 `business_router.include_router(...)` 模式，`business_router.py:39-49` 已示范 `include_router(workflow_configuration_router, prefix="/api/v1", dependencies=[Depends(require_permission("LIFECYCLE_ADMIN"))])`，授权门禁复用同一模式，零侵入。
- **人员敏感字段保护故意保留公开**：`apps/api/src/hris/core/personnel_security.py` 存在且保留在公开仓——它是安全机制而非商业能力，公开反而建立信任。
- **版权头守卫实测**：本地 347 个源文件全量刷入后，`node scripts/check-license-header.mjs` → `扫描 347 个源文件，2 个源码根，0 处违规`；故意删掉 `apps/api/src/hris/core/licensing/token.py` 的版权行后守卫报红（`发现 347 个源文件中 1 个缺版权声明`），恢复后转绿；补写脚本二次预演为 `将写入 0 个文件`（幂等）。守卫与补写脚本的判定规则一致（必须是**真正的注释行**且不在块注释内部），二者为镜像实现。
- **规划依据完整**：`docs/implementation/open-core-licensing-plan.md`（706 行）已落盘，含目标架构、公开/私有边界表、Token 规格、三级版本、只读模式三道拦截、并发与降级矩阵、风险表与决策定案表；本 ADR 的每一条决策均可回溯到该文档的具体章节。
- **PRD 冲突点逐行定位**：`16-coreHR产品总体PRD.md` 修订前 `:24`（阉割条目，位于 §2）、`:72`（企业人数条目，位于 §4.2）、`:463`（PROD-Q001 表格行，位于 §20）；全文件 `阉割` 命中 1 次。修订后对应位置为 `:24`（§2 限定表述）、`:51`（§3.2 新增非目标条目）、`:73`（§4.2 运行时与授权关系）、`:464`（PROD-Q001 标记为已决并链接本 ADR）。

## 复审条件

出现以下任一情况，须重新审视本决策：

- **产品决策人改变形态定案**：要求改为纯 OSI 开源、要求公开核心引擎实现、或要求把最高保护模块改为托管 API 路线。
- **商业模式转向 SaaS 订阅 / 公有云托管**，或出现按人头、按用量计费并需要在运行时裁剪功能的诉求（当前 D-108.2 明确 `seat_limit` 只作合同条款与签发元数据，不做运行时功能裁剪）。
- **签发链路需要强制在线**（例如合同或监管要求定期心跳、强制吊销在无网络时也必须生效），与 D-108.3 的离线优先冲突。
- **私有包被大规模泄露或存在实际的绕过授权获利的案例**，需要引入 DRM、硬件指纹绑定或更强的防篡改措施。
- **Wave 2 拆包后 Demo 读路径与商业版出现数值不一致**（风险 2），需要改变「只读演示 + 写能力授权」的形态，例如改为数据脱敏演示。
- **社区反馈证明只读演示模式严重阻碍贡献者参与**，需要调整免费层的写能力范围（D-108.8）。
- **出现 GPL 传染性依赖被引入生产依赖**，或 `NOTICE` 清单核对结论发生变化，触发许可证条款复审。
- **GitHub 上现有仓库已被 fork / 大量引用**，使「公开仓仅保留骨架」的历史包袱无法通过新建干净公开仓解决。
- **私有包交付形态的工程代价评估发生重大变化**（例如确实需要跨语言实现核心模块），触发 D-108.6 的 RPC 升级路径评估。
