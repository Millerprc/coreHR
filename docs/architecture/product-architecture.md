# coreHR 产品架构图

> 版本：v0.1 · 日期：2026-08-09 · 状态：基于当前 main `55369b6` 实际代码生成
>
> 依据：
> - 09 文档第 4 节模块边界
> - `apps/api/src/hris/`、`apps/web/src/`、`deploy/compose.yaml` 实际目录
> - 03-项目决策 D-001 ~ D-054
> - 10-代码规范 §3 §4 §5
>
> 描述方式：C4 模型（Context → Container → Module）

---

## 1. 系统上下文（System Context）

谁在用 coreHR，coreHR 跟谁对话。

```mermaid
graph TB
    subgraph 角色["使用者（按 D-004 / Q-010 划分）"]
        SysAdmin["系统管理员<br/>系统配置、账号、字典"]
        SscAdmin["SSC 管理员<br/>数据初始化与维护"]
        Hrbp["HRBP / 业务负责人<br/>查询下级数据"]
        Emp["员工<br/>（第一阶段不开放自助）"]
        Auditor["只读审计员<br/>（Q-010 待确认）"]
    end

    subgraph CoreHR["coreHR（企业内部 HRIS）"]
        System["企业级 HRIS<br/>第一阶段：基础数据 + 编制 + 招聘需求<br/>第二阶段：流程引擎<br/>第三阶段：考勤<br/>第四阶段：薪酬<br/>第五阶段：本地化 + 多租户"]
    end

    subgraph External["外部系统（受控对接）"]
        Wecom["企业微信<br/>D-035 / 第一阶段 SSO 后续接"]
        Oa["自建 OA<br/>第五阶段"]
        Downstream["下游业务系统<br/>Q-016 待提供清单"]
    end

    subgraph Source["源系统镜像（ADR-0002）"]
        EhrSource["MySQL ehr_source<br/>114 张源表<br/>只读镜像，DDL-only 提取"]
    end

    SysAdmin -.认证.-> CoreHR
    SscAdmin -.本地账号.-> CoreHR
    Hrbp -.授权查看.-> CoreHR
    Emp -.预留.-> CoreHR
    Auditor -.只读查询.-> CoreHR

    CoreHR -. "第五阶段对接" .-> Wecom
    CoreHR -. "第五阶段对接" .-> Oa
    CoreHR -. "Q-016 待对接" .-> Downstream

    EhrSource -. "DDL 提取 + 桥接表" .-> CoreHR
```

**关键点**
- 第一阶段使用者**只**有系统管理员和 SSC 管理员（HRBP / 业务负责人 / 员工 / 审计员按 D-004 / Q-010 后续开放）
- 企业微信、OA、下游系统**前四阶段不接入**（D-035、09 文档 §4.2）
- EHR 源库**只作只读镜像**，不进入 coreHR 运行时（ADR-0002）

---

## 2. 容器图（Container）

运行时的物理 / 进程单元。

```mermaid
graph TB
    subgraph 浏览器["Web 浏览器"]
        WebApp["apps/web<br/>React 19 + TS + Vite 6 + Ant Design<br/>业务管理端"]
    end

    subgraph 业务API容器["FastAPI 进程（双入口）"]
        SysEntry["main.py<br/>系统入口<br/>health / modules status<br/>路由：api_router"]
        BizEntry["business_main.py<br/>业务入口<br/>auth + 配置 + 导入 + 业务域<br/>路由：business_router"]
    end

    subgraph 数据层["数据层（compose.yaml 编排）"]
        Pg[("PostgreSQL 16.14<br/>统一业务 schema<br/>命名约定：naming_convention")]
        Redis[("Redis 7.4.10<br/>缓存 / 限流 / 任务协调")]
    end

    subgraph 镜像层["源镜像（ADR-0002 隔离）"]
        EhrMysql[("MySQL ehr_source<br/>本地只读<br/>4 张归一化桥接表")]
    end

    WebApp -- "HTTPS / REST<br/>统一 /api/v1 命名空间<br/>X-Trace-ID + Bearer Token" --> SysEntry
    WebApp -- "同上" --> BizEntry

    SysEntry -- "SQLAlchemy 2.0 async<br/>AsyncSession" --> Pg
    BizEntry -- "同上" --> Pg
    BizEntry -- "advisory lock + Redis" --> Redis

    BizEntry -- "DDL-only 提取<br/>归一化映射" --> EhrMysql
    EhrMysql -- "SHA-256 比对" --> BizEntry
```

**关键点**
- **双 API 入口**：`main.py` 跑最小系统面，`business_main.py` 跑全部业务
- **PostgreSQL 是唯一业务库**：MySQL ehr_source 仅做只读桥接（ADR-0002）
- **Redis 用途收敛**：缓存、限流、任务协调；不存业务事实
- **Web → API**：HTTPS / REST / `/api/v1` 命名空间 / 统一 token / 统一 trace_id

---

## 3. 模块图（Module）

API 内部模块边界（基于 `apps/api/src/hris/modules/` 实际目录 + 代码规范 §4.2 依赖方向）。

```mermaid
graph TB
    subgraph API层["API 适配层（api.py / extended_api.py）"]
        SysApi[system.api]
        PlatApi[platform.api<br/>configuration_api<br/>import_api]
        OrgApi[workforce.api<br/>organization_api<br/>extended_api]
        WfApi[workflow.api<br/>extended_api]
        AttApi[attendance.api<br/>extended_api]
    end

    subgraph 应用服务["应用服务（service.py / extended_service.py）"]
        PlatSvc[platform.service<br/>认证/权限/编号/密码]
        OrgSvc[workforce.service<br/>组织/法人/职务/人员/编制/招聘]
        WfSvc[workflow.service<br/>流程定义/执行/事件]
        AttSvc[attendance.service<br/>考勤/假期/排班/月度]
    end

    subgraph 领域["领域（domain.py / models.py）"]
        OrgModels[workforce.models<br/>Organization / Person / Employment]
        WfModels[workflow.models<br/>Flow / Event / Contract]
        AttModels[attendance.models<br/>RuleSet / Schedule / Punch]
        PlatModels[platform.models<br/>UserAccount / Role / Permission / NumberSequence]
    end

    subgraph 平台能力["平台公共能力（core/ + shared/）"]
        Errors["core.errors<br/>ApiError + 统一响应"]
        Middleware["core.middleware<br/>TraceId + CORS"]
        Concurrency["core.concurrency<br/>VersionCommand<br/>(expected_version + idempotency_key)"]
        Config["core.config<br/>Pydantic Settings"]
        DbBase["shared.db.base<br/>UuidPrimaryKeyMixin<br/>TimestampMixin<br/>naming_convention"]
    end

    subgraph 数据["数据访问（ORM + 迁移）"]
        Models["SQLAlchemy 2.0 Models"]
        Alembic["Alembic 迁移<br/>f3a000000004 (当前 head)"]
    end

    subgraph 外部观测["外部可见（仅读）"]
        Audit["AuditLog 表<br/>操作 / 敏感访问 / 导入导出"]
    end

    SysApi --> OrgSvc
    SysApi --> PlatSvc

    PlatApi --> PlatSvc
    OrgApi --> OrgSvc
    WfApi --> WfSvc
    AttApi --> AttSvc

    PlatSvc --> PlatModels
    OrgSvc --> OrgModels
    WfSvc --> WfModels
    AttSvc --> AttModels
    OrgSvc -.跨域协作.-> WfSvc
    OrgSvc -.跨域协作.-> AttSvc

    PlatSvc --> Errors
    OrgSvc --> Errors
    WfSvc --> Errors
    AttSvc --> Errors

    PlatSvc --> Concurrency
    OrgSvc --> Concurrency
    WfSvc --> Concurrency
    AttSvc --> Concurrency

    PlatModels --> DbBase
    OrgModels --> DbBase
    WfModels --> DbBase
    AttModels --> DbBase
    PlatModels --> Audit
    OrgModels --> Audit
    WfModels --> Audit
    AttModels --> Audit

    Models --> Alembic

    classDef platform fill:#e1f5e1,stroke:#2e7d32,color:#1b5e20
    classDef domain fill:#e3f2fd,stroke:#1565c0,color:#0d47a1
    classDef service fill:#fff3e0,stroke:#e65100,color:#bf360c
    classDef api fill:#f3e5f5,stroke:#6a1b9a,color:#4a148c
    classDef infra fill:#fafafa,stroke:#424242,color:#212121
    classDef audit fill:#ffebee,stroke:#c62828,color:#b71c1c

    class PlatSvc,PlatApi,PlatModels platform
    class OrgSvc,OrgApi,OrgModels,WfSvc,WfApi,WfModels,AttSvc,AttApi,AttModels domain
    class SysApi service
    class Errors,Middleware,Concurrency,Config,DbBase,Models,Alembic infra
    class Audit audit
```

**关键点（按代码规范 §4.2 依赖方向）**
- `api.py` 只做 HTTP 适配：接收输入、鉴权、调用 service、映射状态
- `service.py` 写业务规则、事务边界、幂等键
- `models.py` 持久化模型，**不**承载业务规则
- 跨模块协作只走 service 公开接口，**不**直接 import 对方 models
- 平台能力（errors / middleware / concurrency / db base）所有模块共享

---

## 4. 数据架构（Data）

```mermaid
graph TB
    subgraph 运行时库["PostgreSQL 16.14（统一 schema）"]
        TblOrg[("organization*<br/>有效版本 + 历史")]
        TblPerson[("person / employment<br/>工号 / 雇佣关系")]
        TblWf[("workflow_definition<br/>workflow_event<br/>contract")]
        TblAtt[("attendance_rule_set<br/>schedule / punch / leave")]
        TblPlat[("user_account / role / permission<br/>number_sequence")]
        TblAudit[("audit_log")]
    end

    subgraph 桥接层["4 张归一化桥接表（ADR-0002）"]
        TblBridge[("ehr_*_source_link<br/>ehr_*_mapping")]
    end

    subgraph 镜像源["MySQL ehr_source（只读）"]
        MysqlEhr[("114 张源表<br/>DDL-only 镜像")]
    end

    MysqlEhr -- "DDL 提取 + SHA-256 比对" --> TblBridge
    TblBridge -- "显式字段映射<br/>+ 外部记录 ID 对照" --> TblOrg
    TblBridge --> TblPerson

    TblOrg -.约束检查.-> TblAudit
    TblPerson -.约束检查.-> TblAudit
    TblWf -.约束检查.-> TblAudit
    TblAtt -.约束检查.-> TblAudit
    TblPlat -.约束检查.-> TblAudit
```

**关键点**
- **唯一业务库**是 PostgreSQL 16.14（和 T-004 一致）
- **审计日志**是普通表，不是事件总线；不替代业务历史（08 文档 §10）
- **桥接表**是 EHR 接入的唯一路径，原表结构不进入 coreHR（ADR-0002）
- 所有表走 `naming_convention` 统一命名（base.py）

---

## 5. 关键流程：写操作路径

```mermaid
sequenceDiagram
    autonumber
    participant Browser as 浏览器
    participant Web as React<br/>Web 管理端
    participant API as FastAPI<br/>business_main
    participant Auth as platform.service<br/>require_permission
    participant Service as 业务 service
    participant Db as PostgreSQL
    participant Audit as AuditLog

    Browser->>Web: 点"保存"按钮
    Web->>API: POST /api/v1/...<br/>Authorization: Bearer ...<br/>X-Trace-ID: ...<br/>Body: {expected_version, idempotency_key, change_reason, ...}
    API->>API: TraceIdMiddleware 注入 trace_id
    API->>Auth: require_permission("WORKFORCE_ADMIN")
    Auth-->>API: 权限通过 / 403
    API->>Service: 命令对象<br/>CreateCommand(...)
    Service->>Service: 业务规则校验
    Service->>Db: SELECT ... FOR UPDATE<br/>(乐观锁检查 expected_version)
    Db-->>Service: 行数据
    Service->>Db: INSERT / UPDATE
    Service->>Db: 写 AuditLog<br/>(actor / trace_id / before / after / reason)
    Db-->>Service: commit
    Service-->>API: 领域对象
    API-->>Web: {code, message, data, trace_id}
    Web-->>Browser: 更新 UI
```

**关键点**
- 写操作必带三件套：**expected_version + idempotency_key + change_reason**（concurrency.py）
- 服务端鉴权（`require_permission`），前端隐藏按钮**不**代替权限
- 每次写自动写审计，trace_id 贯穿
- 错误统一格式 `{code, message, details, trace_id}`

---

## 6. 部署拓扑（compose.yaml）

```mermaid
graph TB
    subgraph dev["本地 / 8GB 开发环境"]
        C1[db<br/>postgres:16.14-alpine<br/>127.0.0.1:54329]
        C2[redis<br/>redis:7.4.10-alpine<br/>127.0.0.1:63800]
        C3[api<br/>built from apps/api/Dockerfile]
        C4[web<br/>built from apps/web/Dockerfile<br/>dev: vite :5173]
    end

    C3 --> C1
    C3 --> C2
    C4 -- "fetch /api/v1" --> C3

    classDef container fill:#e1f5e1,stroke:#2e7d32
    class C1,C2,C3,C4 container
```

**关键点**
- 端口只绑 `127.0.0.1`，不暴露外网
- 容器间通过 compose 网络用服务名互访
- `security_opt: no-new-privileges` 开启
- 启动用 `scripts/dev-business-up.sh`，停用 `scripts/dev-down.sh`

---

## 7. 不在本架构内（第五阶段 / 未确定）

| 项 | 状态 | 来源 |
|---|---|---|
| 多租户 | `DEFERRED` | 03-项目决策 D-008 |
| 多语言 | `DEFERRED` | 99-待确认问题 §3 |
| MCP 入口 | `DEFERRED` | T-007 |
| 移动端 | `DEFERRED` | 09 文档 §4.2 |
| 员工自助 | `DEFERRED` | D-006 |
| MySQL / Oracle 生产替换 | 第五阶段 | ADR-0002 |
| 企业微信正式身份 | 第一阶段后续 | T-006 |
| 一万人并发 | 第三、四阶段专项 | D-007 |

---

## 附录：图例

| 颜色 | 含义 |
|---|---|
| 绿 | 平台 / 公共能力 |
| 蓝 | 业务领域 |
| 橙 | 应用服务 |
| 紫 | API 适配层 |
| 灰 | 基础设施 / 跨切关注点 |
| 红 | 审计 / 不可变日志 |
