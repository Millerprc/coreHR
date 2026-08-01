# coreHR业务切片运行手册

> 适用范围：业务第一至第三阶段的首批可运行切片。

## 1. 启动环境

当前运行栈为PostgreSQL 16、Redis 7、FastAPI、React和Ant Design。MySQL、Oracle、多租户和应用服务器中间件延后到第五阶段。

在PowerShell中设置本地环境变量并启动：

```powershell
$env:COREHR_DB_PASSWORD = "本地随机数据库密码"
$env:COREHR_BOOTSTRAP_TOKEN = "一次性随机初始化凭证"
./scripts/dev-business-up.ps1
```

Linux或macOS：

```bash
export COREHR_DB_PASSWORD="本地随机数据库密码"
export COREHR_BOOTSTRAP_TOKEN="一次性随机初始化凭证"
./scripts/dev-business-up.sh
```

启动脚本会构建容器、等待PostgreSQL和Redis健康、启动业务API与Web，并执行数据库迁移。

## 2. 首个主管理员

数据库没有任何账号时，可执行一次初始化：

```powershell
$bootstrapBody = @{
  bootstrap_token = $env:COREHR_BOOTSTRAP_TOKEN
  username = "admin"
  display_name = "主管理员"
  password = "替换为至少12位的强密码"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/auth/bootstrap `
  -ContentType "application/json" `
  -Body $bootstrapBody
```

初始化完成后，再次调用会返回`409 BOOTSTRAP_ALREADY_COMPLETED`。生产环境必须使用HTTPS，并撤销初始化凭证。

## 3. 访问地址

- 主管理员工作台：`http://127.0.0.1:5173/business.html`
- 项目建设状态：`http://127.0.0.1:5173/`
- API与请求模型：`http://127.0.0.1:8000/docs`
- 服务就绪状态：`http://127.0.0.1:8000/health/ready`

## 4. 自动检查

PowerShell：

```powershell
./scripts/check-business-portable.ps1
```

Linux或macOS：

```bash
./scripts/check-business-portable.sh
```

检查脚本继承Compose中的数据库连接设置，并依次验证：

1. API和Web镜像构建。
2. Python语法与后端测试。
3. 前端测试和TypeScript严格检查。
4. `index.html`与`business.html`双入口生产构建。
5. 完整SQLAlchemy业务模型与PostgreSQL实际结构一致性。

## 5. 停止

```powershell
./scripts/dev-down.ps1
```

停止容器不会删除PostgreSQL数据卷。除非明确需要重新初始化，不要删除数据卷。

## 6. 当前边界

- 真实流程图未提供：流程引擎只支持定义、版本、发布和实例，不生成实际审批人或自动执行人事变更。
- 考勤规则未提供：支持规则容器、班次、排班、原始打卡、假期和请假，不生成正式日报、月报或薪资输入。
- 企业表结构和脱敏样例未提供：尚未完成正式导入映射、完整员工档案表单与历史数据校验。
- 一万人同时打卡或查询的容量目标尚未压测，不宣称已经达到。
