# coreHR 消息引擎选型报告（站内信 / 短信 / 邮件）

> 日期：2026-10-24
> 关联决策：D-100「消息引擎（站内信、短信、邮件）作为平台内核级基础服务统一建设，通过稳定端口适配各投递通道，不与任一业务域耦合」（`docs/01-foundation/03-项目决策.md:175`）
> 审查对象：coreHR 当前 `main` 工作区代码（`apps/api`、`apps/web`、`deploy`）
> 审查方式：只读代码 + 定点检索；未运行服务、未执行写操作、未修改任何项目文件
> 结论状态：`PARTIALLY_CONFIRMED` — §1.1 的三条分水岭（**一期通道范围 / 队列实现 / 实时推送通道**）已由产品决策人拍板（待确认清单 P-10 / P-11 / P-12），并已落地实现（ADR-0006 状态 Accepted）；
> §9.2 中的 **Q-A4（收件人范围与免打扰）、Q-A5（未读提醒重复策略）、Q-A6（消息保留期限与归档）、Q-A8（模板与文案所有权）** 仍待拍板，
> 已随本轮落地情况登记到[待确认清单](pending-confirmations-2026-10-24.md)与[待办清单](open-items-2026-10-24.md)。
> 本文性质：选型调研与落地方案。**§1.1 三条分水岭已实现；其余部分不代表已完成相应改造。**

---

## 1. 决策摘要

### 1.1 三个答案

| 议题 | 推荐 | 一句话理由 |
|---|---|---|
| 一期通道 | **站内信（In-App）优先**；邮件作为一期后半段补充；短信延后到二期独立立项 | 站内信零外部依赖、投递结果可 100% 站内观测、无第三方资质约束；短信涉及签名资质、实名制与持续计费，合规与成本责任远高于另外两条通道 |
| 队列方案 | **PostgreSQL 做队列（`FOR UPDATE SKIP LOCKED`）+ 独立 Worker 进程**；不引入 RabbitMQ / Kafka | 复用已在运行的 PostgreSQL 16（`deploy/compose.yaml:4-20`）与已有的 Outbox 表（`apps/api/src/hris/modules/platform/governance_models.py:11-24`），零新增中间件即满足 D-064「第一至第四阶段不引入大型集成中间件」（`docs/01-foundation/03-项目决策.md:132`） |
| 实时推送 | **SSE（Server-Sent Events）**，以 `fetch` + `ReadableStream` 承载，**不使用 `EventSource`** | 服务端→浏览器单向推送已足够；浏览器原生自带自动重连；但 `EventSource` 无法设置自定义请求头，无法携带现有的 `Authorization: Bearer` 令牌（`apps/web/src/business/client.ts:61`），改用 fetch 流可完整复用现有鉴权链路 |

### 1.2 三条需要产品拍板的分水岭

1. **一期是否包含邮件通道？** 站内信与邮件在模板渲染、附件、退信/硬退信处理上差异极大；若一期只做站内信，通道抽象仍需预留邮件端口，但不实现任何供应商对接。
2. **通知是「必达型」还是「尽力型」？** 必达型事件（审批待办、合同到期）需要重试 + 降级 + 兜底；尽力型事件（绩效评分卡发布）只需一次投递。这直接决定重试策略、是否强制多通道降级、以及未读数能否容忍最终一致。
3. **短信是否进入一期？** 涉及企业短信签名资质、号码实名制、员工号码覆盖率（`person_contacts` 已有加密手机号，但仓库内无覆盖率统计）以及持续计费；一旦上量，成本与合规责任显著高于站内信与邮件。

### 1.3 一句话结论

> coreHR 目前**没有消息引擎**：只有一张只写不投的 Outbox 表，没有任何通知模型、通道、调度器或推送通道；建议一期以「**站内信 + PostgreSQL 队列 + SSE**」为最小闭环落地，邮件二期接入、短信三期独立立项，D-100 的三条分水岭待产品决策人拍板。

---

## 2. 现状盘点

> 判定口径：`存在` = 检索到实现并可定位到行；`不存在` = 在指定范围内按 §10 的检索词全量检索后零命中。全部「不存在」结论的检索范围与检索词见 §10，可复现。

### 2.1 能力清单

| 能力 | 判定 | 证据（文件:行） | 说明 |
|---|---|---|---|
| Outbox 表结构 | **存在** | `apps/api/src/hris/modules/platform/governance_models.py:11-24`；迁移 `apps/api/alembic/versions/f1a000000001_phase_1a_organization_domain.py:251` | `outbox_events` 含 `event_type`(:14)、`aggregate_type`(:15)、`aggregate_id`(:16)、`payload`(:17)、`occurred_at`(:18-22)、`published_at`(:23)、`attempt_count`(:24) |
| Outbox 写入侧 | **存在** | `apps/api/src/hris/modules/workforce/organization_service.py:2232-2249`（`_outbox` 辅助方法，13 处调用：`:122`、`:170`、`:261`、`:394`、`:463`、`:763`、`:872`、`:997`、`:1106`、`:1243`、`:1394`、`:1575`、`:1902`）；`apps/api/src/hris/modules/platform/import_service.py:2875-2882` | 全部事件类型均为组织域事件（`organization.*`），无任何通知语义事件类型 |
| Outbox 投递器 / 消费者 | **不存在** | 全仓 `apps/api` 检索 `published_at` 仅 2 处命中：模型定义 `governance_models.py:23`、迁移 `f1a000000001_phase_1a_organization_domain.py:251`。两者**均未被赋值或读取**；`attempt_count` 定义于 `governance_models.py:24`，写入时恒为 0（`organization_service.py:2246`、`import_service.py:2881`） | 结论：Outbox **只写不读**，没有投递器、没有消费者、没有重试记录。已有复审已记录同一事实（`docs/review/moka-vs-corehr-feature-gap.md:396`、`docs/review/platform-kernel-architecture-fit-review-2026-08-18.md:53`） |
| 站内信 / 通知数据模型 | **不存在** | `apps/api/src` 检索 `\bnotify\b\|\bnotification\b\|websocket\|EventSource\|\bsms\b\|\bsmtp\b\|\bemail\b\|MessageBus\|producer\|consumer` → 仅 4 处命中，全部为人员联系信息的归一化/脱敏：`apps/api/src/hris/modules/workforce/personnel_service.py:276-277`、`:671-672`（`normalize_email`/`mask_email`），与投递无关 | 无 `messages`/`notifications`/`deliveries` 表，无投递记录实体 |
| 通道抽象（Port） | **不存在** | 上述同一检索零命中；`apps/api/src/hris/modules/` 下仅 `platform`/`workforce`/`workflow`/`attendance`/`performance`/`system` 六个业务模块，无 messaging 模块 | PRD 要求的「消息通知端口」未落地 |
| 前端消息组件 | **不存在** | `apps/web/src` 检索 `websocket\|EventSource\|notification\|setInterval\|poll` → **零命中**；顶栏结构 `apps/web/src/business/AppShell.tsx:298-321`（`Header` 内仅面包屑、用户摘要、退出按钮） | 无铃铛、无未读数、无消息列表页 |
| 调度器 / 后台任务框架 | **不存在** | `apps/api` 检索 `celery\|scheduler\|apscheduler\|cron\|backgroundtask\|arq\|rq\b\|kombu` → 仅命中 `redis` 依赖声明（`apps/api/requirements.in:8`、`apps/api/pyproject.toml:18`）与健康探测（`apps/api/src/hris/modules/system/api.py:31-36`、连接串 `apps/api/src/hris/core/config.py:21`），无任何调度器/队列客户端 | Redis 目前**仅用于 `/health/ready` 的 `ping()`**，不承担任务协调 |
| 到期类任务的现有替代 | **手工 HTTP 触发** | `apps/api/src/hris/modules/workforce/organization_api.py:212-225`（`POST /api/v1/organization-events/apply-due`）；`apps/api/src/hris/modules/workflow/extended_api.py:332-333`（合同状态）；`:544-545`（人事事件到期） | 到期生效、合同到期提醒等「本该定时跑」的动作，全靠人工或前端点按钮触发，没有常驻 Worker |
| 队列中间件依赖 | **不存在** | `apps/api/requirements.in:1-12`、`apps/api/pyproject.toml:10-21` 均无 celery/kombu/pika/kafka 客户端 | 现依赖仅 12 项：alembic、cryptography、fastapi、httpx、psycopg、pydantic、pydantic-settings、redis、SQLAlchemy、uvicorn、pytest、pytest-asyncio |
| 部署拓扑中的 Worker / Broker | **不存在** | `deploy/compose.yaml:4-33`（`postgres:16.14-alpine`、`redis:7.4.10-alpine`）、`:35-71`（`api`）、`:73-88`（`web`） | compose 只有 4 个服务，无 worker、无 broker；新增 Worker 需在此文件追加服务 |
| 幂等键机制（可复用） | **存在** | `apps/api/src/hris/core/concurrency.py:6-11`（`VersionCommand.idempotency_key: UUID`） | 消息去重可直接复用同款「幂等键 + 唯一约束」范式 |
| 收件人解析依据（部分） | **部分存在** | 审批任务：`apps/api/src/hris/modules/workflow/models.py:88`（`assignee_type`）、`:89`（`assignee_ref`）；人员联系方式：`apps/api/src/hris/modules/workforce/models.py:425-453`（`person_contacts`，`contact_type:447`、`contact_value_ciphertext:453` 加密存储） | `assignee_ref` 可定位到审批人；手机号/邮箱**有数据但无覆盖率、无免打扰策略、无投递地址解析服务** |
| 审计 / 追踪可参考实现 | **存在** | `apps/api/src/hris/modules/platform/audit_service.py:144`（`AuditLogService`）、`:156`、`:180`、`:195`、`:215`、`:289`、`:312` | 消息投递追踪的表结构与查询范式可直接照抄，不必另立风格 |
| 流水号服务（可复用） | **存在** | `apps/api/src/hris/modules/platform/models.py:96-103`（`NumberSequence`） | 消息单号可复用现有编号机制 |

### 2.2 与 PRD / 决策的差距

| 条款（文件:行） | 要求摘要 | 判定 | 证据 |
|---|---|---|---|
| `docs/01-foundation/03-项目决策.md:175`（D-100） | 消息引擎作为平台内核级基础服务统一建设，通过稳定端口适配各投递通道 | **未实现** | §2.1 全部「不存在」行；已有复审判定一致（`docs/review/D-考勤-待确认-决策-文档规范.md:315`，标注 P0） |
| `docs/01-foundation/16-coreHR产品总体PRD.md:123` | Kernel 承载：文件、对象存储、**消息通知**、密钥和外部集成端口 | **未实现** | 无端口定义、无适配器 |
| `docs/01-foundation/16-coreHR产品总体PRD.md:104` | 架构图中 Kernel 与基础设施适配层之间存在「消息端口」/「消息服务」 | **未实现** | `docs/01-foundation/16-coreHR产品总体PRD.md:107` 将「消息服务」列为基础设施适配层目标 |
| `docs/01-foundation/16-coreHR产品总体PRD.md:121` | Kernel 承载：幂等、后台任务、调度、Outbox 和可重试执行框架 | **部分实现** | 幂等 ✓（`core/concurrency.py:6-11`）；Outbox 写入 ✓；**后台任务 ✗、调度 ✗、可重试执行框架 ✗、Outbox 投递 ✗** |
| `docs/01-foundation/16-coreHR产品总体PRD.md:255` | Outbox 确保业务提交和后续事件发布之间可追溯 | **未实现** | 无投递侧即无可追溯链路 |
| `docs/01-foundation/16-coreHR产品总体PRD.md:274` | 通知适配器：站内、邮件、企业微信、短信、自建OA | **未实现** | 三类通道全部为零 |
| `docs/01-foundation/16-coreHR产品总体PRD.md:275` | 任务：本机任务进程**或经验证的外部任务队列** | **未实现** | 无本机任务进程，亦无外部队列；PRD 此处已允许「本机任务进程」，与 §4 的推荐方向一致 |
| `docs/01-foundation/16-coreHR产品总体PRD.md:39` | 目标5：让身份、文件、**消息**、任务、监控和外部连接等基础设施可以通过受控适配器替换 | **未实现** | 无可替换面 |
| `docs/01-foundation/16-coreHR产品总体PRD.md:280` | Apusic、独立API网关、消息总线和ESB等企业级中间件在第五阶段按国产化、集成规模和部署要求评估，**不得成为便携版和标准版的强制依赖** | 约束条款 | 直接约束 §4 的队列选型：引入 RabbitMQ/Kafka 会在第二至第四阶段即违反此条 |
| `docs/01-foundation/03-项目决策.md:132`（D-064） | 第一至第四阶段不引入 Apusic 等企业级应用服务器或大型集成中间件 | 约束条款 | 同上 |
| `docs/01-foundation/03-项目决策.md:138`（T-005） | Redis 只用于明确的缓存、限流或任务协调场景 | 约束条款 | 允许 Redis 用于「任务协调」，但不构成引入 Redis 作为主队列的充分理由（见 §4.3） |

### 2.3 现状小结

coreHR 已经具备消息引擎的**两个零件**：一张事务性 Outbox 表（`governance_models.py:11-24`）和一套审计追踪范式（`audit_service.py:144`）；但**投递器、通道抽象、调度器、Worker 进程、前端承载五项全部为零**。这不是「优化」问题而是「从零建设」问题，必须作为独立立项按 P0 → P1 → P2 分期交付（见 §8）。

---

## 3. 三条通道对比

### 3.1 汇总对比

| 维度 | 站内信（In-App） | 短信（SMS） | 邮件（Email） |
|---|---|---|---|
| **送达保证** | 强。消息落库即视为送达成功，可查 `deliveries` 表逐条核对；失败仅限用户不存在/已停用等业务前置校验 | 中。依赖运营商回执与供应商状态回查；回执本身可能丢失，只能做到「最终可能送达」 | 中。依赖 SMTP/供应商投递结果与回执；退信链路长且存在硬退信/软退信区分 |
| **延迟** | 亚秒级（同库读取 + SSE 推送） | 秒级至分钟级（受供应商排队与运营商网关影响） | 秒级至分钟级（同上），大附件会显著拉长 |
| **成本** | 接近零。只有存储与带宽成本 | **按条计费，且是唯一有硬性现金支出的通道**；单价随国家/地区与签名资质差异极大 | 极低（企业邮件 SaaS 通常按席位订阅而非按封），但需外网出口 |
| **失败可观测性** | **最好**。投递明细与用户已读状态同库存储，失败原因可枚举、可重放、可对账 | 差。失败原因来自供应商文案，跨供应商不统一；本系统只能记录供应商返回码 | 中。有供应商返回码，但硬退信/软退信/投诉需分别建模 |
| **合规风险** | **最低**。数据不出系统，不受外部传输合规约束；但仍属员工个人信息，适用内部权限与审计要求 | **最高**。涉及号码实名制、企业短信签名资质（未经签名可能被运营商拦截）、营销短信与通知短信的区分监管、员工是否同意接收 | 中高。涉及外部传输、员工个人邮箱合规（可用企业邮箱规避）、退信与投诉带来的发信域名信誉风险 |
| **适用场景** | 审批待办、流程流转提醒、系统公告、数据变更通知、未读数驱动的工作台 | 高时效且不可遗漏的关键事件（账号异常、批量异动生效确认、合同临期兜底）；**不建议做常规通道** | 需要承载长文本、表格、附件、正式文书的场景（合同到期通知、绩效评分卡、批量导出结果） |

### 3.2 选型判断

- **站内信**是唯一同时满足「零外部依赖 + 送达可观测 + 合规风险最低 + 成本为零」的通道，应作为**唯一一期必做通道**。它是消息引擎的载体本身，没有它，抽象层无从验证。
- **邮件**的技术门槛主要不在「能不能发」，而在**渲染与退信治理**（模板版本、长文本截断、附件、硬退信抑制）。建议作为一期后半段接入，复用同一套投递/重试/追踪骨架。
- **短信**是三通道中唯一需要**外部资质与持续预算**的通道，且失败可观测性最差。把它放在一期，等于让整个消息引擎的验收标准绑定在一条最不可控的链路上。建议延后到二期，并作为独立立项（需同步启动短信签名与资质申请，周期不可控）。

### 3.3 三通道与 D-100 的关系

D-100（`docs/01-foundation/03-项目决策.md:175`）要求「通过稳定端口适配各投递通道」。因此：

- 一期只实现 `IN_APP` 一个通道**不违反** D-100 —— D-100 约束的是「内核统一建设 + 端口适配」的结构，不是「一期必须同时上线三条通道」。
- 但一期**必须**同时交付：端口定义、通道注册表、以及为 `SMS`/`EMAIL` 预留的空实现（明确返回「通道未启用」而非「不存在」），否则 D-097 之类的「不得共用同一操作入口」式要求会在下一轮重构时被破坏。

---

## 4. 队列方案对比

### 4.1 汇总对比

| 维度 | PostgreSQL 队列（`SKIP LOCKED`） | Redis Streams / Celery | RabbitMQ | Kafka |
|---|---|---|---|---|
| **可靠性** | **高**。消息与业务数据同库同事务，天然不丢；`FOR UPDATE SKIP LOCKED` 保证并发 worker 不重复消费；崩溃后未 ack 的行自动回到可领取状态 | 中高。Streams 有持久化（`appendfsync everysec`），但 Redis 配置为 `--save "" --appendonly no`（`deploy/compose.yaml:24`）时**重启即丢全部 Streams**；Celery 的 ack 语义需额外配置 | 高。成熟的 ack/nack/persist 语义，交换机与队列持久化成熟 | 最高。日志复制模型，副本间不丢已确认消息；但运维复杂度也最高 |
| **运维复杂度** | **最低**。无新增进程、无新增中间件；复用已有的 Postgres 备份、监控与迁移流程 | 中。需新增 Worker 进程；Celery 需 broker + result backend + beat 三件套；Redis 持久化策略必须显式配置 | 中高。需新增 broker 进程、镜像、卷、健康检查、升级与容量规划 | **最高**。需新增集群（KRaft 或 ZooKeeper）、分区规划、再均衡策略、分层存储与多运维能力 |
| **与本项目现有依赖的契合度** | **最高**。PostgreSQL 16 已在运行（`deploy/compose.yaml:4-20`）、连接池与事务管理已在 `apps/api/src/hris/core/database.py` 成型、`psycopg[binary]==3.2.3` 已锁定（`apps/api/requirements.in:5`）；Outbox 表已存在（`governance_models.py:11-24`） | 中。`redis==5.2.1` 已锁定（`apps/api/requirements.in:8`）但**仅用于健康探测**（`system/api.py:31-36`）；需引入 celery/kombu 依赖，且 Redis 当前无持久化配置 | 低。需引入 pika/amqp 依赖 + 新中间件 + 新镜像 + 新卷 | 最低。需引入 kafka-python/confluent-kafka + 完整集群 |
| **横向扩展能力** | 中。靠加 worker 进程横向扩展，受单表行锁与 Postgres 连接数限制；`SKIP LOCKED` 下多 worker 可真并行，但吞吐上限低于专用 broker | 中高。Celery worker 横向扩展容易，受 Redis 单线程模型与网络往返影响 | 高。原生多消费者、优先级、延迟队列、死信队列 | **最高**。分区级并行、消费位点独立提交、适合百万级积压与多业务域共享 |
| **运维契合度（额外维度）** | 与 `docs/01-foundation/03-项目决策.md:132`（D-064）、`docs/01-foundation/16-coreHR产品总体PRD.md:280` 完全不冲突：零新增强制中间件 | 需新增依赖但不违反 D-064 | **直接违反** D-064「第一至第四阶段不引入大型集成中间件」 | **直接违反** D-064 与 PRD `:280` |
| **本项目量级匹配** | 第一阶段（系统管理员 + SSC，`docs/01-foundation/03-项目决策.md:15` D-004）至第三阶段量级绰绰有余 | 够用 | 过剩 | 严重过剩 |

### 4.2 各方案在本项目的具体风险

- **PostgreSQL 队列**：`SKIP LOCKED` 在高并发下会争用行锁，且长事务会阻塞 vacuum；需要配套「短事务 + 独立连接 + 指数退避 + 领取批次上限」。这是可工程化控制的常规成本，不是阻塞性风险。
- **Redis Streams / Celery**：`deploy/compose.yaml:24` 当前为 `redis-server --save "" --appendonly no`，**明确关闭持久化**。若消息存 Redis，容器重启即全丢；要么改持久化策略（增加磁盘 IO 与恢复时间），要么 Redis 只做唤醒信号、消息仍存 Postgres —— 后者说明它在本项目里只是「优化项」而非「必需项」。
- **RabbitMQ**：单看技术能力是四项中最贴合「延迟队列 + 死信 + 优先级 + 多消费者」的方案。但它的引入成本与 D-064 直接冲突，且当前没有需要优先级队列/延迟队列的业务证据。
- **Kafka**：Kafka 的核心价值是「多业务域共享的高吞吐日志流」。coreHR 当前是模块化单体（T-001，`docs/01-foundation/03-项目决策.md:134`）、单一业务域、第一批用户仅管理员与 SSC，引入 Kafka 是纯粹的成本与运维负债。

### 4.3 推荐

> **推荐：PostgreSQL 做队列（`FOR UPDATE SKIP LOCKED`）+ 独立 Worker 进程，与现有 Outbox 表合并演进为统一的任务表。**

理由，按权重排序：

1. **零新增中间件即可完成闭环**：Outbox 表已存在且含 `published_at` 与 `attempt_count` 两个为投递而设的字段（`governance_models.py:23-24`）——它们从未被使用，恰好说明**表结构已按「队列」方向预留**。把 Outbox 升级为任务表，等于用已有的骨架补上投递器，而不是另起一套。
2. **不违反已生效的约束条款**：D-064（`docs/01-foundation/03-项目决策.md:132`）与 PRD `:280` 在第二至第四阶段禁止引入大型集成中间件。RabbitMQ/Kafka 的唯一优势（吞吐与消费模型）在本项目量级下完全用不上。
3. **事务一致性天然成立**：业务提交与消息落库在同一事务内（现有 `_outbox` 写法已是此模式，`organization_service.py:2232-2249`），不会出现「业务成功但消息丢了」的经典分布式问题。这正是 PRD `:255` 要求的「业务提交和后续事件发布之间可追溯」。
4. **运维心智一致**：备份、迁移、监控、权限全部复用现有 Postgres 体系，`deploy/compose.yaml` 只需新增一个 `worker` 服务而非一整套新中间件。

**明确的升级触发条件**（写死，避免将来反复讨论）：当出现下列任一情形时，重新评估 RabbitMQ：
- 单队列持续积压 > 10 万条且 Worker 消费延迟 > 5 分钟；
- 引入需要优先级队列、延迟投递、死信队列的业务需求；
- Postgres 复制延迟开始影响业务查询的尾延迟。

在触发条件出现前，**不得**为「以后可能需要」而引入消息中间件。

### 4.4 与现有 Outbox 的演进关系

建议不新建第二张队列表，而是**就地扩展 `outbox_events`**：

| 现有字段 | 演进用途 |
|---|---|
| `event_type`（`governance_models.py:14`） | 同时作为消息类型与投递类型；通知类事件沿用 `notification.*` 命名空间 |
| `payload`（`:17`） | 承载消息模板键、变量与收件人引用；**不承载渲染后的正文**（正文由模板在投递时渲染，便于模板热更新） |
| `occurred_at`（`:18-22`） | 业务事件发生时间，同时作为「必达型」消息的 SLA 计时起点 |
| `published_at`（`:23`） | 语义**扩展**为「投递完成时间」；需在 P0 明确该字段的新语义并补一条迁移注释，避免与既有「已发布」语义冲突 |
| `attempt_count`（`:24`） | 重试计数，配合 `next_retry_at`（新增）与 `last_error`（新增）实现指数退避 |

---

## 5. 实时推送方案对比

### 5.1 汇总对比

| 维度 | SSE（Server-Sent Events） | WebSocket | 轮询 |
|---|---|---|---|
| **连接模型** | 单向（服务端→客户端）。客户端只能通过普通 HTTP 请求上行 | 全双工，长连接内可双向发消息 | 无长连接。客户端按固定间隔发普通 HTTP 请求 |
| **鉴权** | **有坑**：`EventSource` API **不支持自定义请求头**（`apps/web/src/business/client.ts:61` 依赖 `Authorization: Bearer`），只能靠 query string 或 Cookie 传令牌；而用 `fetch` + `ReadableStream` 读取 SSE 流则**可以完整复用现有 Bearer 鉴权** | 支持请求头，也支持 URL query 或 Cookie；可在握手阶段完成鉴权 | 最简单：完全复用现有 `apiRequest`（`apps/web/src/business/client.ts:53-68`）的 Bearer 鉴权 |
| **断线重连** | **浏览器原生支持**：断线后自动重连并带 `Last-Event-ID` 头，服务端可据此续传 | 需**自行实现**重连 + 退避 + 心跳 + 消息补齐 | 无需重连概念（每次请求独立），但「已读状态同步」要靠下一轮轮询 |
| **多标签页一致性** | 需**自行实现**：服务端扇出到该用户的所有连接；未读数在多标签页间同步可用浏览器原生 `BroadcastChannel` | 同 SSE，且同样需自行实现 | 需自行实现，且多标签页会各自轮询，服务端压力按标签页数线性放大 |
| **浏览器兼容性** | 现代浏览器全部支持（Chrome/Edge/Firefox/Safari）。IE 不支持，但本项目为 Ant Design 6 管理端，无 IE 需求 | 现代浏览器全部支持，同样不支持 IE | 兼容性最好（纯 HTTP） |
| **实现复杂度** | **低**。服务端用 FastAPI `StreamingResponse` + `text/event-stream`；前端用 `fetch` 读流 + `AbortController` 取消；反向代理需关闭缓冲（`X-Accel-Buffering: no`） | **中**。需额外的连接注册表、心跳、消息路由；FastAPI 需 `websockets` 依赖（当前 `apps/api/requirements.in:1-12` 无此依赖） | **最低**，但延迟 = 轮询间隔，资源浪费最大 |
| **适合本项目** | **是**。消息是典型的服务端单向推送 | 否。本项目当前无「服务端主动发起双向会话」的需求 | 仅作为 SSE 不可用时的**降级兜底** |

### 5.2 推荐

> **推荐：SSE，以 `fetch` + `ReadableStream` 实现（不使用 `EventSource`），并保留轮询作为降级兜底。**

理由：

1. **方向匹配**：消息引擎的推送是「服务端在业务事件发生后主动推给指定用户」，天然单向。WebSocket 的双向能力（在线状态、协同编辑、实时对话）在本项目没有对应的业务需求。
2. **鉴权可完整复用**：`apps/web/src/business/client.ts:53-68` 已建立 `Authorization: Bearer ${token}` 的统一 fetch 模式。若用 `EventSource` 必须把令牌塞进 query string，这会与现有 `apps/api/src/hris/modules/platform/security.py:47-48` 的令牌摘要存储方式不匹配（query string 会进入网关与访问日志）。用 `fetch` 读流则完全无此问题。
3. **重连语义免费**：`Last-Event-ID` 机制让「断线期间的消息不丢」成为浏览器内建能力，无需自己写补齐协议。
4. **降级路径清晰**：SSE 不可用（代理不支持、浏览器限制）时退回低频轮询（如 60 秒一次拉未读数），用户仍能看到通知，只是实时性下降。这也让「断线重连」的风险等级从「阻塞」降为「降级」。

### 5.3 实施注意

- **服务端扇出**：需要维护「用户 → 活跃连接」的注册表。由于本项目已有 Redis（`apps/api/src/hris/core/config.py:21`），可用 Redis Pub/Sub 做多实例间的扇出；单实例部署下可先用进程内注册表 + Postgres `LISTEN/NOTIFY`，Redis 仅在多实例时启用（对应 T-005 允许的「任务协调」场景，`docs/01-foundation/03-项目决策.md:138`）。
- **反向代理缓冲**：生产部署若引入 Nginx，需设置 `X-Accel-Buffering: no` 并关闭 `proxy_buffering`，否则事件会被缓冲、延迟到达。当前 `deploy/compose.yaml` 无反向代理，此项在 P2 引入生产部署时纳入。
- **鉴权过期处理**：SSE 连接的令牌在建立时校验，长连接期间令牌可能过期；需在服务端周期性校验会话有效性（`user_sessions.expires_at` 字段见 `apps/api/src/hris/modules/platform/models.py:87`），过期即主动关闭连接。

---

## 6. 通道抽象设计建议

### 6.1 分层结构

```text
业务域（workflow / workforce / performance / attendance）
    │  只依赖 MessageEngine，不依赖任何具体通道
    ▼
MessageEngine（内核服务）
    │  模板渲染 → 收件人解析 → 通道选择 → 重试 → 追踪 → 去重
    ▼
Channel Port（稳定接口）
    ├─ InAppChannel      （一期）
    ├─ EmailChannel      （一期后半段）
    └─ SmsChannel        （二期，占位实现）
```

关键约束：**业务域只能调用 `MessageEngine.publish()`，不得直接调用任何 `Channel`**。否则端口抽象会在第一个业务需求落地时被绕过（这正是 D-100「不与任一业务域耦合」要防的事）。

### 6.2 `Channel` 端口接口轮廓

```python
# 方法签名级别，非完整实现

class Channel(Protocol):
    code: str                      # 稳定编码：IN_APP / EMAIL / SMS

    def capabilities(self) -> frozenset[ChannelCapability]:
        """通道支持的能力集合：附件、批量、富文本、已读回执、号码/地址校验…"""

    async def validate(self, intent: MessageIntent) -> list[ValidationIssue]:
        """投递前校验：收件人地址是否存在、是否免打扰、模板变量是否齐全。
        校验不通过时不进入重试队列，直接判为不可投递（permanent failure）。"""

    async def prepare(self, intent: MessageIntent) -> PreparedMessage:
        """渲染模板、解析收件地址、生成通道侧幂等键。
        渲染失败属于 permanent failure（不重试），地址缺失亦然。"""

    async def deliver(self, prepared: PreparedMessage) -> DeliveryResult:
        """执行投递，返回三态结果：
        DeliveryResult(status=SENT)            已受理
        DeliveryResult(status=RETRYABLE)       可重试（超时、5xx、限流）
        DeliveryResult(status=PERMANENT)       不可重试（硬退信、号码黑名单、模板不存在）
        三态语义是重试策略与失败可观测性的分界线，必须由端口统一约定。"""

    async def health(self) -> ChannelHealth:
        """通道自身可用性（供应商连通性、配额、熔断状态）。
        与业务投递失败区分开：通道熔断时整体暂停投递而非逐条失败。"""
```

### 6.3 `MessageEngine` 接口轮廓

```python
class MessageEngine(Protocol):
    async def publish(self, request: MessageRequest) -> MessageEnvelope:
        """唯一的业务入口。同事务内写入任务表（复用 outbox_events），
        返回 envelope（含消息 ID、状态、去重键），业务域不等待实际投递。
        传入 idempotency_key 以支持去重（沿用 core/concurrency.py:6-11 的范式）。"""

    async def dispatch_once(self, limit: int) -> DispatchReport:
        """Worker 单轮领取与投递：SELECT ... FOR UPDATE SKIP LOCKED LIMIT n，
        逐条调用 Channel.deliver，按结果回写状态与 attempt_count / next_retry_at。"""

    async def redrive(self, envelope_id: UUID) -> MessageEnvelope:
        """人工补偿重投（PRD docs/01-foundation/16-coreHR产品总体PRD.md:321
        要求的『下游失败不回滚业务事实，通过 Outbox、重试和人工补偿闭环处理』）。"""
```

### 6.4 三通道如何共用同一套逻辑

| 共用能力 | 落点 | 说明 |
|---|---|---|
| **发送** | `MessageEngine.publish` + `Channel.prepare/deliver` | 业务域只发一次意图；渲染与投递在通道内完成 |
| **重试** | `MessageEngine.dispatch_once` 统一实现 | 退避策略与最大次数由引擎统一，通道只负责返回 `RETRYABLE`/`PERMANENT`；不同通道可配不同上限（如短信 3 次、邮件 5 次），但**策略代码只有一份** |
| **追踪** | 统一 `message_deliveries` 明细表 | 每条消息 × 每个通道 × 每次尝试一行，记录 `status`/`attempt_count`/`last_error`/`provider_message_id`；查询与导出范式照抄 `apps/api/src/hris/modules/platform/audit_service.py:144-286` |
| **去重** | 唯一约束落在任务表 | 去重键 = `业务事件ID + 通道 + 收件人 + 模板键`；由数据库唯一约束兜底，不靠应用层检查（与现有 `idempotency_key` 做法一致，`apps/api/src/hris/core/concurrency.py:10`） |
| **模板** | 模板表 + 渲染器，通道无关 | 模板内容与通道解耦；同一模板可按通道渲染出不同篇幅（站内信全文、邮件全文、短信摘要），这是三通道共用逻辑的最大收益点 |
| **收件人解析** | 统一解析服务 | 按 `assignee_ref`（`apps/api/src/hris/modules/workflow/models.py:89`）或 `person_id` 解析出各通道地址；地址来源为 `person_contacts`（`apps/api/src/hris/modules/workforce/models.py:425-453`，加密存储，读取需走 `core/personnel_security.py` 的解密路径） |
| **免打扰/订阅** | 统一策略层，通道无关 | 属产品规则，落入 §9.2 开放问题 Q-A3；策略层先留接口，规则由产品拍板后填充 |

---

## 7. 与现有代码的集成点

> 下表每一行的「文件:行」均为实际检索到的位置；建议动作中的文件名是**新增建议**，尚未创建。

### 7.1 内核侧

| # | 集成点 | 位置（文件:行） | 触发时机 | 收件人依据 | 建议动作 |
|---|---|---|---|---|---|
| K1 | Outbox 写入侧（已有） | `apps/api/src/hris/modules/workforce/organization_service.py:2232-2249`；`apps/api/src/hris/modules/platform/import_service.py:2875-2882` | 业务事务内 | — | 保留现状；新增 `notification.*` 事件类型复用同一写入路径 |
| K2 | Outbox 投递器（缺失） | 新增 `apps/api/src/hris/modules/messaging/dispatcher.py` | Worker 常驻循环 | — | 领取 `published_at IS NULL` 的行 → `SKIP LOCKED` → 调 `Channel.deliver` → 回写 `published_at`/`attempt_count`/`last_error`/`next_retry_at` |
| K3 | Worker 进程（缺失） | 新增 `apps/api/src/hris/worker.py`；`deploy/compose.yaml` 追加 `worker` 服务（参照 `:35-71` 的 `api` 服务写法） | 进程启动 | — | 与 API 镜像同源，命令 `python -m hris.worker`；不引入新中间件 |
| K4 | 通道注册表（缺失） | 新增 `apps/api/src/hris/modules/messaging/channels/` | 启动装配 | — | `IN_APP` 真实实现；`EMAIL`/`SMS` 先注册为「未启用」占位，返回 `PERMANENT` 而非抛异常 |
| K5 | 幂等去重（可复用） | `apps/api/src/hris/core/concurrency.py:6-11` | 每次 `publish` | — | 复用 `idempotency_key` 范式，DB 唯一约束兜底 |
| K6 | 追踪查询（可复用范式） | `apps/api/src/hris/modules/platform/audit_service.py:144-286` | 投递后 | — | 消息投递明细的列表/导出照此结构实现 |

### 7.2 流程与审批域（通知需求最密集）

| # | 集成点 | 位置（文件:行） | 触发时机 | 收件人依据 | 建议动作 |
|---|---|---|---|---|---|
| W1 | 审批任务生成 | `apps/api/src/hris/modules/workflow/extended_service.py:1205-1226` | 流程推进到 `approval` 节点，批量创建 `WorkflowTask` | `assignee_type`/`assignee_ref`（`apps/api/src/hris/modules/workflow/models.py:88-89`） | **最高优先级通知点**。此处追加 `MessageEngine.publish`，逐条生成「待办通知」 |
| W2 | 审批决定 | `apps/api/src/hris/modules/workflow/extended_service.py:1290-1349`（驳回分支 `:1325-1331`，推进分支 `:1338-1342`） | 审批人做出决定 | 发起人（`workflow_instances.started_by`，`apps/api/src/hris/modules/workflow/models.py:68`） | 通知发起人「已通过/已驳回」。**注意**：D-095（`docs/01-foundation/03-项目决策.md:170`）要求撤销/驳回/退回三者语义完全区分，通知文案与事件类型必须同步区分，不能共用一个文案 |
| W3 | 流程实例启动 | `apps/api/src/hris/modules/workflow/extended_service.py:1049-1100` | 流程发起 | 发起人 | 通知发起人「流程已发起」（是否需要属产品规则，见 Q-A2） |
| W4 | 流程完成 / 业务对象联动 | `apps/api/src/hris/modules/workflow/extended_service.py:1351-1380` | 到达 `end` 节点或审批终结 | 业务对象相关人 | 通知业务对象责任人「流程已结束」 |
| W5 | 批量催办 | **当前不存在**，D-096（`docs/01-foundation/03-项目决策.md:171`）要求对齐 Moka 的批量催办能力 | — | — | 催办是消息引擎的典型批量场景，需在消息引擎具备「按条件批量选取收件人 + 限流 + 单条失败不阻断批次」能力后再实现 |

### 7.3 批量异动域

| # | 集成点 | 位置（文件:行） | 触发时机 | 收件人依据 | 建议动作 |
|---|---|---|---|---|---|
| B1 | 方案提交审批 | `apps/api/src/hris/modules/workforce/batch_change_service.py:209-251`（整批共用一个流程实例见 `:225-235`） | 整批提交 | 方案提交人 | 通知提交人「已提交，等待审批」 |
| B2 | 整批审批通过 | `apps/api/src/hris/modules/workforce/batch_change_service.py:253-286`（明细转就绪见 `:275-276`） | 审批通过，整批明细置 `READY` | **整批全部明细的经办人** | 关键通知点：一条消息覆盖 N 条明细的经办人。需支持「一对多收件人 + 合并投递」，避免产生 N×M 条消息 |
| B3 | 整批审批驳回 | `apps/api/src/hris/modules/workforce/batch_change_service.py:288-317`（明细转驳回见 `:306-307`） | 审批驳回 | 整批全部明细的经办人 | 同 B2，与 B2 必须是**不同事件类型与不同文案**（D-095 同理） |
| B4 | 明细生效执行 | `apps/api/src/hris/modules/workflow/extended_service.py:1986`（`_execute_hr_event_if_due`）；执行器 `:1609`、`:1685` | 到期执行人事事件 | 事件相关人 | 通知「异动已生效」。**当前依赖手工触发**（`apps/api/src/hris/modules/workflow/extended_api.py:544-545`），需 Worker 接管后此通知才有意义 |

### 7.4 绩效域

| # | 集成点 | 位置（文件:行） | 触发时机 | 收件人依据 | 建议动作 |
|---|---|---|---|---|---|
| P1 | 周期状态流转 | `apps/api/src/hris/modules/performance/service.py:252-266`（流转白名单校验在 `:260`）；状态值域 `apps/api/src/hris/modules/performance/models.py:29-33` | 周期 `draft → active → closed` | 周期内全部目标所属人员（`PerformanceObjective.person_id`） | 通知「周期已开启，可填写目标」「周期已关闭」 |
| P2 | 目标状态流转 | `apps/api/src/hris/modules/performance/service.py:436`；状态值域 `apps/api/src/hris/modules/performance/models.py:36-45` | 目标 `draft → submitted → approved → archived` | 目标所属人员 | 通知「目标已提交/已通过」 |
| P3 | 关键结果状态流转 | `apps/api/src/hris/modules/performance/service.py:549` | KR 同上 | KR 所属目标的人员 | 同 P2 |
| P4 | 计分卡生成 | `apps/api/src/hris/modules/performance/service.py:599`（`build_scorecard`） | 周期内数据齐备 | 被评分人员 | 典型「长文本 + 表格」场景，是**邮件通道**的主要价值点；一期站内信亦可承载摘要 |

### 7.5 考勤与合同域

| # | 集成点 | 位置（文件:行） | 触发时机 | 收件人依据 | 建议动作 |
|---|---|---|---|---|---|
| A1 | 请假申请创建 | `apps/api/src/hris/modules/attendance/extended_service.py:911`（`status="pending_approval" if payload.workflow_instance_id else "draft"`） | 员工提交请假 | 审批人 | 通知审批人 |
| A2 | 请假状态流转 | `apps/api/src/hris/modules/attendance/extended_service.py:960-968`（允许流转白名单）、`:1020`（`request.status = payload.status`） | 状态变更 | 申请人 | 通知申请人「已通过/已驳回/已撤销」 |
| C1 | 合同到期提醒 | `apps/api/src/hris/modules/workflow/extended_service.py:950`（`list_contract_expiry_alerts`）、`:990-1020`（`process_contract_statuses`） | 合同临期 | **待企业确认**（`docs/01-foundation/99-待确认问题.md:63` Q-017 明确「提醒对象/渠道」未定） | 逻辑已存在但**渠道与对象未定**，必须等企业输入后才能定文案与通道 |

### 7.6 前端承载

| # | 集成点 | 位置（文件:行） | 说明 |
|---|---|---|---|
| F1 | 顶栏铃铛与未读数 | `apps/web/src/business/AppShell.tsx:298-321`（`Header` 结构） | 新增 `Badge` + 铃铛图标；点击展开消息列表（D-069 要求列表/工作台为宿主页，消息列表可用 Drawer 承载） |
| F2 | 消息列表页 | 同上，遵循 `docs/design/antd-page-interaction-standard.md` 的载体规则 | 需先出 Pencil 原型并按 D-087（`docs/01-foundation/03-项目决策.md:64`）登记 |
| F3 | SSE 客户端 | `apps/web/src/business/client.ts:53-68`（现有 fetch + Bearer 模式） | 新增 `fetch` + `ReadableStream` 读取器，复用 `Authorization` 头；令牌来源 `apps/web/src/business/client.ts:8`（`TOKEN_KEY`） |
| F4 | 多标签页未读数同步 | 新增 | 浏览器原生 `BroadcastChannel`，不轮询服务端 |
| F5 | 轮询降级 | 新增 | SSE 不可用时低频拉取未读数（建议 60 秒） |
| F6 | 消息相关 API 客户端 | `apps/web/src/api/client.ts:13-24` 为无鉴权通用示例；业务侧统一走 `apps/web/src/business/client.ts` | 新增接口须沿用 `apiRequest` |

---

## 8. 落地阶段建议

### P0 — 内核地基（不产出任何用户可见的通知）

**交付物**

1. `outbox_events` 表扩展：新增 `next_retry_at`、`last_error`、`provider_message_id`、`dedup_key`（唯一约束）；明确 `published_at` 的新语义为「投递完成时间」（原语义为「已发布」，从未被使用，扩展无兼容负担）。迁移文件：`apps/api/alembic/versions/` 下新增一个版本。
2. `apps/api/src/hris/modules/messaging/` 全新模块：`engine.py`（`publish`/`dispatch_once`/`redrive`）、`channels/base.py`（`Channel` 协议）、`channels/in_app.py`、`channels/registry.py`（含 `EMAIL`/`SMS` 占位实现）。
3. `apps/api/src/hris/worker.py`：常驻 Worker 进程，`FOR UPDATE SKIP LOCKED` 领取任务，指数退避重试。
4. `deploy/compose.yaml` 追加 `worker` 服务（参照 `:35-71` 的 `api` 服务写法，使用同一镜像）。
5. `apps/api/src/hris/modules/messaging/api.py`：只读查询接口（投递明细列表 / 单条详情 / 手动重投），供运维排查。
6. 模板表与模板渲染器（模板键、渠道、版本、变量定义）。

**验收口径**

- 单元测试：`Channel.deliver` 的三态返回值（`SENT`/`RETRYABLE`/`PERMANENT`）分别触发正确的状态回写；`PERMANENT` 不进入重试。
- 集成测试：事务内 `publish` 后回滚 → 任务记录不存在；提交 → 任务记录存在且 `published_at IS NULL`。
- 幂等测试：相同 `dedup_key` 重复 `publish` 只产生一条任务。
- 并发测试：2 个 Worker 并发领取 N 条任务，无重复投递、无丢失（`SKIP LOCKED` 语义验证）。
- 崩溃恢复测试：Worker 在投递中被 `SIGKILL`，未完成任务在下一轮被重新领取。
- `published_at` 与 `attempt_count` 的语义在迁移注释中写明；`docs/01-foundation/03-项目决策.md` 追加一条新决策编号（D-102 及以后）记录「PostgreSQL 队列 + SSE」的技术选型。

### P1 — 一期业务闭环（站内信）

**交付物**

1. `IN_APP` 通道完整实现：消息落库 + 已读/未读状态 + 用户消息列表 + 批量已读。
2. 前端承载：顶栏铃铛与未读数（`apps/web/src/business/AppShell.tsx:298-321`）、消息列表 Drawer、SSE 客户端与轮询降级（`apps/web/src/business/client.ts:53-68`）。
3. 接入 W1（审批待办）、W2（审批结果）、B1/B2/B3（批量异动三态）四个最高价值通知点。
4. 消息模板与文案：每个事件类型一份模板，撤销/驳回/退回按 D-095 分别建模板与事件类型。

**验收口径**

- 端到端：发起一条需审批的业务 → 审批人顶栏在 5 秒内出现未读角标 → 点击进入待办 → 处理后发起人收到结果通知。
- 消息与业务的一致性：业务事务回滚则不产生消息（复用 P0 的事务测试）。
- 未读数一致性：同一用户多标签页角标数一致（`BroadcastChannel` 同步）；服务端 `messages.unread` 与前端角标一致。
- 降级验收：人为断开 SSE 连接，轮询兜底在 60 秒 ±10 秒内仍能拉取到未读数。
- 文案验收：通过/驳回/退回三种结果的文案与事件类型互不相同，且与 D-095 的接口语义区分一致。
- 性能：未读数查询在 1 万条消息量级下 P95 < 100ms（需相应索引）。

### P2 — 扩展通道与实时性完善

**交付物**

1. `EMAIL` 通道：模板渲染（长文本/表格）、SMTP 或邮件服务商对接、硬退信/软退信区分、退信抑制。
2. 合同到期提醒接入（依赖 Q-017 企业输入，`docs/01-foundation/99-待确认问题.md:63`）。
3. 多实例部署下的 Redis Pub/Sub 扇出（仅在多实例时才启用，符合 T-005，`docs/01-foundation/03-项目决策.md:138`）。
4. 生产部署：反向代理的 SSE 缓冲配置（`X-Accel-Buffering: no`）、连接数上限与熔断。
5. 批量催办能力（依赖 D-096 的流程引擎能力，`docs/01-foundation/03-项目决策.md:171`）。

**验收口径**

- 邮件投递：发送 → 收到 → 标记已读；硬退信后自动抑制后续发送；退信事件可在投递明细中查到。
- 扇出：2 个 API 实例 + 1 个 Worker，用户连接到 A 实例时，Worker 投递的消息仍能推达（验证跨实例路径）。
- 熔断：邮件供应商连续失败达阈值后，通道进入熔断状态并可观测，整批消息不被判定为永久失败。
- 批量催办：1000 人批量催办不产生 1000 条独立任务（合并为批次），单条失败不阻断批次，且对同一用户有频率限制。

### P3 — 短信通道（独立立项，不与 P0–P2 绑定）

**交付物**：`SMS` 通道实现、企业短信签名与资质接入、号码覆盖率统计（基于 `person_contacts`）、退订与免打扰策略、按条计费的对账。

**验收口径**：资质合规性由企业侧确认；单条成本可归集到 `message_deliveries`；失败按供应商返回码分类统计。

**前置依赖**：§9.2 的 Q-A3（是否需要短信兜底）必须先有产品结论，否则本阶段不启动。

---

## 9. 风险与开放问题

### 9.1 工程风险（开发侧可消化，不需产品决策）

| 风险 | 影响 | 缓解 |
|---|---|---|
| `SKIP LOCKED` 在高并发下的行锁争用与 vacuum 压力 | 吞吐下降、DB 负载上升 | 短事务、限定领取批次上限、`next_retry_at` 错峰、监控队列深度与领取延迟 |
| 长连接 SSE 的连接数与内存占用 | 单实例连接上限受限 | 心跳 + 空闲连接回收 + 连接数上限 + 多实例 Redis 扇出；上限值在 P2 按压测确定 |
| 模板变量缺失导致渲染失败 | 消息发不出去 | `Channel.validate` 前置校验；渲染失败判为 `PERMANENT` 并在投递明细中记录缺失变量名 |
| 收件人地址缺失（无手机号/邮箱） | 投递静默失败 | `validate` 阶段直接判不可投递并计入「地址缺失」指标；覆盖率统计纳入 P3 |
| `published_at` 语义扩展 | 与既有认知冲突 | 该字段从未被赋值（§2.1），扩展无兼容负担，但须在迁移注释与 D-102 中写明 |
| 业务域绕过 `MessageEngine` 直连通道 | 端口抽象失效，D-100 的内核定位被破坏 | 代码评审检查项：`apps/api/src/hris/modules/` 下业务模块不得 import 具体 Channel 实现；建议加一条守卫脚本，与既有 `apps/web/scripts/check-antd-usage.mjs` 同类做法 |
| Outbox 事件类型继续只增不减 | 事件表膨胀 | 消息类事件独立命名空间 `notification.*`，与组织域事件 `organization.*` 隔离 |

### 9.2 必须由产品决策人拍板的开放问题

> 以下问题**不由本报告下结论**。每条都给出选项与影响面，供产品决策人选择；未拍板前，相关工程不得开工。

| # | 议题 | 选项 | 影响面 |
|---|---|---|---|
| **Q-A1** | 一期通道范围 | (a) 仅站内信；(b) 站内信 + 邮件；(c) 三通道全上 | 选 (a)：P1 最短，但长文本与正式文书场景无解（绩效评分卡 `apps/api/src/hris/modules/performance/service.py:599`、合同到期 `apps/api/src/hris/modules/workflow/extended_service.py:950` 需降级为摘要）。选 (b)：需在 P1 内追加邮件渲染与退信治理，工期增加。选 (c)：直接违反 D-064 精神（`docs/01-foundation/03-项目决策.md:132`），不建议 |
| **Q-A2** | 通知的必达等级 | (a) 全部尽力型（一次投递即止）；(b) 分级（审批待办/合同到期为必达，其余尽力）；(c) 全部必达 | 选 (a)：实现最简，但「审批待办漏了」无法闭环。选 (b)：需产品逐条指定事件等级，**本文建议按 (b) 讨论但不代为判定**。选 (c)：需要多通道降级与人工兜底通道，成本最高 |
| **Q-A3** | 是否需要短信作为兜底 | (a) 不需要；(b) 仅必达型事件在站内信+邮件均失败时兜底；(c) 常规通道 | 选 (a)：P3 短信阶段不启动。选 (b)：短信降级需要先完成资质申请（周期不可控）与号码覆盖率统计。选 (c)：不建议 |
| **Q-A4** | 收件人范围与免打扰 | (a) 管理员/SSC 全量收；(b) 按角色订阅；(c) 用户可自助关停某类通知 | 选 (a)：实现最简但噪音大。选 (b)/(c)：需要订阅模型与策略层（§6.4 已预留接口），且与 D-092「员工端入口后续立项」（`docs/01-foundation/03-项目决策.md:157`）的边界相关 |
| **Q-A5** | 未读提醒的重复策略 | (a) 不重复提醒，直至已读；(b) 固定间隔重复（如每 4 小时）；(c) 按事件等级差异化 | 影响 SSE 推送频率、消息量与用户打扰程度；需与 Q-A2 联动 |
| **Q-A6** | 消息的保留期限与归档 | (a) 永久保留；(b) 保留 N 个月后归档；(c) 已读即清理 | 影响存储估算与合规；已读状态与归档的交互需一并确定 |
| **Q-A7** | 降级策略的可见性 | (a) 静默降级到轮询，用户无感；(b) 顶部提示「实时通道不可用」 | 选 (b) 会占用顶栏空间（`apps/web/src/business/AppShell.tsx:298-321`），需产品确认视觉层级 |
| **Q-A8** | 模板与文案的所有权 | (a) 产品提供固定文案；(b) HR 管理员可在界面自助配置模板；(c) 代码内硬编码 | 选 (b) 需要模板管理界面与权限（当前权限码缺口见 `docs/review/D-考勤-待确认-决策-文档规范.md:366`），工作量显著增加；选 (a)/(c) 则文案变更需走发版 |

### 9.3 需要企业输入（阻塞项，非产品拍板）

| # | 事项 | 出处 | 阻塞范围 |
|---|---|---|---|
| E1 | 合同到期提醒的**提醒对象与提醒渠道** | `docs/01-foundation/99-待确认问题.md:63`（Q-017） | 阻塞 §7.5 C1 的文案与通道选型；不影响 P0/P1 |
| E2 | 企业微信 / 自建 OA 等外部系统接口清单、认证方式、字段映射与主从关系 | `docs/01-foundation/99-待确认问题.md:59`（Q-016） | 阻塞企业微信通道立项；不影响站内信/邮件/短信 |
| E3 | 企业短信签名资质、可用号码段与计费方式 | 无既有条目（属新增企业输入项） | 阻塞 P3 短信阶段 |

### 9.4 本报告不做的判断

- 不替产品决定 §9.2 的任何一条。
- 不替企业确认 §9.3 的任何一条。
- 不宣称已支持万级并发消息投递 —— PRD（`docs/01-foundation/16-coreHR产品总体PRD.md:396-400`）要求的持续负载/峰值负载/P95/P99/积压清空时间等指标，须在 P1 压测后按实测数据填写，本报告不预填数字。

---

## 10. 附录：检索口径（可复现）

本报告中所有「不存在」结论均基于以下检索。检索范围与检索词如下，任何人可原样重跑核对。

| 结论 | 检索范围 | 检索词 | 结果 |
|---|---|---|---|
| 无 Outbox 投递器 / 消费者 | `apps/api` | `published_at` | 2 处命中（`governance_models.py:23`、迁移 `f1a000000001_phase_1a_organization_domain.py:251`），均未被赋值或读取 |
| 无通知模型 / 通道 / 消息中间件 | `apps/api/src` | `\bnotify\b`、`\bnotification\b`、`\bnotifications\b`、`websocket`、`EventSource`、`\bsms\b`、`\bsmtp\b`、`\bemail\b`、`\bmailer\b`、`\bMessageBus\b`、`\bproducer\b`、`\bconsumer\b` | 4 处命中，全部为人员联系信息脱敏：`personnel_service.py:276-277`、`:671-672` |
| 无前端消息/推送组件 | `apps/web/src` | `websocket`、`EventSource`、`notification`、`setInterval`、`poll` | 0 命中 |
| 无调度器 / 队列框架 | `apps/api` | `celery`、`scheduler`、`apscheduler`、`cron`、`backgroundtask`、`arq`、`rq\b`、`kombu` | 仅命中 `redis` 依赖声明（`requirements.in:8`、`pyproject.toml:18`）与健康探测（`system/api.py:31-36`） |
| 无队列中间件依赖 | `apps/api/requirements.in`、`apps/api/pyproject.toml` | `celery`、`kombu`、`pika`、`kafka`、`confluent` | 0 命中 |
| 依赖清单基线 | `apps/api/requirements.in:1-12`、`apps/api/pyproject.toml:10-21` | 全文阅读 | 共 12 项运行时+测试依赖，无消息相关项 |
| 部署拓扑基线 | `deploy/compose.yaml` | 全文阅读 | 4 个服务：db / redis / api / web；无 worker、无 broker |

**已阅读但未逐行引用的关键文件**：`apps/api/src/hris/core/config.py`、`apps/api/src/hris/core/concurrency.py`、`apps/api/src/hris/core/database.py`、`apps/api/src/hris/modules/platform/models.py`、`apps/api/src/hris/modules/platform/governance_models.py`、`apps/api/src/hris/modules/platform/audit_service.py`、`apps/api/src/hris/modules/workflow/models.py`、`apps/api/src/hris/modules/workflow/service.py`、`apps/api/src/hris/modules/workflow/extended_service.py`、`apps/api/src/hris/modules/workflow/extended_api.py`、`apps/api/src/hris/modules/workforce/batch_change_service.py`、`apps/api/src/hris/modules/workforce/organization_service.py`、`apps/api/src/hris/modules/workforce/models.py`、`apps/api/src/hris/modules/workforce/personnel_service.py`、`apps/api/src/hris/modules/performance/service.py`、`apps/api/src/hris/modules/performance/models.py`、`apps/api/src/hris/modules/attendance/extended_service.py`、`apps/api/src/hris/modules/attendance/models.py`、`apps/api/src/hris/modules/system/api.py`、`apps/api/src/hris/modules/platform/import_service.py`、`apps/web/src/business/client.ts`、`apps/web/src/business/AppShell.tsx`、`apps/web/src/api/client.ts`。

**参考的既有复审结论**（本文结论与其一致，非本文原创发现）：

- `docs/review/D-考勤-待确认-决策-文档规范.md:315` — D-100 判定为「未实现」，优先级 P0。
- `docs/review/D-考勤-待确认-决策-文档规范.md:367` — 消息引擎缺失与 D-096 批量催办、Q-016、Q-017 的依赖关系。
- `docs/review/moka-vs-corehr-feature-gap.md:395` — 「后台任务/调度器」全库零匹配。
- `docs/review/moka-vs-corehr-feature-gap.md:396` — 「通知通道」全库零匹配，`outbox_events` 只写不读。
- `docs/review/A-总体PRD-产品边界.md:47` — 七个可插拔面中无一有端口定义。
- `docs/review/A-总体PRD-产品边界.md:77` — Kernel 最大空洞为后台任务/调度/可重试执行框架。
- `docs/review/platform-kernel-architecture-fit-review-2026-08-18.md:52-53` — Redis 仅用于就绪检查，Outbox 有表和写入但无投递器与消费者。

---

*本文由消息引擎选型调研整理入库。所有代码位置均为 2026-10-24 工作区实测；代码变更后需重新核对行号。*
