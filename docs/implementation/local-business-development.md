# 业务一至三阶段本地开发

> 当前交付性质：可运行的首批业务切片，不代表三个阶段全部完工。

## 1. 当前技术栈

- 数据库：PostgreSQL 16。
- 缓存：Redis 7。
- 服务端：Python 3.13、FastAPI、SQLAlchemy、Alembic。
- 管理端：React 19、Ant Design 6、Vite。
- MySQL、Oracle、多租户、中间件平台延后到第五阶段。

## 2. 启动

首次启动前，在当前终端设置两个本地环境变量：

```powershell
$env:COREHR_DB_PASSWORD = "替换为本地随机数据库密码"
$env:COREHR_BOOTSTRAP_TOKEN = "替换为一次性初始化凭证"
./scripts/dev-business-up.ps1
```

Linux或macOS使用：

```bash
export COREHR_DB_PASSWORD="替换为本地随机数据库密码"
export COREHR_BOOTSTRAP_TOKEN="替换为一次性初始化凭证"
./scripts/dev-business-up.sh
```

服务地址：

- 主管理员工作台：`http://127.0.0.1:5173/business.html`
- 建设状态页：`http://127.0.0.1:5173/`
- API契约：`http://127.0.0.1:8000/docs`
- 就绪检查：`http://127.0.0.1:8000/health/ready`

## 3. 首个主管理员

仅在数据库不存在任何账号时允许初始化一次：

```powershell
$body = @{
  bootstrap_token = $env:COREHR_BOOTSTRAP_TOKEN
  username = "admin"
  display_name = "主管理员"
  password = "替换为至少12位的管理员密码"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/auth/bootstrap `
  -ContentType "application/json" `
  -Body $body
```

初始化后再次调用会返回`409 BOOTSTRAP_ALREADY_COMPLETED`。生产环境必须使用HTTPS，并在初始化后撤销`COREHR_BOOTSTRAP_TOKEN`。

## 4. 数据库迁移

正常启动脚本会执行：

```powershell
docker compose -f deploy/compose.yaml -f deploy/compose.business.yaml exec api alembic upgrade head
```

完整业务模型的一致性检查使用`alembic-business.ini`。它在原迁移链上额外加载账号、权限、会话和流水号模型。

## 5. 自动检查

```powershell
./scripts/check-business.ps1
```

检查内容包括：

1. API和Web镜像构建。
2. Python语法编译和后端测试。
3. 前端组件测试和TypeScript严格检查。
4. 双入口生产构建。
5. SQLAlchemy模型与实际PostgreSQL结构一致性。

## 6. 当前边界

- 审批流程图未提供：支持定义、版本、发布和实例，不生成真实审批人，不自动执行人事变更。
- 考勤细则未提供：支持规则容器、班次、排班、原始打卡、假期和请假，不生成正式日/月核算结果。
- 企业表头与脱敏样例未提供：尚未做正式导入映射和员工全字段表单。
- 当前管理端完成登录、权限身份、阶段状态与核心数据计数；完整维护表单继续按原子任务交付。
- 本批未声明达到一万人同时打卡或查薪容量目标。
