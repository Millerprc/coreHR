# coreHR 平台内核架构适配审查

> 日期：2026-08-18
> 审查对象：当前 `main` 工作区代码与《coreHR产品总体PRD》目标架构
> 结论状态：`REVIEW_PENDING`
> 本文性质：代码现状审查与迁移建议，不代表已完成相应改造

## 1. 结论

现有代码**可以继续作为coreHR的工程和业务底座，不需要推倒重写**。已经实现的领域规则、有效期模型、数据库约束、API契约、前端工作台和自动化测试都有保留价值。

但当前系统仍是“按目录划分的模块化单体”，还不是《[coreHR产品总体PRD](../01-foundation/16-coreHR产品总体PRD.md)》定义的“平台内核 + 可组合业务套件”。进入新的模块功能开发前，应先完成一轮边界治理，使后续功能只依赖稳定接口，而不是继续扩大现有模块间的直接依赖。

推荐路线是：

1. 保留现有业务行为和外部API，以测试保护重构。
2. 先完成统一应用入口、静态模块清单、平台归位和依赖检查。
3. 再拆解流程、招聘、合同、考勤之间的内部边界。
4. 最后补齐异步任务、事件投递、生产部署和容量工程。

当前代码**不能宣称已支持20万人规模、模块按需安装、生产高可用或MySQL/Oracle运行**。这些是目标能力，需要按本文后续阶段建设和专项验收。

## 2. 审查口径

本次以以下目标为准：

- Platform Kernel只提供身份、权限、审计、配置、任务、事件、文件、通知、可观测性和模块治理等通用能力。
- Workforce Core是必装业务核心，但不等同于Platform Kernel。
- 招聘、流程、合同、考勤、薪酬、自助与集成是边界明确的业务套件。
- 默认采用模块化单体，同一套代码可以通过不同部署配置服务不同规模组织。
- 业务模块通过公开契约和端口协作，不直接依赖其他模块的数据库模型或内部服务。
- PostgreSQL是当前唯一运行基线；MySQL、Oracle和商业中间件是第五阶段适配目标。
- 5人到20万人不是五套产品，部署档位不裁剪业务功能，只改变运行拓扑、容量和保障等级。

## 3. 当前代码实际结构

```text
React 管理端
  ├─ 系统入口页面
  └─ 业务入口页面
         ↓
FastAPI
  ├─ main.py + api_router
  ├─ business_main.py + business_router
  ├─ platform
  ├─ workforce
  ├─ workflow（流程 + 招聘 + 人事办理 + 合同）
  └─ attendance
         ↓
PostgreSQL（单一模型注册与迁移链）

Redis：当前主要用于就绪检查，尚未形成任务或缓存运行能力
Outbox：已有表和写入，尚无投递器与消费者
```

这套结构具备良好的模块化单体起点，但“目录存在”不等于“边界已经成立”。目前路由、模型和前端菜单仍是静态注册，模块也不能独立启停或验证依赖关系。

## 4. 适配性分类

### 4.1 可直接保留

| 资产 | 判断 | 处理方式 |
|---|---|---|
| 统一错误响应、Trace ID和中间件 | 符合平台通用能力方向 | 归入Platform Kernel公开接口 |
| 并发命令、幂等键和版本检查 | 可复用 | 保持数据库不变量，补端口边界 |
| 人员敏感字段保护 | 可复用 | 作为平台安全策略被业务模块调用 |
| SQLAlchemy基础模型与命名约定 | 可复用 | 继续作为当前PostgreSQL实现 |
| 组织、人员、雇佣、编制等领域模型 | 业务资产完整度较高 | 保留在Workforce Core，不下沉平台 |
| 生效日期、历史版本、事件与回退规则 | 可复用 | 通过Workforce公开服务暴露 |
| 考勤事实、期间冻结、幂等与唯一约束 | 可复用 | 保留领域规则，调整跨模块调用 |
| 现有REST路径和前端工作台 | 可复用 | 重构期间保持外部契约兼容 |
| 后端与前端测试 | 重要保护资产 | 作为迁移验收回归集 |

### 4.2 需要小范围边界调整

| 现状 | 问题 | 目标 |
|---|---|---|
| `main.py`与`business_main.py`双入口 | 不同部署命令可能暴露不同能力 | 一个应用工厂、一个正式组合根；测试可保留精简组合 |
| 路由和模块状态手工登记 | 不能表达依赖、版本和启停状态 | 静态`ModuleManifest`和依赖解析器 |
| 前端菜单硬编码 | 后端模块状态与页面入口不一致 | 菜单从同一模块注册表生成 |
| 数据库连接池固定为`10 + 20` | 多进程部署会放大总连接数 | 通过部署档位配置并纳入容量预算 |
| 单个Service文件过大 | 修改面和AI协作冲突持续扩大 | 按用例拆文件，保持领域和API行为不变 |
| `AuditLog`由Workforce定义 | 平台反向依赖业务模块 | Python所有权迁回Platform，表名和数据不变 |

### 4.3 必须进行结构改造

| 现状 | 风险 | 改造方向 |
|---|---|---|
| Platform导入导出服务直接引用Workforce模型 | 平台无法独立，后续每加套件都要修改平台 | 通用数据交换核心 + 各套件导入导出适配器 |
| Workflow同时承载流程、招聘、合同和人事事件 | 生命周期和依赖边界混合 | 拆为通用Workflow、Recruitment、Contract；人事事件执行归Workforce |
| Attendance直接引用Workflow和Workforce内部模型 | 无法独立演进和组合测试 | 通过人员目录、雇佣查询和可选流程网关协作 |
| 所有模型一次性注册到单一迁移链 | 模块不能表达自身迁移和启用条件 | 建立迁移归属，仍可先保留一个物理库 |
| Outbox只有写入，没有投递器 | 下游同步、通知和异步计算无法可靠运行 | Worker + Outbox Dispatcher + 幂等消费者 + 重试/死信 |
| 导入、报表和未来生效处理位于请求链路 | 大数据量会阻塞API并难以恢复 | Job Queue + Scheduler + 进度、取消、重试和审计 |

### 4.4 尚未实现

- 真正的租户上下文和数据范围策略。
- 模块生命周期、依赖检查、启用/禁用和组合测试。
- 可靠任务队列、调度器、Outbox消费者及死信治理。
- 对象存储、通知发送、密钥管理等基础设施端口。
- Payroll、ESS和Integration套件。
- 生产监控、告警、备份恢复、同城高可用和异地灾备。
- 面向1万至20万人组织的容量模型、压测和故障演练。
- MySQL、Oracle运行时适配和迁移验证。

## 5. 关键代码证据

| 发现 | 代码位置 |
|---|---|
| 业务路由静态挂载 | `apps/api/src/hris/api/business_router.py:3-38` |
| 模块状态硬编码 | `apps/api/src/hris/modules/system/api.py:48-118` |
| 前端菜单与模块入口硬编码 | `apps/web/src/business/AppShell.tsx:17-28,169-191`、`apps/web/src/business/navigation.ts:22-48` |
| 前端已有模块状态请求但尚未驱动菜单 | `apps/web/src/business/client.ts:125-126` |
| 所有模型集中注册 | `apps/api/src/hris/shared/db/models.py:3-62` |
| Alembic一次加载全部元数据 | `apps/api/alembic/env.py:9-20` |
| Platform账号直接关联Workforce Person | `apps/api/src/hris/modules/platform/models.py:10-18` |
| AuditLog定义在Workforce且被Platform引用 | `apps/api/src/hris/modules/workforce/models.py:992-1016`、`apps/api/src/hris/modules/platform/account_admin_service.py:16` |
| Platform导入服务直接引用Workforce实现 | `apps/api/src/hris/modules/platform/import_service.py:37-61` |
| Workflow模型同时包含多个业务域 | `apps/api/src/hris/modules/workflow/models.py:97-189` |
| Workflow直接引用Workforce内部实现 | `apps/api/src/hris/modules/workflow/extended_service.py:49-57` |
| Attendance直接引用Workflow与Workforce | `apps/api/src/hris/modules/attendance/extended_service.py:43-44` |
| Leave记录外键直连Workflow事件 | `apps/api/src/hris/modules/attendance/models.py:149-152` |
| 数据库连接池固定 | `apps/api/src/hris/core/database.py:8-15` |
| PostgreSQL锁语义散落在业务服务 | `apps/api/src/hris/modules/workforce/organization_service.py:2158-2162`、`apps/api/src/hris/modules/attendance/extended_service.py:878-890` |
| Outbox目前只有数据模型 | `apps/api/src/hris/modules/platform/governance_models.py:11-24` |
| Redis当前只执行健康检查 | `apps/api/src/hris/modules/system/api.py:23-36` |
| 默认Docker镜像仍启动精简入口 | `apps/api/Dockerfile:25` |
| Compose仍是开发模式、源码挂载和自动重载 | `deploy/compose.yaml:39-55,76-83`、`deploy/compose.business.yaml:8-15` |

## 6. 推荐目标边界

```text
应用入口 / 组合根
  ├─ Platform Kernel
  │    ├─ Identity / Authorization / Audit / Configuration
  │    ├─ Module Registry / Job / Event / File / Notification
  │    └─ Observability / Security / Infrastructure Ports
  ├─ Workforce Core
  ├─ Generic Workflow
  ├─ Recruitment
  ├─ Contract
  ├─ Attendance
  ├─ Payroll
  ├─ ESS
  └─ Integration

基础设施适配器
  ├─ PostgreSQL / Redis
  ├─ 本地文件或对象存储
  ├─ 本地账号或企业身份源
  ├─ 内置任务进程或外部队列
  └─ 监控、通知和外部连接器
```

建议现在定义但不提前实现所有变体的接口：

- `ModuleManifest`与模块依赖解析器。
- `TenantContextResolver`与`DataScopePolicy`。
- `IdentityProvider`与`SecretProvider`。
- `AuditWriter`。
- `DomainEventPublisher`、`OutboxDispatcher`与`JobScheduler`。
- `ObjectStorage`与`NotificationSender`。
- `LockProvider`和数据库方言能力声明。
- Workforce的人员、雇佣和组织查询契约。
- 可选`WorkflowGateway`。
- Integration Connector契约。

不建议现在建设动态插件市场、第三方代码热加载、Kubernetes、Kafka、自动分片、全量多租户或为每张表机械创建Repository。这些工作会增加当前复杂度，但不能替代清晰的模块边界。

## 7. 迁移顺序与验收点

### P0：建立平台和模块边界

目标：让后续模块开发不再扩大结构债务。

1. 建立统一应用工厂和唯一正式组合根。
2. 新增静态`ModuleManifest`，声明模块ID、版本、依赖、后端路由、前端入口和迁移归属。
3. 当前已有模块默认全部启用，先不改变用户可见功能。
4. 将`AuditLog`的代码所有权迁入Platform，保持表结构和历史数据不变。
5. 将连接池参数外置，提供单机、中型和集群部署默认值。
6. 增加模块依赖和禁止跨层导入的架构测试。

验收：

- 现有公开API路径和响应契约不变。
- 后端、前端与数据库迁移回归通过。
- 正式镜像只存在一个明确启动入口。
- Platform不再导入具体业务模块实现。
- 空迁移检查和当前迁移升级检查通过。

### P1：拆业务套件并补异步平台能力

目标：让套件能够按依赖组合、独立测试和演进。

1. 从现有Workflow中拆出Recruitment和Contract。
2. 将人事事件的业务结果执行归还Workforce，通用Workflow只负责流程定义和流转。
3. 将Platform导入导出改成通用交换内核和套件适配器。
4. 将Attendance对其他模块的依赖替换为公开查询契约和可选流程网关。
5. 前端导航改由模块注册表生成。
6. 实现任务执行器、调度器和Outbox投递闭环。
7. 建立套件迁移归属和最小组合测试。

验收：

- Platform Kernel + Workforce Core可以独立启动。
- 启用或禁用可选套件时，API和UI入口保持一致。
- 跨模块调用只通过公开契约。
- Outbox达到至少一次投递，消费者幂等，具备重试和死信处理。
- 异步导入、报表和未来生效任务可以查询进度并安全重试。

### P2：生产部署和大规模容量工程

目标：把同一套产品代码落到不同部署档位，并用实测数据定义上限。

1. 形成与父PRD逐一对应的便携单机版、标准生产版、企业版、集团版和超大型架构目标五档部署清单。
2. 补监控、日志、指标、告警、备份恢复、同城故障切换和异地恢复演练。
3. 对打卡、考勤计算、薪酬查询、批量导入和报表分别建立容量模型。
4. 对高增长事实表实施分区、归档和保留策略，改造深分页。
5. 将打卡接入与考勤计算解耦，将重计算放到异步任务。
6. 按实际部署档位进行容量、长稳和故障注入测试。
7. 第五阶段再启动MySQL、Oracle和商业中间件适配验证。

验收标准必须使用明确工作负载，至少包含在线人数、请求比例、峰值持续时间、数据规模、响应分位、任务时限、RPO、RTO和降级策略。仅写“支持20万人”不能作为验收。

## 8. 20万人规模的当前硬阻塞

| 阻塞 | 当前表现 | 建议 |
|---|---|---|
| 每请求会话写和权限查询 | 放大数据库写入与热点 | 会话活跃时间节流，权限缓存并支持失效 |
| 固定连接池 | 多副本会迅速耗尽数据库连接 | 按实例数预算连接池，必要时引入连接代理 |
| 无Worker和Scheduler | 未来生效、导入、报表和计算挤占API | 建立可恢复的异步任务面 |
| 导入同步执行 | 大批量请求超时且难续跑 | 分块、断点、进度与幂等重试 |
| 打卡链路未为高并发设计 | 检查后插入存在竞争，审计量巨大 | 数据库唯一约束优先、轻写入、异步计算 |
| 无Outbox消费者 | 下游同步不完整 | 独立投递器、重试、死信、监控 |
| 无分区和数据保留 | 考勤、打卡、审计持续膨胀 | 按日期/主体分区并建立归档策略 |
| 列表依赖`COUNT + OFFSET` | 深页查询随数据量恶化 | 游标分页、异步总数或近似统计 |
| 无生产级可观测与灾备 | 容量和恢复能力不可验证 | 指标、链路、备份恢复及故障演练 |
| PostgreSQL特性散落 | 第五阶段数据库适配成本高 | 收口到LockProvider和方言能力层 |

现有API多数无状态、业务事实集中在PostgreSQL、核心写入已有幂等与数据库约束，这些是未来水平扩展的有利条件。但在上述阻塞关闭并通过专项测试之前，不应给出20万人容量承诺。

## 9. 测试保护缺口

当前已有较多业务回归测试，可以保护迁移行为；仍需补充：

- 模块依赖方向和禁止内部导入的架构测试。
- Platform Kernel + Workforce Core及不同套件组合启动测试。
- 单一正式应用入口的路由契约测试。
- 各套件迁移注册、升级和卸载边界测试。
- 基础设施端口的契约测试。
- Outbox重试、死信、幂等和崩溃恢复测试。
- 生产Compose或等效部署清单的冒烟测试。
- 备份恢复、节点故障切换和异地恢复演练。
- PostgreSQL之外的数据库方言测试；该项第五阶段再启用。
- 分档容量、长稳和峰值场景测试。

现有`apps/api/tests/test_metadata.py:6-39`假定所有模型总是一次启用。引入模块清单后，应把它改为“默认全模块元数据 + 允许组合的模块元数据”两类断言。

## 10. 对下一步开发的约束

在P0完成前，可以继续做不会扩大跨模块依赖的缺陷修复、数据核对和测试补强；不建议继续增加跨模块业务功能。

后续P0、P1和P2实现默认由Codex直接完成，包括任务拆解、代码、迁移、自动化验证、独立复审和交付回执；不再生成转交MinimaxCode的开发任务包。

以后每个功能应先按《[模块功能需求文档规范](../01-foundation/17-模块功能需求文档规范.md)》形成可验收的功能文档，再拆最小开发任务。开发任务必须明确：

- 所属模块和允许依赖。
- 是否新增公开契约或基础设施端口。
- 数据所有权和迁移归属。
- 权限、审计、幂等和失败语义。
- 单机版与多节点部署下的行为是否一致。
- 对应自动化测试和人工验收场景。

## 11. 本次审查没有做什么

- 没有修改现有业务代码、数据库结构或部署配置。
- 没有把当前代码改造成插件系统。
- 没有运行20万人容量测试或高可用演练。
- 没有确认MySQL、Oracle、Apusic等第五阶段具体选型。
- 没有以部署档位为由裁剪任何业务功能。

## 12. 待产品决策人Review

1. 是否批准“保留现有业务资产，以P0/P1/P2渐进重构，不推倒重写”。
2. 是否批准P0先于新的跨模块功能开发。
3. 是否接受Workforce Core为必装业务核心，但与Platform Kernel严格分层。
4. 是否接受部署档位只改变运行拓扑和保障等级，不改变产品功能授权。
5. 是否接受20万人能力必须在真实工作负载和专项测试后再对外承诺。
