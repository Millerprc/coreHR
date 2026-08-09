# coreHR业务工程MVP运行手册

> 适用范围：业务第一至第三阶段主管理员工程 MVP。

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

不要只执行基础 `deploy/compose.yaml`。业务 API 依赖 `deploy/compose.business.yaml` 叠加配置；优先使用上述启动脚本，避免遗漏业务入口或数据库迁移。

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

## 4. 主数据初始化

主管理员登录后进入“数据治理”，按以下顺序操作：

1. 选择数据字典、字典项、组织类型、法人主体、职务或组织。
2. 下载该类型的 CSV 模板，只填写模板中存在的列；不要增加人员、证件、薪酬或联系方式字段。
3. 填写来源系统、来源表或文件用途，选择 CSV 后先执行“校验批次”。
4. 查看逐行结果；被拒绝的行不会写入主数据。
5. 确认通过行并填写执行原因后，再执行导入。

单批最多 1000 行。同一来源记录和内容重复提交时会跳过；相同来源内容发生变化时会拒绝，等待后续明确更新策略。组织导入会保留 CSV 中的历史编码，要求组织类型已经存在，并按上级依赖排序；当前每个组织只初始化首个有效版本。人员、任职、编制及组织多版本等完整历史迁移仍未开放，也不提供物理删除或批次回滚。

如需核对当前主数据，点击“导出当前主数据”，选择一种类型后下载 CSV。导出口径为配置业务时区的当天有效数据，单次最多 50000 行，不包含人员、证件、薪酬或联系方式。该文件是审阅快照，不是历史全量备份；为防止表格公式注入，以危险符号开头的单元格会增加安全前缀。

## 5. 自动检查

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

## 6. 停止

```powershell
./scripts/dev-down.ps1
```

停止容器不会删除PostgreSQL数据卷。除非明确需要重新初始化，不要删除数据卷。

## 7. 当前边界

- 真实流程图未提供：通用流程发布、任务、会签/或签和人事事件执行/回退可验证，但不能宣称企业审批链完成。
- 考勤细则未提供：系统可以计算技术验收用日报/月报，但不能作为正式薪资输入。
- 已分析 EHR 源表结构和每表首行样例；六类主数据已有批量导入与校验报告，组织多版本/人员等完整迁移、回滚工具、完整员工档案表单与历史数据验收尚未完成。
- 当前优先支持主管理员；普通员工、自助端和细分数据权限尚未开放。
- 一万人同时打卡或查询的容量目标尚未压测，不宣称已经达到。

逐项完成度和下一轮资料顺序见[一至三阶段实现符合性审查](../review/phase-1-3-implementation-conformance-review.md)。
