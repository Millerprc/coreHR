# 当前运行手册

本文件是业务一至三阶段首批切片的当前权威入口。

## 启动

```powershell
$env:COREHR_DB_PASSWORD = "本地随机数据库密码"
$env:COREHR_BOOTSTRAP_TOKEN = "一次性随机初始化凭证"
./scripts/dev-business-up.ps1
```

## 访问

- 主管理员工作台：`http://127.0.0.1:5173/business.html`
- API文档：`http://127.0.0.1:8000/docs`

## 完整检查

使用会继承Compose数据库密码的可移植检查脚本：

```powershell
./scripts/check-business-portable.ps1
```

不要把初始化凭证、管理员密码或数据库密码提交到仓库。

## 后端集成测试（临时库）

`apps/api` 容器**没有挂载 `tests/`**，跑集成测试要用 `docker run` 整目录挂载：

```powershell
$root = "C:\Users\83289\Documents\HRMS\coreHR"
$enc = [System.Uri]::EscapeDataString("corehr_dev_only")
$testDb = "corehr_regression_test_$PID"
docker exec corehr-db-1 createdb --username corehr $testDb
$url = "postgresql+psycopg://corehr:${enc}@db:5432/$testDb"
docker run --rm --network corehr_default -v "${root}/apps/api:/work" -w /work -e PYTHONPATH=/work/src -e "DATABASE_URL=$url" -e "TEST_DATABASE_URL=$url" corehr-api sh -c "alembic -c alembic-business.ini upgrade head && alembic -c alembic-business.ini check && python -m compileall -q src && python -m pytest tests/integration -q -p no:cacheprovider"
docker exec corehr-db-1 dropdb --username corehr --if-exists --force $testDb
```

**临时库名必须包含 `test`**（不区分大小写）。`apps/api/tests/integration/conftest.py:32` 会检查库名，
不满足就抛 `RuntimeError: TEST_DATABASE_URL must point to a dedicated test database`，
结果是**全部用例报 error（不是 fail）**，看起来像代码坏了，其实只是库名不合约。

PowerShell 下 `alembic` 的 INFO 日志走 stderr，会触发 `NativeCommandError`；
跑这组命令时不要用 `$ErrorActionPreference = 'Stop'`，否则会在第一条 INFO 上就中断。

## 消息 worker 怎么跑

消息引擎是**平台内核基础服务**（D-100），投递由**独立 Worker 进程**承担，
**不挂在 API 应用启动路径上**——`docker compose up` 不会自动拉起它。

### 一次性冒烟（跑一轮就退出）

```powershell
$root = "C:\Users\83289\Documents\HRMS\coreHR"
docker run --rm --network corehr_default -v "${root}/apps/api:/work" -w /work `
  -e PYTHONPATH=/work/src -e DATABASE_URL="postgresql+psycopg://corehr:corehr_dev_only@db:5432/corehr" `
  corehr-api sh -c "python -m hris.modules.messaging.worker --once --log-level INFO"
```

### 常驻运行

```powershell
docker run -d --name corehr-worker --network corehr_default `
  -v "${root}/apps/api:/work" -w /work `
  -e PYTHONPATH=/work/src -e DATABASE_URL="postgresql+psycopg://corehr:corehr_dev_only@db:5432/corehr" `
  corehr-api sh -c "python -m hris.modules.messaging.worker --batch-size 50 --poll-interval 2"
```

常用参数：`--batch-size`（单轮领取上限，默认 50）、`--poll-interval`（空队列轮询间隔秒数，默认 2）、
`--once`（只跑一轮）、`--log-level`。

**多实例安全**：Worker 用 `FOR UPDATE SKIP LOCKED` 领取投递记录，
多个实例可以并行跑，不会重复消费同一条记录；重复消费也不会产生重复站内信
（消息本体在业务事务里已按幂等键去重）。

停止：`docker stop corehr-worker`（Worker 收到停止信号后优雅退出，不丢在途投递记录）。

### 实时推送（SSE）

端点 `GET /api/v1/messaging/stream`，用现有 Bearer 令牌鉴权：

```powershell
curl.exe -N -H "Authorization: Bearer <token>" "http://127.0.0.1:8000/api/v1/messaging/stream"
```

- 只推送**本人**的消息；带 `Last-Event-ID` 头可从断点续传。
- 默认连接时长 **120 秒**，到时服务端主动断开，客户端应自动重连（前端已实现指数退避重连）。
- 并发连接上限：全局 20、单用户 3，超限返回 503。
- **不要用 `EventSource`**（无法带 `Authorization` 头），前端用 `fetch` + `ReadableStream` 消费。

## 外部产品调研约束（Moka 等）

> 产品决策人 2026-10-24 追加的硬约束。

- **可以点开 Moka 看界面与流程**（只读浏览，用于功能结构对标）。
- **不得保存、删除或提交任何信息**：不点任何保存 / 删除 / 提交 / 确认类按钮，不在 Moka 里新建或修改任何数据，不触发任何写操作。
- 调研产出只作为**分析输入**，按 `docs/design/antd-page-interaction-standard.md` §9 转成 coreHR 自己的需求与视觉方案，不复制对方代码、商标、图标资产或整页成品。

---

## Pencil `.pen` 原型落盘

Pencil MCP（`mcp__pencil__execute`）**只改编辑器内存文档**，磁盘文件 `C:\Users\83289\Documents\HRMS\coreHR.pen`
的 mtime 与 size 不会变。MCP 侧也**读不到磁盘的新内容**（`Get("<磁盘里才有的 id>")` 会报 `Can't find node`），
所以**内存与磁盘可能同时存在两份内容**，必须由脚本显式同步。

### 落盘流程

1. **MCP 编辑**（`Insert` / `Copy` / `Update` / `Move` / `Delete`）。
2. **导出片段**：`Print(JSON.stringify(Get("<节点 id>", {depth:100})))`。
3. **Python 写回**：读磁盘 `.pen` → `json.loads` → 定位并替换 → `json.dumps(doc, indent=2, ensure_ascii=False)` 写回。
4. **写回前必须做字节级往返比对**：`json.dumps(doc, indent=2, ensure_ascii=False) == 磁盘原文`。
   不一致就**中止**，不要继续写（否则整个文件会被重排成全文件 diff）。
5. **写回后校验**：JSON 可解析、无 BOM、**无尾随换行**、节点 ID 无重复、`ref` 目标都存在。

### 增量落盘法（新增画板时用，别整树传输）

新增一张画板时，**不要把整棵子树从 MCP 传过来**：

- MCP 侧 `Copy("已有画板", document, {...})` 建画板 → 只改差异部分。
- 传输时**只导出差异子树**（例如抽屉内容框、底部操作条）。
- Python 侧：深拷贝磁盘上的已有画板 → **重编号所有节点 ID** → 替换差异子树 → 追加为新根节点。

这样上下文消耗降低一个数量级（整树约 30 KB/张，增量约 10 KB/张）。

### 重编号规则（踩过的坑）

磁盘 `.pen` 曾出现 **159 个重复节点 ID**：上一轮拼装画板时把一整棵子树复制进另一张画板却没重编号。
Pencil 载入时被迫重编号，**导致画布上的 ID 与磁盘文件里的 ID 不一致**（表现为「MCP 改不到自己刚写的节点」）。

- 重编号时**只改 `children` 里节点的 `id`**，不要动 `ref` 的值（指向顶层 COMP）和 `descendants` 的键（指向 COMP 的子节点 ID）。
- 改完必须**校验没有任何 `ref` / `descendants` 指向被重编号的 ID**。
- 磁盘根节点 ID 要与画布 ID 对齐（新画板用画布给的 ID），否则画板登记表里的 ID 对不上文件。

### 校验脚本

`tmp/pen-export/rebuild/` 下现成可用：

| 脚本 | 作用 |
|---|---|
| `patch_btn_split.py` | 按钮拆分落盘（带往返比对与备份） |
| `patch_new_boards.py` | 新画板增量落盘 |
| `alias_root_ids.py` | 磁盘根 ID 对齐画布 ID，并输出 size/sha256/节点数 |
| `validate_pen.py` | 结构校验：重复 ID、`ref` 目标存在、按钮顺序与文案覆盖 |

### 画布状态区（供画板输入）

1. 在画布上完成编辑 → `Export(["<画板 id>"], "png", "<目录>")` 实拍。
2. 预览图放 `docs/review/pen-prototypes/`，登记表放 `docs/review/pen-artboard-registry.json`。
3. 登记表里的 `sha256Prefix` / `sizeBytes` / `totalNodes` 由 `alias_root_ids.py` 输出，**不要手写**。

> PowerShell 控制台输出中文乱码是 GBK 问题，**文件本身是 UTF-8**。判定编码必须用 Python 或 Pencil `Export` 实拍。

---

当前仍是首批切片：企业导入映射、真实审批链、考勤核算规则和完整管理表单尚未完成。
