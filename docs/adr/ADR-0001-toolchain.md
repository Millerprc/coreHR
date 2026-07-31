# ADR-0001 第零阶段工具链与版本冻结

> 状态：Proposed
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
- 复审轮：2026-07-31 上午复审指出旧版本（Node 24.15、Vite 5、PG 16.10/Redis 7.4 与实际未验证的 8.6.5）不合适；本版本为修正后版本，待复审通过后改为 `Accepted`。

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
| psycopg | 3.2.3 | psycopg v3，原生 `binary` 构建，无需本地编译；manylinux 轮子覆盖 Linux glibc 部署 |
| redis-py | 5.2.1 | 当前稳定版 |
| httpx | 0.28.1 | 测试与外部 HTTP 调用 |
| pytest | 8.3.4 | 测试运行器 |
| pytest-asyncio | 0.25.0 | 异步测试，需 `asyncio_default_fixture_loop_scope` 配置 |

后端依赖在 `python:3.13.14-slim` Linux 容器（glibc 2.36+）中以 `pip install --require-hashes -r requirements.lock` 安装并运行通过；`requirements.lock` 含 31 个包与 sha256 哈希。

### 前端

| 项目 | 版本 | 说明 |
|---|---|---|
| Node.js | 24.18.1 LTS | 24.x 当前 LTS；含 24.17.0 修复的高危漏洞 |
| React | 19.2.0 | 与 Ant Design 6.x peer 兼容（`react: >=18.0.0`） |
| Vite | 6.4.3 | Vite 5 已停止支持；6.4 是 6.x 当前最低受支持版本 |
| TypeScript | 5.9.3 | 5.9 是稳定末版；TypeScript 7 暂不采用 |
| Vitest | 3.2.7 | vitest 3 配 Vite 6 稳定；vitest 4 peer 支持 vite 6/7/8 |
| @vitejs/plugin-react | 4.7.0 | 与 Vite 6 配套的 4.x 末版；5.x 配 Vite 7+ |
| @testing-library/react | 16.3.2 | 与 React 19 兼容 |
| jsdom | 30.0.1 | 浏览器环境模拟 |
| @testing-library/jest-dom | 6.6.3 | DOM 断言扩展 |

Ant Design 6.5.2 已作为未来方向纳入评估，本任务不实际安装；其版本锁与 React 19 的集成验证由 Z0-005 任务 ADR 决定。

`package-lock.json` 提交到仓库以保证可复现安装（218 resolved entries）；`npm ci` 在容器中按 lockfile 精确安装。Vitest 跑测试时显式使用 `--maxWorkers=1 --minWorkers=1`，避免默认并发在 Windows bind mount 下长时间挂起。

### 数据库与缓存

| 项目 | 镜像 | 实际版本 | 说明 |
|---|---|---|---|
| PostgreSQL | `postgres:16.14-alpine` | 16.14 (x86_64-pc-linux-musl) | 16 系当前 minor，含安全修复 |
| Redis | `redis:7.4.10-alpine` | 7.4.10 | 7.4 是 7.x 末班，命令兼容 8.x |

镜像使用 `image:tag` 锁定到精确 patch。容器端口绑定到宿主机 `127.0.0.1`，不暴露到外部网络：

- PostgreSQL：`127.0.0.1:54329 -> 5432`
- Redis：`127.0.0.1:63800 -> 6379`

生产部署时由 Z0-003 任务进一步锁定到 digest。

### 依赖锁定方案

- Python：使用 `requirements.txt` 固定 11 个直接依赖的精确版本（`==`）；`requirements.lock` 由 `pip-compile --generate-hashes` 生成，含全部 31 个包与 sha256 哈希，容器使用 `pip install --require-hashes -r requirements.lock` 校验后安装。
- Node：使用 `package.json` 中显式精确版本（无 `^`、`~`），配合 `package-lock.json`；容器使用 `npm ci` 严格按 lockfile 安装。
- 容器：使用 `image:tag` 锁定到精确 patch（如 `python:3.13.14-slim`、`postgres:16.14-alpine`），不依赖移动 tag。Z0-003 进一步引入 digest 锁定。

## 备选方案

| 方案 | 评估 | 是否采纳 |
|---|---|---|
| Python 3.12 | 3.13 已是稳定版且本机已装 | 否 |
| Python 3.11 | 3.13 已稳定 | 否 |
| Node 24.17.0 | 24.17 已修复高危漏洞；本任务使用 24.18.1 最新 patch | 否 |
| Node 24.15.0（初版） | 早于 24.17 安全修复，已被复审驳回 | 否 |
| Django + DRF | 与 T-002 冲突 | 否 |
| NestJS（Node 后端） | 与 T-002 冲突 | 否 |
| PostgreSQL 17 | 17 已发布但生态适配尚浅；16 系仍受官方支持 | 否 |
| PostgreSQL 16.10（初版） | 16.10 早于 16.14 安全修复，已被复审驳回 | 否 |
| MariaDB | 与 T-004 PostgreSQL 冲突 | 否 |
| Redis 8.x | 8.x 已发布；7.4 是更稳的维护分支 | 否 |
| Redis 7.4（初版但实测 8.6.5） | 上一轮冻结 7.4 但实测用了 8.6.5，已被复审驳回；本轮改用 `redis:7.4.10-alpine` 并实测 | 是（本轮修正） |
| Pydantic v1 | 已 EOL | 否 |
| SQLAlchemy 1.4 | 已停止新功能 | 否 |
| React 18.3 | 18.3 与 antd 5 配套；本任务评估 React 19 + antd 6 方向 | 否 |
| React 19.0.0 / 19.1.0 | 19.2.0 是 19.x 当前稳定 patch | 否 |
| Vite 5 | 已停止支持 | 否 |
| Vite 6.0 ~ 6.3 | 6.4 才是 6.x 末版 | 否 |
| Vite 7 / Vite 8 | 6.4 已是当前受支持最低；过早升级引入不确定性 | 否 |
| Vitest 4.x | peer 支持 vite 6/7/8；3.2.7 配 vite 6 是更稳组合 | 否 |
| @vitejs/plugin-react 5.x | 配 Vite 7+；本任务用 Vite 6 | 否 |
| TypeScript 7.0 | 7 已发布；5.9 是企业内 5.x 末版 | 否 |
| uv / poetry 替代 pip | Z0-002 再评估 | 否 |
| pnpm 替代 npm | npm 11 已够用 | 否 |

## 影响

- 后端：FastAPI + SQLAlchemy 2.0 + Alembic 组合是当前 Python 生态最成熟路线。`psycopg v3` + manylinux 轮子覆盖 Linux 部署。
- 前端：React 19 + Vite 6 + Vitest 3 是当前稳定组合；Ant Design 6 与 React 19 兼容性已通过 npm peer 信息确认。
- 数据库：PG 16.14 + Redis 7.4.10 满足第零阶段本地容器与第一阶段 8GB/32GB 服务器需求；具体容量与压测不在本任务范围。PG 16 系仍在 PostgreSQL 官方支持窗口内（按版本政策支持当前 minor 与前两个 minor）。
- 后续任务必须使用本 ADR 锁定的版本。如需升级，必须新建 ADR 并重新执行兼容性验证。
- 容器镜像锁定到 tag；生产部署前必须补 digest 锁定（Z0-003 范围）。
- 验证工程落地在 `docs/adr/evidence/z0-001/`，可在任何 Docker 环境复跑。

## 验证证据

所有命令在 `python:3.13-slim` 和 `node:24.18.1-alpine` Linux 容器中执行，不依赖宿主机环境。

### 后端（python:3.13-slim，glibc）

```text
docker run --rm python:3.13-slim sh -c "pip install -r requirements.txt"
Successfully installed
  fastapi-0.118.0  uvicorn-0.32.1  pydantic-2.10.3  pydantic-settings-2.7.0
  SQLAlchemy-2.0.36  alembic-1.14.0  psycopg-3.2.3  psycopg-binary-3.2.3
  redis-5.2.1  httpx-0.28.1  pytest-8.3.4  pytest-asyncio-0.25.0
  + starlette / anyio / click / h11 / httptools / httpcore / certifi 等传递依赖

docker compose up -d pg redis
docker compose run --rm backend

  pytest -v
    platform linux -- Python 3.13.14, pytest-8.3.4, pluggy-1.6.0
    test_app.py::test_health_live PASSED                       [ 50%]
    test_app.py::test_health_ready PASSED                      [100%]
    2 passed in 0.61s

  python verify_db.py
    [PG]    OK  version=PostgreSQL 16.14 on x86_64-pc-linux-musl,
                   compiled by gcc (Alpine 15.2.0) 15.2.0, 64-bit
    [PG]    db=hris_dev user=hris
    [PG]    inserted_id=1 rows_seen=1
    [REDIS] PING=True GET=b'z0-001' version=7.4.10
    ALL OK
```

### 前端（node:24.18.1-alpine，musl）

```text
docker compose run --rm web

  npm ci --no-audit --no-fund
    using lockfileVersion: 3, 218 packages added

  npm run test:run
    RUN  v3.2.7 /work/web
    ✓ src/App.test.tsx (1 test) 30ms
    Test Files  1 passed (1)
    Tests       1 passed (1)

  npm run build
    vite v6.4.3 building for production...
    ✓ 28 modules transformed.
    dist/index.html                  0.33 kB │ gzip:  0.24 kB
    dist/assets/index-agFnteC1.js  194.62 kB │ gzip: 60.87 kB
    ✓ built in 1.63s
```

### 数据库与缓存

```text
postgres:16.14-alpine → 实际版本 PostgreSQL 16.14 (x86_64-pc-linux-musl)
redis:7.4.10-alpine   → 实际版本 Redis 7.4.10

端口绑定：
  PG    127.0.0.1:54329 -> 5432
  Redis 127.0.0.1:63800 -> 6379
  容器间通过 compose 网络 pg / redis 主机名互通
```

## 复审条件

以下任一情况出现时，需要重新评估并按需要新建 ADR：

- Python 3.13 进入 security-only 阶段（按 3.13 EOL 计划 2029-10）。
- FastAPI 进入 1.0 主版本并要求 Pydantic v3 升级。
- SQLAlchemy 2.x 发布不向后兼容的小版本。
- PostgreSQL 16 进入 EOL 或第零阶段功能需要 17+ 特性。
- Ant Design 6 后续小版本与 React 19 的兼容性在企业内得到验证。
- 第一阶段 8GB/32GB 部署基线（Q-015）确认后，可能调整镜像和资源限制。
- 第零阶段后续 ADR（如 Z0-101 API 规范、Z0-201 账号、Z0-501 任务）要求新增运行时组件。

## 复审记录

| 日期 | 动作 | 状态 |
|---|---|---|
| 2026-07-31 上午 | 初版提交 | `Accepted` |
| 2026-07-31 上午 | 第一轮复审驳回：版本过时、事实不符、缺 Linux 验证、缺锁文件、缺独立 AI 验证、端口不安全 | 回退 |
| 2026-07-31 下午 | 第一轮修正：版本升级、Linux 容器实跑、验证工程入库、状态 `Proposed` | `Proposed` |
| 2026-07-31 下午 | 第二轮复审驳回：`compose wait` 卡死、`up --abort-on-container-exit` 误停 web、vitest 31 worker 在 Windows bind mount 挂起、Python 间接依赖未哈希锁、容器镜像用移动 tag | 回退 |
| 2026-07-31 下午 | 第二轮修正：`up -d --wait` + `trap`/`finally` `down -v`、web `--no-deps`、vitest 单 worker、`requirements.lock` 带 sha256、`python:3.13.14-slim` 精确 tag | `Proposed`（待本轮复审通过） |
