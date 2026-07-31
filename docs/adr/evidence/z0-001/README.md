# Z0-001 验证工程

用于复跑 [ADR-0001-toolchain](../../ADR-0001-toolchain.md) 的版本兼容性验证。验收方可在任何 Docker 环境中跑下面任一命令复现。

## 目录

- `backend/` — 最小 FastAPI 应用 + pytest + 数据库连通性脚本
- `web/` — 最小 React 19 + Vite 6 + TypeScript 应用 + Vitest
- `docker-compose.yml` — 一键起 PostgreSQL 16.14、Redis 7.4.10、运行后端测试、运行前端测试与构建
- `scripts/run-all.sh` / `run-all.ps1` — 跨平台复跑入口

## 锁定版本

| 组件 | 版本 | 镜像 |
|---|---|---|
| Python | 3.13-slim | `python:3.13-slim` |
| Node | 24.18.1 LTS | `node:24.18.1-alpine` |
| PostgreSQL | 16.14 | `postgres:16.14-alpine` |
| Redis | 7.4.10 | `redis:7.4.10-alpine` |
| FastAPI | 0.118.0 | — |
| Uvicorn | 0.32.1 | — |
| Pydantic | 2.10.3 | — |
| Pydantic Settings | 2.7.0 | — |
| SQLAlchemy | 2.0.36 | — |
| Alembic | 1.14.0 | — |
| psycopg | 3.2.3 (binary) | — |
| redis-py | 5.2.1 | — |
| httpx | 0.28.1 | — |
| pytest | 8.3.4 | — |
| pytest-asyncio | 0.25.0 | — |
| React | 19.2.0 | — |
| react-dom | 19.2.0 | — |
| Vite | 6.4.3 | — |
| Vitest | 3.2.7 | — |
| @vitejs/plugin-react | 4.7.0 | — |
| TypeScript | 5.9.3 | — |
| @testing-library/react | 16.3.2 | — |
| @testing-library/jest-dom | 6.6.3 | — |
| jsdom | 30.0.1 | — |

> 说明：Ant Design 版本不在本验证范围内。ADR-0001 决策了 React 19 + Ant Design 6 方向，Ant Design 的版本锁由 Z0-005 任务 ADR 决定。

## 端口绑定

所有容器端口绑定到 `127.0.0.1`，不暴露到外部网络：

- PostgreSQL：`127.0.0.1:54329 -> 5432`
- Redis：`127.0.0.1:63800 -> 6379`

容器之间通过 compose 网络直接用 `pg` / `redis` 主机名访问。

## 复跑方式

### 一键复跑（推荐）

```bash
# POSIX / Git Bash
bash scripts/run-all.sh

# PowerShell
powershell -ExecutionPolicy Bypass -File scripts/run-all.ps1
```

或直接：

```bash
docker compose up --abort-on-container-exit
```

### 分步复跑

```bash
docker compose up -d pg redis
docker compose wait pg redis
docker compose run --rm backend
docker compose run --rm web
```

## 预期输出

- 后端：`2 passed`，随后 `[PG] OK version=PostgreSQL 16.14 ...`、`[REDIS] PING=True ... version=7.4.10`、`ALL OK`
- 前端：`Test Files 1 passed (1)`、`Tests 1 passed (1)`、`vite v6.4.3 building for production...`、生成 `dist/index.html` 和 `dist/assets/index-*.js`

## 验收

- 不创建任何业务模型。
- 不修改仓库其他目录。
- 仅在 `docs/adr/evidence/z0-001/` 范围内运行。
