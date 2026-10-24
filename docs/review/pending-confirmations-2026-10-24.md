# coreHR 待用户 / 产品确认清单（2026-10-24）

> 维护人：AI 助手（代核心HR 项目组整理）
> 状态：**待拍板**——本清单内所有条目均未自行决策，需用户逐条给出结论
> 适用范围：本轮 `.pen` 原型落地 + 前端对齐 + 文档审计 + 消息引擎 / BPMS 选型
> 相关文档：[Pencil 原型设计说明](pen-prototype-spec-2026-10-24.md) / [消息引擎选型报告](message-engine-selection-2026-10-24.md) / [Moka 功能差距对照](moka-vs-corehr-feature-gap.md)

---

## 0. 一句话结论

本轮已完成：`.pen` 中文渲染链路诊断（**四条链路全部健康，问题无法复现**）、6 个产品画板 + 12 个可复用组件落盘、前端公共组件层抽取（22 处重复 → 0）、前端按画板对齐 6 个页面。

**未自行拍板、必须由你决策的事项共 25 条**，分 9 组列在下面。每条都给了「当前默认」和「备选」，如果你只回「按默认走」，我就按默认执行。

> 2026-10-24 决策进度更新：其中 **P-13、P-14、P-16、P-19 已决策并落地**，**P-15 已完全决策**（前端按画板开发已授权；画板已于 2026-10-24 由产品决策人签字，Review 状态升为 `PROTOTYPE_APPROVED`）。逐条状态以各表内「【已决策】」标记为准，落地位置见文末「本轮已直接执行」表。

---

## 组 1 · Pencil 画板评审（8 条）

> **2026-10-24 状态：画板 Review 状态已由产品决策人签字，升为 `PROTOTYPE_APPROVED`**（13 张画板；`docs/review/pen-artboard-registry.json` schemaVersion 1.2）。
> 下面 8 条是**画板层的产品决策**，其中涉及「是否再加一张画板 / 再加一个功能」的条目（P-01 / P-02 / P-04 / P-07 / P-08）**仍然开放**——它们决定的是**新增**画板与**新增**功能，不影响已签画板的有效性。已签画板与其实现的有意差异逐条登记在登记表的 `implementationDeltas`。
>
> 画板预览：`docs/review/pen-prototypes/` 13 张 PNG + `.pen` 源文件。

| # | 议题 | 当前默认（画板已画成） | 备选 | 影响面 |
|---|---|---|---|---|
| P-01 | 汇报关系「结束」是否保留二次确认弹窗 | 画板只画了链接，**实现里已有 Popconfirm** | 补一张 Popconfirm 状态画板 | 前端 `ReportingWorkspace.tsx` |
| P-02 | 操作日志是否需要「详情」抽屉看单条完整上下文 | 当前只有表格，**无详情入口** | 新增 Drawer 画板 + 后端详情接口 | 前端 + 后端 API |
| P-03 | 人员中心档案入口用 Drawer 还是新标签页 | 用 **Drawer**（与实现一致） | 改 NEW_TAB（档案含 7 Tab，接近新标签页升级线） | 交互规范 D-068 |
| P-04 | 员工标签是否需要独立「标签库管理」页面 | 当前**只在 Drawer 内消费标签库**，无管理页 | 新增独立画板 + 管理页 | 新增模块 |
| P-05 | 标签「结束」是软失效，是否需要「恢复」入口 | 画板**无恢复入口** | 增加「恢复」操作 | 前端 + 后端软失效恢复接口 |
| P-06 | 指标条是否推广到其他工作区 | **画板只画了职位页**。前端落地时已让「工作台」与「职位管理」共用同一个 `MetricStrip` 组件（D-091 要求同一能力域不得出现第二套写法），工作台外观随之变为「数值在上」 | 若你只认可职位页的样式，则需给工作台单独一套结构（会与 D-091 冲突）→ 见 **P-25** |
| P-07 | 汇报关系「关系图」Tab 的可视化形态 | 只画了 Tab 标签，**没有关系图画板** | 需你给形态（组织树 / 力导向图 / 甘特） | 新增画板 + 前端图形库选型 |
| P-08 | 是否为「批量异动」「绩效 OKR」补画板 | **本轮未画** | 新增两张画板 | 新模块原型 |

**这一组的统一解锁动作（已执行，2026-10-24）**：画板 Review 状态已从 `DRAFT_FOR_REVIEW` 改为 `PROTOTYPE_APPROVED`，并已在功能需求文档 §10.4 登记画板 ID（规范 §10.2 要求）。

---

## 组 2 · BPMS 流程引擎（1 条）

| # | 议题 | 现状与取舍 | 建议 |
|---|---|---|---|
| ~~P-09~~ | **是否允许在 Python 主栈之外引入 Java 运行时** | 调研结论：Python 生态**没有生产可用的 BPMN 引擎**（Camunda/Flowable 是 Java，Camunda 8 走 Zeebe 重集群）。方案 A＝自研轻量引擎（**不引 Java**，但流程能力要自己写）；方案 B＝引 Flowable（**功能完备**，但多一套 JVM 运行时，与现有 Python + React 技术栈异构） | ✅ **已决策（2026-10-24，Miller）：选方案 A**——继续在 Python 栈内自研引擎，不引入 JVM 运行时 |

**P-09 落地位置（2026-10-24 完成）**

- 决策落点：[ADR-0007 流程引擎（BPMS）选型与自研边界](../adr/ADR-0007-bpms-engine-selection.md) 状态已改 **Accepted**。
- 代码落点：`apps/api/src/hris/modules/workflow/`
  - `actions.py`：审批动作枚举与中文标签（唯一来源）
  - `state_machine.py`：实例状态机 / 任务状态机的显式迁移表
  - `transitions.py`：流转历史记录 + 节点停留统计推导
  - `notifier.py`：通知出口抽象（默认空实现，等消息引擎接入）
  - `scheduler.py`：**基于 asyncio 的调度循环**（**不用 APScheduler**，避免重建 API 镜像），独立 Worker 进程运行
- 迁移：`f2i000000001` 建 `workflow_transitions` 表（只追加）+ `workflow_tasks.overdue_reminded_at`
- 与原建议的两处偏差：**① 画布（LogicFlow）本轮不做**，属前端与选型范围，不在 BPMS P0 批次内；**② 调度器不用 APScheduler**，改为零新依赖的 asyncio 循环（镜像里没有该包，加依赖要重建镜像）。
- 门禁：后端 `tests/integration` 151 passed；`alembic check` 在本任务范围零漂移。

---

## 组 3 · 消息引擎（3 条）

完整论证见 [消息引擎选型报告](message-engine-selection-2026-10-24.md)（§9.2 列了 8 条分水岭，这里收敛为 3 个决策）。

| # | 议题 | 建议默认 | 备选 |
|---|---|---|---|
| ~~P-10~~ | **一期通道范围** | **站内信**（一期只做站内信，短信/邮件在报告里已给出接入设计但不做实现） | 一期就做短信 + 邮件（需采购短信通道、配置 SMTP，成本与合规上升） |
| ~~P-11~~ | **队列实现** | **PostgreSQL `SKIP LOCKED` + 独立 Worker 进程**（复用现有 PG 16，零新中间件） | Redis Streams / Celery / RabbitMQ / Kafka（吞吐与可靠性上限更高，但多一套要运维的组件） |
| ~~P-12~~ | **实时推送通道** | **SSE**（`fetch` + `ReadableStream`，不要用 `EventSource`——因为需要带 Authorization 头） | WebSocket（双向，当前通知是单向推送，SSE 够用） |

> 附带一项工程决策已按默认执行：消息引擎定位为**平台内核基础服务**（D-100），不挂在某个业务模块下。

**P-10 / P-11 / P-12 落地位置（2026-10-24 完成）**

- 决策落点：[ADR-0006 消息引擎定位为平台内核基础服务](../adr/ADR-0006-message-engine-platform-service.md) 状态已改 **Accepted**。
- 代码落点：`apps/api/src/hris/modules/messaging/`
  - `categories.py`：消息分类枚举与中文标签（**单一来源**，前端经 `GET /api/v1/messaging/categories` 取用）
  - `models.py`：`messages`（站内信本体）+ `message_deliveries`（投递侧发件箱）
  - `service.py`：`MessageService.publish()` / `publish_many()`，**与业务同事务**写入，幂等键由唯一约束兜底
  - `channels.py`：通道端口；一期实现 `in_app`，`email` / `sms` 注册为「未启用」占位
  - `dispatcher.py`：`FOR UPDATE SKIP LOCKED` 领取 + 指数退避重试 + 超过上限置 `failed`
  - `worker.py`：独立 Worker 进程入口（`python -m hris.modules.messaging.worker`）
  - `stream.py` / `api.py`：SSE 端点 `GET /api/v1/messaging/stream`（只推本人消息）
- 迁移：`f2j000000001` 建 `messages` 与 `message_deliveries` 两张表
- 前端落点：`apps/web/src/business/features/messaging/`——顶栏铃铛 + 未读徽标 + Drawer 消息列表 + 标记已读；SSE 用 `fetch` + `ReadableStream` 消费（**代码中不出现 `EventSource`**）
- 与原建议的两处偏差：**① SSE 默认连接时长 120 秒**（到时服务端主动断开，客户端自动重连），避免长连接长期占用数据库连接；**② 广播选择器（按角色/组织）一期显式拒绝**，接口留了 `recipient_selector` 扩展位并返回明确错误码，不做静默忽略。

---

## 组 4 · 权限落差（2 条）

审计中发现的**真实 403 风险**，需要你选方案：

| # | 议题 | 现状 | 备选 |
|---|---|---|---|
| **P-13** | **【已决策 2026-10-24 · 选 (b) 并已执行】** 审计页「操作人」下拉的数据源 | 前端调 `/api/v1/platform/users`，该接口权限码是 `*`（仅主管理员），但审计页用的是 `DATA_GOVERNANCE_ADMIN` → **治理管理员会 403** | (a) 放宽 `/platform/users` 到 `DATA_GOVERNANCE_VIEW` 及以上；(b) 新建审计专用接口 `/audit/actors`，只返回 `id + 姓名 + 工号`，权限 `DATA_GOVERNANCE_VIEW`——**推荐 (b)，字段更窄、权限面更小**。<br>**决策（已落地）**：新建审计专用只读端点 `GET /api/v1/platform/audit/actors`，只返回 `id` + `display_name` + `username`，按 `display_name` 升序，**不返回**邮箱 / 手机号等 PII，也不返回账号状态与角色；权限放宽为 `DATA_GOVERNANCE_VIEW` **或** `DATA_GOVERNANCE_ADMIN` 任一命中即放行（并集语义，治理管理员与只读治理角色都可用，且不收窄已有角色）。前端 `actors()` 改指新端点，不再调用 `/platform/users`。<br>**落地位置**：`apps/api/src/hris/modules/platform/audit_api.py`、`audit_service.py`、`apps/api/src/hris/modules/platform/dependencies.py`（新增 `require_any_permission`）、`apps/web/src/business/features/platform/audit-api.ts`、`AuditLogWorkspace.test.tsx`、`apps/api/tests/integration/test_audit_logs_api.py`（新增 4 条用例） |
| **P-14** | **【已决策 2026-10-24 · 选 (b) 并已执行】** 汇报关系 GET 的权限要求 | 现在**读写同权**，都要求 `WORKFORCE_ADMIN` → 只读用户 403 | (a) 保持现状；(b) GET 放宽到 `ORGANIZATION_VIEW`，写操作仍要 `WORKFORCE_ADMIN`——**推荐 (b)**，符合「读宽写窄」。<br>**决策（已落地）**：读端点 `GET /api/v1/workforce/reporting-relations` 放宽为 `ORGANIZATION_VIEW` **或** `WORKFORCE_ADMIN` 任一命中即放行；**写端点（新增、结束汇报关系）权限一个字都没放宽，仍为 `WORKFORCE_ADMIN`**。并集语义的理由：`HEADCOUNT_ADMIN` / `SSC_ADMIN` 角色只持有 `WORKFORCE_ADMIN`（迁移 `f2g000000001`），若读端点只认 `ORGANIZATION_VIEW` 会让这两个角色「能新建却不能查看」，反而收窄了已有能力。<br>**落地位置**：`apps/api/src/hris/modules/workforce/reporting_api.py`（新增 `ViewerUser` 依赖，读写分组）、`apps/api/src/hris/modules/platform/dependencies.py`、`apps/api/tests/integration/test_reporting_relations_api.py`（拆分为「只读可读不可写」「编制管理员读写皆可」两条新用例） |

### 4.1 本轮在真实库上查到的事实（2026-10-24 实测，非推测）

`docker exec corehr-db-1 psql` 查 `corehr` 库的实际数据：

```
permissions 表 15 行：CONFIGURATION_ADMIN/VIEW、DATA_GOVERNANCE_ADMIN/VIEW、
ONBOARDING_INITIATE、ORGANIZATION_ADMIN/EVENT_APPLY/VIEW、PERSON_EDIT_BASIC/EXPORT/
IMPORT/SENSITIVE_REVEAL/SENSITIVE_VIEW/VIEW、*

roles 表 2 行：SYSTEM_ADMIN（主管理员）→ 持有 `*`
              SSC_ADMIN（SSC管理员）→ 只持有 ONBOARDING_INITIATE
```

由此查出**两个真实缺陷**（不是产品选择题，是 bug，已派修复）：

1. **3 个权限码从未落库**：`WORKFORCE_ADMIN` / `LIFECYCLE_ADMIN` / `ATTENDANCE_ADMIN` 被源码 `require_permission(...)` 引用了 10 处，但 `permissions` 表里没有对应行。权限解析链是 `UserRole → Role → role_permissions → permissions.code`，**没有行的码永远无法被任何角色持有** ⇒ 这三个能力域（人力编制 / 员工生命周期 / 考勤）目前**只有主管理员能用**。
2. **`PERSON_*` 授权语句空跑**：`f1c000000001_personnel_record_foundation.py:171-190` 有一段 SQL，意图是「把 `PERSON_VIEW` 等 5 个权限授予持有 `WORKFORCE_ADMIN` 的角色」，因为第 1 条的码不存在，子查询返回 0 行 ⇒ **`PERSON_VIEW` / `PERSON_SENSITIVE_VIEW` / `PERSON_EXPORT` / `PERSON_IMPORT` / `PERSON_EDIT_BASIC` 当前授予给了 0 个角色**，人员档案类接口对非主管理员全部 403。

> 修复动作：新迁移补 3 个权限码 + 重放那段 `PERSON_*` 授权意图 + 加一条「源码引用的权限码必须全部存在于 `permissions` 表」的防回归守卫测试。**不改任何权限判定逻辑。**

### 4.2 由缺陷 2 引出的产品决策（**需要你拍板**）

| # | 议题 | 现状 | 需要你定的 |
|---|---|---|---|
| **P-19** | **【已决策 2026-10-24 · 已执行】** **角色目录**：库里目前只有 `SYSTEM_ADMIN`（主管理员）和 `SSC_ADMIN`（SSC管理员）两个角色 | **已修一半**：新迁移 `f2f000000001` 已把 3 个缺失权限码落库（真实库 `permissions` 现为 18 行，`alembic_version = f2f000000001`），并重放了「持有 `WORKFORCE_ADMIN` 的角色自动获得 `PERSON_*`」的授权意图。**但仍没有任何角色持有这 3 个新码** —— 不新建角色或给现有角色授权的话，人力编制 / 员工生命周期 / 考勤三个域依旧只有主管理员能用 | **决策（已落地）**：新建 3 个业务角色 —— `HEADCOUNT_ADMIN`（编制管理员）、`LIFECYCLE_ADMIN`（员工生命周期管理员）、`ATTENDANCE_ADMIN`（考勤管理员）；按 D-062 把 `WORKFORCE_ADMIN` + `PERSON_*` 一并授给已有的 `SSC_ADMIN`。<br>**落地位置**：新迁移 `apps/api/alembic/versions/f2g000000001_seed_business_admin_roles.py`（已临时库验证 upgrade + downgrade）。迁移链占位与 `f2f000000001` 的 seed 修复由主 agent 完成，本轮未改动这两个迁移文件。<br>**遗留**：`HEADCOUNT_ADMIN` / `SSC_ADMIN` 只持有 `WORKFORCE_ADMIN` 而不持有 `ORGANIZATION_VIEW`，因此 P-14 的读权限放宽采用并集语义（见组 4 P-14），避免这两个角色失去汇报关系读取能力。 |

> 另有一条已查实但**不在本轮修**的：`ATTENDANCE_ADMIN` 现在同时管 7 类高风险动作（考勤规则、班次、排班、打卡、假勤、报表、冻结），审计 D（`:185`）要求拆成 7 个独立权限码。这是独立立项，未动。

> 注：P-19 与组 1~3、6 无耦合，可以独立决策。

---

## 组 5 · 流程门禁与文档规范（3 条）

| # | 议题 | 现状 | 需要你确认的 |
|---|---|---|---|
| **P-15** | **【已决策 2026-10-24 · 已执行】** 画板通过后是否即授权前端按画板开发/替换 | 你本轮已指示「让前端根据 pen 文件开发或替换已有的界面」，**已按此推进**；画板亦已于 2026-10-24 由你签字确认 | **已决策并执行**：① 前端按画板开发 / 替换已获授权；② 13 张画板的 Review 状态已从 `DRAFT_FOR_REVIEW` 升为 `PROTOTYPE_APPROVED`（`docs/review/pen-artboard-registry.json` schemaVersion 1.2，`reviewStatus.signedAt = 2026-10-24`）；③ 6 份功能需求文档 §10.4 的状态、Q 记录结论、§19 任务状态（`BLOCKED` → `READY`）与自查第 15 项已同步改写，第 7 份（历史花名册）已补登画板 `Gxgyj`。<br>**落地位置**：`docs/review/pen-artboard-registry.json`、`docs/review/pen-prototype-spec-2026-10-24.md`（§1 / §1.1 / §2 / §8）、`docs/requirements/**`（7 份）、`docs/01-foundation/00-正式文档目录.md` §1.4、`docs/review/open-items-2026-10-24.md` D2 |
| **P-16** | **【已决策 2026-10-24 · 已执行】** `docs/requirements/` 模块功能需求文档 | 审计 D 证实：**该目录不存在**，17 号规范一份都未落地 | **决策（已落地）**：按 17 号规范为本轮 6 个页面建立模块功能需求文档并登记画板 ID。<br>**落地位置**：`docs/requirements/WFC-workforce-core/WFC-position/WFC-POSITION-F001-position-management.md`（职位管理）、`docs/requirements/WFC-workforce-core/WFC-reporting/WFC-REPORTING-F001-reporting-relation-management.md`（汇报关系）、`docs/requirements/PLT-platform/PLT-AUDIT/PLT-AUDIT-F001-audit-log-review.md`（操作日志）、`docs/requirements/WFC-workforce-core/WFC-people/WFC-PEOPLE-F001-person-profile.md`（人员中心 · 员工档案）、`docs/requirements/WFC-workforce-core/WFC-label/WFC-LABEL-F001-person-label-tab.md`（员工档案 Drawer · 员工标签 Tab）、`docs/requirements/WFC-workforce-core/WFC-label/WFC-LABEL-F002-batch-label-create-modal.md`（批量新增标签 Modal）、`docs/requirements/WFC-workforce-core/WFC-roster/WFC-ROSTER-F001-historical-roster.md`（历史花名册 · M1 复刻产出）；<br>前 6 份均按 20 章模板、逐条对照实现文件与行号；**第 7 份（历史花名册）目前只写到「实现口径说明」级别，尚未按 17 号规范补全 20 章**（已登记在 `docs/review/open-items-2026-10-24.md`）。全部已登记进 `docs/01-foundation/00-正式文档目录.md` §1.4 |
| P-17 | `docs/adr/` 未登记 | 已有决策 D-088~D-101 落在 `docs/01-foundation/03-项目决策.md`，但 ADR 目录只有 0001/0002/0004 | **已补登记**：`ADR-0005`（原型先行门禁，Accepted）、`ADR-0006`（消息引擎定位，Proposed）、`ADR-0007`（BPMS 选型，Proposed），`docs/adr/README.md` 索引表已更新并注明 0003 编号空缺不复用。**Proposed 的两份等你拍板后才升级 Accepted** |

---

## 组 6 · 审计 P0 修复排期（1 条）

| # | 议题 | 需要你确认的 |
|---|---|---|
| P-18 | A/B/C/D 四份审计报告共 **20 条 P0** 的修复顺序 | 建议顺序：**① 权限 seed 缺失（3 个权限码从未落库，影响面最大）→ ② 审计操作人 403 与汇报关系 403 → ③ 批量异动 / 绩效 OKR 的接口契约缺口 → ④ 其余业务规则 P0**。每批一次提交、本机全绿后再进下一批。**需要你确认这个顺序，或指定别的优先级** |

### 6.1 画板覆盖范围（需要你确认要不要扩）

你说「**前端的所有页面**可能有问题」——本轮画板只覆盖了 **6 个**页面，而业务工作区实际有 **约 23 个**（`apps/web/src/business/features/` 下：organization 3 个、workforce 5 个、people 1 个、attendance 1 个 + 5 个面板、lifecycle 5 个、governance 1 个、configuration 1 个、platform 2 个）。

**当前没有画板覆盖的页面**：组织树/组织详情/组织版本导入、编制管理（Headcount）、职务体系（JobArchitecture）、人员中心之外的招募（Recruitment）、人事子记录（PersonnelSubrecords）、考勤 5 个面板、生命周期 5 个面板、治理（Governance）、字典（Dictionary）、账号（Account）。

| # | 议题 | 我的建议 |
|---|---|---|
| **P-20** | 剩下的约 17 个页面要不要继续按同规格补画板 | **建议补，但分批**：下一批先补「编制管理 + 组织版本导入 + 人事子记录」这三个**有版本/生效日期语义**的页面（画板最容易出错的地方），再一次补齐纯列表页。纯列表页可以直接套现有 6 张画板的结构模板，边际成本很低。**你也可以说「先把这 6 个做扎实」**，我就不再扩 |

---

## 组 7 · 交付与工程纪律（已生效，仅作复核）

| 项 | 当前状态 |
|---|---|
| push | **不 push**。分支 `main` 已 ahead 7，工作区有大量未提交改动（4 份审计报告 + 公共组件 + 5 个后端模块 + 3 个迁移 + 6 个前端工作区）。等本机全绿或你明确要求才推 |
| 推送身份 | GitHub 账号 `Millerprc`（gh 已确认可用），仓库提交身份已同步 |
| 浏览器登录 | AI **不得代填密码**。UI 端到端验证需要你手动在 `http://127.0.0.1:5173/business.html` 登录 |

---

## 组 8 · 前端按画板落地后暴露的产品决策（5 条）

前端 6 个页面已按画板对齐落地（门禁全绿）。落地过程中撞到 5 处「画板要什么 / 后端给什么 / 现有实现是什么」三方不一致，**需要你定**，否则只能按现状留着。

| # | 议题 | 画板要求 | 后端/实现现状 | 我的建议 |
|---|---|---|---|---|
| **P-21** | 人员中心列表的「主组织 / 职位 / 入职日期」三列 + 「主组织」筛选 | 7 列表格含这三列，筛选含主组织 | `GET /api/v1/workforce/persons` **列表响应不含这三字段**（只在 `GET /persons/{id}` 档案里有），且**没有 organization 过滤参数**。实现按仓库既有空值约定显示「—」，**没有**用 N+1 档案拉取去凑 | **(a) 后端列表接口补字段**（推荐，一致性最好、也是真需求）；(b) 前端删掉这 3 列与主组织筛选，列表只剩「姓名或工号 + 在职状态」 |
| **P-22** | 「在职状态」用哪个字段定义 | 列名「在职状态」，值「在职」 | 后端 `persons.status` 是**通用启停语义**，不是劳动关系状态 | **(a) 改用 `employment.status`（劳动关系状态）定义「在职」**（推荐）；(b) 保留 `persons.status` 并把列名改成「状态」 |
| **P-23** | 操作日志 Tag 的严重度分级 | 画板：操作 Tag 蓝、来源 Tag 橙 | 原实现按动作名分级（delete 红 / create 绿）。按画板统一蓝橙后，**红/绿严重度消失** | (a) 接受统一蓝/橙；(b) 保留分级，在画板里补上分级规则 |
| **P-24** | 汇报关系「生效日期」默认值 | 画板默认 `2026-10-24`（等于只看当前生效关系） | 实现保留原「不限日期」默认值，避免改变查询语义 | (a) 默认今天，跟画板；**(b) 保留「不限日期」**（推荐，避免默认少列数据） |
| **P-25** | 指标条是否全站统一 | 画板只画了职位页 | 工作台与职位管理现已**共用同一个 `MetricStrip`**，工作台外观随之变成「数值在上、标签在下」 | (a) 全站统一（现状，符 D-091）；(b) 工作台保留旧样式 |

> 另有 3 处**有意保留**的画板差异，不需要你决策，列出来备查：① 搜索框用 antd 6 原生 `Input.Search`（渲染为「输入框 + 右侧搜索按钮」），画板是「框内左侧放大镜」——为了不引入 `package.json` 里未声明的 `@ant-design/icons`；② 画板未画「新建职位 / 新建人员」按钮，但删掉会丢写操作能力，故保留；③ 员工标签第二行多了一行「有效期」文本（画板只有「来源 + 有效性」）——既有测试断言了该文案，删掉等于削弱测试。

## 附：你可以直接这样回复

- **「组 1 全部按默认」** → 我把 6 个画板置为 `PROTOTYPE_APPROVED` 并登记进功能需求文档。
- **「P-09 选 A / P-10~P-12 按建议」** → 我直接开工 BPMS 自研引擎 + 消息引擎一期落地。
- **「P-13 选 b，P-14 选 b」** → 我先修这两个 403，再排其余 P0。
- **「P-18 按你建议的顺序」** → 我按 ①→④ 分四批修复，每批本机全绿。
- **「P-19 建三个角色，成员范围先不限」** → 我补「编制管理员 / 人事管理员 / 考勤管理员」三个角色并授权，同时给 SSC_ADMIN 补上它应得的只读权限。

---

## 本轮已直接执行、无需你决策的部分（供你复核）

| 事项 | 动作 | 依据 |
|---|---|---|
| **审计页「操作人」下拉的 403（P-13，方案 b）** | **新建审计专用只读端点 `GET /api/v1/platform/audit/actors`**，只返回 `id` + `display_name` + `username`（按 `display_name` 升序，不返回邮箱 / 手机号等 PII）；权限放宽为 `DATA_GOVERNANCE_VIEW` 或 `DATA_GOVERNANCE_ADMIN` 任一命中即放行。前端 `actors()` 改指新端点，不再调用权限码为 `*` 的 `/api/v1/platform/users`。**不改任何权限判定逻辑的既有语义** | 本文件组 4 P-13；`apps/api/src/hris/modules/platform/audit_api.py`、`audit_service.py`、`dependencies.py`、`apps/web/src/business/features/platform/audit-api.ts`、`AuditLogWorkspace.test.tsx`、`apps/api/tests/integration/test_audit_logs_api.py` |
| **汇报关系读权限的 403（P-14，方案 b）** | 读端点 `GET /api/v1/workforce/reporting-relations` 放宽到 `ORGANIZATION_VIEW`（并集 `WORKFORCE_ADMIN`，只放宽不收窄）；**写端点（新增 / 结束）权限一字未放宽，仍为 `WORKFORCE_ADMIN`** | 本文件组 4 P-14；`apps/api/src/hris/modules/workforce/reporting_api.py`、`apps/api/src/hris/modules/platform/dependencies.py`、`apps/api/tests/integration/test_reporting_relations_api.py` |
| **角色目录（P-19）** | 新建 `HEADCOUNT_ADMIN`（编制管理员）/ `LIFECYCLE_ADMIN`（员工生命周期管理员）/ `ATTENDANCE_ADMIN`（考勤管理员）三个业务角色，并按 D-062 把 `WORKFORCE_ADMIN` + `PERSON_*` 授给已有的 `SSC_ADMIN` | 本文件组 4 §4.2 P-19；`apps/api/alembic/versions/f2g000000001_seed_business_admin_roles.py`（主 agent 落地并验证，本轮未改动） |
| **其余 5 份模块功能需求文档（P-16）** | 按 17 号规范为本轮其余 5 个画板建立功能需求文档（汇报关系 / 操作日志 / 人员中心 · 员工档案 / 员工档案 Drawer · 员工标签 Tab / 批量新增标签 Modal），每份 20 章、逐条对照实现文件与行号、§15 检查表自查后写入 §20；并登记进 `docs/01-foundation/00-正式文档目录.md` §1.4 | 本文件组 5 P-16；`docs/requirements/**` |
| `.pen` 中文渲染 | **不修文件**。实测四条链路（字节 / 字体变量 / 本机字体 / CDN）全部健康，中文实拍渲染正常，定性为「首次打开字体未加载完」的环境时序现象。保持 `$corehr-font = Noto Sans SC` | `pen-prototype-spec-2026-10-24.md` §1.1 的 8 行取证表 |
| 权限码 seed 缺失 + `PERSON_*` 授权空跑 | **新迁移补 3 个权限码 + 重放授权意图 + 加防回归守卫测试**；不改任何权限判定逻辑。真实库已升级到 `f2f000000001`，`permissions` 18 行，`alembic check` 零漂移，后端 **135 passed**（基线 130 + 守卫 5） | 本文件 §4.1 的实测数据 |
| 6 个画板的前端对齐 | **按画板实现**（你已在本轮直接授权）。已落地：指标条 / 扁平筛选栏 / 表格计数行 / 关系类型双态 Tag / 标签两行结构 / Drawer 副标题等。门禁：AntD 守卫 0 违规、`tsc -b` exit 0、前端 **27 文件 / 73 测试全绿**（基线 68 → 73，新增 5 条结构断言，未削弱任何既有断言） | 你的原话「再让前端根据 pen 文件开发或者替换已有的界面」 |
| 第一份模块功能需求文档 | **按 17 号规范建立「职位管理」**（`docs/requirements/WFC-workforce-core/WFC-position/WFC-POSITION-F001-position-management.md`，579 行 / 20 章），登记画板 ID，Review 状态如实写 `DRAFT_FOR_REVIEW`；规范 §15 检查表 13 通过 / 2 部分通过 | 规范 §6 / §10.2 / §15 |
| 模块代码登记 | 规范 §4.1 要求模块代码在「正式目录」登记，但 `00-正式文档目录.md` 此前一个模块代码都没有 → 已补 §1.4「模块功能需求文档」，登记 9 个模块代码 + 已落地功能文档 | 规范 §4.1 |
| AntD 守卫漏掉「整体废弃的组件」 | 守卫原先只查废弃**属性**，antd 6.5.2 里整体废弃的 `List` / `BackTop` 从眼皮底下过去（vitest 里一直在打废弃告警）。→ 守卫新增组件级检查（判定信号取自 antd js 实现的 `Deprecated.displayName` / `devUseWarning`，**不能靠 d.ts 的 `@deprecated`**，因为 antd 故意不在类型里标），并把两处 `List` 用法换成语义化列表。已做**否定对照**：插入 `BackTop` 守卫报红、短路检测函数后内置自检报红 | D-090 |
