# ADR-0006 消息引擎定位为平台内核基础服务

> 状态：Accepted
> 日期：2026-10-24
> 决策人：Miller（已确认）、Mavis
> 关联任务：D-100；`docs/review/message-engine-selection-2026-10-24.md`；待确认清单 P-10 / P-11 / P-12

## 背景

2026-10-24 用户提出：「除了流程引擎做调研之外，再去调研一下消息引擎，包含站内信、短信、邮件，并且给我选型，作为整个程序挂载的基础服务来。」

关键约束是「**作为整个程序挂载的基础服务**」——消息能力不是某个业务模块的附属功能，而是所有模块（流程通知、审批提醒、审计告警、批量异动结果、数据治理预警）共同依赖的平台内核服务。因此选型的第一判据不是「哪个队列最快」，而是「哪个方案在 coreHR 当前的部署形态（单机 Docker Compose + PostgreSQL 16 + Redis）下能长期可靠运行」。

调研结论已落 `docs/review/message-engine-selection-2026-10-24.md`（478 行），§9.2 列出 8 条必须产品拍板的分水岭。2026-10-24 用户确认 P-10 / P-11 / P-12 **按报告建议执行**，本 ADR 记录**技术定位**与**一期方案**，状态转为 Accepted。

## 决策

### 已定（技术定位，无需产品决策）

- **消息引擎是平台内核基础服务**，不属于任何单一业务模块。业务模块通过平台消息接口投递，不直接依赖队列实现。
- **通知渠道与传输机制解耦**：领域事件 → 消息引擎 → 渠道适配器（站内信 / 短信 / 邮件）。新增渠道不改动业务模块。
- **消息投递必须留痕**：每条消息的投递状态、渠道、失败原因与重试次数入库，不依赖日志作为唯一证据。

### 一期方案（**P-10 / P-11 / P-12 已确认**）

- **通道范围**：一期只做**站内信**。短信与邮件在报告中已给出接入设计，但一期不实现，避免在通道供应商、签名合规与发送限流未确定前产生返工。
- **队列实现**：`PostgreSQL SKIP LOCKED` + **独立 Worker 进程**。理由是复用已有的 PostgreSQL 16 事实库，零新增中间件，与单机 Compose 部署形态一致；消息表天然与业务事务同库，可与业务写入同事务落库，保证「业务提交成功即消息必达」。
- **实时推送**：**SSE**（`fetch` + `ReadableStream`）。**不使用 `EventSource`**——`EventSource` 无法携带 `Authorization` 头，而 coreHR 的鉴权是 Bearer Header 模式。SSE 本身是单向推送，足够覆盖站内信与流程通知场景。

## 备选方案

### Redis Streams 作为队列

- 优点：吞吐高、消费组语义原生、重放方便。
- 缺点：需要 Redis 持久化配置与独立运维面；消息与业务事务不在同一事务边界，业务回滚时需额外补偿；当前栈中 Redis 仅用于健康检查，引入后要承担持久化与容量责任。
- 未采用原因：一期消息量不需要该吞吐；多一个中间件就多一份运行风险。

### Celery + RabbitMQ

- 优点：成熟的分布式任务框架。
- 缺点：引入 broker + worker + 监控三套运维面；Celery 的任务序列化与 Python 运行时耦合较深；对「同一事务内落库」这一核心诉求没有帮助。
- 未采用原因：与 coreHR 单机部署基线不匹配，运维成本远超收益。

### Kafka

- 优点：高吞吐、可回放、多消费组。
- 缺点：资源占用与运维复杂度最高；coreHR 当前无事件溯源或流式计算需求。
- 未采用原因：过度设计。

### WebSocket 替代 SSE

- 优点：双向、可用于协同编辑与在线状态。
- 缺点：需要额外的连接管理、心跳、重连与鉴权刷新机制；当前通知场景全部是服务端单向推送。
- 未采用原因：SSE 已覆盖需求，且实现面小得多。若将来出现双向协同需求可再升级，两者可共存。

### 一期就实现短信 + 邮件

- 优点：触达能力完整。
- 缺点：短信通道需采购与实名，邮件需配置 SMTP 与域名 SPF/DKIM；合规与限流问题会在没有真实业务量之前就成为负担。
- 未采用原因：通道扩展是增量工作，一期不做不产生返工成本。

## 影响

- 消息表与投递记录表进入平台内核 schema，需纳入 `docs/requirements/` 的平台类功能需求文档。
- Worker 必须可独立部署与重启；投递需幂等，重复消费不得产生重复站内信。
- 一期不引入新中间件，部署形态不变（仍是 `corehr-db-1` / `corehr-redis-1` / `corehr-api-1` / `corehr-web-1`）。
- 短信与邮件渠道适配器预留接口但一期不实现；接入时需新增合规评审，触发 ADR 复审。
- SSE 端点需要处理断线重连与鉴权过期，接口形态须先在功能需求文档中定义。

## 落地情况（2026-10-24）

| 决策 | 落地位置 |
|---|---|
| 平台内核定位 | `apps/api/src/hris/modules/messaging/`（独立模块，业务域只调用 `MessageService`） |
| 一期只做站内信 | `channels.py`：`in_app` 真实实现；`email` / `sms` 注册为「未启用」占位，返回不可重试失败而非抛异常 |
| PostgreSQL `SKIP LOCKED` + 独立 Worker | `dispatcher.py`（`FOR UPDATE SKIP LOCKED` 领取 + 指数退避 + 超上限置 `failed`）、`worker.py`（`python -m hris.modules.messaging.worker`） |
| SSE（`fetch` + `ReadableStream`） | `stream.py` / `api.py`：`GET /api/v1/messaging/stream`，只推本人消息；前端 `apps/web/src/business/features/messaging/stream.ts` 用 `fetch` 读流，**不出现 `EventSource`** |

数据模型：`messages`（站内信本体）+ `message_deliveries`（投递侧发件箱），迁移 `f2j000000001`。
接口契约：`MessageService.publish()` / `publish_many()` 与业务**同事务**写入，幂等键由 `(idempotency_key, recipient_user_id)` 唯一约束兜底。

## 验证证据

- 调研报告 `docs/review/message-engine-selection-2026-10-24.md`（54535 B / 478 行）已落盘 `docs/review/`。
- 现状核实：当前栈中 Redis 仅用于容器健康检查 ping；`apps/api` 无 Celery / RabbitMQ / Kafka 客户端依赖；PostgreSQL 16 已在用，`SKIP LOCKED` 无需新增组件。
- 待确认清单 `docs/review/pending-confirmations-2026-10-24.md` P-10 / P-11 / P-12 已标记决策并登记落地位置。
- 实现证据：后端 `apps/api/tests/integration/test_messaging_api.py` 覆盖同事务写入、业务回滚不落库、幂等去重、`SKIP LOCKED` 并发领取、退避重试与失败上限、错误信息脱敏、SSE 只推本人消息。

## 复审条件

- 消息量超过单库 Worker 的处理能力，或需要跨库 / 跨机投递。
- 出现双向实时协同需求（在线状态、协同编辑、实时白板）。
- 引入短信通道并需要处理签名合规、限流与回执。
- 部署形态从单机 Compose 改为多节点或上云托管数据库。
- 一期只做站内信的前提变化（例如需要多通道必达型通知），触发通道扩展评审。
