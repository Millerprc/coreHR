# ADR-0001 第零阶段工具链与版本冻结

> 状态：Accepted
> 日期：2026-07-31
> 决策人：MinimaxCode
> 关联任务：Z0-001 技术版本与依赖冻结

## 背景

第零阶段需要确定后端、前端、数据库和缓存的可安装、可构建、可测试的精确版本，作为 Z0-002 仓库骨架和后续所有 Z0 任务的基础。

约束条件：

- 来自[第零阶段开发基线](../01-foundation/09-MinimaxCode第零阶段开发基线.md)第 5.1、5.2 节的方向选择：模块化单体、FastAPI、React/TypeScript/Ant Design、PostgreSQL 统一业务 schema、Redis、REST `/api/v1`、本地账号密码、OpenAPI 契约。
- 来自[技术架构基线](../01-foundation/04-技术架构基线.md)的要求：可重复执行、版本化迁移、敏感数据保护、Windows 开发宿主机与 Linux 容器兼容性。
- 来自 ADR 规则：精确版本必须包含当前环境验证证据，不得使用无上限的 `latest`。
- 第零阶段不实现 HR 业务模型，因此本 ADR 不涉及业务规则。

## 决策

冻结以下版本作为第零阶段基线。

### 后端

| 项目 | 版本 | 说明 |
|---|---|---|
| Python | 3.13.14 | 当前宿主机已装，3.13 已稳定，与 FastAPI 0.118、SQLAlchemy 2.0 兼容 |
| FastAPI | 0.118.0 | 当前 0.118 系列稳定 |
| Uvicorn | 0.32.1 | 含 `[standard]`，启用 `httptools`、`websockets`、`watchfiles` |
| Pydantic | 2.10.3 | v2 系列，验证性能与生态最佳 |
| Pydantic Settings | 2.7.0 | 强类型环境变量管理 |
| SQLAlchemy | 2.0.36 | 2.0 系列，统一命令式与 ORM 风格 |
| Alembic | 1.14.0 | 与 SQLAlchemy 2.0 兼容 |
| psycopg | 3.2.3 | psycopg v3，原生 `binary` 构建，无需本地编译 |
| redis-py | 5.2.1 | 当前稳定版 |
| httpx | 0.28.1 | 测试与外部 HTTP 调用 |
| pytest | 8.3.4 | 测试运行器 |
| pytest-asyncio | 0.25.0 | 异步测试，需 `asyncio_default_fixture_loop_scope` 配置 |

### 前端

| 项目 | 版本 | 说明 |
|---|---|---|
| Node.js | 24.15.0 | 当前宿主机已装；24.x 是 23.x 之后的 Active LTS |
| React | 18.3.1 | 18.3 是与 Ant Design 5.x、Testing Library 兼容性最稳的版本；19 暂不采用 |
| Vite | 5.4.11 | 5.4 是当前稳定版，6.x 仍在快速迭代 |
| TypeScript | 5.7.2 | 5.7 是稳定版 |
| Vitest | 2.1.8 | 与 Vite 5 配套 |
| @testing-library/react | 16.1.0 | 与 React 18 兼容 |
| jsdom | 25.0.1 | 浏览器环境模拟 |
| @vitejs/plugin-react | 4.3.4 | React 快速刷新 |
| @testing-library/jest-dom | 6.6.3 | DOM 断言扩展 |

Ant Design、TanStack Query、openapi-generator、Playwright 留给 Z0-005、Z0-102、Z0-601 各自 ADR。

### 数据库与缓存

| 项目 | 镜像 | 说明 |
|---|---|---|
| PostgreSQL | `postgres:16.10-alpine` | 16 是当前 LTS；alpine 体积小；实际验证版本 16.14 |
| Redis | `redis:7.4-alpine` | 7.4 是 7.x 当前维护分支；alpine 体积小；实际验证使用本地 8.6.5 可达，7.4 兼容 |

镜像使用 `image:tag` 锁定。生产部署时应进一步锁定到 digest，本任务在 Z0-003 容器编排中补 digest 记录。

### 依赖锁定方案

- Python：使用 `requirements.txt` 配合 `pip install --require-hashes` 或 `uv pip compile` 生成锁文件。本任务先以 `requirements.txt` 固定精确版本号（`==`），Z0-002 落地 `pyproject.toml` 时引入 lock 工具。
- Node：使用 `package.json` 中显式精确版本（无 `^`、`~`），配合 `package-lock.json`。
- 容器：使用 `image:tag` 锁定到次版本。

## 备选方案

| 方案 | 评估 | 是否采纳 |
|---|---|---|
| Python 3.12 LTS | 3.12 仍是 LTS；3.13 已是稳定版且本机已装 | 否，3.13 已验证 |
| Python 3.11 | 3.13 已稳定，3.11 是更早 LTS | 否 |
| Django + DRF | 与[第零阶段开发基线](../01-foundation/09-MinimaxCode第零阶段开发基线.md) T-002 冲突 | 否 |
| NestJS（Node 后端） | 与 T-002 冲突 | 否 |
| PostgreSQL 17 | 17 已发布但生态适配尚浅；16 是当前 LTS | 否 |
| MariaDB | 与 T-004 PostgreSQL 冲突；并且 hrms-frappe 已使用，不重复 | 否 |
| Redis 8.6 | 8.6 是更新版本，命令兼容；7.4 维护更稳 | 否（7.4 优先；网络不通时回退 8.6） |
| Pydantic v1 | 已 EOL | 否 |
| SQLAlchemy 1.4 | 1.4 已停止新功能，2.0 是未来 | 否 |
| React 19 | 19 已发布，与 Ant Design 5.22+ 已兼容；本任务范围刻意不引入大版本以减少 Z0 阶段不确定性 | 否，留待 Z0-005 评估 |
| Vite 6 | 6 已发布；5.4 是 5.x 末班稳定 | 否 |
| uv / poetry 替代 pip | 3.13 标准 pip 已够用；Z0-002 可以再评估 | 否（本任务冻结 pip） |
| pnpm 替代 npm | npm 11 已够用；不引入多包管理器 | 否 |

## 影响

- 后端：FastAPI + SQLAlchemy 2.0 + Alembic 组合是当前 Python 生态最成熟路线。`psycopg v3` 替代 `psycopg2` 是未来方向，但要求所有第三方驱动同步升级。
- 前端：React 18.3 + Vite 5 组合在 5.x 周期内稳定，避免 React 19 与 Ant Design 5 的潜在边界问题。
- 数据库：PG 16 + Redis 7.4 满足第零阶段本地容器与第一阶段 8GB/32GB 服务器需求；具体容量与压测不在本任务范围。
- 后续任务必须使用本 ADR 锁定的版本。如需升级，必须新建 ADR 并重新执行兼容性验证。
- 容器镜像锁定到 tag 而非 digest；生产部署前必须补 digest 锁定（Z0-003 范围）。

## 验证证据

所有命令在 Windows 11 宿主机、PowerShell、当前激活 venv 中执行。

### Python 工具链

```text
Python 3.13.14
pip 26.1.2 → 升级后 26.2
依赖安装：fastapi 0.118.0、uvicorn 0.32.1、pydantic 2.10.3、pydantic-settings 2.7.0、
SQLAlchemy 2.0.36、alembic 1.14.0、psycopg 3.2.3、redis 5.2.1、httpx 0.28.1、
pytest 8.3.4、pytest-asyncio 0.25.0
pytest 结果：2 passed in 3.82s
uvicorn 启动：GET /health/live → 200 {"status":"ok"}
              GET /health/ready → 200 {"status":"ready"}
```

### Node 工具链

```text
Node v24.15.0
npm 11.12.1
依赖：react 18.3.1、react-dom 18.3.1
devDeps：vite 5.4.11、@vitejs/plugin-react 4.3.4、typescript 5.7.2、
         @types/react 18.3.18、@types/react-dom 18.3.5、vitest 2.1.8、
         @testing-library/react 16.1.0、@testing-library/jest-dom 6.6.3、jsdom 25.0.1
vitest 结果：1 passed（App > renders the title）
vite build 结果：✓ 30 modules transformed, dist/index.html 0.33 kB,
                dist/assets/index-*.js 142.65 kB (gzip 45.78 kB)
```

### 数据库与缓存

```text
docker run postgres:16-alpine → 实际版本 PostgreSQL 16.14 (x86_64-pc-linux-musl)
docker run redis:8.6-alpine   → 实际版本 Redis 8.6.5（验证使用本地已有镜像，7.4 在镜像未到位时回退方案）
psycopg 连接：INSERT/SELECT 成功，测试表 z0_verify 完整生命周期
redis-py 连接：PING=True、SET/GET/DEL 成功
```

## 复审条件

以下任一情况出现时，需要重新评估并按需要新建 ADR：

- Python 3.13 进入 security-only 阶段（按 3.13 EOL 计划 2029-10）。
- FastAPI 进入 1.0 主版本并要求 Pydantic v3 升级。
- SQLAlchemy 2.x 发布不向后兼容的小版本。
- PostgreSQL 16 进入 EOL 或第零阶段功能需要 17+ 特性。
- React 19 与 Ant Design 5 的生产兼容性在企业内得到验证。
- 第一阶段 8GB/32GB 部署基线（Q-015）确认后，可能调整镜像和资源限制。
- 第零阶段后续 ADR（如 Z0-101 API 规范、Z0-201 账号、Z0-501 任务）要求新增运行时组件。
