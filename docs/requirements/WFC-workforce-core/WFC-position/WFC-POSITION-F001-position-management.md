# WFC-POSITION-F001 职位管理

> 模块：WFC / Workforce Core
> 能力域：WFC-POSITION / 职位与职务维度管理
> 状态：`DRAFT`
> 版本：v0.1
> 产品Owner：MillerMax（产品决策人）
> 业务Owner：产品决策人 MillerMax 兼任（仓库内没有记录企业侧 HR 业务负责人；依据 `docs/01-foundation/03-项目决策.md` D-066「用户负责业务规则、优先级和最终UAT确认」）
> 上级需求：[16-coreHR产品总体PRD](../01-foundation/16-coreHR产品总体PRD.md) §5.3 Workforce Core 职责（职务与人员关系）；[组织管理产品需求输入稿](../input-packs/10-organization-management-product-input.md) §5.10 职位与职务体系关系
> 依赖功能：无已批准的模块功能需求文档可作为前置依赖（本文件建立前 `docs/requirements/` 目录不存在）；本功能自身包含职务维度子能力，不拆成第二个功能
> 最后更新：2026-10-24

## 1. 背景与期望结果

- 当前问题：后端已经存在生效日期化的职务体系（`job_dimensions`、`job_dimension_versions`、`job_catalog_versions` 三张版本表由 `apps/api/alembic/versions/f1b000000001_effective_dated_job_architecture.py` 建立），且第一阶段已交付「按生效日期查看、新建维度/职务和新增未来版本」的管理端能力（`docs/delivery/P1-JOB-ARCHITECTURE.md`）。但组织管理分组下的「职位管理」入口此前保持禁用（`docs/input-packs/10-organization-management-product-input.md` §10「暂不实现：职位管理入口保持禁用」），职务目录只能靠 CSV 导入维护。2026-10-24 前端已按 Pencil 画板 `op8Nx` 实现该宿主页（`apps/web/src/business/features/organization/PositionWorkspace.tsx`），但按《模块功能需求文档规范》§10.2 / D-087，缺少功能需求文档登记画板 ID 时，前端开发任务没有合法依据，画板状态也无处落档。
- 用户价值：产品决策人和职务体系维护者可以在一个页面按生效日期查看职位目录与四类职务维度；任何调整都形成新版本，历史版本不被覆盖，编制、任职、招聘需求引用职位时按目标日期校验的结果稳定可解释。
- 本功能完成后可观察的业务结果：
  1. 侧栏「组织管理 › 职位管理」进入宿主页，按当前生效日期列出职位目录，并显示有效职位、职级、职等、职类、序列五项指标（`PositionWorkspace.tsx:551-557`）。
  2. 「新建职位」「新增版本」在 Modal 内完成，保存后职位目录出现新版本且旧版本区间自动闭合。
  3. 每次创建与版本变更在审计日志中留下 `object_type=job` / `object_type=job_dimension` 的记录。
- 不做本功能的影响：任职、编制月度版本、招聘需求在选定目标日期时会拒绝引用不存在或未启用的职务（`apps/api/src/hrris/modules/workforce/extended_service.py:474-480` `ensure_job_effective`），目录只能靠导入批次变更，缺少页面上的可见性和版本历史解释。

## 2. 范围

### 2.1 纳入范围

- 职位列表宿主页：指标条、职位列表 / 职务维度两个页签、生效日期筛选、搜索、重置、职位表格与分页（`PositionWorkspace.tsx:525-626`）。
- 职位新建与新增版本：Modal 表单「职位标识 / 所属维度 / 生效与变更」三组字段（`PositionWorkspace.tsx:628-749`）。
- 职务维度新建与新增版本：Modal 表单「维度标识 / 层级与顺序 / 生效与变更」三组字段（`PositionWorkspace.tsx:751-842`）。
- 职位与四类职务维度（职级 / 职等 / 职类 / 序列）的按生效日期版本维护。
- 无权限拒绝态（`PositionWorkspace.tsx:514-522`）、加载失败与空态、审计写入。
- 本功能的 Pencil 画板登记（见 §10.4）。

### 2.2 不纳入范围

- 职位与部门（组织）的关联维护：D-085 已确认「职位与部门为可选多对多关系」，但 `job_catalog` 无部门关联列（`apps/api/src/hris/modules/workforce/models.py:127-145`），当前后端无此数据面。
- 职位族 / 职位类 / 职位子类体系与「职位关联一个职务、一个职级、多个职等」的模型：`docs/input-packs/10-organization-management-product-input.md` §5.7–§5.9、D-073～D-082 描述的新体系尚未落到 `job_catalog`；当前 `job_catalog` 只保存单一 `grade_code`（`models.py:139`），无法承载「多个职等连续区间」（D-086）。
- 职位的物理删除与撤销版本：本模块无 DELETE 接口（`apps/api/src/hris/modules/workforce/extended_api.py` 职位相关路由只有 2 组 POST + 2 组 GET），也无撤销版本入口。
- 职位目录的页面导出：本页面没有导出入口（`position-api.ts:111-143` 无下载调用）。
- 汇报关系、人员中心、操作日志等其他工作区的页面需求（各自独立成功能文档）。
- 职务维度的跨类型统一检索、指标条推广到其他工作区（见 §18 Q-04、Q-05）。

### 2.3 假设与约束

| ID | 状态 | 内容 | 假设不成立时的处理 |
|---|---|---|---|
| ASM-01 | `PENDING` | 企业完整职务目录、职级、职等、职类、序列码表尚未全部提供，当前仅有 2026-08-12 确认的首个组合（`docs/input-packs/04-job-architecture-input.md` §1、§4；`docs/01-foundation/99-待确认问题.md` Q-012） | 页面按库内现有目录展示；缺少目录项不阻塞本功能验收，涉及企业码表完整性时按 §18 Q-06 挂起 |
| ASM-02 | `CONFIRMED` | 前端日期控件取浏览器本地日期（`PositionWorkspace.tsx:75-81` `today()`），后端缺省 `effective_at` 取业务时区当天（`extended_api.py:85-86` → `apps/api/src/hris/core/config.py:22` `Asia/Shanghai`） | 前端始终显式传 `effective_at`，后端不再使用缺省值；两者不一致时以请求中显式传入的 `effective_at` 为准 |
| ASM-03 | `CONFIRMED` | 除持 `*` 的主管理员外，没有第二个账号被授予 `WORKFORCE_ADMIN`：该权限码在 `apps/api/alembic/versions/` 全量迁移中没有 seed 行（唯一引用是 `f1c000000001_personnel_record_foundation.py:180` 的一句 SELECT） | 本功能验收由主管理员完成；普通角色的权限分级验收按 §18 Q-07 与 P-18 批次①处理 |
| ASM-04 | `CONFIRMED` | 「职位」在产品术语中与「职务」是不同对象（`docs/input-packs/10-organization-management-product-input.md` §5.10、D-084、D-085），而当前页面维护的是后端 `job_catalog`（职务目录） | 本文档按现状把「职位管理」作为页面名与功能名，数据合同按 `job_catalog` 描述；术语与数据模型的差异记为 §18 Q-03，不在本功能内自行改模型 |

## 3. 参与者、权限边界和业务场景

| 参与者 | 目标 | 前置权限 | 数据范围 |
|---|---|---|---|
| 主管理员 | 维护职位目录与四类职务维度，按生效日期形成新版本 | `*`（`apps/api/src/hris/modules/platform/dependencies.py:90` 对 `*` 短路放行） | 全部职位与职务维度；本模块无行级数据范围 |
| 职务体系维护者 | 同上 | `WORKFORCE_ADMIN`（`apps/api/src/hris/modules/workforce/extended_api.py:60`） | 全部职位与职务维度；本模块无行级数据范围 |
| 只读查看者 | 查看职位目录与职务维度 | 当前不存在只读权限码：读接口与写接口同为 `WORKFORCE_ADMIN`，因此只读账号访问即 403 | 不适用——见 §9 PERM006 与 §18 Q-08 |
| 未登录 / 会话失效访问者 | —— | 无有效会话 | 401 `AUTHENTICATION_REQUIRED` / `SESSION_INVALID`（`dependencies.py:32`、`:47`） |

场景边界说明：本功能只有一个业务结果——「维护职位目录及其生效版本」。查看与编辑是同一结果的不同参与深度，不拆成两个功能；职务维度与职位共用同一页面、同一权限和同一套版本语义，拆成两个功能会重复字段合同与权限合同。

## 4. 名词与依赖

| 名词/依赖 | 定义或引用 | 数据所有者 |
|---|---|---|
| 职位（页面口径） | 页面「职位管理」中的一条职位记录，对应后端 `job_catalog` 行及其 `job_catalog_versions` 版本行 | Workforce Core（`apps/api/src/hris/modules/workforce/models.py:127-145`、`:191-237`） |
| 职务（后端口径） | `job_catalog` 的后端命名，`JobResponse` 不区分「职位 / 职务」 | Workforce Core |
| 职务维度 | 职级、职等、职类、序列四类主数据：`job_dimensions` 稳定主档 + `job_dimension_versions` 版本行 | Workforce Core（`models.py:148-188`） |
| 生效日期版本 | 以 `effective_from` / `effective_to` 表达的业务有效区间，版本表是事实来源，`job_catalog` 旧列是兼容投影 | Workforce Core（`docs/delivery/P1-JOB-ARCHITECTURE.md` §2） |
| 兼容投影 | `job_catalog` 上仍保留的 `name`、`level_code`…`status`、`effective_from/to`、`attributes` 旧列，新版本写入时同步刷新（`extended_service.py:604-612`） | Workforce Core |
| 组织 / 部门 | `organizations` 等组织数据，本功能只读不写 | Workforce Core |
| 下游引用方 | 任职、编制月度版本、招聘需求、人事调动按目标日期校验职位是否有效（`extended_service.py:474-480`） | 各业务模块，通过公开查询接口引用，不在本功能内写入 |

## 5. 用户故事

### WFC-POSITION-F001-US01 按生效日期查看职位目录

作为职务体系维护者，我希望按生效日期查看当前有效的职位目录，从而确认某一天组织可以引用哪些职位。

- 触发条件：进入「组织管理 › 职位管理」，或修改筛选区「生效日期」。
- 前置条件：账号具备 `WORKFORCE_ADMIN` 或 `*`；后端 `job_catalog_versions` 已有数据。
- 主路径：页面加载 → 并行请求 `GET /api/v1/workforce/jobs?effective_at={日期}&limit=20&offset=0` 与 `GET /api/v1/workforce/job-dimensions?...`（`PositionWorkspace.tsx:229-264`）→ 指标条显示「有效职位 / 职级 / 职等 / 职类 / 序列」→ 职位表格按「职位编码、职位名称、所属维度（职级、职等、职类、序列）、生效日期、版本、状态、操作」展示，生效日期渲染为「{from} 至 {to ?? "长期"}」。
- 结束状态：表格显示该日期有效的职位版本；无数据时显示空态「没有符合条件的职位」；无权限时显示「无权查看职位管理」。

### WFC-POSITION-F001-US02 新建职位

作为职务体系维护者，我希望新建一个职位并指定它引用的四类职务维度，从而让编制和任职可以引用新的职位。

- 触发条件：在「职位列表」页签点击「新建职位」。
- 前置条件：账号具备 `WORKFORCE_ADMIN`；目标生效日期上四类维度均存在且处于启用状态。
- 主路径：打开 Modal（宽 760，`PositionWorkspace.tsx:628-639`）→ 填写「职位标识」（职位编码、职位名称）→「所属维度」（职级、职等、职类、序列，均为可搜索下拉，选项来自启用中的维度 `PositionWorkspace.tsx:303-316`）→「生效与变更」（状态、生效日期、失效日期、变更原因、备注）→ 点击「保存」→ 提交 `POST /api/v1/workforce/jobs`。
- 结束状态：服务端创建 `job_catalog` 行与 `version=1` 的版本行，刷新两个列表，Modal 关闭；若维度未生效则返回 422，Modal 内保留已填内容并在顶部显示错误（`PositionWorkspace.tsx:640-642`）。

### WFC-POSITION-F001-US03 新增职位未来版本

作为职务体系维护者，我希望在不覆盖历史的前提下新增一个未来生效的职位版本，从而让职级、名称或状态的变化按时间留痕。

- 触发条件：在职位表格「操作」列点击「新增版本」。
- 前置条件：账号具备 `WORKFORCE_ADMIN`；该职位已存在至少一个版本。
- 主路径：打开 Modal（标题「新增职位版本」）→ 编码以文字形式展示为「稳定编码：{code}（版本不修改编码）」（`PositionWorkspace.tsx:653-656`）→ 生效日期默认取「原生效日期 + 1 天」与「今天」中较晚者（`PositionWorkspace.tsx:94-98`）→ 填写变更原因 → 提交 `POST /api/v1/workforce/jobs/{job_id}/versions`。
- 结束状态：生成 `version+1` 的版本行，旧版本 `is_current=false` 且 `effective_to` 自动收敛为新版本生效日减一天（`extended_service.py:583-585`），`job_catalog` 兼容投影同步刷新。

### WFC-POSITION-F001-US04 维护职务维度

作为职务体系维护者，我希望维护职级、职等、职类、序列四类维度及其层级，从而让职位可以引用稳定的维度代码。

- 触发条件：切换到「职务维度」页签，点击「新建职务维度」或某一行的「新增版本」。
- 前置条件：账号具备 `WORKFORCE_ADMIN`。
- 主路径：填写「维度标识」（维度类型、维度代码、维度名称）→「层级与顺序」（上级维度、显示顺序）→「生效与变更」（状态、生效日期、失效日期、变更原因、备注）→ 提交 `POST /api/v1/workforce/job-dimensions` 或 `POST /api/v1/workforce/job-dimensions/{id}/versions`。
- 结束状态：维度主档与版本行落库；父级未生效时返回 422 `JOB_DIMENSION_PARENT_NOT_EFFECTIVE`；父级成环时返回 422 `JOB_DIMENSION_PARENT_CYCLE`（`extended_service.py:185-198`）。

## 6. 业务流程与状态机

```text
职位记录（job_catalog 稳定身份 + job_catalog_versions 版本链）
  新建 ──► 版本1（is_current=true，effective_to 可空）
              │ 新增版本（effective_from 必须晚于最新版本）
              ▼
           版本2（is_current=true；版本1 的 effective_to = 新版本生效日 - 1 天，is_current=false）
              │ ……
              ▼
           版本N（历史版本只读，不在本页面展示）

职务维度记录（job_dimensions 稳定身份 + job_dimension_versions 版本链）
  同上，额外约束：父维度在生效日必须存在且启用，且不得形成循环。
```

| 当前状态 | 操作 | 条件 | 下一状态 | 失败结果 |
|---|---|---|---|---|
| 职位编码不存在 | `POST /jobs` | 编码唯一、四类维度在 `effective_from` 有效且启用 | 版本 1 生效 | 409 `JOB_CODE_EXISTS`；422 `JOB_DIMENSION_NOT_EFFECTIVE` |
| 职位已有版本 | `POST /jobs/{id}/versions` | `effective_from` 晚于最新版本生效日 | 新版本生效，旧版本区间自动闭合 | 409 `JOB_VERSION_DATE_NOT_FORWARD`；404 `JOB_NOT_FOUND` |
| 维度代码不存在 | `POST /job-dimensions` | 同类型内编码唯一、父级有效 | 版本 1 生效 | 409 `JOB_DIMENSION_CODE_EXISTS`；422 `JOB_DIMENSION_PARENT_NOT_EFFECTIVE`；422 `JOB_DIMENSION_PARENT_CYCLE` |
| 维度已有版本 | `POST /job-dimensions/{id}/versions` | `effective_from` 晚于最新版本生效日 | 新版本生效，旧版本区间自动闭合 | 409 `JOB_DIMENSION_VERSION_DATE_NOT_FORWARD`；404 `JOB_DIMENSION_NOT_FOUND` |
| 任意写操作 | 提交请求 | 权限满足 | 数据与审计在同一事务内提交（`apps/api/src/hris/core/database.py:18-25`） | 403 `PERMISSION_DENIED`；422 `REQUEST_VALIDATION_FAILED` |

## 7. 业务规则

状态约定：`CONFIRMED` 表示该规则已有已确认决策、已交付能力或服务端强制的合同约束支撑；`PENDING` 表示该规则取决于尚未签字的产品决策，开发者不得自行猜测；`NOT_APPLICABLE` 表示经核查本功能不涉及，并写明依据。

| ID | 状态 | 规则 | 规则来源 | 验证方式 |
|---|---|---|---|---|
| WFC-POSITION-F001-BR001 | `CONFIRMED` | 职位稳定编码在系统内全局唯一；同一编码重复创建时返回 409 `JOB_CODE_EXISTS`，不覆盖既有职位 | 实现 `extended_service.py:503` + `models.py:136` UniqueConstraint；输入包 04 §3「全局唯一稳定职务代码」 | AC004 |
| WFC-POSITION-F001-BR002 | `CONFIRMED` | 职位编码必须匹配 `^[A-Z0-9][A-Z0-9_.-]{0,49}$`，长度上限 50 位 | 契约 `extended_schemas.py:107`、`:109-112`；前端同规则 `PositionWorkspace.tsx:43` 与提示文案「使用大写字母、数字、点、下划线或短横线，最多 50 位」 | AC002 |
| WFC-POSITION-F001-BR003 | `CONFIRMED` | 新建或变更职位时，`level_code`、`grade_code`、`class_code`、`sequence_code` 必须分别指向在目标生效日有效且 `status=active` 的职级、职等、职类、序列；否则整单拒绝并返回 422 `JOB_DIMENSION_NOT_EFFECTIVE`，不写入任何数据 | 实现 `extended_service.py:383-411`；前端只把启用维度放进下拉选项 `PositionWorkspace.tsx:303-316` | AC003 |
| WFC-POSITION-F001-BR004 | `CONFIRMED` | 新版本的 `effective_from` 必须严格晚于该职位最新版本的 `effective_from`；不满足时返回 409 `JOB_VERSION_DATE_NOT_FORWARD`，历史版本不被修改 | 实现 `extended_service.py:570-575`；前端同规则校验并提示「新版本生效日期必须晚于 {原生效日}」（`PositionWorkspace.tsx:714-720`） | AC002 |
| WFC-POSITION-F001-BR005 | `CONFIRMED` | 新增版本时，若旧版本的 `effective_to` 为空或大于等于新版本生效日，系统把旧版本的 `effective_to` 置为新版本生效日减一天并置 `is_current=false`；旧版本的名称、状态、维度引用不被改写 | 实现 `extended_service.py:583-585` | AC005、AC008 |
| WFC-POSITION-F001-BR006 | `CONFIRMED` | `effective_to` 不得早于 `effective_from`；后端由 CheckConstraint `effective_period_order` 兜底，前端提示「失效日期不能早于生效日期」 | 实现 `models.py:196-199`、`:163-166`；前端 `PositionWorkspace.tsx:729-739`、`:821-831` | AC002 |
| WFC-POSITION-F001-BR007 | `CONFIRMED` | 每次创建与版本变更必须填写 `change_reason`（1–500 字符），后端以该值写入审计记录的 `reason` 字段 | 契约 `extended_schemas.py:119`、`:140`；审计写入 `extended_service.py:544-550`、`:614-621` | AC007 |
| WFC-POSITION-F001-BR008 | `CONFIRMED` | 职务维度代码在同类型内唯一；重复创建返回 409 `JOB_DIMENSION_CODE_EXISTS` | 实现 `extended_service.py:230-241`；`models.py:151` UniqueConstraint | AC010 |
| WFC-POSITION-F001-BR009 | `CONFIRMED` | 职务维度的父维度必须在生效日存在且启用，否则返回 422 `JOB_DIMENSION_PARENT_NOT_EFFECTIVE`；父级链路形成循环时返回 422 `JOB_DIMENSION_PARENT_CYCLE` | 实现 `extended_service.py:169-224` | AC010 |
| WFC-POSITION-F001-BR010 | `CONFIRMED` | 职位列表按请求中的 `effective_at` 返回该日期有效（`effective_from <= effective_at` 且 `effective_to` 为空或不早于 `effective_at`）的职位版本；未传 `effective_at` 时后端取业务时区当天 | 实现 `extended_service.py:631-637`、`extended_api.py:85-86`、`:146-149` | AC008 |
| WFC-POSITION-F001-BR011 | `CONFIRMED` | 列表按 `job_catalog.code` 升序返回，总数按去重职位计数；前端按 `limit=20` 服务端分页 | 实现 `extended_service.py:643`、`:654-659`；前端 `PositionWorkspace.tsx:40`、`:235-236` | AC001 |
| WFC-POSITION-F001-BR012 | `PENDING` | 搜索框「搜索职位名称或编码」只对当前已加载页内的数据做大小写不敏感匹配，不是服务端检索；是否改为服务端检索取决于产品对规模与一致性的判断 | 现状实现 `PositionWorkspace.tsx:274-281`；画板说明 §5 差异说明第 3 条同属「有意保留的实现特征」 | 见 §18 Q-05 |
| WFC-POSITION-F001-BR013 | `PENDING` | 「重置」只清空搜索词并回到第 1 页，不清空生效日期筛选（与操作日志页的「重置清空全部筛选」语义不一致） | 现状实现 `PositionWorkspace.tsx:535-539`；画板说明 §5 差异说明第 1 条明确保留 | 见 §18 Q-04 |
| WFC-POSITION-F001-BR014 | `PENDING` | 职务维度页签的分页是静态的：表格固定每页 20 条且没有翻页控件，实际最多加载 500 条，超出部分在页面上不可达 | 现状实现 `PositionWorkspace.tsx:41-42`、`:252-256`、`:616-620`；画板说明 §5 差异说明第 3 条 | 见 §18 Q-05 |
| WFC-POSITION-F001-BR015 | `PENDING` | 指标条「有效职位 / 职级 / 职等 / 职类 / 序列」是否保留在职位管理页、是否推广到其他工作区 | 现状实现 `PositionWorkspace.tsx:551-557`；画板 `op8Nx` 已画；待确认清单 P-06「指标条是否推广到其他工作区」 | 见 §18 Q-04 |
| WFC-POSITION-F001-BR016 | `PENDING` | 职位载荷中的 `source_job_id` 与 `attributes` 是否在本页面提供录入控件；当前契约存在但表单无控件 | 契约 `extended_schemas.py:116`、`:118`；实现 `PositionWorkspace.tsx:146`、`:148`、`:167`、`:169`；画板说明 §5 差异说明第 5 条 | 见 §18 Q-09 |
| WFC-POSITION-F001-BR017 | `PENDING` | 停用（`status=inactive`）职位或维度前是否必须检查当前有效引用与未来生效引用；当前后端没有引用检查，只写版本 | 缺口对照 `docs/input-packs/10-organization-management-product-input.md` §3「禁用前检查当前有效引用和未来生效引用；任一存在时拒绝禁用并说明引用来源」；当前实现 `extended_service.py:502-622` 无该校验 | 见 §18 Q-06 |
| WFC-POSITION-F001-BR018 | `PENDING` | 「新增版本」属于改写职务目录的高风险操作，是否需要二次确认（Popconfirm）；当前实现没有二次确认 | 现状实现 `PositionWorkspace.tsx:453-462`、`:628-639`；规范 §5「高风险操作说明具体对象、影响和是否可恢复」 | 见 §18 Q-10 |

规则写法自查（对照规范 §8.1 / §8.2）：所有 `CONFIRMED` 规则都写明了适用对象与时间点、条件与唯一性维度、成功与拒绝结果、历史版本影响，不使用「合理处理」「一般情况」「尽量」等表述；不包含未说明配置范围的「支持灵活配置」、未说明幂等与最终状态的「失败后重试」、未说明下游与历史保留的「可以回退」。

## 8. 数据要求

### 8.1 数据所有权与关系

- 本功能拥有的数据：
  - `job_dimensions`（职务维度稳定主档，字段 `dimension_type`、`code`）与 `job_dimension_versions`（维度版本行）。
  - `job_catalog`（职位稳定主档，含兼容投影列）与 `job_catalog_versions`（职位版本行，版本事实来源）。
  - 归属模块：Workforce Core；表定义见 `apps/api/src/hris/modules/workforce/models.py:127-237`；迁移见 `apps/api/alembic/versions/f1b000000001_effective_dated_job_architecture.py`。
- 引用但不拥有的数据：组织（`organizations`）、人员（`persons`）、任职（`employments`）、编制（`headcount_plans`）、招聘需求等，通过 `job_catalog.id` 引用职位稳定身份。
- 业务唯一键：
  - `job_catalog.code` 全局唯一（`models.py:136`）。
  - `job_dimensions(dimension_type, code)` 唯一（`models.py:151`）。
  - `job_catalog_versions(job_id, version)` 唯一且 `version > 0`（`models.py:194-195`）。
  - `job_dimension_versions(dimension_id, version)` 唯一且 `version > 0`（`models.py:161-162`）。
- 有效日期/版本/快照要求：
  - 同一对象的版本区间不得重叠，且 `effective_to` 不得早于 `effective_from`（CheckConstraint `effective_period_order`，`models.py:131-133`、`:196-199`、`:163-166`）。
  - 新版本生效日必须晚于最新版本生效日（`extended_service.py:570-575`、`:298-303`）。
  - 查询以版本表为事实来源，`job_catalog` 旧列只是兼容投影（`docs/delivery/P1-JOB-ARCHITECTURE.md` §2）。
  - 快照：编制月度版本与招聘需求按目标日期引用职位，本功能不产生快照数据。

### 8.2 字段合同

「来源」列中的文件均位于 `apps/api/src/hris/modules/workforce/extended_schemas.py`，行号在括号内注明。

| ID | 字段 | 类型/格式 | 必填 | 来源 | 默认值 | 校验 | 敏感级别 | 历史策略 |
|---|---|---|---|---|---|---|---|---|
| WFC-POSITION-F001-DAT001 | `code` | string(50)，`^[A-Z0-9][A-Z0-9_.-]{0,49}$` | 条件必填：新建职位必填；新增版本不传且不可改 | `JobCreate.code`（:107）、`JobResponse.code`（:151） | 无 | 全局唯一，重复 409 `JOB_CODE_EXISTS` | 非敏感 | 稳定编码；新增版本时以文字展示「稳定编码：{code}（版本不修改编码）」（`PositionWorkspace.tsx:653-656`） |
| WFC-POSITION-F001-DAT002 | `name` | string(200) | 是 | `JobCreate.name`（:108）、`JobResponse.name`（:152） | 无 | 1–200 字符 | 非敏感 | 按版本保存（`models.py:209`） |
| WFC-POSITION-F001-DAT003 | `level_code` | string(50)，同 DAT001 正则 | 是 | `JobCreate.level_code`（:109）、`JobResponse.level_code`（:153） | 无 | 目标生效日必须存在有效且启用的 LEVEL 维度，否则 422 `JOB_DIMENSION_NOT_EFFECTIVE` | 非敏感 | 版本内以 `level_dimension_id` 固化引用（`models.py:210-214`） |
| WFC-POSITION-F001-DAT004 | `grade_code` | string(50)，同 DAT001 正则 | 是 | `JobCreate.grade_code`（:110）、`JobResponse.grade_code`（:154） | 无 | 同 DAT003，维度类型为 GRADE | 非敏感 | 同 DAT003（`models.py:215-219`） |
| WFC-POSITION-F001-DAT005 | `class_code` | string(50)，同 DAT001 正则 | 是 | `JobCreate.class_code`（:111）、`JobResponse.class_code`（:155） | 无 | 同 DAT003，维度类型为 CLASS | 非敏感 | 同 DAT003（`models.py:220-224`） |
| WFC-POSITION-F001-DAT006 | `sequence_code` | string(50)，同 DAT001 正则 | 是 | `JobCreate.sequence_code`（:112）、`JobResponse.sequence_code`（:156） | 无 | 同 DAT003，维度类型为 SEQUENCE | 非敏感 | 同 DAT003（`models.py:225-229`） |
| WFC-POSITION-F001-DAT007 | `status` | `"active"` / `"inactive"` | 是（表单必选） | `JobCreate.status`（:113）、`JobResponse.status`（:157） | `active`（前端 `statusOptions`，`PositionWorkspace.tsx:57-60`） | 枚举内取值 | 非敏感 | 按版本保存（`models.py:230`） |
| WFC-POSITION-F001-DAT008 | `effective_from` | date（业务日期） | 是 | `JobCreate.effective_from`（:114）、`JobResponse.effective_from`（:158） | 新建默认今天（`PositionWorkspace.tsx:354`）；新增版本默认「原生效日 + 1 天」与「今天」中较晚者（`:94-98`、`:350`） | 新增版本必须晚于最新版本，否则 409 `JOB_VERSION_DATE_NOT_FORWARD` | 非敏感 | 版本生效起点（`models.py:231`） |
| WFC-POSITION-F001-DAT009 | `effective_to` | date，可空 | 否 | `JobCreate.effective_to`（:115）、`JobResponse.effective_to`（:159） | 空 = 长期有效 | 不得早于 `effective_from`；前端提示「失效日期不能早于生效日期」 | 非敏感 | 版本生效终点（`models.py:232`）；前端渲染「{from} 至 {to ?? "长期"}」（`:442`） |
| WFC-POSITION-F001-DAT010 | `source_job_id` | string(255)，可空 | 否 | `JobCreate.source_job_id`（:116）、`JobVersionCreate.source_job_id`（:137）、`JobResponse.source_job_id`（:161） | 空 | **契约存在、表单无控件**：`buildPositionPayload` 与 `buildPositionVersionPayload` 从表单值读取该键（`PositionWorkspace.tsx:146`、`:167`），但表单没有对应控件（职位表单字段清单 `:650-748`），新建提交时恒为 `undefined` | 非敏感 | 按版本保存（`models.py:234`）；输入包 04 §3 定义其用途为「如需保留来源ID则填写」 |
| WFC-POSITION-F001-DAT011 | `notes` | string(1000)，可空 | 否 | `JobCreate.notes`（:117）、`JobResponse.notes`（:162） | 空 | ≤1000 字符 | 非敏感 | 按版本保存（`models.py:235`） |
| WFC-POSITION-F001-DAT012 | `attributes` | JSON 对象 | 否 | `JobCreate.attributes`（:118）、`JobVersionCreate.attributes`（:139）、`JobResponse.attributes`（:163） | `{}` | **契约存在、表单无控件**：新建固定提交 `{}`（`PositionWorkspace.tsx:148`），新增版本继承原记录（`:169`）；后端不校验键名与内容 | 非敏感（开放扩展字段，内容未评审） | 按版本保存（`models.py:236`） |
| WFC-POSITION-F001-DAT013 | `change_reason` | string(500) | 是 | `JobCreate.change_reason`（:119）、`JobVersionCreate.change_reason`（:140） | 无 | 1–500 字符 | 非敏感 | 不进版本业务字段；写入审计 `reason`（`extended_service.py:544-550`、`:614-621`） |
| WFC-POSITION-F001-DAT014 | `id` | UUID | 响应只读 | `JobResponse.id`（:150） | — | — | 非敏感 | 稳定身份，跨版本不变 |
| WFC-POSITION-F001-DAT015 | `version` | int | 响应只读 | `JobResponse.version`（:160） | — | `version > 0`（DB CheckConstraint `models.py:195`） | 非敏感 | 同一职位内唯一（`models.py:194`） |
| WFC-POSITION-F001-DAT016 | `dimension_type` | `"LEVEL"` / `"GRADE"` / `"CLASS"` / `"SEQUENCE"` | 是（新建维度必填） | `JobDimensionCreate.dimension_type`（:38）、`JobDimensionResponse.dimension_type`（:92） | 前端新建默认 `LEVEL`（`PositionWorkspace.tsx:375`） | 枚举内取值；中文标签固定为「职级 / 职等 / 职类 / 序列」（`:45-50`） | 非敏感 | 属于稳定主档，不随版本变化（`models.py:154`） |
| WFC-POSITION-F001-DAT017 | `code`（维度代码） | string(50)，同 DAT001 正则 | 是（新建维度必填） | `JobDimensionCreate.code`（:39）、`JobDimensionResponse.code`（:93） | 无 | 同类型内唯一，重复 409 `JOB_DIMENSION_CODE_EXISTS` | 非敏感 | 稳定编码，版本不修改 |
| WFC-POSITION-F001-DAT018 | `name`（维度名称） | string(200) | 是 | `JobDimensionCreate.name`（:40）、`JobDimensionResponse.name`（:94） | 无 | 1–200 字符 | 非敏感 | 按版本保存（`models.py:176`） |
| WFC-POSITION-F001-DAT019 | `parent_dimension_type` | 枚举，可空 | 否 | `JobDimensionCreate.parent_dimension_type`（:41）、`JobDimensionResponse.parent_dimension_type`（:96） | 空 | 父维度必须在生效日存在且启用，否则 422 `JOB_DIMENSION_PARENT_NOT_EFFECTIVE` | 非敏感 | 版本内以 `parent_dimension_id` 固化（`models.py:177-181`） |
| WFC-POSITION-F001-DAT020 | `parent_dimension_code` | string(50)，可空，同 DAT001 正则 | 否 | `JobDimensionCreate.parent_dimension_code`（:42-45）、`JobDimensionResponse.parent_dimension_code`（:97） | 空 | 同 DAT019；不得指向自身或形成环，否则 422 `JOB_DIMENSION_PARENT_CYCLE` | 非敏感 | 同 DAT019 |
| WFC-POSITION-F001-DAT021 | `sort_order` | int ≥ 0 | 是（表单必填） | `JobDimensionCreate.sort_order`（:46）、`JobDimensionResponse.sort_order`（:98） | `0`（前端新建默认 0，`PositionWorkspace.tsx:376`） | `ge=0` | 非敏感 | 按版本保存（`models.py:182`） |
| WFC-POSITION-F001-DAT022 | `status`（维度） | `"active"` / `"inactive"` | 是 | `JobDimensionCreate.status`（:47）、`JobDimensionResponse.status`（:99） | `active` | 枚举内取值 | 非敏感 | 按版本保存（`models.py:183`） |
| WFC-POSITION-F001-DAT023 | `effective_from`（维度） | date | 是 | `JobDimensionCreate.effective_from`（:48）、`JobDimensionResponse.effective_from`（:100） | 同 DAT008 | 新增版本必须晚于最新版本，否则 409 `JOB_DIMENSION_VERSION_DATE_NOT_FORWARD` | 非敏感 | 版本生效起点（`models.py:184`） |
| WFC-POSITION-F001-DAT024 | `effective_to`（维度） | date，可空 | 否 | `JobDimensionCreate.effective_to`（:49）、`JobDimensionResponse.effective_to`（:101） | 空 = 长期有效 | 同 DAT009 | 非敏感 | 版本生效终点（`models.py:185`） |
| WFC-POSITION-F001-DAT025 | `notes`（维度） | string(1000)，可空 | 否 | `JobDimensionCreate.notes`（:50）、`JobDimensionResponse.notes`（:103） | 空 | ≤1000 字符 | 非敏感 | 按版本保存（`models.py:187`） |
| WFC-POSITION-F001-DAT026 | `change_reason`（维度） | string(500) | 是 | `JobDimensionCreate.change_reason`（:51）、`JobDimensionVersionCreate.change_reason`（:79） | 无 | 1–500 字符 | 非敏感 | 写入审计 `reason`（`extended_service.py:268-278`、`:328-335`） |
| WFC-POSITION-F001-DAT027 | `id`（维度） | UUID | 响应只读 | `JobDimensionResponse.id`（:91） | — | — | 非敏感 | 稳定身份，跨版本不变 |
| WFC-POSITION-F001-DAT028 | `parent_dimension_id` | UUID，可空 | 响应只读 | `JobDimensionResponse.parent_dimension_id`（:95） | — | — | 非敏感 | 随版本记录父级解析结果 |
| WFC-POSITION-F001-DAT029 | `version`（维度） | int | 响应只读 | `JobDimensionResponse.version`（:102） | — | `version > 0`（DB CheckConstraint `models.py:162`） | 非敏感 | 同一维度内唯一（`models.py:161`） |
| WFC-POSITION-F001-DAT030 | `attributes`（响应扩展） | JSON 对象 | 响应只读 | `JobResponse.attributes`（:163） | — | 后端不校验键名 | 非敏感（开放扩展字段，内容未评审） | 见 DAT012 |

### 8.3 数据生命周期

- 创建：新建职位写入 `job_catalog` 一行 + `job_catalog_versions` 的 `version=1`；新建职务维度写入 `job_dimensions` 一行 + `job_dimension_versions` 的 `version=1`（`extended_service.py:502-551`、`:226-279`）。
- 修改/更正：只能通过新增版本修正，不允许原地改写历史版本；新增版本时服务端同步刷新 `job_catalog` 的兼容投影列（`extended_service.py:604-612`）。
- 生效/失效：版本区间由 `effective_from` / `effective_to` 表达；新增版本时旧版本自动闭合到新版本生效日减一天（`extended_service.py:583-585`、`:310-311`）；把状态改为 `inactive` 也是一次新版本，不改写历史。
- 保留：版本行永久保留，本模块无删除接口；审计日志另表保存（`audit_logs`，`models.py:992-1016`）。
- 删除：本功能不提供物理删除，也不提供撤销版本的入口；停用只能通过新增 `status=inactive` 的版本实现，且当前没有引用检查（见 §7 BR017、§18 Q-06）。
- 迁移与兼容：`f1b000000001` 把旧 `job_catalog` 当前投影回填为首版本，并把旧的四类代码投影为职务维度，迁移备注写明「由旧职务投影迁移，正式名称待企业码表确认」「由旧 job_catalog 当前投影迁移」（`f1b000000001_effective_dated_job_architecture.py:249-256`、`:284-291`）；旧兼容列保留待所有消费者切换后再评估移除（`docs/delivery/P1-JOB-ARCHITECTURE.md` §5）。

## 9. 权限要求

| ID | 状态 | 参与者 | 功能/动作权限 | 数据范围 | 字段权限 | 拒绝结果 |
|---|---|---|---|---|---|---|
| WFC-POSITION-F001-PERM001 | `CONFIRMED` | 持有 `WORKFORCE_ADMIN` 或 `*` 的账号 | 查看职位列表（`GET /api/v1/workforce/jobs`） | 全部职位，无行级过滤 | 全部只读字段（DAT001–DAT015、DAT030） | 403 `PERMISSION_DENIED`「没有执行此操作的权限」；前端渲染「无权查看职位管理」「请联系主管理员分配职务体系维护权限。」（`PositionWorkspace.tsx:514-522`） |
| WFC-POSITION-F001-PERM002 | `CONFIRMED` | 同上 | 新建职位（`POST /api/v1/workforce/jobs`）、新增职位版本（`POST /api/v1/workforce/jobs/{id}/versions`） | 全部职位 | 可写 DAT001–DAT013；DAT001 仅新建时可写 | 同 PERM001；无权限时前端按钮置灰（`PositionWorkspace.tsx:458`、`:569`） |
| WFC-POSITION-F001-PERM003 | `CONFIRMED` | 同上 | 查看职务维度（`GET /api/v1/workforce/job-dimensions`） | 全部维度 | 全部只读字段（DAT016–DAT029） | 同 PERM001 |
| WFC-POSITION-F001-PERM004 | `CONFIRMED` | 同上 | 新建职务维度（`POST /api/v1/workforce/job-dimensions`）、新增维度版本（`POST /api/v1/workforce/job-dimensions/{id}/versions`） | 全部维度 | 可写 DAT016–DAT026；DAT016、017 仅新建时可写 | 同 PERM001；无权限时前端按钮置灰（`PositionWorkspace.tsx:507`、`:603`） |
| WFC-POSITION-F001-PERM005 | `CONFIRMED` | 持有 `WORKFORCE_ADMIN` 或 `*` 的账号 | 侧栏入口可见性：侧栏「组织管理 › 职位管理」按 `WORKFORCE_ADMIN` 过滤，无权限时不渲染 | — | — | 无权限时侧栏入口不出现（`navigation.ts:45-50`、`AppShell.tsx:184-187` 的 `visibleWorkspaces` 过滤） |
| WFC-POSITION-F001-PERM006 | `PENDING` | 只读角色 | 当前没有只读权限码，读取与写入同为 `WORKFORCE_ADMIN`，是否拆出只读权限待产品拍板 | — | — | 现状为只读账号一律 403；见 §18 Q-08（与待确认清单 P-14 同族议题） |
| WFC-POSITION-F001-PERM007 | `CONFIRMED` | 未登录或会话失效账号 | 任何接口 | — | — | 401 `AUTHENTICATION_REQUIRED`「需要登录」或 `SESSION_INVALID`「登录状态无效或已过期」（`dependencies.py:32`、`:47`） |
| WFC-POSITION-F001-PERM008 | `CONFIRMED` | 任意已登录账号 | 工作台入口卡片「职位管理」不做权限过滤，属登录后可见的静态入口；点击「进入职位管理」后由接口 403 兜底 | — | — | 无权限账号点击后进入工作区并看到「无权查看职位管理」拒绝态（`AppShell.tsx:128-131` 静态渲染卡片 → `PositionWorkspace.tsx:514-522` 拒绝态） |

代办与代理说明：

- 主管理员（持 `*`）可以直接执行全部写操作，不需要额外审批（`dependencies.py:90` 对 `*` 短路放行）。
- 每次写操作必须填写业务变更原因 `change_reason`，该值原样写入审计 `reason`（`extended_service.py:544-550`），因此原因不是可选元数据。
- **本功能没有代办 / 代理身份机制**：审计只记录操作者本人 `actor_id`，没有 `on_behalf_of` 或代理角色字段（`models.py:995-1016`、`extended_service.py:64-87`）。若企业要求「管理员代替业务部门操作并留痕代理身份」，需另立功能。
- 未知范围默认拒绝：权限判定为「不具备所需权限码即拒绝」，不做任何隐式放行（`dependencies.py:79`、`:90`）。

## 10. 交互与页面要求

### 10.1 入口与可见性

- 菜单/页面/按钮：
  - 侧栏：「组织管理 › 职位管理」（`navigation.ts:45-50`、`:79-85`；`AppShell.tsx:209-218`）。
  - 工作台卡片：标题「职位管理」，说明「维护职务与职级、职等、职类、序列维度，并按生效日期管理版本。」，按钮「进入职位管理」（`AppShell.tsx:128-131`）。
  - 面包屑：「组织管理 / 职位管理」（`AppShell.tsx:299-306`）。
  - 页内操作：「新建职位」「新建职务维度」（主按钮）、每行「新增版本」（链接按钮）、「重置」（筛选栏）。
  - 页面标题与副标题（宿主页页头，逐字复用实现）：标题「职位管理」；副标题「维护职位目录及其生效版本。职位引用职级、职等、职类和序列四类职务维度，每次调整都会按生效日期形成新版本，历史版本不被覆盖。」（`PositionWorkspace.tsx:528-529`）。
  - 筛选区文案：标签「生效日期」（`PositionWorkspace.tsx:541`）；搜索框占位符在职位列表页签为「搜索职位名称或编码」、在职务维度页签为「搜索维度名称或代码」（`:546`），可访问名称「搜索职位或职务维度」（`:544`）。
- 无权限或未启用模块时：侧栏不渲染该入口（`navigation.ts:45-50`、`AppShell.tsx:184-187`）；工作台的「职位管理」卡片是登录后可见的静态入口，不做权限过滤（`AppShell.tsx:128-131`）；直接进入时整页替换为 `WorkspaceDenied`，标题「职位管理」、提示「无权查看职位管理」、说明「请联系主管理员分配职务体系维护权限。」（`PositionWorkspace.tsx:514-522`；`components/WorkspaceShell.tsx:69-81`）。
- 宿主页：列表。组织管理分组下的独立宿主页，内部以「职位列表 / 职务维度」两个页签承载同一宿主页上下文（`PositionWorkspace.tsx:558-626`）。
- 交互载体：`MODAL`。新建职位、新增职位版本、新建职务维度、新增职务维度版本全部使用 Modal（宽 760，`PositionWorkspace.tsx:628-639`）。
- 选择理由：四个表单均为单任务、字段数不超过 12、无页内标签、无多步骤、无并行参照需求，落在 [Ant Design 页面与交互载体规范](../design/antd-page-interaction-standard.md) §3 的 `MODAL` 默认边界内（通常不超过 6 个简单字段、无页内标签），且不满足 `DRAWER`（保留宿主页预览、需要看到表格对照）或 `NEW_TAB`（超过 20 字段、超过 3 分组、存在页内标签或历史对比）的升级条件。载体为已实现形态，选择理由在此登记以便评审复核。
- 路由或深链接：宿主页为 hash 路由 `#positions`（`navigation.ts:126-132`），刷新后回到同一受权资源；Modal 不占用独立路由，关闭后回到宿主页并保留筛选、分页与页签状态（宿主页组件未被卸载）。
- Pencil源文件：`C:\Users\83289\Documents\HRMS\coreHR.pen`（Pencil 2.17）。
- 画板ID/名称/原型版本：`op8Nx` / 「职位管理 · 组织管理 v1.0」 / `v1.0`（画板 1440×960）。
- 原型状态：`PROTOTYPE_APPROVED`。2026-10-24 产品决策人确认全部画板并签字，规范 §10.1 的状态枚举中对应 `PROTOTYPE_APPROVED`；按规范 §10.2 与 D-087，前端开发门禁已解除，本功能可按画板继续开发（见 §19 T002 状态与 §18 Q-01）。

### 10.2 页面状态

| 状态 | 页面表现 | 可执行操作 |
|---|---|---|
| 首次/空数据 | 表格空态「没有符合条件的职位」（`PositionWorkspace.tsx:582`）/「没有符合条件的职务维度」（`:615`），由 `EmptyState` 承载（`components/EmptyState.tsx:12-14`）；指标条全部为 0 | 切换生效日期、切换页签、调整搜索词；有权限时可「新建职位 / 新建职务维度」 |
| 加载中 | 表格 `loading` 态（`components/DataTable.tsx:50`），指标条保持上一次数值 | 等待；可切换页签 |
| 正常 | 指标条 + Tabs + 表格 + 分页器：职位列表分页文案「共 N 个职位」（`PositionWorkspace.tsx:583-590`），职务维度页签分页文案「共 N 个职务维度」（`:616-620`） | 筛选、搜索、翻页、新建、新增版本 |
| 部分失败 | 职位列表或职务维度其中之一加载失败时，页面顶部显示可关闭的错误条，失败信息为「职位列表加载失败」（`:242`）或「职务维度加载失败」（`:260`），另一张表仍可显示（`components/WorkspaceShell.tsx:19-22`、`:54`） | 关闭错误条、修改生效日期重试 |
| 完全失败 | 两个列表请求同时返回 403 时，整页切换为「无权查看职位管理」拒绝态（`:241`、`:259`、`:514-522`）；其他错误按「完全失败」表现为顶部错误条 | 关闭错误条或联系管理员 |
| 无权限 | 同上；侧栏入口同时不可见 | 退出登录或联系主管理员 |

### 10.3 表单与确认

- 字段顺序与联动：
  - 新建职位：「职位标识」→「职位名称」；「所属维度」→「职级 / 职等 / 职类 / 序列」；「生效与变更」→「状态 / 生效日期 / 失效日期 / 变更原因 / 备注」（`PositionWorkspace.tsx:650-748`）。
  - 新增职位版本：编码位置变为只读文字「稳定编码：{code}（版本不修改编码）」（`:653-656`），其余分组与字段一致。
  - 新建职务维度：「维度标识」→「维度类型 / 维度代码 / 维度名称」；「层级与顺序」→「上级维度 / 显示顺序」；「生效与变更」→同职位（`:751-840`）。
  - 联动：四个维度下拉的选项只包含当前 `status=active` 的维度（`:303-316`）；上级维度下拉的选项格式为「{维度类型} · {名称} ({代码})」，编辑时排除自身（`:318-321`、`:786-789`）；「失效日期」依赖「生效日期」做先后校验（`:725-739`、`:817-831`）。
- 即时校验与提交校验：前端 antd Form 规则（必填提示如「请输入职位编码」「请选择职级」「请填写变更原因」；编码格式提示「使用大写字母、数字、点、下划线或短横线，最多 50 位」；「变更原因」输入框占位符「说明本次调整原因，后端按此记录版本审计」，`PositionWorkspace.tsx:744`）；后端 pydantic 校验失败返回 422 `REQUEST_VALIDATION_FAILED`，逐字段 `details` 返回（`apps/api/src/hris/core/errors.py:41-61`）。
- 高风险二次确认：**当前实现没有二次确认**。「新增版本」直接提交。是否补 Popconfirm 见 §18 Q-10；在该问题关闭前，前端不得自行增加未经批准的确认步骤（D-087：原型与需求是实现依据）。
- 成功反馈与下一步：保存成功后关闭 Modal 并并行刷新职位与维度两个列表（`PositionWorkspace.tsx:417-418`）；失败时在 Modal 顶部显示可关闭的错误条并保留用户输入（`:640-642`、`:419-421`）。
- 打开、关闭和焦点返回：Modal 使用 `destroyOnHidden`（`:629`），关闭即销毁表单；antd 默认在打开后把焦点移入容器、关闭后焦点回到触发元素。
- 未保存变更与重复提交保护：未保存变更**不拦截**关闭（当前实现没有脏检查）；保存期间 `confirmLoading={saving}` 使「保存」按钮进入加载态，阻止重复提交（`:636`、`:395`、`:421`）。
- 弹窗关闭后表单重置或保留策略：关闭即销毁，下次打开时由 `openPositionEditor` / `openDimensionEditor` 重新写入初始值（`:340-381`），不保留上一条记录的输入。

### 10.4 Pencil原型登记

| 原型ID | 页面/交互载体 | Pencil文件 | 画板ID与名称 | 版本 | 状态 | 批准人/日期 |
|---|---|---|---|---|---|---|
| WFC-POSITION-F001-PROT001 | `MODAL`（宿主页「职位管理 · 组织管理 v1.0」含职位列表与职务维度两个页签，画板 `op8Nx` 1440×960；新建职位 / 新增职位版本 / 新建职务维度 / 新增职务维度版本四个 Modal 尚未单独出画板） | `C:\Users\83289\Documents\HRMS\coreHR.pen` | 画板ID `op8Nx`；画板名称「职位管理 · 组织管理 v1.0」 | v1.0 | `PROTOTYPE_APPROVED` | 2026-10-24 产品决策人签字确认（见 §18 Q-01 / §20） |

登记说明（按事实记录，不做美化）：

- 画板状态 `PROTOTYPE_APPROVED`（2026-10-24 产品决策人签字确认）依据 `docs/review/pen-prototype-spec-2026-10-24.md` 头部状态标注与 §7 后续动作第 3 条；预览图为 `docs/review/pen-prototypes/01-职位管理.png`。
- 画板与实现的差异已在设计说明 §5 中列为「有意保留」：第 1 条职位页「重置」不清空生效日期（对应 BR013）；第 3 条职务维度 Tab 分页静态（对应 BR014）；第 5 条职位载荷 `source_job_id` / `attributes` 表单无控件（对应 BR016、DAT010、DAT012）。
- 画板表达的是宿主页与信息层级；四个 Modal 的表单结构、校验文案与焦点行为目前只存在于实现（`PositionWorkspace.tsx:628-844`），没有对应的 Pencil 画板。规范 §10.4 要求「显著不同的加载、空数据、失败、无权限和冲突状态应在原型中可Review」，这些状态同样未出画板——见 §18 Q-01。

## 11. API与事件合同

### 11.1 同步API

| ID | 方法与路径 | 调用者 | 请求摘要 | 响应摘要 | 权限 | 幂等 | 事务边界 |
|---|---|---|---|---|---|---|---|
| WFC-POSITION-F001-API001 | `GET /api/v1/workforce/jobs`（`extended_api.py:139-158`） | 职位管理宿主页 | 查询参数：`effective_at`（date，可选，缺省业务时区当天）、`limit`（1–200，缺省 50，前端传 20）、`offset`（≥0，前端传 `(page-1)*20`） | `PageResponse`：`items`（`JobResponse` 列表）、`total`、`limit`、`offset` | `WORKFORCE_ADMIN` | 天然幂等（只读） | 单请求单事务，`get_db` 在响应前提交（`core/database.py:18-25`） |
| WFC-POSITION-F001-API002 | `POST /api/v1/workforce/jobs`（`extended_api.py:117-121`，201） | 职位管理宿主页「新建职位」 | `JobCreate`：`code`、`name`、`level_code`、`grade_code`、`class_code`、`sequence_code`、`status`、`effective_from`、`effective_to?`、`source_job_id?`、`notes?`、`attributes`、`change_reason` | `JobResponse`（201） | `WORKFORCE_ADMIN` | 不幂等：同 `code` 第二次调用返回 409 `JOB_CODE_EXISTS`，不产生第二条记录 | 单请求单事务；数据行、版本行与审计行同事务提交或同事务回滚 |
| WFC-POSITION-F001-API003 | `POST /api/v1/workforce/jobs/{job_id}/versions`（`extended_api.py:124-136`，201） | 职位管理宿主页「新增版本」 | `JobVersionCreate`：DAT002–DAT013（不含 `code`） | `JobResponse`（201） | `WORKFORCE_ADMIN` | 不幂等：每次调用生成新版本号；`effective_from` 未递进时返回 409 `JOB_VERSION_DATE_NOT_FORWARD` | 单请求单事务；旧版本闭合、新版本写入、兼容投影刷新与审计写入同事务 |
| WFC-POSITION-F001-API004 | `GET /api/v1/workforce/job-dimensions`（`extended_api.py:193-214`） | 职位管理宿主页「职务维度」页签与职位表单下拉 | 查询参数：`dimension_type`（可选）、`effective_at`（可选）、`limit`（1–500，缺省 200，前端传 500）、`offset` | `PageResponse`：`items`（`JobDimensionResponse` 列表）、`total`、`limit`、`offset` | `WORKFORCE_ADMIN` | 天然幂等 | 单请求单事务 |
| WFC-POSITION-F001-API005 | `POST /api/v1/workforce/job-dimensions`（`extended_api.py:161-172`，201） | 职位管理宿主页「新建职务维度」 | `JobDimensionCreate`：`dimension_type`、`code`、`name`、`parent_dimension_type?`、`parent_dimension_code?`、`sort_order`、`status`、`effective_from`、`effective_to?`、`notes?`、`change_reason` | `JobDimensionResponse`（201） | `WORKFORCE_ADMIN` | 不幂等：同类型同代码返回 409 `JOB_DIMENSION_CODE_EXISTS` | 单请求单事务 |
| WFC-POSITION-F001-API006 | `POST /api/v1/workforce/job-dimensions/{dimension_id}/versions`（`extended_api.py:175-190`，201） | 职位管理宿主页「新增版本」（职务维度行） | `JobDimensionVersionCreate`：DAT018–DAT026（不含 `dimension_type` 与 `code`） | `JobDimensionResponse`（201） | `WORKFORCE_ADMIN` | 不幂等：每次调用生成新版本号 | 单请求单事务 |

调用者与所有权说明：上述六个接口由 Workforce Core 模块提供（`apps/api/src/hris/modules/workforce/`），其他模块只读引用职位稳定身份，不通过本组接口写入职位数据。前端调用封装在 `apps/web/src/business/features/organization/position-api.ts:111-143`，认证统一使用 Bearer Token（`apps/web/src/business/client.ts:58-67`）。

### 11.2 异步事件与任务

`NOT_APPLICABLE`。依据：本功能的所有写路径（`extended_service.py:226-279`、`:281-336`、`:502-551`、`:553-622`）只做数据库写入与审计写入，模块内没有消息发布或领域事件调用（`apps/api/src/hris/modules/workforce/` 全目录检索 `publish` / `emit` 无命中）；职位数据的下游消费由引用方在自己的事务内按目标日期查询完成（`extended_service.py:474-480`），不存在本功能发出的异步消息。若后续引入消息引擎（待确认清单 P-10～P-12），本功能是否需要发布「职位版本生效」事件需重新评审并补写本节。

### 11.3 兼容与废弃

- 当前合同版本：v1。接口路径与响应字段自第一阶段生效日期职务体系交付以来未变（`docs/delivery/P1-JOB-ARCHITECTURE.md`）；前端类型定义与后端 schema 一一对应（`position-api.ts:10-98` ↔ `extended_schemas.py:37-163`）。
- 向后兼容策略：`job_catalog` 保留旧列作为兼容投影，新版本写入时同步刷新（`extended_service.py:604-612`）；既有编制、招聘、任职外键继续指向 `job_catalog.id`，不因版本化而改变（`docs/delivery/P1-JOB-ARCHITECTURE.md` §2）。
- 废弃通知和截止版本：当前无废弃项。若后续按输入包 §5.7–§5.9 引入职位族 / 职位类 / 职位子类，`job_catalog` 旧列与 `attributes` 扩展字段的废弃必须先在本节登记并同步 `docs/01-foundation/03-项目决策.md`，不得直接删除（规范 §13 变更控制）。

## 12. 异常、并发与回退

| ID | 状态 | 场景 | 系统结果 | 用户提示/错误码 | 是否重试 | 补偿/回退 |
|---|---|---|---|---|---|---|
| WFC-POSITION-F001-ERR001 | `CONFIRMED` | 职位编码重复提交 | 拒绝，不写入任何行 | 409 `JOB_CODE_EXISTS`「业务编码已存在」（`extended_service.py:62`） | 否——重试不会改变结果，需换编码 | 不适用 |
| WFC-POSITION-F001-ERR002 | `CONFIRMED` | 新版本生效日期未递进 | 拒绝，不修改旧版本 | 409 `JOB_VERSION_DATE_NOT_FORWARD`「新版本生效日期必须晚于最新版本」（`extended_service.py:571-574`）；前端另有同规则即时校验 | 否——需改生效日期 | 不适用 |
| WFC-POSITION-F001-ERR003 | `CONFIRMED` | 引用了目标日未生效或已停用的维度 | 整单拒绝，不写入职位 | 422 `JOB_DIMENSION_NOT_EFFECTIVE`「{类型}维度代码不存在或在职务生效日未启用」（`extended_service.py:404-409`） | 否——需改维度或生效日期 | 不适用 |
| WFC-POSITION-F001-ERR004 | `CONFIRMED` | 职务维度代码重复 | 拒绝 | 409 `JOB_DIMENSION_CODE_EXISTS`「同类型职务维度代码已存在」（`extended_service.py:237-241`） | 否 | 不适用 |
| WFC-POSITION-F001-ERR005 | `CONFIRMED` | 父维度不存在、未生效或已停用 | 拒绝 | 422 `JOB_DIMENSION_PARENT_NOT_EFFECTIVE`「父职务维度不存在或在生效日期未启用」（`extended_service.py:185-189`） | 否 | 不适用 |
| WFC-POSITION-F001-ERR006 | `CONFIRMED` | 父维度链路成环 | 拒绝 | 422 `JOB_DIMENSION_PARENT_CYCLE`「职务维度父级不能形成循环」（`extended_service.py:194-198`） | 否 | 不适用 |
| WFC-POSITION-F001-ERR007 | `CONFIRMED` | 对不存在的职位或维度新增版本 | 拒绝 | 404 `JOB_NOT_FOUND`「职务不存在」/ `JOB_DIMENSION_NOT_FOUND`「职务维度不存在」（`extended_service.py:560`、`:288`） | 否 | 不适用 |
| WFC-POSITION-F001-ERR008 | `CONFIRMED` | 请求体不满足 schema | 请求被拒 | 422 `REQUEST_VALIDATION_FAILED`「请求参数校验失败」，`details` 逐字段给出（`core/errors.py:41-61`） | 否 | 不适用 |
| WFC-POSITION-F001-ERR009 | `CONFIRMED` | 无权限访问或写入 | 请求被拒 | 403 `PERMISSION_DENIED`「没有执行此操作的权限」（`dependencies.py:80`、`:91`） | 否 | 不适用 |
| WFC-POSITION-F001-ERR010 | `CONFIRMED` | 会话无效或过期 | 请求被拒 | 401 `AUTHENTICATION_REQUIRED` / `SESSION_INVALID`（`dependencies.py:32`、`:47`） | 重新登录后重试 | 不适用 |
| WFC-POSITION-F001-ERR011 | `CONFIRMED` | 两人同时为同一职位新增版本 | 服务端对职位行与最新版本行加行锁（`with_for_update`，`extended_service.py:558-567`），两个请求串行执行；后到的请求基于已提交的新最新版本判定，`effective_from` 未递进则 409 `JOB_VERSION_DATE_NOT_FORWARD`，递进则生成下一个版本号 | 前端展示后端 message（`PositionWorkspace.tsx:419-421`） | 视错误码：409 需改生效日期后重试 | 无需补偿：失败的请求未写入任何行 |
| WFC-POSITION-F001-ERR012 | `CONFIRMED` | 写入过程中数据库异常 | 整个请求事务回滚，职位行、版本行与审计行都不落库 | 前端展示「保存失败」（`PositionWorkspace.tsx:420`） | 可在修复原因后重试 | 自动回滚（`core/database.py:23-25`） |
| WFC-POSITION-F001-ERR013 | `CONFIRMED` | 后台任务中断 | `NOT_APPLICABLE`：本功能没有后台任务（依据 §11.2） | — | — | — |
| WFC-POSITION-F001-ERR014 | `CONFIRMED` | 下游系统失败 | `NOT_APPLICABLE`：本功能不调用外部系统（依据 §11.2） | — | — | — |
| WFC-POSITION-F001-ERR015 | `PENDING` | 版本回退（撤销一次误调整） | 当前没有撤销入口：只能新增一个更晚生效的版本把状态改回，历史版本不可删除。若企业需要「撤销上一版本」，需产品拍板后新增能力 | 现状无对应提示 | — | 建议路径是新增补偿版本；是否提供显式撤销见 §18 Q-11 |

## 13. 审计与数据保护

| ID | 状态 | 动作 | 审计内容 | 禁止记录内容 | 保留要求 |
|---|---|---|---|---|---|
| WFC-POSITION-F001-AUD001 | `CONFIRMED` | 创建职位 | `action=create`、`object_type=job`、`object_id=职位 id`、`reason=change_reason`、`after_payload={code, name, version:1}`、`actor_id`、`trace_id`、`source=api`（`extended_service.py:544-550`、`:64-87`） | 不记录 `attributes` 全文；不记录认证凭据 | 审计行随 `audit_logs` 表保留，无删除入口 |
| WFC-POSITION-F001-AUD002 | `CONFIRMED` | 新增职位版本 | `action=create_version`、`object_type=job`、`before_payload={version, effective_to}`、`after_payload={version, effective_from}`、`reason=change_reason`（`extended_service.py:614-621`） | 同上 | 同上 |
| WFC-POSITION-F001-AUD003 | `CONFIRMED` | 创建 / 新增职务维度版本 | `action=create` 或 `create_version`、`object_type=job_dimension`、`before/after` 载荷含 `dimension_type`、`code`、`version`（`extended_service.py:268-278`、`:328-335`） | 同上 | 同上 |
| WFC-POSITION-F001-AUD004 | `CONFIRMED` | 审计记录读取 | 审计查询接口 `GET /api/v1/platform/audit-logs` 要求 `DATA_GOVERNANCE_ADMIN`，读取不降级为 VIEW（`apps/api/src/hris/modules/platform/audit_api.py:21-24`、`:58`） | 审计导出不含 `before_payload` / `after_payload`（`platform/audit_service.py:19-22`） | 按审计模块既有保留策略执行 |

- 敏感字段加密：`NOT_APPLICABLE`。依据：本功能写入的表 `job_catalog`、`job_catalog_versions`、`job_dimensions`、`job_dimension_versions` 没有任何个人敏感列（`models.py:127-237`），字段集合仅为编码、名称、层级引用、状态、生效区间、备注、扩展 JSON 与变更原因，不含证件、薪资、生物特征；人员档案的加密要求属于 `docs/01-foundation/07-人员档案领域规范.md` 与 ADR-0004。
- 页面脱敏：`NOT_APPLICABLE`。依据同上：页面展示的列全部为职务体系主数据，不含个人敏感信息（`PositionWorkspace.tsx:426-512`）。
- 明文访问：`NOT_APPLICABLE`。依据：本功能不存在「明文才能读取」的字段（区别于人员档案的敏感字段）。
- 导出与临时文件：`NOT_APPLICABLE`。依据：职位管理页面没有导出入口（`position-api.ts:111-143` 无下载调用），也不产生临时文件；职位目录的批量导出属于数据治理模块（`apps/api/src/hris/modules/platform/master_data_export.py`），不在本功能范围。
- 非生产数据：验收使用合成数据，不使用真实企业职务目录以外的任何人员数据；现有自动化测试即采用合成 fixture（`apps/web/src/business/features/organization/PositionWorkspace.test.tsx:8-94`）。

## 14. 非功能需求

| ID | 状态 | 类别 | 可验证要求 | 环境/数据量 | 验证证据 |
|---|---|---|---|---|---|
| WFC-POSITION-F001-NFR001 | `CONFIRMED` | 性能 | 职位列表采用服务端分页，单页固定 20 条且 `showSizeChanger=false`；职务维度单次最多拉取 500 条 | 本机开发库；数据量由企业码表决定 | 前端 `PositionWorkspace.tsx:40-42`、`:583-590`、`:616-620`；后端 `extended_api.py:144`、`:200` |
| WFC-POSITION-F001-NFR002 | `PENDING` | 性能 | 页面首屏（职位列表 + 职务维度并行请求）的响应时间目标 | 需要容量输入：本机并发用户数、职位目录条数、维度条数 | 缺容量输入，暂不可验收；输入模板见 `docs/input-packs/templates/07-capacity-scenarios.csv`，容量场景见 `docs/input-packs/09-nonfunctional-acceptance-input.md` |
| WFC-POSITION-F001-NFR003 | `CONFIRMED` | 可用性 / 可访问性 | 筛选区日期控件具备 `aria-label="生效日期"`，搜索框具备 `aria-label="搜索职位或职务维度"`；表格行键为 `id`；Modal 具有可识别的对话框角色与标题；状态不只依赖颜色，同时输出「启用 / 停用」文字 | 键盘与屏幕阅读器人工检查 | `components/EffectiveDatePicker.tsx:19-23`、`PositionWorkspace.tsx:542-549`、`:576`、`:628-639`；规范 §7 状态不只依赖颜色的要求 |
| WFC-POSITION-F001-NFR004 | `CONFIRMED` | 兼容 | 页面使用仓库锁定的 Ant Design 6.5.2 组件，不使用已废弃属性 | 生产构建 `npm run build` | D-090；`docs/design/antd-page-interaction-standard.md` §2 |
| WFC-POSITION-F001-NFR005 | `CONFIRMED` | 复用 | 页面骨架、筛选栏、表格与空态统一使用 `WorkspaceShell`、`FilterBar`、`DataTable`、`EmptyState`，不在本能力域内出现第二套写法 | 全站一致性 | D-091；`components/WorkspaceShell.tsx:36-58`、`components/FilterBar.tsx:18-42`、`components/DataTable.tsx:36-67`、`components/EmptyState.tsx:12-14` |
| WFC-POSITION-F001-NFR006 | `CONFIRMED` | 可观测 | 每次请求返回 `trace_id`，写入审计行的 `trace_id` 与响应一致，可用于按请求串起页面操作与审计记录 | 本机开发库 | `core/errors.py:24-38`、`extended_service.py:64-87`、`models.py:1001` |
| WFC-POSITION-F001-NFR007 | `CONFIRMED` | 安全 | 页面不展示也不提交任何个人敏感数据；写操作受 `WORKFORCE_ADMIN` 约束 | 本机开发库 | §9 权限表、§13 敏感字段条目 |

## 15. 验收场景

### WFC-POSITION-F001-AC001 按生效日期查看职位目录

- 类型：正常
- 前置数据：至少 1 个状态为 `active` 的职位，版本 1 的 `effective_from` 为 `2026-01-01`、`effective_to` 为空。
- Given：账号具备 `WORKFORCE_ADMIN`，进入「组织管理 › 职位管理」，生效日期为 `2026-01-01`。
- When：页面加载完成。
- Then：请求为 `GET /api/v1/workforce/jobs?effective_at=2026-01-01&limit=20&offset=0`；表格出现该职位，列「职位编码 / 职位名称 / 所属维度（职级、职等、职类、序列）/ 生效日期 / 版本 / 状态 / 操作」齐全；生效日期渲染为「2026-01-01 至 长期」；状态显示「启用」；指标条「有效职位」等于该日期有效职位数。
- 数据库/事件/审计证据：`job_catalog_versions` 中该职位在 `2026-01-01` 命中的版本行被返回；本次为只读操作，不产生审计行。
- 自动化层级：前端单元测试 + 后端集成测试。

### WFC-POSITION-F001-AC002 业务边界——新版本生效日期必须晚于最新版本

- 类型：边界 / 规则拒绝
- 前置数据：职位 `JOB_001` 最新版本 `effective_from=2026-01-01`。
- Given：维护者在「新增职位版本」表单把生效日期填为 `2026-01-01`（等于最新版本生效日）。
- When：提交。
- Then：前端即时校验拦截并提示「新版本生效日期必须晚于 2026-01-01」；若绕过前端直接调用 `POST /api/v1/workforce/jobs/{id}/versions`，返回 409 `JOB_VERSION_DATE_NOT_FORWARD`，消息「新版本生效日期必须晚于最新版本」。
- 数据库/事件/审计证据：`job_catalog_versions` 行数不变，旧版本的 `effective_to` 与 `is_current` 不变，无审计行写入。
- 自动化层级：前端单元测试 + 后端集成测试。

### WFC-POSITION-F001-AC003 业务规则拒绝——引用未生效或停用的维度

- 类型：异常 / 规则拒绝
- 前置数据：职级 `LEVEL_09` 的版本在目标生效日 `2026-01-01` 不存在或 `status=inactive`。
- Given：维护者新建职位，生效日期 `2026-01-01`，职级选择 `LEVEL_09`（该下拉在启用维度集合外时不会出现；本用例通过直接调用接口构造）。
- When：提交 `POST /api/v1/workforce/jobs`。
- Then：返回 422 `JOB_DIMENSION_NOT_EFFECTIVE`；不创建 `job_catalog` 行，不创建版本行，不写审计行。
- 数据库/事件/审计证据：`select count(*) from job_catalog where code = <本次编码>` 为 0。
- 自动化层级：后端集成测试。

### WFC-POSITION-F001-AC004 重复请求——同一职位编码重复创建

- 类型：幂等
- 前置数据：已存在职位 `JOB_001`。
- Given：维护者再次提交 `code=JOB_001` 的新建职位请求。
- When：请求到达服务端。
- Then：返回 409 `JOB_CODE_EXISTS`；职位行数不变，版本行数不变。
- 数据库/事件/审计证据：`job_catalog` 中 `JOB_001` 只有一行，`job_catalog_versions` 中该职位仍只有 1 个版本。
- 自动化层级：后端集成测试。

### WFC-POSITION-F001-AC005 并发修改——两名维护者同时新增版本

- 类型：并发
- 前置数据：职位 `JOB_001` 最新版本 `effective_from=2026-01-01`。
- Given：两个请求同时提交 `effective_from=2026-01-01` 的新版本。
- When：两个请求并发到达。
- Then：服务端按 `with_for_update` 串行处理；先到者成功并生成 `version=2`（旧版本 `effective_to=2025-12-31`、`is_current=false`），后到者基于新的最新版本判定，返回 409 `JOB_VERSION_DATE_NOT_FORWARD`。
- 数据库/事件/审计证据：该职位最终只有 `version=2` 一条新版本行；审计中只有一条 `action=create_version` 记录。
- 自动化层级：后端集成测试。

### WFC-POSITION-F001-AC006 无权限访问

- 类型：权限
- 前置数据：一个不含 `WORKFORCE_ADMIN`、也不含 `*` 的账号。
- Given：该账号进入「组织管理 › 职位管理」（或直接调用 `GET /api/v1/workforce/jobs`）。
- When：页面加载。
- Then：侧栏不出现「职位管理」入口（工作台卡片「职位管理」属登录后可见的静态入口，仍会显示，点击后进入拒绝态）；接口返回 403 `PERMISSION_DENIED`；若页面已被打开，渲染「无权查看职位管理」「请联系主管理员分配职务体系维护权限。」。
- 数据库/事件/审计证据：无数据写入，无审计行。
- 自动化层级：前端单元测试 + 后端集成测试。

### WFC-POSITION-F001-AC007 审计证据核对

- 类型：审计
- 前置数据：维护者具备 `WORKFORCE_ADMIN`，`change_reason` 填「晋升职级」。
- Given：其为 `JOB_001` 新增一个版本。
- When：保存成功。
- Then：`audit_logs` 出现一行 `action=create_version`、`object_type=job`、`object_id=<职位 id>`、`reason=晋升职级`、`before_payload.version=<旧版本号>`、`after_payload.version=<新版本号>`；该行 `trace_id` 与响应返回的 `trace_id` 一致。
- 数据库/事件/审计证据：`audit_logs` 查询结果 + 页面错误条为空、列表刷新后版本列递增。
- 自动化层级：后端集成测试 + 人工 UAT（审计页核对）。

### WFC-POSITION-F001-AC008 生效时点查询——生效日前、生效日与历史时点

- 类型：边界
- 前置数据：职位 `JOB_001` 版本 1 `effective_from=2026-01-01`；版本 2 `effective_from=2026-07-01`，版本 1 已闭合为 `effective_to=2026-06-30`。
- Given：依次以 `2026-06-30`、`2026-07-01` 两个生效日期查询。
- When：调用 `GET /api/v1/workforce/jobs`。
- Then：`2026-06-30` 返回版本 1（`version=1`，`effective_to=2026-06-30`）；`2026-07-01` 返回版本 2（`version=2`，`effective_from=2026-07-01`）。
- 数据库/事件/审计证据：两次查询的返回体 `items[0].version` 分别为 1 与 2。
- 自动化层级：后端集成测试。

### WFC-POSITION-F001-AC009 空数据、搜索与重置语义

- 类型：正常 / 边界
- 前置数据：库中 1 个职位，生效日期为 `2026-10-24`。
- Given：维护者在搜索框输入不存在的名称。
- When：输入完成（搜索为前端即时过滤，不触发请求）。
- Then：表格显示空态「没有符合条件的职位」，原数据不残留在页面上；生效日期输入框仍为 `2026-10-24`；点击「重置」后搜索词清空、页码回到第 1 页，生效日期**不**被清空。
- 数据库/事件/审计证据：无请求产生，无数据变化。
- 自动化层级：前端单元测试。

### WFC-POSITION-F001-AC010 维护职务维度与父级校验

- 类型：正常 / 异常
- 前置数据：已存在启用中的职级 `LEVEL_06`；不存在启用的父级 `LEVEL_99`。
- Given：维护者新建职务维度（类型 LEVEL、代码 `LEVEL_07`、名称「七级」、显示顺序 70、生效日期今天、变更原因「新增职级」）。
- When：提交成功；随后把该维度的上级维度改为 `LEVEL_99` 并提交新版本。
- Then：第一次返回 201，维度出现在「职务维度」页签的「维度类型 = 职级」标签下；第二次返回 422 `JOB_DIMENSION_PARENT_NOT_EFFECTIVE`，不生成新版本。
- 数据库/事件/审计证据：`job_dimensions` 新增一行 `(LEVEL, LEVEL_07)`；`job_dimension_versions` 只有 `version=1` 一行；审计中有一条 `action=create`、`object_type=job_dimension` 记录。
- 自动化层级：后端集成测试 + 前端单元测试。

### WFC-POSITION-F001-AC011 明文访问与导出拒绝

- 类型：安全
- 前置数据：无。
- Given：维护者尝试从职位管理页面导出职位目录。
- When：查看页面是否存在导出入口并尝试调用职位相关导出接口。
- Then：页面不存在导出入口；`apps/api/src/hris/modules/workforce/extended_api.py` 未定义任何职位导出路由，请求返回 404 或路由不存在。个人敏感字段在本功能不存在，无明文读取路径。
- 数据库/事件/审计证据：无导出文件产生，无数据变化。
- 自动化层级：人工 UAT（页面检查）+ 接口路由核对。

### WFC-POSITION-F001-AC012 后台任务中断与下游失败

- 类型：异常
- 前置数据：无。
- Given：审查本功能的写路径。
- When：检查是否存在异步任务或外部依赖调用。
- Then：不存在——写路径只有数据库写入与审计写入（`extended_service.py:226-279`、`:281-336`、`:502-551`、`:553-622`，模块内无 `publish` / `emit` 调用），因此没有任务中断或下游失败场景需要验收。
- 数据库/事件/审计证据：不适用。
- 自动化层级：人工 UAT（代码核对，核对点已记录在 §11.2）。

## 16. 迁移、发布与回滚

- 现有数据影响：本功能管理的四张表已存在于本机库；`f1b000000001` 已把旧 `job_catalog` 当前投影回填为首版本，并把旧四类代码投影为职务维度（迁移备注：「由旧职务投影迁移，正式名称待企业码表确认」「由旧 job_catalog 当前投影迁移」）。企业码表补齐后，新增记录走本功能的页面写入，不再依赖批量导入。
- 数据迁移与校验：企业码表导入仍走数据治理入口（预校验、审计、幂等导入），见 `docs/delivery/P1-JOB-ARCHITECTURE.md` §6；本功能不提供导入功能。
- 功能开关或模块启用：没有功能开关；入口按 `WORKFORCE_ADMIN` 权限显隐（`navigation.ts:45-50`）。
- 发布顺序：后端接口与迁移已在库；前端页面随 Web 构建发布。页面依赖 `GET /jobs`、`GET /job-dimensions` 两个既有接口，发布不改变接口合同。
- 升级兼容：`job_catalog` 旧列保留为兼容投影并在新版本写入时同步刷新（`extended_service.py:604-612`）；旧消费者（编制、任职、招聘）继续按 `job_catalog.id` 引用，不受版本化影响。
- 应用回滚：前端回滚到上一构建即可，接口未变更；后端回滚不涉及本功能的迁移（表结构由 `f1b000000001` 引入，已在本机库落地）。
- 数据不可逆时的恢复或前向修复：版本行只增不删，回滚不会删除数据；若版本数据有误，只能新增补偿版本前向修正（见 §12 ERR015 与 §18 Q-11）。

## 17. 可观测与运行手册

- 指标：本功能不新增业务指标。现有可观测项：接口调用量与错误码分布（403 / 404 / 409 / 422）、列表查询的 `total` 规模。
- 日志和Trace：每次请求带 `trace_id`（`core/errors.py:24-38`），审计行 `trace_id` 与之对应（`extended_service.py:64-87`）；排查具体一次调整时，用 `trace_id` 关联审计记录与请求日志。
- 告警：本功能不定义专属告警；接口 5xx 与事务回滚沿用平台内核既有告警口径。
- 后台任务：无（依据 §11.2）。
- 人工补偿：写入失败时事务自动回滚（`core/database.py:23-25`），无需人工补偿；业务纠错通过新增版本前向修正（§16）。
- 健康检查：页面可用性依赖 `GET /api/v1/workforce/jobs` 与 `GET /api/v1/workforce/job-dimensions` 两个接口的可用性（`position-api.ts:112-126`）。

## 18. 待确认问题

| ID | 问题 | 影响规则/场景 | Owner | 期望日期 | 不确认时的处理 |
|---|---|---|---|---|---|
| WFC-POSITION-F001-Q01 | 待确认清单 **P-15**「画板通过后是否即授权前端按画板开发/替换」：是否确认把画板 `op8Nx` 的 Review 状态从 `DRAFT_FOR_REVIEW` 改为 `PROTOTYPE_APPROVED`。**2026-10-24 产品决策人已确认全部画板并签字**，§10.4 状态升级为 `PROTOTYPE_APPROVED` | §10.1 原型状态、§10.4 PROT001、§19 T002、AC001–AC012 的页面形态验收 | 产品决策人 | 2026-10-25 | 已关闭：2026-10-24 产品决策人签字确认画板，规范 §10.2 的前端开发门禁解除，本功能可按画板继续开发|
| WFC-POSITION-F001-Q02 | 待确认清单 **P-16**「`docs/requirements/` 模块功能需求文档」：本文件是第一份按 17 号规范落地的功能文档；是否继续为汇报关系、操作日志、人员中心、员工档案 Drawer、批量新增标签 Modal 等本轮画板建立同规范文档 | §19 T001 的范围界定 | 产品决策人 | 2026-10-25 | 保持阻塞：只维护本功能文档，其余 5 个页面仍无功能需求文档，相应前端开发任务不得创建 |
| WFC-POSITION-F001-Q03 | 职位与职务的术语与数据模型归属：产品定义中「职位」绑定一个职务、一个职级、多个职等，且与部门为可选多对多（D-085）；当前页面维护的是后端 `job_catalog`（职务侧），只保存单一 `grade_code`，也没有部门关联列。是把本页继续叫「职位管理」并只承载职务侧，还是另立「职位」功能 | §2.2、§8.2 全部字段合同、BR001–BR003 | 产品决策人 | 企业码表冻结前 | 采用已实现口径：本文档按 `job_catalog` 描述字段与规则，不在本功能内自行扩展模型 |
| WFC-POSITION-F001-Q04 | 待确认清单 **P-06**「指标条是否推广到其他工作区」：本页面指标条「有效职位 / 职级 / 职等 / 职类 / 序列」是否保留在本页；同时确认职位页「重置」是否继续不清空生效日期（与操作日志页语义不一致，画板说明 §5 差异第 1 条已按现状保留） | BR013、BR015、AC009 | 产品决策人 | 2026-10-25 | 采用画板现状：指标条保留在本页；「重置」不清空生效日期 |
| WFC-POSITION-F001-Q05 | 列表检索是否需要服务端化：当前搜索只过滤当前已加载页（职位每页 20 条），职务维度页签分页静态、只显示首 20 条但实际加载最多 500 条 | BR012、BR014、AC009 | 产品决策人 | 企业目录规模确认后 | 采用已实现行为，并在页面上不提供超出当前页的检索承诺 |
| WFC-POSITION-F001-Q06 | 停用前的引用检查与完整企业码表：当前把职位或维度置为 `inactive` 没有引用检查（输入包 §3 要求「禁用前检查当前有效引用和未来生效引用」）；同时企业完整职务目录尚未提供（99-待确认问题 Q-012） | BR017、§8.3 删除策略、AC003、AC010 | 产品决策人 + 企业码表提供方 | 企业码表交付时 | 采用已实现行为：不做引用检查，停用通过新增 `status=inactive` 的版本实现 |
| WFC-POSITION-F001-Q07 | 权限可授予性：`WORKFORCE_ADMIN` 在全量 Alembic 迁移中没有 seed 行，除持 `*` 的主管理员外没有第二个账号可用该权限（与待确认清单组 4 的已查实事实、P-18 修复批次①相关） | PERM001–PERM006、AC006、ASM-03 | 产品决策人 | 随 P-18 批次① | 验收只覆盖主管理员路径；普通角色权限分级验收延后 |
| WFC-POSITION-F001-Q08 | 读权限拆分：当前职位与职务维度的读取与写入同为 `WORKFORCE_ADMIN`，没有只读权限码（与待确认清单 P-14「汇报关系 GET 读写同权」同族，但本接口尚未被列入 P-14 范围） | PERM006、§3 参与者表 | 产品决策人 | 2026-10-25 | 保持现状：只读账号一律 403 |
| WFC-POSITION-F001-Q09 | `source_job_id` 与 `attributes` 是否在本页面提供录入控件（契约存在、表单无控件，画板说明 §5 差异第 5 条已按现状保留） | BR016、DAT010、DAT012 | 产品决策人 | 企业导入方式确定后 | 采用已实现行为：表单不提供控件；新建提交 `attributes={}`，新增版本继承原记录 |
| WFC-POSITION-F001-Q10 | 「新增版本」是否需要二次确认（Popconfirm）；当前无二次确认，规范 §5 要求高风险操作说明对象、影响与可恢复性 | BR018、§10.3 | 产品决策人 | 2026-10-25 | 采用已实现行为：不做二次确认 |
| WFC-POSITION-F001-Q11 | 是否需要「撤销 / 回退版本」入口；当前版本只增不删，误调整只能靠新增补偿版本 | ERR015、§16 | 产品决策人 | 企业 UAT 前 | 采用已实现行为：不做撤销入口，纠错走新增版本 |
| WFC-POSITION-F001-Q12 | 生效日期的时区口径：前端日期控件取浏览器本地日期，后端缺省取业务时区当天（`Asia/Shanghai`）。是否要求前端统一按业务时区计算「今天」 | ASM-02、DAT008 | 产品决策人 | 企业 UAT 前 | 前端始终显式传 `effective_at`，后端不再使用缺省值；用户跨时区访问时以请求参数为准 |
| WFC-POSITION-F001-Q13 | 四个 Modal 与加载、空数据、失败、无权限、冲突状态尚无独立 Pencil 画板（规范 §10.4 要求显著差异状态在原型中可 Review） | §10.4 PROT001、AC001–AC006 | 产品决策人 | 随 Q01 一并签字 | 保持阻塞：不得基于未登记的画板新增前端结构改动 |

## 19. 开发任务与追踪

| 任务ID | 目标 | 依赖 | 文件/模块所有权 | 需求追踪注释 | 验收场景 | 状态 | 交付证据 |
|---|---|---|---|---|---|---|---|
| WFC-POSITION-F001-T001 | 按《模块功能需求文档规范》建立职位管理功能需求文档，登记 Pencil 画板 `op8Nx`、字段合同、权限、错误码与验收场景 | 无 | 仅新增 `docs/requirements/WFC-workforce-core/WFC-position/WFC-POSITION-F001-position-management.md` | 文档头部登记规范 17 号；正文引用 ORG-PROT-001 / D-087 / D-090 / D-091 / D-068 / D-069 / D-070 / D-084 / D-085 / D-086 | AC001–AC012 的判定依据 | `IN_REVIEW` | 本文件（v0.1，2026-10-24） |
| WFC-POSITION-F001-T002 | 前端按已批准画板 `op8Nx` 对齐职位管理宿主页与四个 Modal | WFC-POSITION-F001-Q01（画板签字，`PROTOTYPE_APPROVED`） | `apps/web/src/business/features/organization/PositionWorkspace.tsx`、`position-api.ts`、`apps/web/src/business/components/` | 在规则落点写 `Requirement: WFC-POSITION-F001-BRnnn — 原因` | AC001、AC002、AC009、AC010 | `READY`（2026-10-24 画板已签字，规范 §10.2 的前端开发门禁解除，按画板继续对齐） | — |
| WFC-POSITION-F001-T003 | 为 `WORKFORCE_ADMIN` 补 seed 行使非主管理员账号可被授予该权限 | 待确认清单 P-18 修复批次① | `apps/api/alembic/versions/`（新增迁移）、`apps/api/src/hris/modules/platform/` | 迁移内注明权限来源决策 ID | AC006 | `BLOCKED`（阻塞原因：P-18 修复顺序未由产品决策人确认） | — |
| WFC-POSITION-F001-T004 | 按产品结论补齐列表服务端检索与职务维度分页 | WFC-POSITION-F001-Q05 | `apps/api/src/hris/modules/workforce/extended_api.py`、`extended_service.py`、`apps/web/src/business/features/organization/` | 规则落点写 `Requirement: WFC-POSITION-F001-BR012 / BR014 — 原因` | AC009 | `BLOCKED`（阻塞原因：Q05 未拍板，不允许开发者自行选择检索口径） | — |

## 20. Review与批准记录

| 版本 | 日期 | 变更摘要 | 产品/业务结论 | 技术结论 | 批准人 |
|---|---|---|---|---|---|
| v0.1 | 2026-10-24 | 初稿：按 17 号规范建立职位管理功能需求文档；登记 Pencil 画板 `op8Nx`（初稿状态 `DRAFT_FOR_REVIEW`）；逐条对齐后端合同（字段、接口、权限码、错误码）与前端实现文案 | 已由产品决策人 Review 并签字，状态升级为 `PROTOTYPE_APPROVED`（Q01） | 字段、接口、权限与错误码全部指向实现文件与行号，未发明后端不存在的字段；契约存在但表单无控件的 `source_job_id` / `attributes` 已如实标注；未修改任何代码 | 已批准（2026-10-24 产品决策人签字） |

现状说明（按事实记录）：

- 2026-10-24 用户已指示「按画板开发或替换已有界面」，前端据此先行实现了该宿主页，并已获授权先行实现。
- 画板已于 **2026-10-24** 经产品决策人签字确认，§10.4 的 Review 状态升级为 `PROTOTYPE_APPROVED`。
- 在 Q01 关闭之前，按规范 §10.2 与 D-087，不得为本功能创建新的前端开发任务（T002 状态为 `BLOCKED`）。

### 20.1 规范 §15 文档 Review 检查表自查（2026-10-24）

| # | 检查项 | 自查结论 | 依据 |
|---|---|---|---|
| 1 | 文档是否只描述一个可独立验收的功能 | 是 | 全文只描述「维护职位目录及其生效版本」一个业务结果；职务维度作为同一宿主页、同一权限、同一版本语义下的子能力合并在内，并在 §3 给出不拆分理由 |
| 2 | 是否能明确说出谁在什么条件下得到什么结果 | 是 | §3 参与者表（主管理员 / 职务体系维护者 / 只读账号 / 未登录账号）+ §5 四条用户故事的触发条件、前置条件、主路径、结束状态 |
| 3 | 是否区分确认规则、待确认问题和推荐方案 | 是 | §7 规则表带 `CONFIRMED` / `PENDING` 状态列并写明状态约定；§18 全部为待确认项并给出「不确认时的处理」；本文件未代替产品决策人做结论 |
| 4 | 数据所有者、唯一键、有效日期和历史策略是否明确 | 是 | §8.1 数据所有权、四组业务唯一键、版本区间约束与兼容投影说明；§8.2 每行含「历史策略」列 |
| 5 | 权限是否覆盖动作、数据范围、字段和高风险操作 | 是 | §9 PERM001–PERM007 覆盖读、写、入口可见性、字段可写性、403 拒绝结果与代办说明；高风险操作缺口在 BR018 / Q10 / ERR015 显式登记 |
| 6 | 接口是否明确幂等、事务、版本和失败补偿 | 是 | §11.1 六个接口逐个写明幂等性与单请求单事务边界；§12 覆盖重复、并发、异常与回滚；§11.2 说明无异步事件及依据 |
| 7 | 是否覆盖异常、并发、回退、审计和敏感数据 | 是 | §12 ERR001–ERR015；§13 AUD001–AUD004 及敏感字段、页面脱敏、明文访问、导出、非生产数据逐项结论；回退缺口在 ERR015 / Q11 登记 |
| 8 | NFR是否可以在指定环境中验证 | 部分通过 | NFR001、NFR003–NFR007 可在指定环境验证并给出证据；NFR002（首屏响应时间）因缺容量输入标记 `PENDING`，已在 §14 写明需要的输入文件与验收环境 |
| 9 | 验收场景是否包含明确输入、动作和预期证据 | 是 | §15 AC001–AC012，每条含类型、前置数据、Given / When / Then、数据库或审计证据、自动化层级 |
| 10 | 是否可以在不猜业务规则的情况下拆出最小任务 | 是 | §19 四个任务均声明所有权、依赖、追踪注释与验收场景；三个任务因 Q01 / P-18 / Q05 未决而 `BLOCKED`，未把 PENDING 规则写进任务 |
| 11 | 是否说明对已有数据、模块和部署的影响 | 是 | §16 覆盖现有数据影响、迁移与校验、开关、发布顺序、升级兼容、应用回滚与前向修复；§4 列出下游引用方 |
| 12 | 是否存在与父级PRD或已确认决策冲突的内容 | 是（无冲突） | 载体选择符合 D-068/D-069 与交互载体规范 §3；组件复用符合 D-091；原型门禁符合 D-087；职位与部门、职等连续区间按 D-085/D-086 列入不纳入范围；术语差异按 Q03 登记 |
| 13 | 所有需求驱动的代码变化是否明确了追踪注释所引用的ID和预计代码落点 | 是 | §19 T002、T004 写明 `Requirement: WFC-POSITION-F001-BRnnn — 原因` 及预计落点文件；本轮不产生代码变化 |
| 14 | 涉及前端时，是否明确宿主页、`MODAL`/`DRAWER`/`NEW_TAB`载体及其打开、退出和状态恢复行为 | 是 | §10.1 宿主页=列表、主载体=`MODAL`、选择理由与升级条件、hash 路由 `#positions`、Modal 无独立路由且关闭后保留宿主页上下文；§10.3 打开 / 关闭 / 焦点 / 重置策略 |
| 15 | 涉及前端时，是否登记Pencil文件、画板ID、版本和`PROTOTYPE_APPROVED`证据 | 通过 | §10.4 已登记 Pencil 源文件、画板 ID `op8Nx`、画板名称、版本 `v1.0` 与状态；`PROTOTYPE_APPROVED` 证据**已存在**（2026-10-24 产品决策人签字确认）；原缺口 Q01、Q13 登记 |

自查结论汇总：15 项中 14 项通过，1 项为「部分通过」——第 8 项因缺容量输入把 NFR002 标为 `PENDING`（不是编造）；第 15 项已随 2026-10-24 画板签字补齐 `PROTOTYPE_APPROVED` 证据。按规范 §15 末句「任一关键项为否时，不得进入 `READY_FOR_TASKS`」，本功能当前状态仍保持 `DRAFT`（余下 1 项为第 8 项 NFR002 容量输入待补），画板门禁已不再是阻塞项。
