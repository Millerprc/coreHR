# coreHR

面向企业内部使用、按产品化方式建设的 HRIS。项目采用 AI Native Coding 方式开发，当前以 PostgreSQL、FastAPI、React 和 Ant Design 为技术基线。

## 当前状态

第零阶段工程底座已经完成，业务第一至第三阶段的主管理员工程 MVP 已落地，并通过自动化测试、本机 Docker 和浏览器整栈验证。

这里的“工程 MVP”不等于生产替换验收完成：正式编码对照、完整档案字段、真实人事流程图、合同正式字段/附件规则、企业考勤细则和打卡接口仍需补充。准确状态见[一至三阶段实现符合性审查](./docs/review/phase-1-3-implementation-conformance-review.md)。

### 已落地能力

- 平台底座：主管理员初始化、本地账号认证、角色权限、审计日志、统一错误和并发安全流水号。
- 第一阶段：数据字典、有效日期组织、法人及组织关系、负责人、BP、成本与收入目标、独立职务维度与有效日期职务目录、人员、工号、劳动/协议关系、任职、月度编制、快照和招聘需求。
- 数据治理：七类现状主数据支持 CSV 模板、预校验、逐行拒绝报告、来源追踪及幂等执行，并可按业务日期导出有效快照；另提供职务维度、职务的向前追加历史版本任务。组织导入保留历史编码并校验有效父级。
- 第二阶段：流程定义/发布/执行、会签/或签、审批任务、候选人、应聘、录用转待入职、合同/协议建档/变更/续签/解除/取消/到期提醒，以及直接生效、未来生效、审批生效和回退人事事件。
- 第三阶段：考勤规则版本、班次、排班、幂等原始打卡、假期、请假/销假、年度假期余额与不可变流水、可重算考勤日报和月报，以及月结/特殊业务期间冻结与有因解冻。
- 管理端：主管理员可在 9 个业务菜单中完成当前核心操作；普通角色和自助端尚未开放。

### 尚未宣称完成

- 未配置真实审批图时，只能验证通用流程能力，不能宣称企业审批链完成。
- 未配置企业考勤细则时，日报/月报仅用于技术验收，不能进入正式薪酬。
- 已开放七类非敏感现状主数据的批量导入、校验报告和有效快照导出，以及职务维度、职务的向前追加历史版本导入；企业正式码表仍待输入。组织多版本、人员、任职、编制等完整迁移、任意倒插历史、历史导出及批次回滚仍未完成。
- 尚未固化企业自动计提/跨年结转公式，也未完成真实打卡设备连接器、合同正式字段、附件归档和电子签章规则。
- 尚未完成一万人同时打卡、查询考勤或薪酬的容量验证。
- MySQL、Oracle、多租户和应用服务器中间件兼容性延后到第五阶段评估。

## 技术栈

- PostgreSQL 16
- Redis 7
- Python / FastAPI / SQLAlchemy / Alembic
- React / TypeScript / Vite / Ant Design
- Docker Compose

## 快速开始

详细步骤以[业务切片运行手册](./docs/implementation/business-runbook.md)为准。

PowerShell：

```powershell
$env:COREHR_DB_PASSWORD = "本地随机数据库密码"
$env:COREHR_BOOTSTRAP_TOKEN = "一次性随机初始化凭证"
./scripts/dev-business-up.ps1
```

Linux 或 macOS：

```bash
export COREHR_DB_PASSWORD="本地随机数据库密码"
export COREHR_BOOTSTRAP_TOKEN="一次性随机初始化凭证"
./scripts/dev-business-up.sh
```

启动脚本会构建容器、等待 PostgreSQL 和 Redis 就绪、启动 API 与 Web，并执行数据库迁移。首次启动后还需按照运行手册初始化主管理员。

## 访问地址

- 主管理员工作台：<http://127.0.0.1:5173/business.html>
- 项目建设状态：<http://127.0.0.1:5173/>
- API 文档：<http://127.0.0.1:8000/docs>
- 服务就绪状态：<http://127.0.0.1:8000/health/ready>

## 验证与停止

运行完整业务检查：

```powershell
./scripts/check-business-portable.ps1
```

检查会使用并自动清理独立临时测试库，运行全部后端数据库集成测试，不会读写现有业务数据；任一步失败都会返回失败码。

停止本地服务：

```powershell
./scripts/dev-down.ps1
```

停止服务不会删除 PostgreSQL 数据卷。

## 目录结构

```text
apps/api/                FastAPI 服务、业务模块、迁移和后端测试
apps/web/                React 管理端、状态页和前端测试
deploy/                  Docker Compose 与环境变量示例
docs/01-foundation/      项目基线、第一阶段规格、PRD 和决策记录
docs/adr/                架构决策记录
docs/delivery/           阶段交付回执
docs/implementation/     实施计划与运行手册
scripts/                 启动、停止和自动检查脚本
```

## 文档入口

- [正式文档目录](./docs/01-foundation/00-正式文档目录.md)
- [第一阶段需求规格](./docs/01-foundation/01-第一阶段需求规格.md)
- [第一阶段 PRD](./docs/01-foundation/02-第一阶段PRD.md)
- [项目决策](./docs/01-foundation/03-项目决策.md)
- [技术架构基线](./docs/01-foundation/04-技术架构基线.md)
- [代码结构与编码规范](./docs/01-foundation/10-代码结构与编码规范.md)
- [一至三阶段实现符合性审查](./docs/review/phase-1-3-implementation-conformance-review.md)
- [一至三阶段整体 Review 指南](./docs/review/phase-1-3-user-review-guide.md)
- [企业输入包 01：主数据与稳定编码对照](./docs/input-packs/01-master-code-mapping.md)
- [一至三阶段企业输入顺序](./docs/input-packs/00-enterprise-input-sequence.md)
- [已确认首个样本：职务体系与职务目录](./docs/input-packs/04-job-architecture-input.md)
- [当前输入：人员档案字段验收](./docs/input-packs/05-personnel-record-field-acceptance.md)
- [人员档案字段实施计划](./docs/implementation/personnel-record-field-delivery-plan.md)
- [ADR-0004：人员敏感字段应用层保护](./docs/adr/ADR-0004-personnel-sensitive-field-protection.md)
- [人员敏感字段密钥运行手册](./docs/implementation/personnel-sensitive-key-runbook.md)
- [人事流程图与审批规则输入包](./docs/input-packs/06-hr-workflow-input.md)
- [考勤、班次与假期规则输入包](./docs/input-packs/07-attendance-rule-input.md)
- [打卡来源与接口契约输入包](./docs/input-packs/08-punch-interface-input.md)
- [部署、安全、备份与容量验收输入包](./docs/input-packs/09-nonfunctional-acceptance-input.md)
- [旧EHR完整字典处置与coreHR映射基线](./docs/input-packs/03-ehr-lookup-full-extraction-and-mapping.md)
- [企业输入包 02：合同/协议正式字段与附件规则](./docs/input-packs/02-contract-agreement-fields-and-attachments.md)
- [第一阶段数据治理导入交付回执](./docs/delivery/P1-DATA-GOVERNANCE-IMPORT.md)
- [第一阶段有效日期职务体系交付回执](./docs/delivery/P1-JOB-ARCHITECTURE.md)
- [第三阶段考勤期间冻结交付回执](./docs/delivery/P3-ATTENDANCE-PERIOD-FREEZE.md)
- [第三阶段假期余额交付回执](./docs/delivery/P3-LEAVE-BALANCE.md)
- [第二阶段合同/协议生命周期交付回执](./docs/delivery/P2-CONTRACT-LIFECYCLE.md)
- [第一至第三阶段首批交付回执（历史快照）](./docs/delivery/P1-P3-BATCH-A.md)
- [待确认问题](./docs/01-foundation/99-待确认问题.md)

## 数据与安全

- 不提交密钥、Personal Access Token、`.env`、真实人员数据、本地数据库或构建产物。
- 示例配置只用于本地开发；生产环境必须使用独立强密码、HTTPS 和受控的凭据管理方式。
- 导入企业数据前必须完成脱敏、字段映射和校验规则确认。
- “数据治理”入口当前只接收九类非人员敏感导入任务：七类现状主数据和两类职务历史版本；单批最多 1000 行，未知列和人员敏感字段会被拒绝。
