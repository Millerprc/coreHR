# Z0-001 验证工程

用于复跑 [ADR-0001-toolchain](../../ADR-0001-toolchain.md) 的版本兼容性验证。验收方可在任何 Docker 环境中跑下面任一命令复现。

## 目录

- `backend/` — 最小 FastAPI 应用 + pytest + 数据库连通性脚本
  - `requirements.txt` — 直接依赖（11 个）
  - `requirements.lock` — pip-compile 生成的全量锁文件，31 个包 + sha256 hash
- `web/` — 最小 React 19 + Vite 6 + TypeScript 应用 + Vitest
  - `package.json` — 直接依赖
  - `package-lock.json` — npm ci 用的锁文件，218 resolved entries
- `docker-compose.yml` — 拉镜像、起 PG/Redis、运行后端、运行前端
- `scripts/run-all.sh` / `run-all.ps1` — 跨平台复跑入口

## 锁定版本

| 组件 | 版本 | 镜像 / 来源 |
|---|---|---|
| Python | 3.13.14 | `python:3.13.14-slim` |
| Node | 24.18.1 LTS | `node:24.18.1-alpine` |
| PostgreSQL | 16.14 | `postgres:16.14-alpine` |
| Redis | 7.4.10 | `redis:7.4.10-alpine` |
| FastAPI | 0.118.0 | `requirements.txt` |
| Uvicorn | 0.32.1 | `requirements.txt` |
| Pydantic | 2.10.3 | `requirements.txt` |
| Pydantic Settings | 2.7.0 | `requirements.txt` |
| SQLAlchemy | 2.0.36 | `requirements.txt` |
| Alembic | 1.14.0 | `requirements.txt` |
| psycopg | 3.2.3 (binary) | `requirements.txt` |
| redis-py | 5.2.1 | `requirements.txt` |
| httpx | 0.28.1 | `requirements.txt` |
| pytest | 8.3.4 | `requirements.txt` |
| pytest-asyncio | 0.25.0 | `requirements.txt` |
| React | 19.2.0 | `package.json` |
| react-dom | 19.2.0 | `package.json` |
| Vite | 6.4.3 | `package.json` |
| Vitest | 3.2.7 | `package.json` |
| @vitejs/plugin-react | 4.7.0 | `package.json` |
| TypeScript | 5.9.3 | `package.json` |
| @testing-library/react | 16.3.2 | `package.json` |
| @testing-library/jest-dom | 6.6.3 | `package.json` |
| jsdom | 30.0.1 | `package.json` |

间接依赖（starlette、anyio、certifi、typing-extensions、watchfiles、uvloop、websockets、httptools、httpcore、idna、h11、click、MarkupSafe、Mako、python-dotenv、pyyaml、pluggy、packaging、iniconfig 等）通过 `requirements.lock` 的 sha256 哈希锁定。

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

两个脚本都做了：

1. 拉取 4 个精确镜像。
2. `docker compose up -d --wait pg redis` 等待 healthcheck 通过。
3. `docker compose run --rm backend` 跑后端测试。
4. `docker compose run --rm --no-deps web` 跑前端测试与构建。
5. `try/finally` 或 `trap EXIT` 执行 `docker compose down -v`，成功失败都清理容器。

### 分步复跑

```bash
docker compose up -d --wait pg redis
docker compose run --rm backend
docker compose run --rm --no-deps web
docker compose down -v
```

> 注意事项：
> - `up --wait` 会等待 healthcheck 真正通过，因此 `up` 后立刻 `run` 是安全的。
> - 不要用 `up --abort-on-container-exit`：后端服务正常退出（exit 0）会触发 compose 整体停止，web 还没启动就被 SIGKILL（退出码 137）。
> - 不要用 `compose wait <service>`：`wait` 等待容器**退出**，PG/Redis 不会退出，会永久挂起。

## 预期输出

- 后端：pip 用 `--require-hashes` 校验 31 个包；`2 passed`；随后
  `[PG] OK version=PostgreSQL 16.14 ...`、`[REDIS] PING=True ... version=7.4.10`、`ALL OK`。
- 前端：`npm ci` 按 lockfile 安装；`vitest run --maxWorkers=1` 跑 `1 passed`；`vite v6.4.3 build` 生成 `dist/`。
- 在 Windows + Docker Desktop + bind mount 环境下，vitest 实测约 100+ 秒（受 bind mount I/O 影响，单 worker 串行）。

## 验收

- 不创建任何业务模型。
- 不修改仓库其他目录。
- 仅在 `docs/adr/evidence/z0-001/` 范围内运行。
- `requirements.lock` 与 `package-lock.json` 与 ADR 决策保持一致。
