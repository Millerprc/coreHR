# PLT-AUDIT-F001 操作日志

> 模块：PLT / Platform Kernel
> 能力域：PLT-AUDIT / 平台审计与数据治理
> 状态：`DRAFT`
> 版本：v0.1
> 产品Owner：MillerMax（产品决策人）
> 业务Owner：产品决策人 MillerMax 兼任（仓库内没有记录企业侧合规 / 内控业务负责人；依据 `docs/01-foundation/03-项目决策.md` D-066）
> 上级需求：[16-coreHR产品总体PRD](../01-foundation/16-coreHR产品总体PRD.md) §5.1 Platform Kernel 职责（账号权限、审计）；[16-coreHR产品总体PRD](../01-foundation/16-coreHR产品总体PRD.md) §7 质量门槛（可追溯）
> 依赖功能：无（本功能是审计读取的唯一入口，其它模块只写入审计行）
> 最后更新：2026-10-24

## 1. 背景与期望结果

- 当前问题：平台内核已经存在审计写入链路（`audit_logs` 表，`apps/api/src/hris/modules/workforce/models.py:992-1016`）与审计读取模块（`apps/api/src/hris/modules/platform/audit_api.py`、`audit_service.py`），前端也已有「数据治理 › 操作日志」宿主页（`apps/web/src/business/features/platform/AuditLogWorkspace.tsx`）。但该页面此前有两个问题：① 「操作人」下拉复用主管理员专用的 `GET /api/v1/platform/users`（权限码 `*`），而审计页自身要求 `DATA_GOVERNANCE_ADMIN`，治理管理员必然 403、下拉恒为空（待确认清单 P-13）；② 缺少按《模块功能需求文档规范》登记的功能需求文档与画板 ID，前端结构改动没有合法依据。
- 用户价值：合规与内控角色可以在一个只读页面上按时间范围、操作类型、对象类型、追踪 ID 与操作人定位关键写操作，按同一筛选条件导出 CSV 对账；下拉数据源可用后，筛选不再是空操作。
- 本功能完成后可观察的业务结果：
  1. 侧栏「数据治理 › 操作日志」进入宿主页，列出「时间 / 操作人 / 操作 / 对象类型 / 对象 ID / 追踪 ID / 来源 / 原因」八列（`AuditLogWorkspace.tsx:72-133`）。
  2. 「导出CSV」按当前筛选条件导出附件，CSV 列固定且不含 payload（`apps/api/src/hris/modules/platform/audit_service.py:19-29`）。
  3. 每次导出本身也是一条审计记录（`audit_service.py:250-283`）。
  4. 治理管理员与只读治理角色都能取到「操作人」下拉选项（`GET /api/v1/platform/audit/actors`，`audit_api.py:115-125`）。
- 不做本功能的影响：写操作没有统一的可追溯出口，问题追溯只能靠各业务模块自己的日志；合规问询时无法按筛选条件导出证据。

## 2. 范围

### 2.1 纳入范围

- 操作日志宿主页：页头与「导出CSV」操作、扁平筛选栏（时间范围 / 操作类型 / 对象类型 / 追踪 ID / 操作人 / 重置 / 查询）、日志表格与服务端分页（`AuditLogWorkspace.tsx:219-320`）。
- 筛选：时间范围（闭区间）、操作类型（由后端聚合的 action 下拉）、对象类型（自由文本）、追踪 ID（自由文本）、操作人（账号下拉）。
- 导出：按当前已生效筛选条件导出 CSV 附件（`AuditLogWorkspace.tsx:201-217`；后端 `audit_api.py:128-170`）。
- 单条审计日志详情接口 `GET /api/v1/platform/audit-logs/{id}`（后端已实现，含 payload；前端当前没有入口，见 §18 Q-03）。
- 审计专用「操作人」只读端点 `GET /api/v1/platform/audit/actors`（`audit_api.py:115-125`）。
- 本功能的 Pencil 画板登记（见 §10.4）。

### 2.2 不纳入范围

- 审计日志的修改与删除：日志只写不读改，本模块没有任何写接口（`audit_api.py` 只定义 4 组 GET）。
- 审计日志的详情抽屉：后端已有详情端点，但前端没有入口（待确认清单 P-02「操作日志是否需要『详情』抽屉看单条完整上下文」），见 §18 Q-03。
- 审计日志的保留期与归档策略：本模块不实现归档或清理，按审计模块既有保留策略执行。
- 其它模块的审计写入契约（各模块 `action` / `object_type` 取值字典）：本功能只读取，不定义取值全集。
- 数据治理（主数据导入导出）与账号与权限工作区的页面需求：各自独立成功能文档。

### 2.3 假设与约束

| ID | 状态 | 内容 | 假设不成立时的处理 |
|---|---|---|---|
| ASM-01 | `CONFIRMED` | 审计数据敏感，读取不降级为 `DATA_GOVERNANCE_VIEW`，列表 / 动作聚合 / 导出 / 详情四个端点一律要求 `DATA_GOVERNANCE_ADMIN`（`audit_api.py:23-27`） | 若产品要求只读治理角色也能看日志正文，需要单独立项并同步 §9 权限表与 §13 脱敏结论 |
| ASM-02 | `CONFIRMED` | 「操作人」下拉是审计专用的**辅助数据源**，权限比日志正文更宽：持有 `DATA_GOVERNANCE_VIEW` 或 `DATA_GOVERNANCE_ADMIN` 任一即可（`audit_api.py:29-35`） | 若要进一步收紧，只需调整 `require_any_permission` 的实参，不影响前端 |
| ASM-03 | `CONFIRMED` | 后端 `action` / `object_type` / `source` 是原始代码，前端不做中文映射（`AuditLogWorkspace.tsx:67-71` 的 Requirement 注释；画板登记表 `rawValueNote`） | 需要中文映射时必须先扩充后端取值字典，不得在前端硬编码猜测语义 |
| ASM-04 | `PENDING` | 企业侧的审计保留期、归档周期与合规取证要求尚未提供 | 本功能不实现归档与清理，保留期按平台既有策略执行，见 §18 Q-04 |
| ASM-05 | `CONFIRMED` | 未带时区的时间按 UTC 解释；服务端筛选为闭区间（`audit_service.py:91-97`、`:118-134`） | 客户端与服务端时区口径差异按 §18 Q-06 处理 |

## 3. 参与者、权限边界和业务场景

| 参与者 | 目标 | 前置权限 | 数据范围 |
|---|---|---|---|
| 主管理员 | 查看与导出全部审计日志 | `*`（`apps/api/src/hris/modules/platform/dependencies.py:90` 对 `*` 短路放行） | 全部审计日志；本模块无行级数据范围 |
| 数据治理管理员 | 查看与导出审计日志 | `DATA_GOVERNANCE_ADMIN`（`audit_api.py:23-27`） | 全部审计日志；本模块无行级数据范围 |
| 只读治理角色 | 取到「操作人」下拉候选项 | `DATA_GOVERNANCE_VIEW`（`audit_api.py:29-35`） | 只能读账号 id / 显示名 / 登录名，不能读日志正文 |
| 未登录 / 会话失效访问者 | —— | 无有效会话 | 401 `AUTHENTICATION_REQUIRED` / `SESSION_INVALID`（`dependencies.py:32`、`:47`） |

场景边界说明：本功能只有一个业务结果——「按条件检索并导出平台写操作记录」。查看与导出是同一结果的不同动作深度（导出复用同一筛选条件），不拆成两个功能。

## 4. 名词与依赖

| 名词/依赖 | 定义或引用 | 数据所有者 |
|---|---|---|
| 审计日志 | `audit_logs` 表的一行，记录一次写操作 | Workforce Core（`apps/api/src/hris/modules/workforce/models.py:992-1016`） |
| 操作（action） | 写操作的代码标识，如 `platform.audit_logs.export` | 各业务模块各自定义，本功能只读取 |
| 对象类型（object_type） | 被操作对象的类型标识，如 `person`、`reporting_relation` | 各业务模块各自定义，本功能只读取 |
| 追踪 ID（trace_id） | 一次请求的关联标识，写入审计行并随响应返回 | 平台内核（`apps/api/src/hris/core/middleware.py` 的 `TraceIdMiddleware`） |
| 来源（source） | 写入来源，当前实现统一为 `api` | 各业务模块各自定义 |
| 操作人（actor） | 触发操作的用户账号，落在 `user_accounts` 表 | Platform Kernel（`apps/api/src/hris/modules/platform/models.py:10-20`） |
| 载荷（before_payload / after_payload） | 操作前后的业务快照，只在单条详情端点返回 | Workforce Core（`models.py:1006-1015`） |

## 5. 用户故事

### PLT-AUDIT-F001-US01 按条件检索操作日志

作为数据治理管理员，我希望按时间范围、操作类型、对象类型、追踪 ID 与操作人组合筛选审计日志，从而定位一次可疑写操作。

- 触发条件：进入「数据治理 › 操作日志」，或修改筛选区后点击「查询」。
- 前置条件：账号具备 `DATA_GOVERNANCE_ADMIN` 或 `*`；后端 `audit_logs` 已有数据。
- 主路径：页面加载 → 并行请求 `GET /api/v1/platform/audit-logs?page=1&page_size=20`、`GET /api/v1/platform/audit-logs/actions`、`GET /api/v1/platform/audit/actors`（`AuditLogWorkspace.tsx:153-178`）→ 表格按「时间 / 操作人 / 操作 / 对象类型 / 对象 ID / 追踪 ID / 来源 / 原因」八列展示，操作列是 processing 蓝 Tag、来源列是 warning 橙 Tag，`action` / `object_type` / `source` 保留后端原始代码（`:67-133`）。
- 结束状态：表格显示命中记录；无数据时显示空态「暂无符合条件的操作日志」（`:302`）；日志接口 403 时页面顶部显示错误条（`:161`）。

### PLT-AUDIT-F001-US02 导出当前筛选结果

作为数据治理管理员，我希望把当前筛选条件下的日志导出为 CSV，从而完成合规对账与离线取证。

- 触发条件：点击页头「导出CSV」按钮（仅 `canAdmin` 可见，`:224-226`）。
- 前置条件：账号具备 `DATA_GOVERNANCE_ADMIN` 或 `*`；页面上已有生效的筛选条件。
- 主路径：点击「导出CSV」→ 前端请求 `GET /api/v1/platform/audit-logs/export?<当前筛选>`（`audit-api.ts:200-204`）→ 服务端按同一套筛选条件取数，写入固定列的 CSV（`audit_service.py:17-29`）→ 浏览器以 Blob 触发下载，文件名 `audit-logs.csv`（`AuditLogWorkspace.tsx:201-217`；`audit_service.py:286`）。
- 结束状态：浏览器下载 `audit-logs.csv`；导出同时在 `audit_logs` 留下一条 `action=platform.audit_logs.export` 的记录（`audit_service.py:250-283`）。

### PLT-AUDIT-F001-US03 按操作人筛选

作为数据治理管理员，我希望按操作人筛选日志，从而查清某个账号做过的所有写操作。

- 触发条件：在「操作人」筛选下拉中选择一个账号。
- 前置条件：账号具备 `DATA_GOVERNANCE_ADMIN` 或 `*`；候选列表来自 `GET /api/v1/platform/audit/actors`。
- 主路径：下拉展开显示账号显示名（按 `display_name` 升序，`audit_service.py:208-232`）→ 选择后点击「查询」→ 请求带 `actor_id` 参数（`audit-api.ts:156-169`）→ 表格只显示该操作人的记录。
- 结束状态：列表被过滤为该操作人的记录；下拉可清空（`allowClear`，`AuditLogWorkspace.tsx:287`）。

### PLT-AUDIT-F001-US04 重置筛选

作为数据治理管理员，我希望一键清空全部筛选条件，从而回到全量视图。

- 触发条件：点击筛选栏「重置」。
- 前置条件：无。
- 主路径：点击「重置」→ 草稿与生效筛选同时清空、页码回到第 1 页（`AuditLogWorkspace.tsx:195-199`）。
- 结束状态：列表回到无条件全量视图（与职位管理页「重置」不清空生效日期的语义不同，见 BR010）。

## 6. 业务流程与状态机

```text
业务模块写操作
  └─► 同事务写入 audit_logs 一行（action / object_type / object_id / reason / payload / trace_id / actor_id）
        │
        ├─► 列表读取（DATA_GOVERNANCE_ADMIN）：按筛选条件 + 分页返回，不含 payload
        ├─► 详情读取（DATA_GOVERNANCE_ADMIN）：返回单条含 payload
        ├─► 导出（DATA_GOVERNANCE_ADMIN）：按同一筛选取数写 CSV，并再写一条导出审计
        └─► 操作人下拉（DATA_GOVERNANCE_VIEW 或 DATA_GOVERNANCE_ADMIN）：只读账号清单
```

| 当前状态 | 操作 | 条件 | 下一状态 | 失败结果 |
|---|---|---|---|---|
| 无筛选条件 | `GET /audit-logs` | 权限满足 | 返回第 1 页，默认每页 20 条 | 403 `PERMISSION_DENIED`；401 会话无效 |
| 时间区间非法 | `GET /audit-logs?occurred_from>occurred_to` | 起点晚于终点 | 请求被拒 | 422 `AUDIT_TIME_RANGE_INVALID` |
| 有筛选条件 | `GET /audit-logs/export` | 权限满足且结果 ≤ 50000 行 | 返回 CSV 附件 | 422 `AUDIT_EXPORT_TOO_LARGE`；403 |
| 任意读取 | `GET /audit/actors` | 持有治理查看或治理管理权限 | 返回账号清单 | 403 `PERMISSION_DENIED` |
| 任意读取 | `GET /audit-logs/{id}` | 权限满足且记录存在 | 返回含 payload 的单条详情 | 404 `AUDIT_LOG_NOT_FOUND`；403 |

## 7. 业务规则

状态约定：`CONFIRMED` 表示该规则已有已确认决策、已交付能力或服务端强制的合同约束支撑；`PENDING` 表示该规则取决于尚未签字的产品决策，开发者不得自行猜测；`NOT_APPLICABLE` 表示经核查本功能不涉及，并写明依据。

| ID | 状态 | 规则 | 规则来源 | 验证方式 |
|---|---|---|---|---|
| PLT-AUDIT-F001-BR001 | `CONFIRMED` | 审计数据敏感，列表、动作聚合、导出与单条详情四个端点一律要求 `DATA_GOVERNANCE_ADMIN`，读取不降级为 `DATA_GOVERNANCE_VIEW` | 实现 `audit_api.py:23-27`、`:58-73`、`:104-112`、`:128-149`、`:177-198` | AC006 |
| PLT-AUDIT-F001-BR002 | `CONFIRMED` | 列表响应不返回 `before_payload` / `after_payload`；payload 只在单条详情端点返回 | 实现 `audit_service.py:74-75`、`:288-309`；前端类型也没有 payload 字段（`audit-api.ts:29-40`） | AC007、AC008 |
| PLT-AUDIT-F001-BR003 | `CONFIRMED` | 列表默认按发生时间倒序，同一时间按主键倒序；翻页稳定 | 实现 `audit_service.py:172-173` | AC001 |
| PLT-AUDIT-F001-BR004 | `CONFIRMED` | 时间区间是闭区间过滤：`occurred_at >= occurred_from` 且 `occurred_at <= occurred_to`；起点晚于终点时返回 422 `AUDIT_TIME_RANGE_INVALID` | 实现 `audit_service.py:117-134`、`:315-316` | AC002、AC003 |
| PLT-AUDIT-F001-BR005 | `CONFIRMED` | 未带时区的时间按 UTC 解释，避免服务端时区导致区间漂移 | 实现 `audit_service.py:91-97` | AC002 |
| PLT-AUDIT-F001-BR006 | `CONFIRMED` | 「操作类型」下拉来自后端按现有数据聚合的 action 计数，条目多的排在前面 | 实现 `audit_service.py:180-193`；前端 `AuditLogWorkspace.tsx:180-183` | AC004 |
| PLT-AUDIT-F001-BR007 | `CONFIRMED` | 导出 CSV 列固定为 `occurred_at / actor_name / action / object_type / object_id / trace_id / reason / source`，不含 payload 及其字段名 | 实现 `audit_service.py:17-29` | AC009 |
| PLT-AUDIT-F001-BR008 | `CONFIRMED` | 单次导出上限 50000 行，超出时返回 422 `AUDIT_EXPORT_TOO_LARGE` 并提示缩小筛选范围 | 实现 `audit_service.py:17`、`:225-232` | AC010 |
| PLT-AUDIT-F001-BR009 | `CONFIRMED` | 导出本身必须被审计：写一条 `action=platform.audit_logs.export` 的记录，`before_payload` 为空，`after_payload` 只记录行数与筛选条件，不记录任何 payload 内容 | 实现 `audit_service.py:250-283` | AC011 |
| PLT-AUDIT-F001-BR010 | `CONFIRMED` | 「重置」清空全部筛选条件（含时间范围、操作类型、对象类型、追踪 ID、操作人）并回到第 1 页 | 实现 `AuditLogWorkspace.tsx:195-199`；画板登记表 `implementationDeltas` 第 1 条 | AC012 |
| PLT-AUDIT-F001-BR011 | `CONFIRMED` | `action` / `object_type` / `source` 一律保留后端原始代码，前端不做中文映射 | 实现 `AuditLogWorkspace.tsx:67-71`；画板登记表 `rawValueNote` | AC004 |
| PLT-AUDIT-F001-BR012 | `CONFIRMED` | 操作列固定用 processing 蓝 Tag、来源列固定用 warning 橙 Tag，两列一眼可辨 | 实现 `AuditLogWorkspace.tsx:67-71`、`:85-118`；D-091 | AC004 |
| PLT-AUDIT-F001-BR013 | `CONFIRMED` | 「操作人」下拉必须使用审计专用只读端点 `GET /api/v1/platform/audit/actors`，不得复用权限码为 `*` 的 `/api/v1/platform/users` | 决策：待确认清单 P-13（方案 b，已决策）；实现 `audit_api.py:29-35`、`:115-125`；前端 `audit-api.ts:193-205` | AC013、AC014、AC015 |
| PLT-AUDIT-F001-BR014 | `CONFIRMED` | 操作人端点只返回 `id`、`display_name`、`username` 三个字段，按 `display_name` 升序；不返回邮箱、手机号等个人联系方式，也不返回账号状态与角色 | 实现 `audit_service.py:71-76`、`:208-232` | AC014 |
| PLT-AUDIT-F001-BR015 | `CONFIRMED` | 操作人端点不按账号状态过滤：审计记录可能引用已停用账号的历史操作，过滤会漏掉操作人 | 实现 `audit_service.py:216` | AC014 |
| PLT-AUDIT-F001-BR016 | `PENDING` | 操作日志 Tag 的严重度分级：画板要求统一蓝 / 橙，原实现按动作名分级（delete 红 / create 绿）；本轮按画板统一蓝橙，红绿严重度消失 | 现状实现 `AuditLogWorkspace.tsx:85-118`；待确认清单 P-23 | 见 §18 Q-05 |
| PLT-AUDIT-F001-BR017 | `PENDING` | 是否需要单条日志的详情抽屉：后端详情端点已存在（含 payload），前端无入口 | 待确认清单 P-02 | 见 §18 Q-03 |
| PLT-AUDIT-F001-BR018 | `PENDING` | 企业侧的审计保留期与归档周期尚未提供 | 依据 `docs/01-foundation/99-待确认问题.md` 与本轮输入包缺口 | 见 §18 Q-04 |

规则写法自查（对照规范 §8.1 / §8.2）：所有 `CONFIRMED` 规则都写明了适用对象与时间点、条件与唯一性维度、成功与拒绝结果、敏感数据边界，不使用「合理处理」「一般情况」「尽量」等表述；不包含未说明配置范围的「支持灵活配置」、未说明幂等与最终状态的「失败后重试」、未说明下游与历史保留的「可以回退」。

## 8. 数据要求

### 8.1 数据所有权与关系

- 本功能拥有的数据：**无**。本功能是只读功能，不拥有任何表；它读 `audit_logs` 与 `user_accounts`，只向 `audit_logs` 追加导出审计行。
- 引用但不拥有的数据：
  - `audit_logs`（审计日志）：归属 Workforce Core（`apps/api/src/hris/modules/workforce/models.py:992-1016`）。
  - `user_accounts`（账号清单）：归属 Platform Kernel（`apps/api/src/hris/modules/platform/models.py:10-20`）。
- 业务唯一键：
  - `audit_logs.id` 是稳定身份 UUID（`UuidPrimaryKeyMixin`）。
  - `user_accounts.username` 全局唯一（`models.py:13`）。
  - 审计日志**没有**业务唯一键——同一次操作被重复写入是允许的，本模块不做去重。
- 有效日期/版本/快照要求：
  - 本模块不产生版本数据。
  - 时间字段 `occurred_at` 是带时区的时间戳（`models.py:995-999`），按 UTC 解释。
  - 快照：`before_payload` / `after_payload` 就是操作前后的业务快照，本模块只透传不解释。

### 8.2 字段合同

「来源」列中的文件均位于 `apps/api/src/hris/modules/platform/audit_service.py`，行号在括号内注明。

| ID | 字段 | 类型/格式 | 必填 | 来源 | 默认值 | 校验 | 敏感级别 | 历史策略 |
|---|---|---|---|---|---|---|---|---|
| PLT-AUDIT-F001-DAT001 | `id` | UUID | 响应只读 | `AuditLogResponse.id`（:36） | — | — | 非敏感 | 稳定身份，永久保留 |
| PLT-AUDIT-F001-DAT002 | `occurred_at` | datetime（带时区，UTC） | 响应只读 | `AuditLogResponse.occurred_at`（:37） | 写入时取 `datetime.now(UTC)`（`audit_service.py:251`） | 筛选时按闭区间比较 | 非敏感 | 永久保留 |
| PLT-AUDIT-F001-DAT003 | `actor_id` | UUID，可空 | 响应只读 | `AuditLogResponse.actor_id`（:38） | 可空 | 外键语义上指向 `user_accounts.id`，但**没有**数据库外键约束（`models.py:1000`） | 非敏感 | 永久保留 |
| PLT-AUDIT-F001-DAT004 | `actor_name` | string(200)，可空 | 响应只读 | `AuditLogResponse.actor_name`（:40） | 联表不到时为 `null` | 由 `user_accounts.display_name` 左连接得出（`audit_service.py:288-309`） | 个人信息（姓名） | 实时联表，不落库快照 |
| PLT-AUDIT-F001-DAT005 | `trace_id` | string(100) | 响应只读 | `AuditLogResponse.trace_id`（:41） | 写入时取请求头关联的 trace id | 筛选时精确匹配 | 非敏感 | 永久保留 |
| PLT-AUDIT-F001-DAT006 | `action` | string(100) | 响应只读 | `AuditLogResponse.action`（:42） | 由写入方定义 | 筛选时精确匹配；下拉值来自后端聚合 | 非敏感 | 永久保留 |
| PLT-AUDIT-F001-DAT007 | `object_type` | string(50) | 响应只读 | `AuditLogResponse.object_type`（:43） | 由写入方定义 | 筛选时精确匹配 | 非敏感 | 永久保留 |
| PLT-AUDIT-F001-DAT008 | `object_id` | UUID，可空 | 响应只读 | `AuditLogResponse.object_id`（:44） | 可空 | 筛选时精确匹配 | 非敏感 | 永久保留 |
| PLT-AUDIT-F001-DAT009 | `reason` | string(500)，可空 | 响应只读 | `AuditLogResponse.reason`（:45） | 可空 | 前端以 Tooltip + 省略号展示，超长不换行（`AuditLogWorkspace.tsx:119-132`） | 可能含业务原因文本 | 永久保留 |
| PLT-AUDIT-F001-DAT010 | `source` | string(50) | 响应只读 | `AuditLogResponse.source`（:46） | 当前写入方统一为 `api` | 筛选时精确匹配 | 非敏感 | 永久保留 |
| PLT-AUDIT-F001-DAT011 | `before_payload` | JSON 对象 | **仅详情端点返回** | `AuditLogDetailResponse.before_payload`（:51） | `{}` | 列表与导出均不返回 | 高敏感（可能含业务快照） | 永久保留；导出不含 |
| PLT-AUDIT-F001-DAT012 | `after_payload` | JSON 对象 | **仅详情端点返回** | `AuditLogDetailResponse.after_payload`（:52） | `{}` | 同上 | 高敏感 | 同上 |
| PLT-AUDIT-F001-DAT013 | `id`（操作人） | UUID | 响应只读 | `AuditActorResponse.id`（:74） | — | — | 非敏感 | — |
| PLT-AUDIT-F001-DAT014 | `display_name`（操作人） | string(200) | 响应只读 | `AuditActorResponse.display_name`（:75） | — | 按该字段升序排序 | 个人信息（姓名） | — |
| PLT-AUDIT-F001-DAT015 | `username`（操作人） | string(100) | 响应只读 | `AuditActorResponse.username`（:76） | — | 全局唯一（`models.py:13`） | 登录标识 | — |

### 8.3 数据生命周期

- 创建：审计行由各业务模块在**自己的事务内**创建；本功能不创建业务数据，只在导出时追加一行导出审计（`audit_service.py:250-283`）。
- 修改/更正：`NOT_APPLICABLE`。依据：本模块没有更新审计行的接口（`audit_api.py` 只定义 4 组 GET），审计行一旦写入不可修改。
- 生效/失效：`NOT_APPLICABLE`。依据：审计行没有生效区间语义，写入即生效（`models.py:992-1016` 无 `effective_from` / `effective_to` 列）。
- 保留：审计行永久保留，本模块无删除端点，也未实现归档或清理（保留期待确认，见 BR018 / §18 Q-04）。
- 删除：`NOT_APPLICABLE`。依据：本模块只有 GET 端点，物理删除与归档清理都不在本功能范围。
- 迁移与兼容：本轮无结构变更；新增的 `GET /api/v1/platform/audit/actors` 只读现有 `user_accounts`，不涉及迁移。

## 9. 权限要求

| ID | 状态 | 参与者 | 功能/动作权限 | 数据范围 | 字段权限 | 拒绝结果 |
|---|---|---|---|---|---|---|
| PLT-AUDIT-F001-PERM001 | `CONFIRMED` | 持有 `DATA_GOVERNANCE_ADMIN` 或 `*` 的账号 | 查看审计日志列表（`GET /api/v1/platform/audit-logs`） | 全部审计日志，无行级过滤 | 全部列表字段（DAT001–DAT010）；**不含** DAT011、DAT012 | 403 `PERMISSION_DENIED`「没有执行此操作的权限」（`dependencies.py:119`）；前端显示顶部错误条「操作日志加载失败」（`AuditLogWorkspace.tsx:161`） |
| PLT-AUDIT-F001-PERM002 | `CONFIRMED` | 同上 | 读取动作聚合（`GET /api/v1/platform/audit-logs/actions`） | 全部 action 计数 | 只返回 `code` 与 `count`（`audit_service.py:62-68`） | 同 PERM001；前端取不到时退化为空下拉（`AuditLogWorkspace.tsx:172-173`） |
| PLT-AUDIT-F001-PERM003 | `CONFIRMED` | 同上 | 导出 CSV（`GET /api/v1/platform/audit-logs/export`） | 与列表同一套筛选条件 | 只返回固定 8 列，不含 payload（`audit_service.py:19-29`） | 同 PERM001；无权限时前端不渲染「导出CSV」按钮（`AuditLogWorkspace.tsx:224-226`） |
| PLT-AUDIT-F001-PERM004 | `CONFIRMED` | 同上 | 查看单条详情（`GET /api/v1/platform/audit-logs/{id}`） | 单条 | 含 DAT001–DAT012 | 同 PERM001；记录不存在时 404 `AUDIT_LOG_NOT_FOUND`（`audit_service.py:198-205`） |
| PLT-AUDIT-F001-PERM005 | `CONFIRMED` | 持有 `DATA_GOVERNANCE_VIEW` 或 `DATA_GOVERNANCE_ADMIN` 或 `*` 的账号 | 读取「操作人」下拉数据源（`GET /api/v1/platform/audit/actors`） | 全部账号，无行级过滤 | 只返回 DAT013–DAT015；不返回账号状态、角色、邮箱、手机号 | 403 `PERMISSION_DENIED`；前端取不到时下拉退化为空（`AuditLogWorkspace.tsx:175-176`） |
| PLT-AUDIT-F001-PERM006 | `CONFIRMED` | 持有 `DATA_GOVERNANCE_ADMIN` 或 `*` 的账号 | 侧栏入口可见性：侧栏「数据治理 › 操作日志」按 `DATA_GOVERNANCE_ADMIN` 过滤 | — | — | 无权限时侧栏入口不出现（`apps/web/src/business/navigation.ts:69-74`、`AppShell.tsx:184-187` 的 `visibleWorkspaces` 过滤） |
| PLT-AUDIT-F001-PERM007 | `CONFIRMED` | 持有 `DATA_GOVERNANCE_VIEW` 的只读治理角色 | 可以进入「数据治理」工作区（侧栏按 `DATA_GOVERNANCE_VIEW` 过滤），但操作日志页的列表接口会 403 | — | — | 进入操作日志页后列表请求 403，页面显示顶部错误条（见 PERM001） |
| PLT-AUDIT-F001-PERM008 | `CONFIRMED` | 未登录或会话失效账号 | 任何接口 | — | — | 401 `AUTHENTICATION_REQUIRED`「需要登录」或 `SESSION_INVALID`「登录状态无效或已过期」（`dependencies.py:32`、`:47`） |

代办与代理说明：

- 主管理员（持 `*`）可以直接执行全部读操作（`dependencies.py:118` 对 `*` 短路放行）。
- 本功能**没有代办 / 代理身份机制**：审计只记录操作者本人 `actor_id`，没有 `on_behalf_of` 字段（`models.py:992-1016`）。
- 未知范围默认拒绝：权限判定为「不具备所需权限码即拒绝」，不做任何隐式放行（`dependencies.py:117-120`）。

## 10. 交互与页面要求

### 10.1 入口与可见性

- 菜单/页面/按钮：
  - 侧栏：「数据治理 › 操作日志」（`navigation.ts:69-74`）。
  - 面包屑：「数据治理 / 操作日志」。
  - 页内操作：页头次按钮「导出CSV」（`AuditLogWorkspace.tsx:224-226`）；筛选栏「重置」「查询」（`:233-238`）。
  - 页面标题与副标题（宿主页页头，逐字复用实现）：标题「操作日志」；副标题「记录平台内的关键写操作，供合规核查与问题追溯使用。日志只读，不提供修改或删除入口。」（`AuditLogWorkspace.tsx:222-223`）。
  - 筛选区文案：标签「时间范围」「操作类型」「对象类型」「追踪 ID」「操作人」（`:240`、`:248`、`:262`、`:271`、`:280`）；占位符「开始日期 / 结束日期」「全部操作」「例如 user」「例如 trace-0001」「全部操作人」。
- 无权限或未启用模块时：侧栏不渲染该入口（`navigation.ts:69-74`）；已进入页面但接口 403 时显示顶部可关闭错误条，不做整页拒绝态（本页面的 403 兜底是错误条而非 `WorkspaceDenied`，见 §10.2）。
- 宿主页：列表。数据治理分组下的独立宿主页，无页内页签（画板登记表 `tabs: []`）。
- 交互载体：`NOT_APPLICABLE`。审计日志是只读宿主页：筛选、分页与导出都在当前标签页内完成，不引入 Modal / Drawer / 新标签页等额外载体（`AuditLogWorkspace.tsx:136-139` 的注释；[Ant Design 页面与交互载体规范](../design/antd-page-interaction-standard.md)）。单条详情抽屉属待确认项，见 §18 Q-03。
- 选择理由：审计日志没有表单、没有写操作，不满足 Modal / Drawer / NEW_TAB 任一载体的适用前提；规范 §10.1 要求「必须且只能选择一个主载体」，本功能的载体是宿主页本身，如后续按 P-02 决定加详情抽屉，需同步在本节补登 `DRAWER`。
- 路由或深链接：宿主页为 hash 路由 `#audit`（`navigation.ts:126-132` 的 `workspaceFromHash` 统一处理）；刷新后回到同一受权资源。
- Pencil源文件：`C:\Users\83289\Documents\HRMS\coreHR.pen`（Pencil 2.17）。
- 画板ID/名称/原型版本：`laZ5d` / 「操作日志 · 数据治理 v1.0」 / `v1.0`（画板 1440×960）。
- 原型状态：`PROTOTYPE_APPROVED`。2026-10-24 产品决策人确认全部画板并签字，规范 §10.1 的状态枚举中对应 `PROTOTYPE_APPROVED`；按规范 §10.2 与 D-087，前端开发门禁已解除，本功能可按画板继续开发（见 §19 T002 状态与 §18 Q-01）。

### 10.2 页面状态

| 状态 | 页面表现 | 可执行操作 |
|---|---|---|
| 首次/空数据 | 表格空态「暂无符合条件的操作日志」（`AuditLogWorkspace.tsx:302`），由 `DataTable` 的 `emptyText` 承载；分页器与计数行显示「共 0 条操作日志」 | 调整筛选条件、点击「查询」 |
| 加载中 | 表格 `loading` 态（`AuditLogWorkspace.tsx:297`）；筛选区保持可用 | 等待；可修改筛选草稿 |
| 正常 | 筛选栏 + 表格 + 分页器，计数行与分页器总数一致（如「共 128 条操作日志」出现两处）；分页支持每页 20 / 50 / 100 条 | 筛选、查询、重置、翻页、改每页条数、导出 |
| 部分失败 | 「操作类型」或「操作人」下拉取数失败时静默退化为空下拉，不影响表格（`AuditLogWorkspace.tsx:169-178`）；列表成功但导出失败时显示顶部错误条「操作日志导出失败」（`:213`） | 关闭错误条、重新导出 |
| 完全失败 | 列表接口返回 403 或其它错误时显示顶部可关闭错误条「操作日志加载失败」（`:161`），表格保持空 | 关闭错误条或联系管理员 |
| 无权限 | 侧栏入口不渲染；已打开页面时列表请求 403 → 顶部错误条 | 退出登录或联系主管理员 |

### 10.3 表单与确认

- 字段顺序与联动：
  - 筛选栏顺序：「时间范围」→「操作类型」→「对象类型」→「追踪 ID」→「操作人」→ 右侧「重置」「查询」（`AuditLogWorkspace.tsx:230-294`）。
  - 筛选是**草稿式**：改值不立即查询，点「查询」才生效（`AuditLogWorkspace.tsx:190-193`）；「重置」清空全部筛选并回到第 1 页（`:195-199`）。
  - 时间范围用 antd `RangePicker`，格式 `YYYY-MM-DD`，提交时换算为当天 00:00:00.000 到当天 23:59:59.999 的 ISO 串（`AuditLogWorkspace.tsx:54-64`）。
- 即时校验与提交校验：本页无写操作表单，筛选无客户端校验；查询参数非法（如 `page_size > 200`）由后端返回 422 `REQUEST_VALIDATION_FAILED`（`apps/api/src/hris/core/errors.py:41-61`）。
- 高风险二次确认：`NOT_APPLICABLE`。依据：本功能是只读的，唯一写操作是追加导出审计行，该行由服务端在导出请求内自动写入，用户不通过页面修改任何数据（`audit_service.py:250-283`）。导出本身没有二次确认，是否需要确认见 §18 Q-07。
- 成功反馈与下一步：导出成功后浏览器直接下载 `audit-logs.csv`，无额外提示条（`AuditLogWorkspace.tsx:201-217`）；失败时显示顶部错误条。
- 打开、关闭和焦点返回：`NOT_APPLICABLE`。依据：本功能不使用任何弹窗或抽屉载体（§10.1），无打开 / 关闭 / 焦点返回行为需要描述。
- 未保存变更与重复提交保护：导出按钮在导出期间进入 `loading` 态，阻止重复提交（`AuditLogWorkspace.tsx:225`）；筛选草稿不发起请求，无并发写入风险。
- 弹窗关闭后表单重置或保留策略：`NOT_APPLICABLE`。依据：本功能没有弹窗；筛选草稿由「重置」显式清空（`AuditLogWorkspace.tsx:196`）。

### 10.4 Pencil原型登记

| 原型ID | 页面/交互载体 | Pencil文件 | 画板ID与名称 | 版本 | 状态 | 批准人/日期 |
|---|---|---|---|---|---|---|
| PLT-AUDIT-F001-PROT001 | 宿主页（画板 `laZ5d` 1440×960；本功能不引入 Modal / Drawer / 新标签页，单条详情抽屉尚未单独出画板） | `C:\Users\83289\Documents\HRMS\coreHR.pen` | 画板ID `laZ5d`；画板名称「操作日志 · 数据治理 v1.0」 | v1.0 | `PROTOTYPE_APPROVED` | 2026-10-24 产品决策人签字确认（见 §18 Q-01 / §20） |

登记说明（按事实记录，不做美化）：

- 画板状态 `PROTOTYPE_APPROVED`（2026-10-24 产品决策人签字确认）依据 `docs/review/pen-prototype-spec-2026-10-24.md` 头部状态标注与 §7 后续动作第 3 条；预览图为 `docs/review/pen-prototypes/03-操作日志.png`。
- 画板与实现的有意差异已登记在画板登记表 `implementationDeltas`：第 1 条「『重置』清空全部筛选（与职位页语义不同）」对应 BR010；第 2 条「action / object_type / source 保留英文原值」对应 BR011。
- 画板规格中的 `filters` 列出 6 项筛选、实际实现同样是 6 项（时间范围、操作类型、对象类型、追踪 ID、操作人 + 重置 / 查询 按钮），逐项对应（`AuditLogWorkspace.tsx:230-294`）。
- 规范 §10.4 要求「显著不同的加载、空数据、失败、无权限和冲突状态应在原型中可Review」，这些状态目前只存在于实现（`AuditLogWorkspace.tsx:295-319`），没有对应的 Pencil 画板——见 §18 Q-01。

## 11. API与事件合同

### 11.1 同步API

| ID | 方法与路径 | 调用者 | 请求摘要 | 响应摘要 | 权限 | 幂等 | 事务边界 |
|---|---|---|---|---|---|---|---|
| PLT-AUDIT-F001-API001 | `GET /api/v1/platform/audit-logs`（`audit_api.py:58-101`） | 操作日志宿主页 | 查询参数：`occurred_from`、`occurred_to`（datetime，可选）、`actor_id`（UUID，可选）、`action`（≤100）、`object_type`（≤50）、`object_id`（UUID）、`trace_id`（≤100）、`page`（≥1，缺省 1）、`page_size`（1–200，缺省 20） | `PageResponse`：`items`（`AuditLogResponse` 列表）、`total`、`page`、`page_size` | `DATA_GOVERNANCE_ADMIN`；`*` 放行 | 天然幂等（只读） | 单请求单事务，`get_db` 在响应前提交（`apps/api/src/hris/core/database.py:18-25`） |
| PLT-AUDIT-F001-API002 | `GET /api/v1/platform/audit-logs/actions`（`audit_api.py:104-112`） | 操作日志宿主页「操作类型」下拉 | 无查询参数 | `ActionListResponse`：`items`（`{code, count}`） | `DATA_GOVERNANCE_ADMIN`；`*` 放行 | 天然幂等 | 单请求单事务 |
| PLT-AUDIT-F001-API003 | `GET /api/v1/platform/audit-logs/export`（`audit_api.py:128-170`） | 操作日志宿主页「导出CSV」 | 与 API001 相同的筛选参数，**不分页** | `text/csv; charset=utf-8` 附件；响应头 `Content-Disposition: attachment; filename="audit-logs.csv"`、`X-Export-Row-Count` | `DATA_GOVERNANCE_ADMIN`；`*` 放行 | 幂等边界：重复导出每次都会新增一条导出审计行，CSV 内容按数据现状返回 | 单请求单事务；CSV 生成与导出审计行同事务 |
| PLT-AUDIT-F001-API004 | `GET /api/v1/platform/audit-logs/{audit_log_id}`（`audit_api.py:177-198`） | （当前前端无入口；见 §18 Q-03） | 路径参数 `audit_log_id`（UUID） | `AuditLogDetailResponse`：列表字段 + `before_payload` + `after_payload` | `DATA_GOVERNANCE_ADMIN`；`*` 放行 | 天然幂等 | 单请求单事务 |
| PLT-AUDIT-F001-API005 | `GET /api/v1/platform/audit/actors`（`audit_api.py:115-125`） | 操作日志宿主页「操作人」下拉 | 无查询参数 | `AuditActorListResponse`：`items`（`{id, display_name, username}`）、`total` | `DATA_GOVERNANCE_VIEW` 或 `DATA_GOVERNANCE_ADMIN`（并集）；`*` 放行 | 天然幂等 | 单请求单事务 |

调用者与所有权说明：五个接口由 Platform Kernel 提供（`apps/api/src/hris/modules/platform/`）；审计行的写入方是各业务模块，本模块只读。前端调用封装在 `apps/web/src/business/features/platform/audit-api.ts:179-205`，认证统一使用 Bearer Token（`apps/web/src/business/client.ts`）。

### 11.2 异步事件与任务

`NOT_APPLICABLE`。依据：本功能的所有路径（`audit_service.py:156-286`）只做数据库读取与一次审计追加，模块内没有消息发布或领域事件调用（`apps/api/src/hris/modules/platform/audit_service.py` 全文件检索 `publish` / `emit` 无命中）；审计数据的产生方是各业务模块在自己的事务内写行，不通过本功能分发。若后续引入消息引擎（待确认清单 P-10～P-12），「审计事件实时推送」需重新评审并补写本节。

### 11.3 兼容与废弃

- 当前合同版本：v1。列表 / 动作聚合 / 导出三个接口的路径与响应字段自审计模块落地以来未变；本轮新增 `GET /api/v1/platform/audit/actors`（API005），属**新增只读端点**，不改变任何既有接口的合同。
- 向后兼容策略：前端 `mapAuditLogEntry` / `mapAuditLogPage` / `mapActionCount` 收敛了 snake_case ↔ camelCase 的映射（`audit-api.ts:113-145`），后端调整字段名时只改映射函数，页面与表格不需要改动。
- 废弃通知和截止版本：原「操作人」下拉数据源 `GET /api/v1/platform/users`（权限码 `*`）**仍然存在且继续服务于账号与权限工作区**，本功能只是不再调用它，不构成废弃（该端点定义在 `apps/api/src/hris/modules/platform/account_admin_api.py:48-65`，属账号管理功能，不在本功能范围）。

## 12. 异常、并发与回退

| ID | 状态 | 场景 | 系统结果 | 用户提示/错误码 | 是否重试 | 补偿/回退 |
|---|---|---|---|---|---|---|
| PLT-AUDIT-F001-ERR001 | `CONFIRMED` | 时间区间起点晚于终点 | 请求被拒，不查库 | 422 `AUDIT_TIME_RANGE_INVALID`「开始时间不能晚于结束时间」（`audit_service.py:124-134`） | 否——需改区间 | 不适用 |
| PLT-AUDIT-F001-ERR002 | `CONFIRMED` | 导出结果超过 50000 行 | 请求被拒，不写审计行 | 422 `AUDIT_EXPORT_TOO_LARGE`「当前筛选结果超过单次导出上限，请缩小筛选范围后重试」（`audit_service.py:225-232`） | 否——需缩小筛选 | 不适用 |
| PLT-AUDIT-F001-ERR003 | `CONFIRMED` | 查询不存在的日志详情 | 拒绝 | 404 `AUDIT_LOG_NOT_FOUND`「审计日志不存在」（`audit_service.py:198-205`） | 否 | 不适用 |
| PLT-AUDIT-F001-ERR004 | `CONFIRMED` | 请求参数不满足 schema（如 `page_size=201`） | 请求被拒 | 422 `REQUEST_VALIDATION_FAILED`「请求参数校验失败」，`details` 逐字段给出（`apps/api/src/hris/core/errors.py:41-61`） | 否 | 不适用 |
| PLT-AUDIT-F001-ERR005 | `CONFIRMED` | 无权限访问或导出 | 请求被拒 | 403 `PERMISSION_DENIED`「没有执行此操作的权限」（`dependencies.py:119`） | 否 | 不适用 |
| PLT-AUDIT-F001-ERR006 | `CONFIRMED` | 会话无效或过期 | 请求被拒 | 401 `AUTHENTICATION_REQUIRED` / `SESSION_INVALID`（`dependencies.py:32`、`:47`） | 重新登录后重试 | 不适用 |
| PLT-AUDIT-F001-ERR007 | `CONFIRMED` | 导出内容含公式注入风险 | 服务端在写入 CSV 前给以 `= + - @` 或制表符开头的单元格加前缀 `'`（`audit_service.py:30`、`:347-357`） | 不适用——前端无感知 | 不适用 | 不适用 |
| PLT-AUDIT-F001-ERR008 | `CONFIRMED` | 两人同时导出 | 两个请求各自独立取数并各自写一条导出审计行；审计行数增加 2，其余不变 | 不适用 | 不适用 | 不适用——导出是只读语义，副作用仅为审计留痕 |
| PLT-AUDIT-F001-ERR009 | `CONFIRMED` | 导出过程中数据库异常 | 整个请求事务回滚，CSV 不产出，导出审计行也不落库 | 前端展示「操作日志导出失败」（`AuditLogWorkspace.tsx:213`） | 可在修复原因后重试 | 自动回滚（`apps/api/src/hris/core/database.py:23-25`） |
| PLT-AUDIT-F001-ERR010 | `CONFIRMED` | 操作人下拉取数失败 | 列表与表格不受影响 | 前端静默退化为空下拉（`AuditLogWorkspace.tsx:175-176`），无错误提示 | 刷新页面可重试 | 不适用——只读辅助数据源失败不阻断主流程 |
| PLT-AUDIT-F001-ERR011 | `CONFIRMED` | 后台任务中断 | `NOT_APPLICABLE`：本功能没有后台任务（依据 §11.2） | — | — | — |
| PLT-AUDIT-F001-ERR012 | `CONFIRMED` | 下游系统失败 | `NOT_APPLICABLE`：本功能不调用外部系统（依据 §11.2） | — | — | — |
| PLT-AUDIT-F001-ERR013 | `CONFIRMED` | 审计行本身写错 | `NOT_APPLICABLE`：审计行不可修改（依据 §8.3） | — | — | 业务侧只能新增更正动作的审计行，旧的错误行永久保留 |
| PLT-AUDIT-F001-ERR014 | `PENDING` | 审计保留期到期的归档与清理 | 当前没有归档或清理入口：审计行永久保留 | 现状无对应提示 | — | 保留期要求见 §18 Q-04 |

## 13. 审计与数据保护

| ID | 状态 | 动作 | 审计内容 | 禁止记录内容 | 保留要求 |
|---|---|---|---|---|---|
| PLT-AUDIT-F001-AUD001 | `CONFIRMED` | 导出审计日志 | `action=platform.audit_logs.export`、`object_type=audit_log_export`、`object_id=null`、`reason=导出审计日志`、`before_payload={}`、`after_payload={row_count, filters}`、`actor_id`、`trace_id`、`source=api`（`audit_service.py:250-283`） | **不记录**任何被导出行的 payload 内容；只记录行数与筛选条件 | 审计行随 `audit_logs` 表保留，无删除入口 |
| PLT-AUDIT-F001-AUD002 | `CONFIRMED` | 读取审计日志 | 读取行为本身不产生审计行（列表、动作聚合、详情、导出前置查询均为只读；只有导出写入审计行） | — | — |
| PLT-AUDIT-F001-AUD003 | `CONFIRMED` | 读取操作人清单 | 只读端点，不产生审计行；只返回 id、显示名与登录名 | 不返回邮箱、手机号、账号状态与角色 | — |

- 敏感字段加密：`NOT_APPLICABLE`。依据：本功能只读 `audit_logs` 与 `user_accounts`，不写入敏感列，也不做加解密；审计载荷里的敏感内容加密责任属于各业务模块的写入方（人员档案的加密要求见 `docs/01-foundation/07-人员档案领域规范.md`）。
- 页面脱敏：页面**不展示** `before_payload` / `after_payload`（列表响应不含 payload，前端类型也没有该字段，`audit-api.ts:29-40`）；「原因」列以 Tooltip + 省略号展示，避免长文本撑破表格（`AuditLogWorkspace.tsx:119-132`）；「操作人」下拉只显示显示名，不显示邮箱或手机号。
- 明文访问：单条详情端点会返回 payload，但它是**受权限保护**的独立端点（`audit_api.py:177-198`），且当前前端没有入口；页面上不存在「点击查看明文」的路径（见 §18 Q-03）。
- 导出与临时文件：导出走 Blob 内存下载，不在服务端落临时文件（`AuditLogWorkspace.tsx:201-217`）；CSV 带 UTF-8 BOM，保证 Excel 打开中文不乱码（`audit_service.py:285`）；导出内容不含 payload（`audit_service.py:19-29`）。
- 非生产数据：验收使用合成数据；现有自动化测试即采用合成 fixture（`apps/api/tests/integration/test_audit_logs_api.py:60-84` 的 `_audit_log`）。

## 14. 非功能需求

| ID | 状态 | 类别 | 可验证要求 | 环境/数据量 | 验证证据 |
|---|---|---|---|---|---|
| PLT-AUDIT-F001-NFR001 | `CONFIRMED` | 性能 | 列表采用服务端分页，默认每页 20 条，每页最多 200 条；分页器支持每页 20 / 50 / 100 条 | 本机开发库；数据量由审计写入频次决定 | 后端 `audit_api.py:70-72`；前端 `AuditLogWorkspace.tsx:33`、`:303-318` |
| PLT-AUDIT-F001-NFR002 | `PENDING` | 性能 | 首屏（列表 + 动作聚合 + 操作人清单三个并行请求）的响应时间目标 | 需要容量输入：本机并发用户数、日均写操作条数、账号总数 | 缺容量输入，暂不可验收；输入模板见 `docs/input-packs/templates/07-capacity-scenarios.csv`，容量场景见 `docs/input-packs/09-nonfunctional-acceptance-input.md` |
| PLT-AUDIT-F001-NFR003 | `CONFIRMED` | 可用性 / 可访问性 | 筛选控件具备可访问名称（`aria-label="操作类型"`、`"对象类型"`、`"追踪 ID"`、`"操作人"`）；表格行键为 `id`；Tag 同时带颜色与文字，不只依赖颜色 | 键盘与屏幕阅读器人工检查 | `AuditLogWorkspace.tsx:250-252`、`:264`、`:273`、`:282`、`:296`；规范 §7 状态不只依赖颜色的要求 |
| PLT-AUDIT-F001-NFR004 | `CONFIRMED` | 兼容 | 页面使用仓库锁定的 Ant Design 6.5.2 组件，不使用已废弃属性 | 生产构建 `npm run build` | D-090；`docs/design/antd-page-interaction-standard.md` §2；`node scripts/check-antd-usage.mjs` 0 违规 |
| PLT-AUDIT-F001-NFR005 | `CONFIRMED` | 复用 | 页面骨架、筛选栏与表格统一使用 `WorkspaceShell`、`FilterBar`、`DataTable`，不在本能力域内出现第二套写法 | 全站一致性 | D-091；`apps/web/src/business/components/WorkspaceShell.tsx`、`FilterBar.tsx`、`DataTable.tsx` |
| PLT-AUDIT-F001-NFR006 | `CONFIRMED` | 可观测 | 每次请求返回 `trace_id`，审计行的 `trace_id` 与响应一致，可用于按请求串起页面操作与审计记录 | 本机开发库 | `apps/api/src/hris/core/errors.py:24-38`、`audit_service.py:255-259`、`models.py:997` |
| PLT-AUDIT-F001-NFR007 | `CONFIRMED` | 安全 | 页面不展示也不提交任何个人敏感数据；导出内容不含 payload；CSV 单元格做公式注入转义 | 本机开发库 | §13 脱敏条目；`audit_service.py:347-357` |
| PLT-AUDIT-F001-NFR008 | `CONFIRMED` | 容量 | 操作人清单端点当前一次返回全部账号、不分页：账号数在企业规模下必须可控，否则下拉请求体会过大 | 本机开发库；账号总数由企业规模决定 | `audit_service.py:208-232`；账号规模上限见 §18 Q-08 |

## 15. 验收场景

### PLT-AUDIT-F001-AC001 列表分页与倒序

- 类型：正常
- 前置数据：3 条审计记录，时间递增。
- Given：账号具备 `DATA_GOVERNANCE_ADMIN`，进入「数据治理 › 操作日志」。
- When：页面加载完成。
- Then：请求为 `GET /api/v1/platform/audit-logs?page=1&page_size=20`；`total` 为 3，`page` 为 1，`page_size` 为 20；返回的 `occurred_at` 严格倒序；`page_size=2` 时第 1 页 2 条、第 2 页 1 条。
- 数据库/事件/审计证据：无数据写入，无审计行。
- 自动化层级：后端集成测试 + 前端单元测试。

### PLT-AUDIT-F001-AC002 时间范围闭区间过滤

- 类型：正常
- 前置数据：3 条审计记录，时间间隔 1 小时。
- Given：管理员设置时间范围覆盖第 1、2 条。
- When：点击「查询」。
- Then：请求带 `occurred_from` / `occurred_to`；返回 `total` 为 2，命中的两条时间恰好落在闭区间端点上。
- 数据库/事件/审计证据：无数据变化。
- 自动化层级：后端集成测试。

### PLT-AUDIT-F001-AC003 业务规则拒绝——时间区间倒置

- 类型：异常 / 规则拒绝
- 前置数据：无。
- Given：管理员把开始时间设在结束时间之后。
- When：请求到达服务端。
- Then：返回 422 `AUDIT_TIME_RANGE_INVALID`，不查库、不返回任何记录。
- 数据库/事件/审计证据：无数据变化，无审计行。
- 自动化层级：后端集成测试。

### PLT-AUDIT-F001-AC004 操作类型下拉来自后端聚合

- 类型：正常
- 前置数据：4 条审计记录，action 分别为 `person.update` × 2、`person.create` × 1、`governance.export` × 1。
- Given：管理员展开「操作类型」下拉。
- When：下拉加载完成。
- Then：选项为 `person.update (2)`、`governance.export (1)`、`person.create (1)`，按计数倒序、同数按 action 升序；`action` 保留后端原始代码，不做中文映射。
- 数据库/事件/审计证据：无数据变化。
- 自动化层级：后端集成测试 + 前端单元测试。

### PLT-AUDIT-F001-AC005 权限——日志正文要求治理管理权限

- 类型：权限
- 前置数据：账号只持有 `DATA_GOVERNANCE_VIEW`（或完全无治理权限）。
- Given：该账号访问操作日志页。
- When：依次请求列表、动作聚合、导出、详情。
- Then：四个端点全部返回 403 `PERMISSION_DENIED`；页面显示顶部错误条。
- 数据库/事件/审计证据：无数据变化；导出被拒时**不**产生导出审计行。
- 自动化层级：后端集成测试。

### PLT-AUDIT-F001-AC006 权限——只读治理角色可取操作人下拉但不可读日志

- 类型：权限
- 前置数据：账号只持有 `DATA_GOVERNANCE_VIEW`。
- Given：该账号访问操作日志页。
- When：请求 `GET /api/v1/platform/audit/actors` 与 `GET /api/v1/platform/audit-logs`。
- Then：actors 返回 200 且包含账号清单；列表返回 403 `PERMISSION_DENIED`。
- 数据库/事件/审计证据：无数据变化。
- 自动化层级：后端集成测试。

### PLT-AUDIT-F001-AC007 列表不泄露 payload

- 类型：安全
- 前置数据：一条审计记录，`before_payload` 与 `after_payload` 含 `salary` 标记串。
- Given：管理员查询列表。
- When：请求返回。
- Then：响应体中不存在 `before_payload` / `after_payload` 字段，也不存在标记串。
- 数据库/事件/审计证据：无数据变化。
- 自动化层级：后端集成测试。

### PLT-AUDIT-F001-AC008 详情端点返回 payload、未知 id 返回 404

- 类型：正常 / 异常
- 前置数据：一条含 payload 的审计记录。
- Given：管理员按 id 请求详情；再按一个不存在的 id 请求详情。
- When：请求到达服务端。
- Then：第一次返回 200 且 `before_payload` / `after_payload` 与库中一致；第二次返回 404 `AUDIT_LOG_NOT_FOUND`。
- 数据库/事件/审计证据：无数据变化。
- 自动化层级：后端集成测试。

### PLT-AUDIT-F001-AC009 导出列固定且不含 payload

- 类型：正常 / 安全
- 前置数据：2 条审计记录，含 `salary` 标记串；其中 1 条 `actor_id` 关联不到账号。
- Given：管理员点击「导出CSV」。
- When：请求到达服务端。
- Then：响应 `Content-Type` 以 `text/csv` 开头，`Content-Disposition` 含 `attachment` 与 `audit-logs.csv`；CSV 首行是 `occurred_at, actor_name, action, object_type, object_id, trace_id, reason, source`；行数为 2 且按时间倒序；关联不到账号的行 `actor_name` 为空串；文本中不含 `before_payload` / `after_payload` 与标记串。
- 数据库/事件/审计证据：产生一条 `action=platform.audit_logs.export` 的审计行（见 AC011）。
- 自动化层级：后端集成测试 + 前端单元测试。

### PLT-AUDIT-F001-AC010 业务边界——导出超过 50000 行被拒绝

- 类型：边界
- 前置数据：命中筛选的记录数超过 50000。
- Given：管理员在无筛选或宽筛选条件下点击「导出CSV」。
- When：请求到达服务端。
- Then：返回 422 `AUDIT_EXPORT_TOO_LARGE`，消息提示缩小筛选范围；不产出 CSV，也不写导出审计行。
- 数据库/事件/审计证据：`audit_logs` 中没有 `action=platform.audit_logs.export` 的新行。
- 自动化层级：后端集成测试。

### PLT-AUDIT-F001-AC011 审计证据核对——导出自身被审计

- 类型：审计
- 前置数据：账号具备 `DATA_GOVERNANCE_ADMIN`；筛选条件为 `action=person.update`。
- Given：管理员导出。
- When：导出成功。
- Then：`audit_logs` 新增一行 `action=platform.audit_logs.export`、`object_type=audit_log_export`、`before_payload={}`、`after_payload.row_count` 等于导出行数、`after_payload.filters` 记录本次筛选条件；该行 `trace_id` 与响应一致。
- 数据库/事件/审计证据：`audit_logs` 查询结果。
- 自动化层级：后端集成测试。

### PLT-AUDIT-F001-AC012 筛选草稿与重置语义

- 类型：正常 / 边界
- 前置数据：库中有若干条审计记录。
- Given：管理员在「对象类型」输入 `user`、在「追踪 ID」输入 `trace-0001`、在「操作人」选择某个账号，但**不点「查询」**。
- When：此时观察表格。
- Then：表格仍是上一次查询的结果（草稿式筛选不触发请求）；点击「查询」后请求带 `object_type=user`、`trace_id=trace-0001`、`actor_id=<所选账号 id>`；点击「重置」后请求不带任何筛选参数且页码回到 1。
- 数据库/事件/审计证据：无数据变化。
- 自动化层级：前端单元测试。

### PLT-AUDIT-F001-AC013 权限——无治理权限时操作人端点 403

- 类型：权限
- 前置数据：账号不持有任何治理权限。
- Given：该账号请求 `GET /api/v1/platform/audit/actors`。
- When：请求到达服务端。
- Then：返回 403 `PERMISSION_DENIED`，响应体不含任何账号信息。
- 数据库/事件/审计证据：无数据变化。
- 自动化层级：后端集成测试。

### PLT-AUDIT-F001-AC014 操作人端点的字段最小性与排序

- 类型：安全 / 正常
- 前置数据：账号清单中至少有两个不同显示名的账号（显示名「甲」「丙」）。
- Given：管理员请求操作人清单。
- When：请求到达服务端。
- Then：每项只含 `id`、`display_name`、`username` 三个键；`display_name` 升序；不返回邮箱、手机号、账号状态与角色；不按账号状态过滤（已停用账号仍在清单里）。
- 数据库/事件/审计证据：无数据变化。
- 自动化层级：后端集成测试。

### PLT-AUDIT-F001-AC015 前端只调用审计专用端点

- 类型：正常
- 前置数据：无。
- Given：打开操作日志页并展开「操作人」下拉。
- When：观察发出的请求。
- Then：请求命中 `/api/v1/platform/audit/actors`；整个页面生命周期内**不出现**对 `/api/v1/platform/users` 的请求。
- 数据库/事件/审计证据：不适用。
- 自动化层级：前端单元测试。

## 16. 迁移、发布与回滚

- 现有数据影响：本功能只读 `audit_logs` 与 `user_accounts`，本轮无结构变更、无数据迁移。
- 数据迁移与校验：不适用——本功能不提供导入功能。
- 功能开关或模块启用：没有功能开关；入口按 `DATA_GOVERNANCE_ADMIN` 权限显隐（`navigation.ts:69-74`）。
- 发布顺序：后端先发布新增的 `GET /api/v1/platform/audit/actors`，再发布前端；顺序反过来时前端会短暂拿到 404，取不到下拉候选项，页面其余部分不受影响。
- 升级兼容：既有接口的路径与响应字段未变；前端只把操作人下拉的数据源从 `/platform/users` 换成 `/audit/actors`，映射函数 `mapAuditActor` 兼容两种字段命名（`audit-api.ts:148-153`）。
- 应用回滚：前端回滚到上一构建即可（会重新调用 `/platform/users`）；后端回滚不涉及本功能的迁移，新增端点是纯新增，删除它不影响既有接口。
- 数据不可逆时的恢复或前向修复：本功能不修改业务数据；导出审计行只增不删。

## 17. 可观测与运行手册

- 指标：本功能不新增业务指标。现有可观测项：接口调用量与错误码分布（403 / 404 / 409 / 422）、列表查询的 `total` 规模、导出次数（可通过 `action=platform.audit_logs.export` 的审计行计数）。
- 日志和Trace：每次请求带 `trace_id`（`apps/api/src/hris/core/errors.py:24-38`），审计行 `trace_id` 与之对应（`audit_service.py:255-259`）；排查一次具体操作时，用 `trace_id` 关联审计记录与请求日志。
- 告警：本功能不定义专属告警；导出接口 5xx 与事务回滚沿用平台内核既有告警口径。
- 后台任务：无（依据 §11.2）。
- 人工补偿：读取失败无需补偿；导出失败事务自动回滚，不留半截 CSV（`apps/api/src/hris/core/database.py:23-25`）。
- 健康检查：页面可用性依赖 `GET /api/v1/platform/audit-logs` 与 `GET /api/v1/platform/audit/actors` 的可用性（`audit-api.ts:180-198`）。

## 18. 待确认问题

| ID | 问题 | 影响规则/场景 | Owner | 期望日期 | 不确认时的处理 |
|---|---|---|---|---|---|
| PLT-AUDIT-F001-Q01 | 待确认清单 **P-15**「画板通过后是否即授权前端按画板开发/替换」：是否确认把画板 `laZ5d` 的 Review 状态从 `DRAFT_FOR_REVIEW` 改为 `PROTOTYPE_APPROVED`。**2026-10-24 产品决策人已确认全部画板并签字**，§10.4 状态升级为 `PROTOTYPE_APPROVED` | §10.1 原型状态、§10.4 PROT001、§19 T002、AC001–AC015 的页面形态验收 | 产品决策人 | 2026-10-25 | 已关闭：2026-10-24 产品决策人签字确认画板，规范 §10.2 的前端开发门禁解除，本功能可按画板继续开发|
| PLT-AUDIT-F001-Q02 | 待确认清单 **P-13**「审计页『操作人』下拉的数据源」已按推荐方案 (b) 决策（新建审计专用端点、权限放宽到只读治理码）。需确认的是「并集语义」这一实现细节：`DATA_GOVERNANCE_VIEW` 与 `DATA_GOVERNANCE_ADMIN` 任一命中即放行——是否接受 `ADMIN` 持有者也可用该只读端点 | BR013、§9 PERM005、AC006、AC013 | 产品决策人 | 2026-10-25 | 采用已实现行为：并集放行（治理管理员必然可用是 P-13 的原始诉求） |
| PLT-AUDIT-F001-Q03 | 待确认清单 **P-02**「操作日志是否需要『详情』抽屉看单条完整上下文」：后端详情端点已存在且返回 payload，前端无入口 | BR017、§11.1 API004、§13 明文访问、§10.1 载体、AC008 | 产品决策人 | 2026-10-25 | 采用已实现行为：不加详情抽屉；payload 只能通过直接调用接口取得 |
| PLT-AUDIT-F001-Q04 | 审计保留期、归档周期与合规取证要求尚未提供；当前审计行永久保留，无归档与清理入口 | BR018、ERR014、§8.3 保留、§16 | 产品决策人 + 企业合规输入方 | 企业 UAT 前 | 采用已实现行为：不实现归档与清理，审计行永久保留 |
| PLT-AUDIT-F001-Q05 | 待确认清单 **P-23**「操作日志 Tag 的严重度分级」：画板要求统一蓝 / 橙，本轮已按画板统一，原有的红 / 绿严重度消失；是否接受统一蓝橙 | BR016、§10.3、AC004 | 产品决策人 | 2026-10-25 | 采用画板现状：操作列 processing 蓝、来源列 warning 橙 |
| PLT-AUDIT-F001-Q06 | 时间口径：服务端把未带时区的时间按 UTC 解释（`audit_service.py:91-97`），前端 `RangePicker` 提交的是浏览器本地时区的 ISO 串。跨时区访问时，界面显示的时间与筛选命中的记录可能不一致 | ASM-05、§10.3、AC002 | 产品决策人 | 企业 UAT 前 | 采用已实现行为：前端按本地时区提交，服务端按 UTC 解释；页面统一按本地时区展示时间（`AuditLogWorkspace.tsx:44-52`） |
| PLT-AUDIT-F001-Q07 | 导出是否需要二次确认或行数预检：当前点击即导出，最长 50000 行 | §10.3、§12 ERR002 | 产品决策人 | 企业 UAT 前 | 采用已实现行为：不做二次确认，超限时由后端 422 兜底 |
| PLT-AUDIT-F001-Q08 | 操作人清单端点当前一次返回全部账号、不分页：企业账号规模上限是多少，是否需要分页或搜索 | NFR008、§11.1 API005 | 产品决策人 + 企业规模输入方 | 企业 UAT 前 | 采用已实现行为：一次返回全部账号，按 `display_name` 升序 |
| PLT-AUDIT-F001-Q09 | 待确认清单 **P-16**「`docs/requirements/` 模块功能需求文档」：本文件是继职位管理、汇报关系之后的第三份功能文档；是否继续为人员中心、员工档案 Drawer、批量新增标签 Modal 建立同规范文档 | §19 T001 的范围界定 | 产品决策人 | 2026-10-25 | 本轮已按默认执行：同批次建立其余 3 份同规范文档（`WFC-PEOPLE-F001`、`WFC-LABEL-F001`、`WFC-LABEL-F002`），登记在 `docs/01-foundation/00-正式文档目录.md` §1.4 |

## 19. 开发任务与追踪

| 任务ID | 目标 | 依赖 | 文件/模块所有权 | 需求追踪注释 | 验收场景 | 状态 | 交付证据 |
|---|---|---|---|---|---|---|---|
| PLT-AUDIT-F001-T001 | 按《模块功能需求文档规范》建立操作日志功能需求文档，登记 Pencil 画板 `laZ5d`、字段合同、权限、错误码与验收场景 | 无 | 仅新增 `docs/requirements/PLT-platform/PLT-AUDIT/PLT-AUDIT-F001-audit-log-review.md` | 文档头部登记规范 17 号；正文引用 AUDIT-001～011 / P-13 / P-15 / P-16 / D-090 / D-091 | AC001–AC015 的判定依据 | `IN_REVIEW` | 本文件（v0.1，2026-10-24） |
| PLT-AUDIT-F001-T002 | 前端按已批准画板 `laZ5d` 对齐操作日志宿主页 | PLT-AUDIT-F001-Q01（画板签字，`PROTOTYPE_APPROVED`） | `apps/web/src/business/features/platform/AuditLogWorkspace.tsx`、`audit-api.ts`、`apps/web/src/business/components/` | 在规则落点写 `Requirement: PLT-AUDIT-F001-BRnnn — 原因` | AC001、AC002、AC004、AC009、AC012 | `READY`（2026-10-24 画板已签字，规范 §10.2 的前端开发门禁解除，按画板继续对齐） | — |
| PLT-AUDIT-F001-T003 | 新增审计专用「操作人」只读端点并把前端下拉切换过去，消除治理管理员 403 | 待确认清单 P-13（已决策，方案 b） | `apps/api/src/hris/modules/platform/audit_api.py`、`audit_service.py`、`apps/api/src/hris/modules/platform/dependencies.py`、`apps/web/src/business/features/platform/audit-api.ts`、`AuditLogWorkspace.test.tsx`、`apps/api/tests/integration/test_audit_logs_api.py` | `Requirement: P-13 — 审计页操作人下拉改用审计专用只读端点，权限放宽到治理只读码`（`audit_api.py:29-35`、`:115-125`；`audit-api.ts:193-205`） | AC006、AC013、AC014、AC015 | `DELIVERED` | 本轮提交：后端集成测试 4 条新用例通过（治理管理员可用、只读治理角色可用、无治理权限 403、字段最小性与排序）；前端新增 1 条用例通过 |
| PLT-AUDIT-F001-T004 | 按 P-02 结论补单条日志详情抽屉 | PLT-AUDIT-F001-Q03 | `apps/web/src/business/features/platform/AuditLogWorkspace.tsx`、`apps/api/src/hris/modules/platform/audit_api.py` | `Requirement: PLT-AUDIT-F001-BR017 — 原因` | AC008 | `BLOCKED`（阻塞原因：Q03 未拍板，且未登记对应 Pencil 画板，规范 §10.4 禁止） | — |

## 20. Review与批准记录

| 版本 | 日期 | 变更摘要 | 产品/业务结论 | 技术结论 | 批准人 |
|---|---|---|---|---|---|
| v0.1 | 2026-10-24 | 初稿：按 17 号规范建立操作日志功能需求文档；登记 Pencil 画板 `laZ5d`（初稿状态 `DRAFT_FOR_REVIEW`）；逐条对齐后端合同（字段、接口、权限码、错误码）与前端实现文案；纳入本轮 P-13 修复后的操作人专用端点 | 已由产品决策人 Review 并签字，状态升级为 `PROTOTYPE_APPROVED`（Q01） | 字段、接口、权限与错误码全部指向实现文件与行号，未发明后端不存在的字段；操作人端点只返回 id / display_name / username，未泄露账号管理信息 | 已批准（2026-10-24 产品决策人签字） |

现状说明（按事实记录）：

- 2026-10-24 用户已指示「按画板开发或替换已有的界面」，前端据此先行实现了该宿主页，并已获授权先行实现。
- 画板已于 **2026-10-24** 经产品决策人签字确认，§10.4 的 Review 状态升级为 `PROTOTYPE_APPROVED`。
- 在 Q01 关闭之前，按规范 §10.2 与 D-087，不得为本功能创建新的前端开发任务（T002 状态为 `BLOCKED`）。

### 20.1 规范 §15 文档 Review 检查表自查（2026-10-24）

| # | 检查项 | 自查结论 | 依据 |
|---|---|---|---|
| 1 | 文档是否只描述一个可独立验收的功能 | 是 | 全文只描述「按条件检索并导出平台写操作记录」一个业务结果；查看与导出复用同一筛选条件，在 §3 给出不拆分理由 |
| 2 | 是否能明确说出谁在什么条件下得到什么结果 | 是 | §3 参与者表（主管理员 / 数据治理管理员 / 只读治理角色 / 未登录账号）+ §5 四条用户故事的触发条件、前置条件、主路径、结束状态 |
| 3 | 是否区分确认规则、待确认问题和推荐方案 | 是 | §7 规则表带 `CONFIRMED` / `PENDING` 状态列并写明状态约定；§18 全部为待确认项并给出「不确认时的处理」；本文件未代替产品决策人做结论 |
| 4 | 数据所有者、唯一键、有效日期和历史策略是否明确 | 是 | §8.1 数据所有权（本功能不拥有数据）、唯一键、时间字段口径与快照语义；§8.2 每行含「历史策略」列 |
| 5 | 是否覆盖动作、数据范围、字段和高风险操作 | 是 | §9 PERM001–PERM008 覆盖列表 / 聚合 / 导出 / 详情 / 操作人清单 / 入口可见性 / 字段权限 / 403 拒绝结果；高风险点在 §13（payload 不外泄、公式注入转义）与 §10.3（导出无二次确认）显式登记 |
| 6 | 接口是否明确幂等、事务、版本和失败补偿 | 是 | §11.1 五个接口逐个写明幂等性与单请求单事务边界；§12 覆盖重复、并发、异常与回滚；§11.2 说明无异步事件及依据 |
| 7 | 是否覆盖异常、并发、回退、审计和敏感数据 | 是 | §12 ERR001–ERR014；§13 AUD001–AUD003 及加密、脱敏、明文访问、导出、非生产数据逐项结论；保留期与归档缺口在 ERR014 / Q04 登记 |
| 8 | NFR是否可以在指定环境中验证 | 部分通过 | NFR001、NFR003–NFR008 可在指定环境验证并给出证据；NFR002（首屏响应时间）因缺容量输入标记 `PENDING`，已在 §14 写明需要的输入文件与验收环境 |
| 9 | 验收场景是否包含明确输入、动作和预期证据 | 是 | §15 AC001–AC015，每条含类型、前置数据、Given / When / Then、数据库或审计证据、自动化层级 |
| 10 | 是否可以在不猜业务规则的情况下拆出最小任务 | 是 | §19 四个任务均声明所有权、依赖、追踪注释与验收场景；两个任务因 Q01 / Q03 未决而 `BLOCKED`，未把 PENDING 规则写进任务 |
| 11 | 是否说明对已有数据、模块和部署的影响 | 是 | §16 覆盖现有数据影响、迁移与校验、开关、发布顺序、升级兼容、应用回滚与前向修复；§4 列出写入方与引用方 |
| 12 | 是否存在与父级PRD或已确认决策冲突的内容 | 是（无冲突） | 组件复用符合 D-091；原型门禁符合 D-087；操作人下拉方案符合待确认清单 P-13 已决策的方案 b；Tag 着色按画板现状登记为 PENDING（BR016 / Q05） |
| 13 | 所有需求驱动的代码变化是否明确了追踪注释所引用的ID和预计代码落点 | 是 | §19 T003 写明 `Requirement: P-13 — 审计页操作人下拉改用审计专用只读端点，权限放宽到治理只读码` 及实际落点 `audit_api.py:29-35`、`:115-125`、`audit_service.py:196-236`、`audit-api.ts:193-205`；T002/T004 写明待建的追踪注释格式 |
| 14 | 涉及前端时，是否明确宿主页、`MODAL`/`DRAWER`/`NEW_TAB`载体及其打开、退出和状态恢复行为 | 是 | §10.1 宿主页=列表、载体 `NOT_APPLICABLE` 并写明理由与后续补登条件、hash 路由 `#audit`；§10.3 说明无弹窗因而无打开 / 关闭 / 焦点行为 |
| 15 | 涉及前端时，是否登记Pencil文件、画板ID、版本和`PROTOTYPE_APPROVED`证据 | 通过 | §10.4 已登记 Pencil 源文件、画板 ID `laZ5d`、画板名称、版本 `v1.0` 与状态；`PROTOTYPE_APPROVED` 证据**已存在**（2026-10-24 产品决策人签字确认）；原缺口 Q01 登记 |

自查结论汇总：15 项中 14 项通过，1 项为「部分通过」——第 8 项因缺容量输入把 NFR002 标为 `PENDING`（不是编造）；第 15 项已随 2026-10-24 画板签字补齐 `PROTOTYPE_APPROVED` 证据。按规范 §15 末句「任一关键项为否时，不得进入 `READY_FOR_TASKS`」，本功能当前状态仍保持 `DRAFT`（余下 1 项为第 8 项 NFR002 容量输入待补），画板门禁已不再是阻塞项。
