# ADR-0007 流程引擎（BPMS）选型与自研边界

> 状态：Accepted
> 日期：2026-10-24
> 决策人：Miller（P-09 已拍板：选方案 A）、Mavis
> 关联任务：待确认清单 P-09；BPMS P0 批次（动作枚举扩展 / 实例状态机 / 任务状态机 / 流转历史表 / 节点停留统计 / 调度器 / 通知出口）

## 背景

coreHR 已经在 `apps/api/src/hris/modules/workflow/` 有一套**手写流程引擎**在生产使用，不是空白：模块共 9 个文件，其中 `extended_service.py` 达 92626 B、`models.py` 8275 B，持久化在 `workflow_instances` / `workflow_tasks` 两张表上。

现状能力与缺口（已逐处核对源码）：

| 能力 | 现状 | 位置 |
|---|---|---|
| 流程实例与任务表 | 已有 | `workflow/models.py:51` `WorkflowInstance`、`:77` `WorkflowTask` |
| 审批 / 驳回 | 已有（`payload.decision == "reject"` 走终止分支） | `workflow/extended_service.py:1325-1331` |
| 节点流转 | 已有，基于边集合推导下一节点 | `workflow/extended_service.py:1188-1192` |
| 状态机 | 部分。业务对象（招聘流程）有 `allowed_transitions` 白名单 | `workflow/extended_service.py:436-444` |
| **撤销 / 退回 / 转办 / 加签** | **缺失** | — |
| **实例 `returned`（退回上一节点）状态** | **缺失**，当前只有终止类终态 | — |
| **任务状态机** | **缺失**，任务状态散落字符串 | — |
| **流转历史表** | **缺失**（全仓库无 `workflow_transitions`） | — |
| **节点停留统计** | **缺失** | — |
| **调度器** | **缺失**（`apps/api` 无 apscheduler / celery / cron 依赖） | `apps/api/pyproject.toml` |
| **流程画布** | **缺失**（`apps/web` 无 logicflow / reactflow / xyflow / antv 依赖） | `apps/web/package.json` |
| **通知通道** | **缺失**，未接入消息引擎 | 与 ADR-0006 关联 |

用户于 2026-10-24 要求做流程引擎调研并给出选型。调研结论：**Python 生态没有可直接投产的 BPMN 执行引擎**——Camunda 7 / Flowable 是 JVM 实现，Camunda 8 走 Zeebe，需要独立集群与运维面；其余 Python 项目多为教学级或长期停滞。因此真正的选择不是「用哪个 Python BPMN 库」，而是**继续自研，还是引入 JVM 运行时换现成引擎**。

## 决策

### 已定（与 P-09 无关的部分，立即执行）

- **不新建第二套流程引擎**。现有 `workflow` 模块继续作为唯一流程运行时。P0 批次是在现有引擎上**补齐语义**，不是重写。
- **审批动作语义固定**（D-095）：**撤销 = 终止、驳回 = 终止、退回 = 回到上一节点**。三者不混用，后端枚举与前端文案必须一致。
- **流转历史必须落库**：新增 `workflow_transitions` 表记录每次流转（实例、节点、动作、操作人、原因、时间、前后状态），作为审计与节点停留统计的唯一事实源，不依赖应用日志。
- **节点停留统计从流转历史推导**，不另建统计表，避免双份事实。
- **通知通道走平台消息引擎**（ADR-0006），流程模块不直接对接短信/邮件供应商。

### P-09 结论（2026-10-24 用户拍板）

- **选方案 A：在 Python 栈内继续演进现有手写引擎，不引入 JVM 运行时。**
- 落点：动作枚举 / 实例状态机 / 任务状态机 / `workflow_transitions` 流转历史表 / 节点停留统计 /
  调度器 / 通知出口，全部落在 `apps/api/src/hris/modules/workflow/`。
- **调度器不引入新依赖**：不用 APScheduler，改用**基于 asyncio 的调度循环**
  （`workflow/scheduler.py`，独立 Worker 进程运行）。理由：`apps/api` 容器镜像里没有该包，
  API 容器只挂载 `src/` 与 `alembic/`，加依赖要重建镜像，属于运维动作，不混在功能任务里。
- **通知通道本轮只留出口**：定义 `WorkflowNotifier` 抽象与默认空实现，
  消息引擎（ADR-0006）落地后注册真实实现；本轮不建消息表、不写站内信端点。
- **流程画布不在本轮范围**：不引入 LogicFlow / ReactFlow / 任何图形库。

## 备选方案

### 直接引入 Camunda 8 / Zeebe

- 优点：云原生、水平扩展能力强。
- 缺点：需要独立集群与运维（网关、Zeebe、Elasticsearch、Operate），与单机 Docker Compose 基线严重不符；流程定义与业务代码的耦合方式需要重学。
- 未采用原因：与部署形态不匹配，运维成本远超 coreHR 现阶段收益。

### 引入 Flowable（方案 B）

- 优点：BPMN 2.0 标准实现、引擎能力完备、社区成熟。
- 缺点：新增 JVM 运行时与 Java 服务；与现有 Python 业务库的事务边界分裂；已有流程实例与业务对象联动逻辑（`extended_service.py` 中大量按 `business_object_type` 分派的业务联动）需要重写与迁移。
- 未采用原因：**未排除**——若业务流程复杂度显著上升（并行网关、跨系统任务、补偿事务、流程版本回溯），B 的长期成本可能更低。但当前阶段引入异构运行时的代价确定收益不确定。

### 用 Python 第三方库（django-flow / viewflow 之类）承接

- 优点：上手快。
- 缺点：多数为教学或半成品，不含持久化、事务、并发与审计能力；与现有 FastAPI + SQLAlchemy 栈不匹配。
- 未采用原因：无法满足「流转历史可审计 + 状态机受控 + 与业务事务同库」的底线要求。

## 影响

- 方案 A：**不新增运行时、不新增中间件、不新增 Python 依赖**（本轮 P0 落地零新依赖），
  部署形态不变。风险集中在自研引擎的状态机严谨性，用显式迁移表 + 表驱动测试兜住。
- 方案 B：新增 JVM 服务与两套数据迁移（流程实例、任务、流转历史），部署、监控、备份、权限模型全部需要扩一套；且 `business_object_type` 的业务联动逻辑要在两套引擎语义间对齐。
- 两种方案下，`workflow_transitions` 表与动作枚举（`approve` / `reject` / `rollback` / `cancel` / `transfer` / `add_sign` / `return`）都是必需的，**可以先行实现**，不阻塞 P-09 的决策。
- 通知通道依赖 ADR-0006 的通道扩展决定（一期站内信）。本轮只留 `WorkflowNotifier` 抽象出口。

## 验证证据

- 模块现状核对：`apps/api/src/hris/modules/workflow/` 共 9 个文件（`extended_service.py` 92626 B、`models.py` 8275 B、`extended_api.py` 17526 B、`extended_schemas.py` 15413 B 等）。
- `grep` 全仓库 `workflow_transitions|WorkflowTransition` → **0 命中**，流转历史表确实不存在。
- `apps/api/pyproject.toml` 匹配 `apscheduler|celery|workflow|cron|temporal` → **0 命中**，无调度器依赖。
- `apps/web/package.json` 匹配 `logicflow|reactflow|react-flow|xyflow|antv|dagre|elkjs` → **0 命中**，无流程画布依赖。
- 现有状态机证据：`extended_service.py:436-444` 的 `allowed_transitions` 白名单覆盖 `active / screening / interview / offer / hired / rejected / withdrawn`。
- 审批语义证据：`extended_service.py:1325-1331` 的 `payload.decision == "reject"` 分支取消同级待办任务并置实例为 `rejected`（终止语义）。
- 调研结论与方案对比已落 `docs/review/pending-confirmations-2026-10-24.md` P-09。

### P0 落地后的现状（2026-10-24）

- 动作枚举与中文标签：`apps/api/src/hris/modules/workflow/actions.py`；
  状态机与迁移表：`workflow/state_machine.py`；
  流转历史与节点停留统计：`workflow/transitions.py`；
  通知出口：`workflow/notifier.py`；调度器：`workflow/scheduler.py`。
- 流转历史表：`workflow_transitions`（迁移 `f2i000000001`），只追加，由数据库触发器禁止 UPDATE / DELETE。
- 调度器零新依赖、独立 Worker 进程运行（`python -m hris.modules.workflow.scheduler`），
  事务级 advisory lock + `FOR UPDATE SKIP LOCKED` 保证多实例安全，阈值与开关走环境变量，默认关闭。
- 门禁：后端 `tests/integration` 151 passed；`alembic check` 在本任务范围内零漂移
  （仓库当前唯一漂移是并行任务 personnel corrections 的 `person_field_versions`，其迁移 `f2h000000001` 仍是占位）。
- 流程画布仍未引入（不在本轮范围）。

## 复审条件

- 流程需求出现并行网关、跨系统人工任务、补偿事务或流程版本回溯等自研引擎难以覆盖的能力。
- 现有引擎在并发审批、超时自动流转上的缺陷无法通过补齐语义解决。
- 部署形态从单机 Compose 改为多节点或引入 Kubernetes。
- 调度器单机 asyncio 循环不足以支撑时，再评估引入独立调度依赖（届时单独走运维动作）。
