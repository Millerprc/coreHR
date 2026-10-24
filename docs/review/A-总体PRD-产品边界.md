# 分片 A：产品总体 PRD ↔ 实现 对账

> 审计对象：`docs/01-foundation/16-coreHR产品总体PRD.md`（v1.2，2026-08-19，状态 `BASELINE / REVIEW_PENDING`）
> 审计范围：仅本份父级 PRD 的**产品级边界**要求；不审计 01/05/06/07/08/12/14 号文档与 `docs/input-packs/`
> 审计方式：只读代码 + 定点检索；未运行服务、未执行写操作、未修改任何项目文件
> 审计日期：2026-10-24（代码基线：`main` @ `8c5d207`，含工作区未提交改动）
> 章节说明：交接单写到 15 章，实际文件为 **20 章**（14=备份灾备与高可用，15=安装升级与回滚，16=非功能质量门槛，17=阶段路线，18=发布与完成定义，19=需求文档产出方式，20=待产品决策人确认）

## 汇总

| 判定 | 条数 |
|---|---|
| 已实现 | 24 |
| 部分实现 | 34 |
| 未实现 | 18 |
| 与PRD冲突 | 4 |
| 待企业输入 | 2 |
| 待决策 | 4 |
| **合计** | **86** |

---

## 明细

> 判定口径：`已实现` 有实现且一致；`部分实现` 有实现但不完整/有偏差；`未实现` PRD 明确要求但代码中检索不到（**检索词已列在证据列**）；`与PRD冲突` 实现与 PRD 明确矛盾；`待企业输入` PRD 自身标注需企业输入；`待决策` PRD 状态未获批准。
> 优先级：`P0` 与 PRD 明确冲突或违反产品红线；`P1` PRD 明确要求但缺失/部分实现；`P2` 体验或一致性优化。

### 1 文档目的与权威边界

| PRD 条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 16-coreHR产品总体PRD.md:13 | 每项功能必须按 17 号规范形成可评审、可开发、可测试、可验收的子级需求文档 | 部分实现 | 规范存在：`docs/01-foundation/17-模块功能需求文档规范.md`；实际功能文档仅 `docs/delivery/*`（9 份交付回执）；检索词 `PROTOTYPE_APPROVED`（全 docs 命中 2 条原型登记，无模块功能需求文档） | 交付回执不能替代"功能需求文档"这一层。职位/汇报/标签/审计/批量异动/绩效 6 个新增能力都没有对应的模块功能需求文档编号与批准状态，导致 §18 完成定义第 1 条无法判定 | P1 |
| 16-coreHR产品总体PRD.md:15 | 冲突时按《00-正式文档目录》规定的优先级处理 | 已实现 | `docs/01-foundation/00-正式文档目录.md` 存在并定义优先级；`docs/01-foundation/README.md` | — | P2 |

### 2 产品定位

| PRD 条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 16-coreHR产品总体PRD.md:24 | 企业规模、部署档位和商业服务方式不得成为阉割开源业务功能的理由 | 已实现 | 全仓检索 `feature_flag`/`license`/`plan`/`edition` 无按规模裁剪开关；`deploy/compose.yaml:35-88` 单套镜像服务所有业务 | — | P2 |
| 16-coreHR产品总体PRD.md:26 | 默认支持私有化和离线环境，不把依赖某一云厂商作为运行前提 | 已实现 | `apps/api/src/hris/core/config.py:18-21`（PostgreSQL+Redis）；`apps/api/src/hris/core/database.py:9-14`；`docs/adr/ADR-0001-toolchain.md`；检索 `s3\|aws\|azure\|gcp` 无云 SDK 依赖 | — | P2 |
| 16-coreHR产品总体PRD.md:27 | 安装、升级、备份、恢复和诊断属于产品能力，不是仅供开发者参考的脚本 | 未实现 | 检索词 `backup`/`restore`/`pg_dump`/`upgrade`/`rollback`/`diagnos`（限 `scripts/`）；`scripts/` 仅 `check-*.ps1/sh`、`dev-up/down`；`apps/api/alembic/versions/` 20 个迁移；无 install/backup/restore/diagnose 脚本 | PRD 把安装/升级/备份/恢复/诊断定为**产品能力**。当前只有开发期脚本。建议 P1 单独建立"发行与运维入口"任务：安装器、备份/恢复脚本、健康诊断命令，形成 `scripts/release/` 命名空间 | P1 |
### 3 产品目标与非目标

| PRD 条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 16-coreHR产品总体PRD.md:35-38 | 目标1-4：完整可组合业务套件、统一人员/组织/有效日期/事件模型、5人组织演进到集团不重写核心、默认模块化单体交付 | 部分实现 | 统一模型已成立：`apps/api/src/hris/modules/workforce/models.py:35`（Organization）、`:41`（OrganizationVersion）、`:324`（Person）、`:604`（Employment）、`:691`（EmploymentAssignment）、`:950`（HrEvent）、`:868/:891`（SnapshotBatch/HeadcountSnapshot）；模块化单体成立：`apps/api/src/hris/api/business_router.py:23-48` | **缺 Payroll、ESS、Integration 三个套件**（见 A-34）；有效日期与事件模型只在 Workforce/Attendance 落地，流程侧未消费事件模型 | P1 |
| 16-coreHR产品总体PRD.md:39 | 目标5：身份、文件、消息、任务、监控和外部连接等基础设施可以通过受控适配器替换 | 未实现 | 检索词（`apps/api/src`）：`oidc\|ldap\|saml\|sso\|oauth2`、`notification\|notify\|webhook`、`object_storage\|s3\|minio`、`secret_provider\|kms`；命中 0（唯一 `notification` 命中来自 `apps/web/package-lock.json` 的 `@rc-component/notification`） | 七个可插拔面一个都没有端口定义。至少应先声明接口（`IdentityProvider`/`ObjectStorage`/`NotificationSender`/`SecretProvider`/`JobScheduler`）再谈替换实现 | P1 |
| 16-coreHR产品总体PRD.md:40 | 目标6：对敏感人事数据提供服务端权限、加密、审计、备份和恢复闭环 | 部分实现 | 权限 ✓ `apps/api/src/hris/modules/workforce/personnel_api.py:44-62`（`PERSON_SENSITIVE_VIEW`/`PERSON_SENSITIVE_REVEAL`）；加密 ✓ `apps/api/src/hris/core/personnel_security.py:83-150`（AES-GCM + 掩码 + 检索摘要）；审计 ✓ `apps/api/src/hris/modules/workforce/personnel_service.py:904-911`；**备份恢复 ✗**（见 A-72） | 四要素中"备份和恢复闭环"完全缺失，敏感数据无法满足"恢复"要求。建议在 A-72 的备份任务中优先覆盖 `person_documents`/`person_contacts` 等密文列与密钥环 | P1 |
| 16-coreHR产品总体PRD.md:41 | 目标7：让 AI Native Coding 产出的需求、代码、测试和交付证据能够双向追踪 | 部分实现 | 前端有追踪注释：`apps/web/src/business/navigation.ts:78,107`、`apps/web/src/business/features/organization/PositionWorkspace.tsx:36`；后端**覆盖不均**——检索词 `Requirement:`（限 `apps/api/src`，共 90 个 .py）→ 17 个文件命中、137 处，集中在新模块 `modules/performance/*`、`modules/workforce/batch_change_*`、`modules/workforce/labels_*`、`modules/workforce/reporting_service.py`、`modules/platform/audit_*`、`modules/workforce/organization_*`，而**平台内核与既有人事/考勤主干零覆盖**（`modules/platform/import_service.py`、`modules/platform/models.py`、`modules/workforce/extended_service.py`、`modules/workforce/personnel_service.py`、`modules/attendance/*`）；交付证据 `docs/delivery/`（9 份） | 追踪机制本身成立（137 处可证），但**平台内核、Attendance 与人员档案主干反而没有追踪注释**，而这几处恰是风险最高的写入点（权限变更、敏感明文、导入导出、组织生效）。建议 P1：把"规则落点写追踪注释"扩到 `platform/`、`attendance/`、`personnel_service.py`、`extended_service.py`，并列入代码评审必检项 | P1 |
| 16-coreHR产品总体PRD.md:45-47 | 非目标1-3：不建通用 DocType/无代码平台、不预先拆微服务、第三方模块不得绕过应用服务直写其他模块表 | 已实现 | 无 DocType/低代码实体（检索 `doctype\|lowcode\|plugin_market` 无命中）；单体交付 `apps/api/src/hris/api/business_router.py:23-48`；无第三方模块/插件机制 | PRD §7.3 明确不建设插件市场，故"第三方越界"当前无暴露面 | P2 |
| 16-coreHR产品总体PRD.md:48-49 | 非目标4-5：不以换连接串宣称兼容 MySQL/Oracle；未完成压测前不宣称万级规模 | 已实现 | 仅 PostgreSQL：`apps/api/src/hris/core/config.py:18-20`、`apps/api/src/hris/core/database.py:9-14`；无 MySQL/Oracle 驱动依赖；`docs/review/platform-kernel-architecture-fit-review-2026-08-18.md:21` 明确"不能宣称已支持20万人规模" | 仓库口径与 PRD 一致，属正面合规证据 | P2 |
| 16-coreHR产品总体PRD.md:50 | 非目标6：不以数据库副本替代历史备份和时间点恢复能力 | 未实现 | 检索词 `pg_dump\|pg_basebackup\|PITR\|时间点恢复`（限 `scripts/`、`docs/implementation/`）；命中 0 个可执行备份流程，仅 `docs/implementation/personnel-sensitive-key-runbook.md:49-53` 描述密钥备份要求 | 同 A-72。当前既无副本也无备份，"不替代"要求虽未被违反，但该能力整体缺失 | P1 |

### 4 目标用户与产品使用方式

| PRD 条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 16-coreHR产品总体PRD.md:56-64 | 七类用户角色（系统主管理员、SSC及HR系统管理员、HRBP及专业BP、业务负责人、员工、审计与合规角色、外部系统） | 部分实现 | 已有角色仅 3 个：`SYSTEM_ADMIN`（`apps/api/src/hris/modules/platform/service.py:31`）、`SSC_ADMIN`（`apps/api/alembic/versions/f2b000000001_seed_onboarding_initiator_role.py:51`）、`ONBOARDING_INITIATE` 权限码（同文件 `:32`）；`HRBP` 仅作为 `bp_type` 枚举存在（`apps/api/alembic/versions/f1a000000001_phase_1a_organization_domain.py:140`），**不是角色**；检索词 `role_code="HRBP"` / `INSERT INTO roles` 全仓仅上述 2 处 | 业务负责人、员工、审计与合规角色、外部系统（API 客户端凭据类型）4 类无对应实现。角色目录是 §4.1 的产品承诺，建议随权限模型一起补齐 | P1 |
| 16-coreHR产品总体PRD.md:60 | HRBP 及专业 BP：企业规则确认后开放 | 待企业输入 | 角色未实现（同上）；企业输入包存在但未固化：`apps/api/src/hris/modules/system/api.py:71-74,92-95,113-116` 三处 `pending_inputs`（正式稳定编码对照、档案字段验收表、考勤与假期计提规则包、打卡接口契约） | PRD 自己把开放节奏挂在"企业规则确认"上，代码侧缺口由企业输入阻塞而非开发缺陷。按 PRD 保持待输入，不要由开发者自行固化 | P1 |
| 16-coreHR产品总体PRD.md:66 | 角色名称不等于固定权限；功能、动作、数据范围和字段权限均通过授权策略组合 | 部分实现 | 功能+动作 ✓：`apps/api/src/hris/modules/platform/models.py:23-74`（Role/Permission/UserRole/RolePermission）+ `apps/api/src/hris/modules/platform/dependencies.py:73-98`；字段级**仅敏感字段专项**：`apps/api/src/hris/modules/workforce/personnel_api.py:48-62`；**数据范围 ✗**：检索词 `data_scope\|scope_policy\|tenant_id\|row_filter`（限 `apps/api/src`）→ 命中 0；权限模型只有 4 张表，无 scope/field 实体 | PRD 明确"功能、动作、数据范围和字段权限"四维。当前只有前两维 + 敏感字段特例。数据范围缺失是"业务负责人按服务范围查看"（L61）无法开放的前置阻塞 | P1 |
| 16-coreHR产品总体PRD.md:70-73 | 业务套件决定启用哪些能力；部署档位决定容量与可用性；企业人数不作为功能开关 | 部分实现 | 人数不作为开关 ✓（无 license/plan 代码）；**套件启用 ✗**：`apps/api/src/hris/modules/system/api.py:52-118` 是硬编码 3 条 `ModuleStatus`（CORE_HR/WORKFLOW_LIFECYCLE/ATTENDANCE）；**档位 ✗**：`deploy/compose.yaml` 只有一份 dev 配置 | 与 A-28、A-45 同源：缺 `ModuleManifest` 与档位配置，套件无法按需启用 | P2 |
| 16-coreHR产品总体PRD.md:77 | 所有 Web 前端遵循 Ant Design 官方当前稳定版原则；只使用仓库锁定版本已支持的 API | 已实现 | 锁定 `antd 6.5.2`（`apps/web/package.json`）；版本守卫 `apps/web/scripts/check-antd-usage.mjs:1-20`（按组件作用域解析 `@deprecated`）；CI 入口 `scripts/check-business-portable.ps1:38-41`；策略说明 `docs/design/antd-page-interaction-standard.md:17-22` | 守卫脚本已纳入一键验收，属高质量实现 | P2 |
| 16-coreHR产品总体PRD.md:78 | 列表/组织树/仪表盘/工作台为宿主页；进入新增、编辑、详情、流程、子任务只能用 Modal/Drawer 或新标签页 | 已实现 | 宿主页 hash 路由不替换：`apps/web/src/business/AppShell.tsx:169-182,237-276`；组织详情走新标签页：`apps/web/src/business/features/organization/OrganizationWorkspace.tsx:331-338`（`window.open(..., "_blank", "noopener,noreferrer")`）；子任务用 Modal/Drawer：`apps/web/src/business/features/organization/PositionWorkspace.tsx:633`、`apps/web/src/business/features/organization/ReportingWorkspace.tsx:586` | 检索 `window.open(` 全前端仅 1 处业务使用（组织详情），其余子任务均在弹窗类容器内，符合"不在当前标签页替换宿主页" | P2 |
| 16-coreHR产品总体PRD.md:79 | 载体默认规则：简短确认用 Modal，中等复杂编辑用 Drawer，多分区/长表单/完整流程用新标签页 | 部分实现 | `PositionWorkspace.tsx:633-849` 用 **Modal** 承载约 9 个字段（职位名称/职级/职等/职类/序列/状态/变更原因/备注/生效日期）的新增表单；规范默认线：`docs/design/antd-page-interaction-standard.md:32`（MODAL ≤6 个简单字段）、`:33`（DRAWER 7-20 字段） | 字段数越过规范 MODAL 默认线却未升为 Drawer，且规范 `:36` 要求"选择不同载体必须写清原因并由产品决策人批准"——本次没有对应的批准记录（见 A-21）。建议 P2：改为 Drawer，或补批准说明 | P2 |
| 16-coreHR产品总体PRD.md:80 | 每份功能需求必须明确页面载体、开关行为、未保存变更处理、权限拒绝、加载与失败状态 | 部分实现 | 规范侧齐备：`docs/design/antd-page-interaction-standard.md:78-87`（页面合同 8 项）、`:110-121`（验收清单 11 项）；需求侧缺位：无模块功能需求文档（见 A-01）；代码侧承载：`apps/web/src/business/features/organization/OrganizationDetailWorkspace.tsx:119`（只允许最新请求更新） | 规范已把这条变成可执行检查项，缺的是"每份功能需求"的实体。建议 P1：把 `17-模块功能需求文档规范.md` 的页面合同章节设为功能需求模板的必填字段并在前端 PR 模板中固化 | P1 |
| 16-coreHR产品总体PRD.md:81 | 所有新增或变更的前端页面必须在编码前完成 Pencil 原型并经产品决策人确认；未达 `PROTOTYPE_APPROVED` 不得进入前端开发 | 未实现 | 全仓已批准原型仅 2 个：检索词 `PROTOTYPE_APPROVED`（限 `docs/`）→ 仅 `docs/input-packs/10-organization-management-product-input.md:266`（ORG-PROT-001）、`:267`（ORG-PROT-002）；职位/汇报/标签/审计/批量异动/绩效 6 个新增前端页面无任何原型登记：`apps/web/src/business/features/organization/PositionWorkspace.tsx`、`ReportingWorkspace.tsx`、`apps/web/src/business/features/people/PersonLabelPanel.tsx`、`apps/web/src/business/features/platform/AuditLogWorkspace.tsx` | PRD 把 Pencil 门禁写成硬性准入条件（配套规范 `docs/design/antd-page-interaction-standard.md:104`、`:113`）。当前 6 个新页面绕过了门禁。建议 P1：为这 6 个页面补原型并登记，或由产品决策人明确豁免并记录决策 ID | P1 |
| 16-coreHR产品总体PRD.md:82 | Moka、Frappe 等只作研究输入，不复制其代码、品牌资产或页面成品 | 已实现 | 检索 `moka\|frappe\|erpnext`（限 `apps/`）→ 0 命中；参考图处理规则已成文：`docs/design/antd-page-interaction-standard.md:89-99` | 无竞品资产引入痕迹，符合要求 | P2 |

### 5 总体产品架构

| PRD 条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 16-coreHR产品总体PRD.md:117 | Kernel 承载：用户、身份提供方、会话和租户上下文预留 | 部分实现 | 用户+会话 ✓ `apps/api/src/hris/modules/platform/models.py:10-21`（UserAccount）、`:77-93`（UserSession）、`apps/api/src/hris/modules/platform/security.py:12-48`（scrypt + token digest）；**身份提供方可插拔 ✗**（仅本地账号，检索 `oidc\|ldap\|saml\|sso` → 0）；**租户上下文 ✗**（检索 `tenant` → 0） | PRD 措辞是"预留"，故判定部分实现而非未实现。但租户上下文是第五阶段多租户（§17）的前置，建议至少定义 `TenantContext` 数据类与请求级中间件占位 | P1 |
| 16-coreHR产品总体PRD.md:118 | Kernel 承载：角色、动作、数据范围、字段权限及默认拒绝策略 | 部分实现 | 角色/动作/默认拒绝 ✓ `apps/api/src/hris/modules/platform/dependencies.py:73-98`（无权限即 403 `PERMISSION_DENIED`）；数据范围 ✗；字段权限 ✗（通用字段级缺失） | 同 A-14。默认拒绝这一半是合规的正面证据 | P1 |
| 16-coreHR产品总体PRD.md:119 | Kernel 承载：系统配置、数据字典、稳定编码和功能能力注册 | 部分实现 | 配置+字典 ✓ `apps/api/src/hris/modules/platform/models.py:96-137`（NumberSequence/DataDictionary/DataDictionaryItem）+ `apps/api/src/hris/modules/platform/configuration_api.py`；**功能能力注册 ✗**：`apps/api/src/hris/modules/system/api.py:52-118` 为硬编码 `ModuleStatus` 列表，无注册表实体 | "功能能力注册"与 A-28 的模块清单是同一件事，应合并为一个 `ModuleManifest` 交付 | P1 |
| 16-coreHR产品总体PRD.md:120 | Kernel 承载：结构化审计、敏感访问日志、Trace ID 和统一错误合同 | 已实现 | 统一错误合同 ✓ `apps/api/src/hris/core/errors.py:28-62`（`code`/`message`/`details`/`trace_id`）；Trace ID ✓ `apps/api/src/hris/core/middleware.py:8-17`（入站 `X-Trace-ID` 或生成，回写响应头）；审计 ✓ `apps/api/src/hris/modules/platform/audit_service.py:144-286`；敏感访问日志 ✓ `apps/api/src/hris/modules/workforce/personnel_service.py:904-911` | 结构化"日志"部分归入 A-69；此处四项要求均已落地 | P2 |
| 16-coreHR产品总体PRD.md:121 | Kernel 承载：幂等、后台任务、调度、Outbox 和可重试执行框架 | 部分实现 | 幂等 ✓ `apps/api/src/hris/core/concurrency.py:6-11`（`expected_version`+`idempotency_key`+`change_reason`）+ 唯一约束 `apps/api/alembic/versions/f3a000000003_application_hire_conversion.py:88`；Outbox 写入 ✓ `apps/api/src/hris/modules/platform/governance_models.py:11-24`；**调度 ✗**：`apps/api/src/hris/modules/workforce/organization_api.py:212-225` 只有手工触发的 `POST /api/v1/organization-events/apply-due`；**后台任务 ✗**、**可重试执行框架 ✗**、**Outbox 投递 ✗**（检索 `published_at` → 仅模型定义 `governance_models.py:23`，**从未被赋值**，即无投递器） | 这是 Kernel 最大的空洞。PRD 要求 Outbox 可追溯（§9.1 L255）与下游失败闭环（§11 L321），当前 Outbox 只有写入侧。建议 P0：把"Worker 进程 + Outbox Dispatcher + 任务表"作为一个纵向切片交付，而不是分散在各处 | P0 |
| 16-coreHR产品总体PRD.md:122 | Kernel 承载：模块清单、依赖检查、启停状态、版本和迁移编排 | 未实现 | 检索词 `ModuleManifest\|module_registry\|manifest\|dependency_check`（限 `apps/api/src`）→ 0；`apps/api/src/hris/modules/system/api.py:52-118` 返回硬编码 `ModuleStatus(phase=..., code=..., status="uat_ready", available_capabilities=[...], available_endpoints=[...], pending_inputs=[...])`，**无 version / dependencies / enabled 状态 / 迁移归属**；`apps/api/src/hris/shared/db/models.py` 把所有模型一次性注册进单一迁移链 | PRD 的模块治理入口目前是"一张写死的展示列表"。建议 P1：落地静态 `ModuleManifest`（模块ID、版本、依赖、后端路由、前端入口、迁移归属），并让前端菜单由它生成（见 A-38 同源问题） | P1 |
| 16-coreHR产品总体PRD.md:123 | Kernel 承载：文件、对象存储、消息通知、密钥和外部集成端口 | 未实现 | 检索词（`apps/api/src`）：`object_storage\|s3\|minio`、`notification\|notify\|webhook`、`secret_provider\|kms` → 0；密钥只有环境变量注入 `apps/api/src/hris/core/config.py:23-34` + `apps/api/src/hris/core/personnel_security.py:159-173`，**非端口** | 与 A-07 同一批空缺。建议 P1：先定端口接口再选实现，避免后续业务直接绑死具体中间件 | P1 |
| 16-coreHR产品总体PRD.md:124 | Kernel 承载：健康检查、日志、指标和追踪输出端口 | 部分实现 | 健康检查 ✓ `apps/api/src/hris/modules/system/api.py:18-45`（`/health/live`、`/health/ready` 含 DB+Redis 探测）；追踪 ✓ `core/middleware.py:8-17`；**日志 ✗**（检索 `logging\|logger` 限 `apps/api` → 仅 `alembic/env.py`、`alembic_business/env.py` 使用，业务代码 0 条）；**指标 ✗**（检索 `prometheus\|/metrics\|opentelemetry` → 0） | 健康与追踪达标，日志与指标两个"输出端口"缺失（与 A-69、A-70 同源）。建议 P1：补 `logging` 结构化配置 + `/metrics` 端点，指标先覆盖请求量/延迟/错误率三项 | P1 |
| 16-coreHR产品总体PRD.md:128-132 | Kernel **禁止**承载：组织有效期与单父树、Person/Employment 唯一性、编制与招聘流程与合同规则、考勤假期薪酬计算 | 与PRD冲突 | Platform 直接依赖业务模块：检索 `from hris\.modules\.(workforce\|workflow\|attendance)`（限 `apps/api/src/hris/modules/platform`）→ `platform/audit_service.py:14`、`platform/account_admin_service.py:16`、`platform/configuration_service.py:15`（均 import `hris.modules.workforce.models.AuditLog`）、`platform/import_service.py:37-61`、`platform/master_data_export.py:17`；`AuditLog` 物理定义在 `apps/api/src/hris/modules/workforce/models.py:992` | PRD 明文禁止"组织有效期、单父树、合并拆分规则"与"Person、Employment 和劳动关系唯一性规则"进入 Kernel。当前 `platform/import_service.py:37-61` 直接引用 Workforce 的 `ExtendedWorkforceService`/`OrganizationService` 实现，把组织版本、有效期、单父树规则整体带进 Kernel。建议 P0：①把 `AuditLog` 所有权迁回 Platform（表名与数据不变）；②把 import/export 拆成"通用交换内核 + 套件适配器" | P0 |
| 16-coreHR产品总体PRD.md:140-145 | Workforce Core 职责：Person 永久身份与多次 Employment、法人/组织/职务/人员关系、主组织主职务汇报负责人BP、当前结果+历史+快照+事件、工号与主数据质量约束 | 已实现 | `apps/api/src/hris/modules/workforce/models.py:324`（Person）、`:604`（Employment）、`:645`（EmploymentLegalEntityRelation）、`:691`（EmploymentAssignment）、`:720`（OrganizationPersonRelation）、`:748`（ReportingRelation）、`:778`（AgreementRelationship）、`:804`（HeadcountPlan）、`:868/:891`（快照）、`:950`（HrEvent）；工号质量约束 `apps/api/alembic/versions/f1a000000001_phase_1a_organization_domain.py` 的 `ck_persons_employee_number_format` | 六项职责逐项有模型与约束支撑，是当前实现质量最高的部分 | P2 |
| 16-coreHR产品总体PRD.md:147 | 业务套件不得复制 Workforce Core 中的人员或组织主档 | 已实现 | 标签/编制/考勤/合同均引用 `persons`/`employments` 外键，无平行主档：检索 `class Person\b` 仅 `workforce/models.py:324` 一处 | — | P2 |
### 6 业务套件边界

| PRD 条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 16-coreHR产品总体PRD.md:153-159 | 七个套件的责任与依赖边界（Recruitment / Workflow / Contract / Attendance / Payroll / ESS / Integration） | 部分实现 | Workflow ✓ `apps/api/src/hris/modules/workflow/models.py:22-77`（定义/版本/实例/任务）；Attendance ✓ `apps/api/src/hris/modules/attendance/models.py:26-320`（规则/班次/排班/打卡/假勤/余额/日报/月报/冻结）；Recruitment 部分 ✓（`workflow/models.py:97` Candidate、`:118` JobApplication、`:145` ApplicationHireConversion）；Contract 部分 ✓（`workflow/models.py:189` ContractRecord）；**Payroll ✗**（检索 `payroll\|salary\|compensation\|社保\|发薪`（限 `apps/api/src`）→ 仅 `workforce/models.py:661` 的法人关系枚举 `relation_kind IN ('contract','payroll','social_insurance','tax')`）；**ESS ✗**（检索 `employee_self_service\|self_service\|/ess` → 0）；**Integration ✗**（检索 `connector\|企业微信\|wechat\|webhook` → 0） | Payroll/ESS/Integration 三个套件完全不存在。PRD §17 L413 把 ESS/Integration 排在第五阶段，属排期未到，但**总体 PRD 是父级权威**，建议在 §6 标注"本版不含 Payroll/ESS/Integration"或补建空壳模块边界，避免各模块文档口径不一 | P1 |
| 16-coreHR产品总体PRD.md:154 | Workflow 不承担：任意脚本、SQL 节点、直接改业务表 | 已实现 | 条件引擎为白名单声明式：`apps/api/src/hris/modules/workflow/conditions.py:40-101`（仅 `exists/not_exists/eq/ne/in/not_in/gt/gte/lt/lte`，不支持的算子抛 `WorkflowConditionError` fail-closed）；节点类型受限 `apps/api/src/hris/modules/workflow/schemas.py:58-71`（仅 start/approval/action/end） | 无 eval/exec/SQL 执行路径，符合"受控流程"定义 | P2 |
| 16-coreHR产品总体PRD.md:156 | Attendance 不承担：薪酬扣款和工资计算 | 已实现 | `apps/api/src/hris/modules/attendance/` 全量无薪酬计算（检索 `payroll\|salary\|deduction` → 0）；考勤只产出 `AttendanceDailyResult`/`AttendanceMonthlyResult`/`AttendancePeriodFreeze` | — | P2 |
| 16-coreHR产品总体PRD.md:153 | Recruitment 不承担：编制强制控制、入职生效 | 已实现 | 招聘需求创建不校验编制占用：`apps/api/src/hris/modules/workforce/extended_service.py`（`create_headcount_plan` 才有冻结校验 `:1148-1157`，招聘侧无对应调用）；入职生效由 lifecycle 承接：`apps/api/src/hris/modules/workflow/extended_api.py`（`POST /api/v1/lifecycle/hr-events`） | 边界正确，编制"参考"而非"强制" | P2 |

### 7 模块生命周期与依赖规则

| PRD 条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 16-coreHR产品总体PRD.md:167-174 | 每个模块必须声明：稳定代码/名称/版本/责任边界、必需与可选依赖与最低兼容版本、提供与使用的能力和公开接口、配置项/权限代码/后台任务/健康检查、数据所有权/迁移序列/回滚限制、启停与升级行为 | 未实现 | 检索词 `ModuleManifest\|module_registry\|manifest\.py\|required_dependencies\|min_compatible_version`（限 `apps/api/src`）→ 0；现存最接近物是 `apps/api/src/hris/modules/system/api.py:52-118` 的硬编码列表，仅含 `phase/code/name/status/available_capabilities/available_endpoints/pending_inputs` | 7 类声明项中只有 3 类有雏形。建议 P1：新建 `modules/<x>/manifest.py` 统一声明，`ModuleManifest` 为 Pydantic 模型并由 `/api/v1/system/modules` 直接序列化，消灭写死列表 | P1 |
| 16-coreHR产品总体PRD.md:188 | Platform Kernel 是所有模块的直接技术底座，**不得反向依赖** HR 业务套件 | 与PRD冲突 | 检索 `from hris\.modules\.(workforce\|workflow\|attendance\|performance)`（限 `apps/api/src/hris/modules/platform`）→ 命中 8 处：`platform/audit_service.py:14`、`platform/account_admin_service.py:16`、`platform/configuration_service.py:15`、`platform/import_service.py:37,43,44,56,57,61`、`platform/master_data_export.py:17` | PRD 的"红线级"依赖方向被实际代码违反，且已违反 8 处横跨 5 个文件。建议 P0：先做 `AuditLog` 所有权迁移（低风险、收益直接），再做 import/export 内核拆分（改动面最大，放第二批） | P0 |
| 16-coreHR产品总体PRD.md:189 | coreHR 最小正式组合是 Platform Kernel + Workforce Core，两者均为必装项 | 部分实现 | 业务入口已含两者：`apps/api/src/hris/api/business_router.py:24-36`；**但镜像与 compose 默认入口不含**：`apps/api/Dockerfile:25`（`CMD uvicorn hris.main:app`）、`deploy/compose.yaml:48-55`（同）；`hris.main` 只挂 system + workflow + attendance：`apps/api/src/hris/api/router.py:8-11`，**无平台认证路由、无 workforce 路由** | PRD 说 Workforce Core 是"必装业务事实底座"，但默认跑起来的进程不含它，也不含 `/api/v1/auth/login`（`apps/api/src/hris/modules/platform/api.py:19`）。同时存在两个正式入口（`hris.main` 与 `hris.business_main`），运维人员按 Dockerfile 起服务会得到一个无法登录的精简 API。建议 P1：统一为单一应用工厂 + 唯一正式组合根 | P1 |
| 16-coreHR产品总体PRD.md:196-198 | 业务套件优先使用公开应用服务或版本化事件合同；跨模块读取必须走公开查询接口/只读投影，不得任意联表形成隐式依赖；跨模块写入只能调用数据所有者提供的命令接口 | 与PRD冲突 | Attendance 直连 Workforce/Workflow 内部模型：检索 `from hris\.modules\.(workflow\|workforce)`（限 `apps/api/src/hris/modules/attendance`）→ `attendance/extended_service.py:43-44`（import `WorkflowInstance`、`AuditLog`、`Employment`、`Person`）、`attendance/service.py:15`（import `AuditLog`）；Workforce 反向依赖 Workflow：`workforce/batch_change_service.py:20-22`（import `HrEventCreate`、`WorkflowInstanceCreate`、`LifecycleService`、`WorkflowDefinition`）；`attendance/models.py:149-152` 的 `LeaveRequest.workflow_instance_id` 外键直连 Workflow 表 | PRD 用"必须/只能"强制的条款被违反。注意 `workforce/batch_change_service.py` 是开发中的批量异动功能，它让 Workforce 反向依赖 Workflow，**与 PRD §7.2 L195「Workforce Core 不得依赖 Recruitment、Attendance 或 Payroll 等可选套件」同向但更严重**（依赖了通用 Workflow 也让 Workforce 绑死流程实现）。建议 P0：批量异动应改为"调用 Workflow 公开命令接口"，且由 Workforce 提供稳定的人员/雇佣查询契约给 Attendance | P0 |
| 16-coreHR产品总体PRD.md:199 | 检测到依赖缺失、版本不兼容或迁移失败时默认拒绝启用 | 未实现 | 检索词 `enable_module\|disable_module\|module_state\|dependency_missing\|version_incompatible`（限 `apps/api/src`）→ 0；模块清单为只读 GET `apps/api/src/hris/modules/system/api.py:48-52` | 无启用流程即无拒绝点。与 A-38/A-42 同批交付 | P1 |
| 16-coreHR产品总体PRD.md:204-210 | 生命周期状态机 registered→installed→enabled→disabled→upgrading→failed；停用默认阻止新业务但保留历史读取/审计/导出；已产生数据的模块不得物理删除；升级须先检查依赖、迁移、备份与回滚 | 未实现 | 检索词 `registered\|installed\|upgrading\|disabled`（限 `apps/api/src`、`apps/web/src/business`）→ 无模块状态机实现；`apps/web/src/business/navigation.ts:31-75` 的 `available` 字段全部硬编码为 `true` | PRD 的"停用保留历史读取"是重要产品承诺，当前无法验证。建议 P1：随 `ModuleManifest` 一起落地 `status` 字段 + 停用中间件（停用套件的写接口返回明确错误码） | P1 |
| 16-coreHR产品总体PRD.md:211 | 当前不建设第三方任意代码热加载、插件市场或运行时脚本机制 | 已实现 | 检索 `hot_load\|plugin_market\|runtime_script\|eval(`（限 `apps/api/src`）→ 0；`apps/api/src/hris/modules/workflow/conditions.py` 白名单算子（同 A-35） | 与 PRD 一致；建议在 §7.3 追加"受控模块注册表已在 PRD 立项，见 A-38"以便后续审计对账 | P2 |

### 8 部署分级与规模参考

| PRD 条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 16-coreHR产品总体PRD.md:215-223 | 五档部署（便携单机/标准生产/企业/集团/超大型目标）共用同一套产品代码与业务功能，每档有推荐形态与最低恢复要求 | 未实现 | 检索词 `compose\.\|docker-compose\|部署档位\|便携单机\|标准生产版`（限 `deploy/`、`scripts/`）→ 仅 `deploy/compose.yaml`（dev 模式，源码挂载 + `--reload`，`deploy/compose.yaml:45-55`）与 `deploy/compose.business.yaml:8-15`（同 dev 模式）；无生产 compose、无对象存储、无独立后台任务服务、无监控告警 | PRD 明确"五档部署使用同一套产品代码和业务功能……人数不是容量承诺"。当前既没有档位清单，也没有"标准生产版"起步所需的最小形态。建议 P1：至少交付"标准生产版"清单（独立 worker、无 `--reload`、外部 PG/Redis/对象存储、备份任务），其余档位按 §17 排期 | P1 |
| 16-coreHR产品总体PRD.md:225,239-243 | "超大型架构目标"是演进档位不是容量声明；不得以人数/QPS/"页面能打开"作容量结论 | 已实现 | 仓库口径合规：`docs/review/platform-kernel-architecture-fit-review-2026-08-18.md:21`（"不能宣称已支持20万人规模"）、`:228-241`（20 万级硬阻塞清单）；代码未见规模声明 | 正面合规证据 | P2 |
| 16-coreHR产品总体PRD.md:229-235 | 部署选型必须至少输入 7 类信息（人数/在线/峰值 RPS/批处理窗口/历史数据量/停机与丢失容忍/监管） | 未实现 | 检索词 `RPO\|RTO\|在线人数\|峰值 RPS\|批处理窗口\|选型`（限 `docs/`、`scripts/`）→ 0（仅 `docs/01-foundation/16-coreHR产品总体PRD.md` 自身命中）；`docs/01-foundation/99-待确认问题.md` 未覆盖 | 属"选型输入表"这一交付物缺失。建议 P2：随标准生产版清单一并给出选型问卷 | P2 |

### 9 轻量与可扩展原则

| PRD 条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 16-coreHR产品总体PRD.md:251-255 | 默认模块化单体：统一发布、API 无状态可增实例、长任务走可重试后台任务、Redis 不保存不可重建业务事实、Outbox 保证业务提交与事件发布可追溯 | 部分实现 | 单体 ✓ `apps/api/src/hris/api/business_router.py:23-48`；API 无状态 ✓（会话落库 `platform/models.py:77-93`，无进程内业务态）；Redis 不存业务事实 ✓（Redis 仅用于就绪探测 `apps/api/src/hris/modules/system/api.py:31-36`，且 `deploy/compose.yaml:24` 以 `--save "" --appendonly no` 启动）；**长任务后台化 ✗**（导入/报表/未来生效仍在请求链路，导入入口 `apps/api/src/hris/modules/platform/import_api.py`）；**Outbox 可追溯 ✗**（无投递器，见 A-27） | 四分之三达标，缺的是长任务与事件投递——也正是 §13.2 的核心。建议 P0/P1：把"任务执行器 + Outbox 投递"作为一个纵向切片，同时补齐 §13.2 的可重试/可查询/可告警语义 | P0 |
| 16-coreHR产品总体PRD.md:259-266 | 只有满足热点/故障域/一致性边界/安全地域四类证据之一才拆分独立服务 | 已实现 | 未拆分，无微服务（`deploy/compose.yaml` 仅 api/web/db/redis 4 服务）；仓库已记录拆分候选与触发条件：`docs/review/platform-kernel-architecture-fit-review-2026-08-18.md:266` | 与 PRD 一致 | P2 |
| 16-coreHR产品总体PRD.md:270-278 | 七类可插拔范围：身份、文件、通知、任务、监控、密钥、集成 | 未实现 | 检索词同 A-07（`oidc\|ldap\|saml`、`object_storage\|s3\|minio`、`notification\|notify`、`scheduler\|celery\|apscheduler`、`prometheus\|opentelemetry`、`secret_provider\|kms`、`connector\|webhook`）→ 在 `apps/api/src` 全部 0 命中；密钥为环境变量注入 `apps/api/src/hris/core/config.py:23-34`（非端口）；`apps/api/src/hris/modules/platform/governance_models.py:11-24` 是唯一"接口化"的尝试但只有 Outbox | 与 A-07/A-29 是同一件事的三个侧面。建议合并为一个任务：定义 7 个端口协议 + 1 个本地默认实现 + 1 个替换点测试 | P1 |
| 16-coreHR产品总体PRD.md:280 | Apusic、独立 API 网关、消息总线、ESB 属第五阶段评估，不得成为便携版/标准版强制依赖 | 已实现 | 无中间件依赖：`deploy/compose.yaml` 仅 PostgreSQL/Redis；`apps/api/src` 无 MQ 客户端（检索 `kafka\|rabbitmq\|pulsar\|nats` → 0） | 正面合规证据 | P2 |
| 16-coreHR产品总体PRD.md:282 | 不允许通过插件改变人员唯一性、有效日期、权限底线、审计不可篡改要求或核心事务边界 | 已实现 | 无插件机制（同 A-42）；人员唯一性由 DB 约束保护 `ck_persons_employee_number_format`；有效日期由 `ck_*_effective_period_order` 系列约束保护 | 正面合规证据 | P2 |

### 10 数据架构

| PRD 条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 16-coreHR产品总体PRD.md:288-296 | 核心业务须区分并关联 5 层事实（当前有效结果、带生效区间历史版本、变化事件/更正记录、时点快照、操作审计与敏感访问记录）；任一层不能独立替代其他层；业务主数据默认不物理删除 | 已实现 | 当前结果+历史版本 `apps/api/src/hris/modules/workforce/models.py:35,41`（Organization + OrganizationVersion）；事件/更正 `:950`（HrEvent，含 `related_event_id`、`cancellation_of_id`）；快照 `:868,:891`（SnapshotBatch + HeadcountSnapshot，month_start/month_end）；审计 `:992`（AuditLog）；不物理删除——组织变更是"取消事件"而非 DELETE：`apps/api/src/hris/modules/workforce/organization_api.py:198-209` | 五层齐备且各有模型支撑，是本 PRD 实现最完整的章节 | P2 |
| 16-coreHR产品总体PRD.md:300-303 | 每张业务表只能由一个模块拥有；数据所有者负责写入规则、约束、迁移与兼容；其他模块通过稳定 ID/公开查询/事件引用 | 部分实现 | 大部分表归属清晰（`audit_logs` 是唯一争议项，见下）；跨模块引用多用 FK+UUID（`apps/api/alembic/versions/f1a000000001_phase_1a_organization_domain.py` 的 `fk_*` 系列）；**归属冲突**：`audit_logs` 表定义在 Workforce `apps/api/src/hris/modules/workforce/models.py:992`，却由 Platform 三处写入 | PRD 说"每张业务表只能由一个模块拥有"，`audit_logs` 当前事实上被两个模块共同拥有。建议 P1（与 A-31 同批）：把 `AuditLog` 的 Python 所有权迁回 Platform，表名/列/数据不变，Workforce 侧改为 import，零数据迁移风险 | P1 |
| 16-coreHR产品总体PRD.md:308-311 | PostgreSQL 是唯一开发/测试/生产基线；MySQL/Oracle 属第五阶段适配目标，未建立迁移与自动化测试矩阵前不得宣传支持 | 已实现 | 仅 PostgreSQL：`apps/api/src/hris/core/config.py:18-20`、`apps/api/src/hris/core/database.py:9-14`；`apps/api/alembic/env.py` + `apps/api/alembic_business/env.py` 双迁移目录但同引擎；无 MySQL/Oracle 驱动 | 与 PRD 完全一致；注意 `alembic/` 与 `alembic_business/` 双链（`apps/api/alembic.ini`、`apps/api/alembic-business.ini`）与 PRD §16.1 L387"版本化迁移"要求相容，但需在 A-71 的发行说明中写清两者关系 | P2 |
| 16-coreHR产品总体PRD.md:304 | 报表与分析负载在集团版以上可与事务库隔离，但不得形成不可追溯的第二事实源 | 待决策 | 未实现隔离（当前单一库 + `COUNT+OFFSET` 分页，见 `docs/review/platform-kernel-architecture-fit-review-2026-08-18.md:237`）；PRD 未为该项指定阶段，§17 阶段表亦未单列 | 属第五阶段/集团版范围，PRD 未排期。建议在 §8 档位表标注"集团版起需 OLAP 隔离决策"，避免后续被当成本版缺陷 | P2 |
### 11 API、事件与外部集成

| PRD 条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 16-coreHR产品总体PRD.md:315 | 对外业务 API 使用版本化命名空间和稳定错误码 | 部分实现 | 稳定错误码 ✓ `apps/api/src/hris/core/errors.py:8-21`（`ApiError(code=...)`）+ `:28-62`（统一响应含 `trace_id`）；版本化命名空间 ✓ `apps/api/src/hris/core/config.py:17`（`api_prefix="/api/v1"`）；**遗留非版本化路由未清理**：`apps/api/src/hris/modules/workforce/api.py:20`（`APIRouter(prefix="/workforce")`，含 `POST /workforce/organization-types`、`GET /workforce/organizations`），检索 `from hris\.modules\.workforce\.api` → **0 处引用**（该 router 未被任何组合根挂载） | 死代码不构成线上冲突，但违反"对外只用版本化命名空间"的收敛意图，且后续若被误挂载会产生双前缀。建议 P2：删除该未挂载 router，或挂载到 `/api/v1` 并标注已废弃 | P2 |
| 16-coreHR产品总体PRD.md:316 | 创建、批量导入、事件执行和外部回调支持幂等 | 部分实现 | 创建 ✓ `apps/api/src/hris/core/concurrency.py:6-11` + `apps/api/alembic/versions/f1a000000001_phase_1a_organization_domain.py:66`（`uq_organization_events_idempotency_key`）；批量导入 ✓ `apps/api/alembic/versions/f2a000000001_import_governance_schema.py:57`；事件执行 ✓ `apps/api/alembic/versions/f3a000000004_contract_lifecycle.py:93`；**外部回调 ✗**（无外部回调入口，检索 `callback\|webhook` → 0） | 内部三类幂等到位，外部回调尚无入口。随 Integration 套件补齐即可，判定部分实现而非未实现 | P2 |
| 16-coreHR产品总体PRD.md:317 | 接口执行服务端认证、动作、数据范围和字段权限校验 | 部分实现 | 认证 ✓ 全路由经 `CurrentSession`（`apps/api/src/hris/modules/platform/dependencies.py:27-50`，401 `AUTHENTICATION_REQUIRED`/`SESSION_INVALID`）；动作 ✓ `dependencies.py:73-98`（403 `PERMISSION_DENIED`）；字段级（敏感专项）✓ `apps/api/src/hris/modules/workforce/personnel_api.py:44-62`；**数据范围 ✗**（检索 `data_scope\|scope` → 0）；**通用字段级 ✗** | 见 A-14/A-64。前两维落地，第三、四维空缺——这条是 PRD §12 的安全基线。建议 P1：先落数据范围（下级组织/BP 服务范围已有数据基础：`PersonBpMembership`+`BpServiceScope`，`apps/api/src/hris/modules/workforce/models.py` 与 `apps/api/src/hris/modules/workforce/organization_api.py:262-303`） | P1 |
| 16-coreHR产品总体PRD.md:319 | 事件合同包含稳定事件代码、对象ID、发生时间、版本和幂等标识 | 部分实现 | 写入点仅 2 处：`apps/api/src/hris/modules/workforce/organization_service.py:2232-2249`（组织域）与 `apps/api/src/hris/modules/platform/import_service.py:2875-2882`（导入）；模型 `apps/api/src/hris/modules/platform/governance_models.py:11-24` 字段为 `event_type/aggregate_type/aggregate_id/payload/occurred_at/published_at/attempt_count`——**版本只在 `payload` 内**（`import_service.py:2879` 的 `{"organization_id":..., "version":1}`），**无幂等标识列**；**覆盖缺口**：考勤、人事事件、招聘、合同均不写 outbox（检索 `OutboxEvent(` → 仅 2 处） | PRD 要求的是"事件合同"，当前只有一个组织域的私有事件写法。版本与幂等标识应升级为**列**，而非埋在 payload。建议 P1：定义统一事件合同（`event_code`/`object_id`/`occurred_at`/`version`/`idempotency_key`），并覆盖所有写业务事实的套件 | P1 |
| 16-coreHR产品总体PRD.md:321 | 下游失败不回滚已提交的本地业务事实，通过 Outbox、重试和人工补偿闭环处理 | 未实现 | 检索词 `retry\|backoff\|dead_letter\|重试\|补偿`（限 `apps/api/src`）→ 0（`attempt_count` 仅在写入时置 0，`governance_models.py:23` 的 `published_at` 从未被赋值，即无投递/重试/死信） | PRD 的"人工补偿闭环"在当前系统里没有任何入口——下游失败既不会发生（无投递器），也没有补偿通道。建议 P0：与 A-27 同一交付切片一起做（投递器 + 重试退避 + 死信表 + 补偿入口） | P0 |
| 16-coreHR产品总体PRD.md:322 | MCP 是受控业务 API 的入口适配器，不直接访问数据库或绕过权限 | 未实现 | 检索词 `mcp\|model_context_protocol`（限 `apps/api/src`、`apps/web/src`）→ 0 命中 | PRD 未给 MCP 排期（§17 第五阶段才提"平台化适配评估"，`:413`），且 §5 架构图把 MCP 列为入口之一。建议标 P2 并在 §17 明确 MCP 归属阶段，避免两处口径打架 | P2 |

### 12 安全、隐私与审计

| PRD 条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 16-coreHR产品总体PRD.md:326 | 所有生产入口默认鉴权；未知角色、权限、数据范围和办理人表达式默认拒绝 | 与PRD冲突 | 默认鉴权 ✓（`dependencies.py:27-50`，缺凭证即 401）；未知权限默认拒绝 ✓（`dependencies.py:79-80`，无授权即 403）；**未知办理人不拒绝，而是静默兜底给系统管理员**：`apps/api/src/hris/modules/workflow/extended_service.py:1205-1220`——审批节点无配置办理人时 `assignees = configured or [{"assignee_type":"role","assignee_ref":"SYSTEM_ADMIN"}]`；**办理人表达式永不求值**：检索 `expression`（限 `apps/api/src`）→ 仅 `apps/api/src/hris/modules/workflow/schemas.py:54` 声明 `assignee_type: Literal["user","role","expression"]`，**全仓无表达式求值实现**；`apps/api/src/hris/modules/workflow/service.py` 中检索 `assignee` → 0（流程定义创建时不校验办理人是否存在） | PRD 用"默认拒绝"强制的条款被反着实现：①未配置办理人 → 任务落到 SYSTEM_ADMIN，而非拒绝；②`expression` 类型被接受但从不求值 → 任务带着无人处理的字符串进入待办；③定义时零校验，未知 user/role 也能落库。建议 P0：①未知办理人一律抛 422 并给出明确错误码；②`expression` 要么实现求值、要么在 schema 层拒收，不得"接受但忽略" | P0 |
| 16-coreHR产品总体PRD.md:327 | 权限至少覆盖功能、动作、数据范围、字段和高风险操作 | 部分实现 | 功能 ✓（`WORKFORCE_ADMIN`/`LIFECYCLE_ADMIN`/`ATTENDANCE_ADMIN`/`DATA_GOVERNANCE_*` 等）；动作 ✓（`PERSON_EDIT_BASIC`/`PERSON_IMPORT`/`PERSON_EXPORT`/`ORGANIZATION_EVENT_APPLY`/`PERSON_SENSITIVE_REVEAL`）；高风险 ✓（明文查看、导出、解冻、回退各有独立码）；**数据范围 ✗**；**通用字段级 ✗** | 五维实现三维。另注：路由依赖的 `ATTENDANCE_ADMIN`（`apps/api/src/hris/api/business_router.py:42`、`apps/api/src/hris/modules/attendance/api.py:22`）与 `LIFECYCLE_ADMIN`（`:36`）在**任何迁移中都未被 seed**（检索 `permissions` 的 `bulk_insert`，仅 `f1a000000001_phase_1a_organization_domain.py:405-409`、`f1c000000001_personnel_record_foundation.py:143-145`、`f2a000000002_seed_governance_permissions.py:23-26`、`f2b000000001_seed_onboarding_initiator_role.py:31-32`）；测试里靠合成 fixture 补：`apps/api/tests/integration/conftest.py:177-178`（`role_code="SYNTHETIC_LIFECYCLE_ADMIN"`, `permission_code="LIFECYCLE_ADMIN"`）。结果：这两个权限实际只有 `*` 超级管理员能持有，普通角色无法被授予 → 建议 P1：补 seed 迁移并提供角色-权限管理入口（当前 `apps/api/src/hris/modules/platform/account_admin_api.py:38-78` 只有 `/roles` 只读与 `/users` 增改） | P1 |
| 16-coreHR产品总体PRD.md:328 | 证件、银行账户、薪资等敏感字段按分级加密、脱敏和授权访问 | 部分实现 | 加密+脱敏+密钥版本+检索摘要 ✓ `apps/api/src/hris/core/personnel_security.py:83-150`（AES-GCM + AAD 绑定 `field_code`+`record_id`）、`:183-237`（规范化与掩码函数）；覆盖字段：证件/联系方式/地址/紧急联系人/教育/工作经历/家庭成员（`apps/api/src/hris/modules/workforce/personnel_service.py:830-871`）；**银行账户 ✗**（无该字段模型）；**薪资 ✗**（Payroll 套件不存在，见 A-34） | 已覆盖的 7 类敏感字段实现质量高（fail-closed + AAD + 密钥轮换版本）。银行账户与薪资缺失是套件缺失的连带结果，不单独记缺陷。建议 P1：在 Payroll 套件立项时同步定义其敏感字段分级，避免后补 | P1 |
| 16-coreHR产品总体PRD.md:329 | 明文查看、导出、权限变更、解冻、回退和数据修订写入不可由普通业务管理员修改的审计记录 | 部分实现 | 明文查看 ✓ `apps/api/src/hris/modules/workforce/personnel_service.py:904-911`（`action="reveal"`，含 `reason`）；导出 ✓ `apps/api/src/hris/modules/platform/audit_service.py:250-283`（导出本身再写一条审计，只记筛选条件与行数）；权限变更 ✓ `apps/api/src/hris/modules/platform/account_admin_service.py:108,167,240-262`；回退 ✓ `apps/api/src/hris/modules/workflow/extended_service.py`（`/hr-events/{event_id}/rollback` 写审计）；**"不可由普通业务管理员修改" ✗**：审计表无 append-only 约束（无触发器/无 DB 权限隔离），`AuditLog` 由业务模块定义且未做写权限隔离 | 六个动作都留痕 ✓，但"不可修改"这半句缺技术保障：任何持有写权限的业务代码都能改/删审计行。建议 P1：审计表改为 append-only（撤销 UPDATE/DELETE 授权，或加触发器拒绝 UPDATE/DELETE），并把所有权迁回 Platform（与 A-31/A-54 同批） | P1 |
| 16-coreHR产品总体PRD.md:330-332 | 密钥与生产凭据不入代码/镜像/日志/示例数据/交付文档；非生产只用合成或脱敏数据；默认不要求上传企业数据至项目维护者或公共云 | 已实现 | `.gitignore:1-8`（`.env`/`.env.*`/`*.pem`/`*.key`/`secrets/`）；`git ls-files deploy/` 仅 3 个文件（`deploy/.env` **未跟踪**，且其内容为本地随机密钥）；密钥经环境变量注入 `apps/api/src/hris/core/config.py:23-34`、`deploy/compose.business.yaml:5-7`；合成数据 ✓ `apps/api/tests/integration/conftest.py:141-178`（`synthetic-admin`/`synthetic-viewer`/`synthetic-ssc`）；无外传路径（检索 `requests\.\|httpx\|urllib` 限 `apps/api/src` → 0） | 三项全部合规，是安全侧执行最扎实的部分 | P2 |
| 16-coreHR产品总体PRD.md:333 | 模块和适配器不得通过开放 JSON 长期承载未经评审的敏感字段 | 部分实现 | 审计 payload 为 JSON ✓ 且做了收敛（`apps/api/src/hris/modules/platform/audit_service.py:20-29` 固定导出列、`:50-52` 详情才带 payload、`:260` 导出只记筛选条件）；流程定义 JSON 化 ✓（`apps/api/src/hris/modules/workflow/models.py:33` 版本 `definition` JSON）；**导入 payload 开放**：`apps/api/src/hris/modules/platform/import_service.py:2866-2874` 把 `payload` 整体存入 `OrganizationEvent.payload`（JSON） | 敏感明文未进审计 ✓。导入通道的开放 JSON 由 Pydantic schema 约束（`apps/api/src/hris/modules/platform/import_schemas.py`），不算"未经评审"。整体判定部分实现，建议 P2：明确"开放 JSON 不得承载证件/银行/薪资明文"的静态检查规则 | P2 |

### 13 可观测、任务与运行保障

| PRD 条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 16-coreHR产品总体PRD.md:341 | 所有部署档位至少提供：结构化日志、统一 Trace ID 和稳定错误码 | 部分实现 | Trace ID ✓ `apps/api/src/hris/core/middleware.py:8-17`；稳定错误码 ✓ `apps/api/src/hris/core/errors.py:28-62`；**结构化日志 ✗**：检索 `logging\|logger\|structlog\|basicConfig`（限 `apps/api`）→ 仅 `apps/api/alembic/env.py:2`、`apps/api/alembic_business/env.py:2`（Alembic 自身配置），**业务代码 0 条日志语句**，应用日志实际由 uvicorn 默认 access log 承担 | PRD 说"所有部署档位至少提供"，当前连结构化日志这一项都没有。建议 P1：引入统一 JSON 日志（请求 ID、actor、业务对象 ID 关联），与 Trace ID 同源 | P1 |
| 16-coreHR产品总体PRD.md:342-345 | 提供 API 请求量/延迟/错误率/资源使用、数据库连接与慢查询与复制与空间观测、导入/生效/快照/考勤/薪酬/集成任务状态与积压、备份结果与恢复校验与失败告警 | 未实现 | 检索词 `prometheus\|/metrics\|opentelemetry\|slow_query\|pg_stat\|backlog\|积压`（限 `apps/api/src`、`apps/web/src`）→ 0；DB 侧只有 `SELECT 1` 存活探测（`apps/api/src/hris/modules/system/api.py:27-29`）；连接池硬编码 `pool_size=10, max_overflow=20`（`apps/api/src/hris/core/database.py:12-13`），**未按档位外置** | §13.1 五项观测能力全部缺失。建议 P1：先落 `/metrics`（请求量/延迟分位/错误率）+ 连接池按部署档位参数化（这是多副本下的真实阻塞点，见 `docs/review/platform-kernel-architecture-fit-review-2026-08-18.md:231`） | P1 |
| 16-coreHR产品总体PRD.md:349-353 | 任务必须可识别、可重试、可查询、可告警、可人工补偿；重复执行不得产生重复业务结果；任务状态不得只在内存或 Redis；长任务限制并发并分批执行并保存输入版本与结果证据；调度器多实例不得重复生效同一计划任务 | 部分实现 | 幂等 ✓（`core/concurrency.py:6-11` + `uq_*_idempotency_key` 唯一约束，见 A-58）；状态持久化 ✓（主数据落 PostgreSQL，无内存态任务）；**可重试/可查询/可告警/可补偿 ✗**（无任务表）；**长任务并发与分批 ✗**（导入同步在请求链路，`apps/api/src/hris/modules/platform/import_service.py`）；**调度去重 ✗**（无调度器，未来生效事件靠手工端点 `apps/api/src/hris/modules/workforce/organization_api.py:212-225`） | 幂等与持久化两项达标，其余四项是 §13.2 主体。建议 P0：建立 `job` 表（状态、输入版本、结果证据、重试次数、错误）+ 执行器 + 调度器 + 手动补偿入口，并把 `apply-due` 改由调度器驱动（保留手工入口作为运维兜底） | P0 |

### 14 备份、灾备与高可用

| PRD 条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 16-coreHR产品总体PRD.md:357-363 | 单机生产也须异机/异地加密备份；副本与基础备份+增量日志同时规划；数据库/附件/配置/密钥分别定义备份保留与恢复步骤；定时执行备份/校验/恢复演练；双节点无仲裁默认人工确认；上线前冻结 RPO/RTO/保留/切换方式/责任人并经实际恢复演练验证 | 未实现 | 检索词 `backup\|restore\|pg_dump\|pg_basebackup\|PITR\|时间点恢复\|演练\|RPO\|RTO`（限 `scripts/`、`deploy/`、`docs/implementation/`）→ 无任何可执行备份/恢复流程；`scripts/` 仅 `check-*.ps1/sh`、`dev-up/down`、`extract_ehr_lookup_tables.py`；仅密钥侧有原则性描述 `docs/implementation/personnel-sensitive-key-runbook.md:49-53`；`deploy/compose.yaml:13` 只有本地卷 `corehr_pgdata`（**单机单盘**，不满足"备份不得只放在主服务器同一磁盘"） | §14 八条几乎全部缺失，而 §2 L27 又把"备份、恢复、诊断"定为产品能力。建议 P1：把备份/恢复演练纳入"标准生产版"交付清单，并优先补异机加密备份脚本 + 隔离环境恢复演练（是 §16.1 L386"可恢复"门槛的前置） | P1 |
| 16-coreHR产品总体PRD.md:359 | Redis 缓存丢失后必须能够重建，不得成为唯一事实源 | 已实现 | Redis 未承担业务事实：`apps/api/src/hris/modules/system/api.py:31-36` 仅 `PING` 探测；`deploy/compose.yaml:24` 以 `--save "" --appendonly no` 启动（无持久化，业务事实不依赖它）；全部业务事实在 PostgreSQL | 正面合规证据 | P2 |

### 15 安装、升级与回滚

| PRD 条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 16-coreHR产品总体PRD.md:369-375 | 正式发行至少提供：支持矩阵（OS/CPU/容器运行时/依赖版本）、开发与体验与生产与离线安装配置边界、首次管理员与安全密钥与域名与 HTTPS 初始化流程、版本化迁移与预检与失败停止、升级前备份与兼容性检查与升级证据与回滚说明、备份恢复诊断健康检查入口、发布说明与破坏性变更说明与支持版本窗口 | 部分实现 | 版本化迁移 ✓ `apps/api/alembic/versions/`（20 个迁移）+ `alembic check` 漂移检查（`scripts/check-business-portable.ps1:34`）；首次管理员初始化 ✓ `apps/api/src/hris/modules/platform/api.py:23-25` + `apps/api/src/hris/modules/platform/service.py:39-46`（`COREHR_BOOTSTRAP_TOKEN` 比对 + 仅允许一次）；健康检查 ✓ `apps/api/src/hris/modules/system/api.py:18-45`；密钥初始化 ✓ `docs/implementation/personnel-sensitive-key-runbook.md`；**其余 ✗**：无支持矩阵文档（检索 `支持的操作系统\|CPU架构\|离线安装\|HTTPS` → 0）、无发布说明/破坏性变更说明、无诊断命令、无回滚说明、无生产 compose | 已具备"迁移 + 初始化 + 健康检查"三件套，缺"发行面"的其余四项。建议 P1：建立 `docs/release/`（支持矩阵、发布说明模板、破坏性变更登记）与 `scripts/release/`（升级预检、诊断、备份） | P1 |
| 16-coreHR产品总体PRD.md:377 | 业务数据迁移已执行且不可逆时，不得用"回滚应用镜像"冒充完整回滚；必须明确恢复备份或前向修复路径 | 未实现 | 检索词 `回滚\|rollback\|前向修复`（限 `docs/`、`scripts/`）→ `docs/01-foundation/16-coreHR产品总体PRD.md` 自身、`docs/review/platform-kernel-architecture-fit-review-2026-08-18.md`（审查意见）命中；**无实际回滚方案文档**；`apps/api/alembic/versions/` 中的 downgrade() 多为 drop_table 形态（如 `apps/api/alembic/versions/f1a000000001_phase_1a_organization_domain.py:514-515`），不构成生产回滚路径 | PRD 明确警告的"假回滚"目前既无方案也无保护。建议 P2：在升级流程文档中写明"哪些迁移不可逆、不可逆后走恢复备份还是前向修复" | P2 |

### 16 非功能质量门槛

| PRD 条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 16-coreHR产品总体PRD.md:383 | 正确性：核心业务约束同时具备领域校验、数据库约束或可证明的等效保护 | 已实现 | 领域校验 + DB 约束双层：如有效日期顺序 `ck_organization_versions_effective_period_order`、`ck_employments_employment_period_order`、`ck_reporting_relations_effective_period_order`、`ck_leave_requests_leave_period_order`、`ck_attendance_rule_sets_effective_period_order`；业务约束 `ck_headcount_plans_planned_count_nonnegative`、`ck_organization_cost_allocations_allocation_percent_range`、`ck_reporting_relations_different_people`、`ck_persons_employee_number_format`（均在 `apps/api/alembic/versions/f1a000000001_phase_1a_organization_domain.py` 等）；领域层 `apps/api/src/hris/modules/workforce/organization_policy.py`、`apps/api/src/hris/modules/workflow/conditions.py:40-101` | 与 PRD §16.1 第一条完全对齐，是质量侧最强项 | P2 |
| 16-coreHR产品总体PRD.md:384 | 安全性：通过越权、敏感字段、导出、会话、秘密和高风险操作测试 | 部分实现 | 已有测试：`apps/api/tests/integration/test_audit_logs_api.py`（导出/权限）、`apps/api/tests/test_personnel_security.py`（加密与掩码）、`apps/api/tests/integration/test_account_admin_api.py`（账号与最后管理员保护 `:162`）；后端测试文件 37 个、前端 24 个（`apps/api/tests/`、`apps/web/src/**/*.test.tsx`）；**缺**：数据范围测试（数据范围未实现）、秘密/密钥泄漏扫描、权限矩阵测试 | 已有 6 类中的 4 类测试证据。缺的部分与功能缺口同源（见 A-14/A-64）。建议 P1：随数据范围实现补对应越权测试，并加一条"敏感明文不得出现在日志/导出"的静态断言 | P1 |
| 16-coreHR产品总体PRD.md:385-389 | 可追溯（需求/规则/代码/迁移/测试/UAT/证据互相引用）、可恢复（隔离环境恢复 + 幂等重试）、可升级（版本化迁移 + 依赖不兼容与预检失败时安全停止）、可运维（故障可经日志/指标/Trace ID/任务记录定位）、可移植（不依赖专有云服务） | 部分实现 | 可升级 ✓（版本化迁移 + `alembic check`，`scripts/check-business-portable.ps1:34`）；可移植 ✓（无云依赖）；可追溯 **部分**（前端有 `Requirement:` 注释，后端 0 条，见 A-09；`docs/delivery/` 9 份交付证据）；可恢复 ✗（无隔离环境恢复，见 A-72）；可运维 部分（Trace ID ✓、审计 ✓，日志与指标与任务记录 ✗） | 五项中 2 项达标、2 项半达标、1 项缺失。建议 P1/P2：可恢复随 A-72；可追溯随 A-09；可运维随 A-69/A-70 | P1 |
| 16-coreHR产品总体PRD.md:393-402 | 每档性能验收必须使用目标拓扑与真实数据分布，至少记录会话数与请求模型、持续/峰值负载与时长、P50/P95/P99/错误率/超时率、DB/缓存/任务队列与系统资源峰值、任务积压清空时间、节点故障与切换后一致性；人数/QPS/"页面能打开"不能单独作为结论 | 未实现 | 检索词 `P95\|P99\|压测\|load test\|k6\|locust\|容量`（限 `apps/`、`scripts/`、`docs/`）→ 无压测脚本与报告；`docs/review/platform-kernel-architecture-fit-review-2026-08-18.md:224` 已写明"验收标准必须使用明确工作负载"但尚无执行 | PRD 允许不声明容量，因此不声明本身不违规；但 §8 表格一旦对外使用就需配套证据。建议 P2：在未压测前，对外只保留"便携单机版（5-100 人）"一档口径，其余四档标注"目标形态，未验证" | P2 |
### 17 阶段路线与产品架构映射

| PRD 条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 16-coreHR产品总体PRD.md:406-415 | 五阶段交付映射；第五阶段 = 多国家/语言、多租户、移动门户及平台化适配评估（ESS、Integration 及企业适配器） | 待决策 | 阶段一到三已交付（代码可证）；第四阶段 Payroll ✗（无实现，见 A-34）；第五阶段无任何实现（ESS/Integration/多租户/移动门户均 0 命中） | PRD 的阶段表本身是排期承诺，不是当前版本缺陷。但第四阶段 Payroll 尚无任何模块骨架，与 §17 L412 的"第四阶段=薪酬"存在排期缺口，建议在 §20 增列待确认项 | P2 |
| 16-coreHR产品总体PRD.md:415 | 已经实现的通用工程能力仍需按企业规则、权限和 UAT 升级为业务可验收状态 | 待企业输入 | 系统侧已登记待输入项：`apps/api/src/hris/modules/system/api.py:71-74`（正式稳定编码对照、档案字段验收表与脱敏迁移样例）、`:92-95`（正式流程图与审批人规则、合同字段与附件与提醒与电子签章规则）、`:113-116`（企业考勤与假期计提规则包、打卡接口契约与万人容量流量模型） | PRD 明确把"业务可验收"挂在企业规则、权限与 UAT 三者上，代码侧缺口属企业输入阻塞，非开发缺陷。建议 P1：把 3 处 `pending_inputs` 汇入企业输入跟踪表并标注责任人与到期日 | P1 |

### 18 产品级发布与完成定义

| PRD 条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 16-coreHR产品总体PRD.md:419-427 | 一个套件只有同时满足 7 条才能声明正式可用（功能需求文档已批准 / 依赖与数据所有权明确 / 正常边界异常并发权限幂等回退审计场景通过 / 迁移初始化升级备份恢复可重复 / 页面 API 任务日志运维文档一致 / 对应档位资源容量恢复门槛验证 / 业务 UAT 与规则确认） | 部分实现 | 第2条部分 ✓（数据所有权除 `audit_logs` 外清晰，见 A-54）；第3条部分 ✓（有权限/幂等/回退/审计场景测试，见 A-76）；第4条 ✗（无备份恢复路径，见 A-72）；第5条部分 ✓（`docs/implementation/business-runbook.md` 存在，但与实现存在已知差异，见其 `:145` 自述）；第6条 ✗（无档位容量与恢复验证，见 A-76）；第1条 ✗（无模块功能需求文档，见 A-01）；第7条 待企业输入 | 7 条中 0 条完全满足（这与当前 `status="uat_ready"` 的模块状态口径不一致——`apps/api/src/hris/modules/system/api.py:59,80,101` 标注三个模块 `uat_ready`）。**建议 P1：模块状态字段必须由 §18 的 7 条完成定义驱动，而非人工写死**，否则对外状态声明失真 | P1 |

### 19 后续需求文档产出方式

| PRD 条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 16-coreHR产品总体PRD.md:436-446 | 采用"总 PRD → 模块 → 能力域 → 功能 → 用户故事与规则 → 数据/权限/接口/异常/审计/NFR → 验收场景 → 最小开发任务"逐级拆分；每份功能需求只描述一个可独立验收的功能 | 部分实现 | 拆分模板已定：`docs/01-foundation/17-模块功能需求文档规范.md`（编号/状态/完成定义）；实际产物只到"交付回执"层：`docs/delivery/P1-JOB-ARCHITECTURE.md` 等 9 份；检索词 `能力域\|用户故事\|验收场景`（限 `docs/01-foundation/17-模块功能需求文档规范.md`）命中模板 | 模板完备、实例缺失。建议 P1：先把最近 6 个新增能力（职位/汇报/标签/审计/批量异动/绩效）各补一份模块功能需求文档作为样板 | P1 |
| 16-coreHR产品总体PRD.md:448-455 | Codex 为默认开发执行主体；自主开发不降低 Review 要求；**代码变更必须在实际规则落点写需求追踪注释，引用稳定需求或决策 ID 并说明变更原因** | 部分实现 | 前端有追踪注释范例：`apps/web/src/business/navigation.ts:78,107`、`apps/web/src/business/features/organization/PositionWorkspace.tsx:36`（引用 `ORG-PROT-001 / D-087`）；追踪注释范例 ✓ 后端 `apps/api/src/hris/modules/platform/audit_service.py:19`（`Requirement: AUDIT-007`）、`apps/api/src/hris/modules/workforce/organization_service.py`、`apps/api/src/hris/modules/workforce/batch_change_service.py`（合计 17 文件/137 处）；**覆盖缺口**：`apps/api/src` 下 90 个 .py 仅 17 个带追踪注释，`modules/platform/import_service.py`、`modules/platform/models.py`、`modules/workforce/extended_service.py`、`modules/workforce/personnel_service.py`、`modules/attendance/*` 均无 | 执行主体 ✓ 已落地（`docs/review/platform-kernel-architecture-fit-review-2026-08-18.md:264`：P0/P1/P2 实现默认由 Codex 完成）；追踪注释只覆盖**新增模块**，**未回补到平台内核与既有人事/考勤主干**，而这几处改动量最大。建议 P1：设一条"修改 `platform/`、`attendance/`、`personnel_service.py`、`extended_service.py` 必须补追踪注释"的评审门禁 | P1 |

### 20 待产品决策人确认

| PRD 条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 16-coreHR产品总体PRD.md:461-467 | 5 项待产品决策人确认（许可证与准入规则 PROD-Q001 / 可选套件默认安装策略 PROD-Q002 / 五档命名与 RPO-RTO PROD-Q003 / 第三方模块进入官方发行 PROD-Q004 / 二十万级目标参数 PROD-Q005） | 待决策 | PRD 自身状态 `BASELINE / REVIEW_PENDING`（`:4`）；仓库已有配套审查待批：`docs/review/platform-kernel-architecture-fit-review-2026-08-18.md:283-289`（5 项待产品决策人 Review）；`docs/01-foundation/99-待确认问题.md` 未收录上述 5 项 | 其中 **PROD-Q002 直接决定 A-38/A-42 怎么建**：可选套件是"默认全装按需启用"还是"按发行包选择安装"，两种答案对应不同的 ModuleManifest 与 compose 设计。建议 P1：把 PROD-Q002 提到最前决策，因为它阻塞 §7 模块治理落地 | P2 |
| 16-coreHR产品总体PRD.md:469 | 未确认项不得由开发者自行固化；其余已确认边界可以继续产出模块级需求 | 待决策 | 代码侧未越权固化上述 5 项（无许可证文件、无发行包选择逻辑）；但已固化若干 PRD 未确认事项：`apps/api/src/hris/modules/system/api.py:59,80,101` 的 `status="uat_ready"`、`:56,78,99` 的 `phase=1/2/3` 划分 | `uat_ready` 与阶段编号属于"正式可用状态"判断，落在 §18 完成定义之下，但 §18 的 7 条尚未满足（见 A-82）。建议 P1：要么补齐完成定义，要么把模块状态降级为 `implemented`/`uat_pending` | P1 |

---

## 本分片 3 条最该先修的

1. **A-39 / A-29 / A-37（跨模块依赖方向）**：PRD §5.2、§7.2 明文禁止 Platform Kernel 反向依赖 HR 业务套件、禁止跨模块直连内部模型，而当前有 8 处 Kernel→Workforce 依赖、Attendance→Workflow/Workforce 直连、Workforce→Workflow 反向依赖，违反的是 PRD 的结构性红线且已扩散到 5 个以上文件；先迁 `AuditLog` 所有权（表名数据不变、零迁移风险），再把 import/export 拆成"通用交换内核 + 套件适配器"。

2. **A-27 / A-48 / A-71 / A-61（异步任务与事件闭环）**：PRD 要求幂等、后台任务、调度、Outbox 与可重试执行框架，且 §9.1 要求 Outbox 保证事件可追溯、§13.2 要求任务可重试可查询可补偿——现状是 Outbox 只有写入侧（`published_at` 从未被赋值）、未来生效靠手工端点、未来生效/导入/报表全部挤在请求链路；这一条同时卡住 §13.1 观测、§9.1 长任务后台化和 §11 下游失败闭环，是投入产出比最高的纵向切片。

3. **A-63（办理人默认拒绝）**：PRD §12 用"默认拒绝"强制未知角色/权限/数据范围/办理人表达式一律拒绝，而实现却在审批节点无办理人时静默兜底给 `SYSTEM_ADMIN`（`extended_service.py:1205-1220`）、`expression` 类型办理人被 schema 接受却全仓无求值实现——这既是安全语义的反向实现，也是"业务负责人/HRBP 按授权办理"这类产品承诺的隐性破口，改动面小、语义收益大。

---

## 附录 A：本次审计未计入 PRD 缺陷的项（避免误报）

| 项 | 为什么不计为 PRD 缺陷 |
|---|---|
| 无可视化流程设计器 | PRD §6 对 Workflow 的责任定义是"受控流程定义、版本、实例、任务、会签/或签和条件选路"，未要求图形化设计器。当前 `apps/api/src/hris/modules/workflow/schemas.py:58-77`（节点/边/条件）与 `apps/web/src/business/features/lifecycle/WorkflowPanel.tsx` 已覆盖 PRD 列出的全部责任项，故**不判未实现** |
| 批量异动方案制（`modules/workforce/batch_change_*`）开发中 | PRD 总体层未要求批量异动能力。但其 `apps/api/src/hris/modules/workforce/batch_change_service.py:20-22` 让 Workforce 反向依赖 Workflow，已计入 A-39 作为依赖方向冲突 |
| 绩效 OKR（`modules/performance/*`）开发中 | PRD 总体层未把绩效列入七套件边界（§6），属新增域；仅作背景，不判缺陷。其路由**已挂载**到 `apps/api/src/hris/api/business_router.py:36`，模型也已注册进 `apps/api/src/hris/shared/db/models.py:16-20,110-112`，但未进入 `apps/api/src/hris/modules/system/api.py` 的模块清单 |
| MySQL/Oracle 适配 | PRD §10.3 明确列为第五阶段目标且禁止在建立测试矩阵前宣传；当前仅 PostgreSQL 属**合规**，不判未实现 |
| Payroll/ESS/Integration 套件 | 见 A-34：PRD 父级确实列出这三套件，故按"部分实现"记录（其自身排期在 §17 第五阶段），不按"未实现"计 |

## 附录 B：无法完全判定的条款及原因

| 条款 | 原因 |
|---|---|
| A-82（§18 完成定义第 1 条"功能需求文档已批准"） | 模块功能需求文档本身不存在（见 A-01），因此"是否已批准"无可核对的基线，只能判为不满足，无法进一步区分"未编写"还是"编写未批准" |
| A-84（§19.1 追踪注释）的覆盖比例 | 精确口径为"`apps/api/src` 下 90 个 .py 文件中 17 个带 `Requirement:` 注释（全文共 137 处）"，已用两条独立命令交叉复核（文件级 `-Quiet` 扫描 + 全文出现次数统计）。无法判定的是"未带注释的改动是否本就无需追踪"——仓库未定义哪些文件属"实际规则落点"，该判定需先补评审规则 |
| A-45（§8 五档部署） | PRD 明确"人数不是容量承诺"，因此无法用"档位未落地"直接判定违反 PRD。本分片按"PRD 明确要求的交付物缺失"记为未实现，实际可接受性需产品决策人裁定 |
| 业务规则的正确性（A-30、A-53 等） | 本分片只做**存在性与边界一致性**对账，未逐条复核领域计算规则正确性；后者属 05/06/07/08 号领域规范与 14 号需求规格的审计范围 |

## 附录 C：本次审计实际执行的检索与只读动作

- 读取：`docs/01-foundation/16-coreHR产品总体PRD.md`（全文 469 行）、`docs/design/antd-page-interaction-standard.md`、`docs/review/platform-kernel-architecture-fit-review-2026-08-18.md`、`docs/01-foundation/17-模块功能需求文档规范.md`（仅定位）、`apps/api/src/hris/**` 关键文件、`apps/web/src/business/**` 关键文件、`deploy/*`、`scripts/*` 清单。
- 检索工具：ripgrep（`grep` 工具）用于跨目录内容检索，PowerShell `Select-String` 仅用于单文件精确匹配；未使用 `Select-String -Path <目录>`（PS 5.1 非递归会返回假 0）。
- Git：仅只读命令（`git log`/`git status`/`git ls-files`/`rev-parse`），**未执行任何写操作、未 push、未改配置**。
- 唯一写入：本文件 `tmp/prd-audit/A-总体PRD-产品边界.md`（`tmp/` 已在 `.gitignore` 中，不污染仓库状态）。
- 并发变更说明：审计期间工作区被另一执行方并发修改（`git status` 显示 `apps/api/src/hris/api/business_router.py`、`apps/api/src/hris/modules/workflow/extended_service.py`、`apps/api/src/hris/shared/db/models.py` 等被改写，且 `modules/performance/`、`modules/workforce/batch_change_*`、`modules/platform/audit_*`、`modules/workforce/labels_*`、`modules/workforce/reporting_*` 处于未跟踪的新文件状态）。**审计结论基于 2026-10-24 10:53 的工作区快照**；受影响的三处证据（`business_router.py` 行号、`extended_service.py` 行号、绩效路由是否挂载）已在成稿前重新复核并更正为当前值，A-29/A-37/A-39/A-63 四个 P0 结论在并发改动后**依然成立**。
- 复核记录：初稿曾把"后端需求追踪注释"判为 0 条，复核时用两条独立命令（文件级 `-Quiet` 扫描 + 全文出现次数统计）推翻该结论，实测 `apps/api/src` 下 90 个 .py 中 17 个带 `Requirement:`、共 137 处，报告 A-09/A-84 及附录 B 已按复核后口径改写。汇总行数与判定分布亦以脚本复核为准（86 行 / 已实现24-部分实现34-未实现18-与PRD冲突4-待企业输入2-待决策4）。