# WFC-PEOPLE-F001 人员中心与员工档案

> 模块：WFC / Workforce Core
> 能力域：WFC-PEOPLE / 人员档案管理
> 状态：`DRAFT`
> 版本：v0.1
> 产品Owner：MillerMax（产品决策人）
> 业务Owner：产品决策人 MillerMax 兼任（仓库内没有记录企业侧 HR 业务负责人；依据 `docs/01-foundation/03-项目决策.md` D-066）
> 上级需求：[16-coreHR产品总体PRD](../01-foundation/16-coreHR产品总体PRD.md) §5.3 Workforce Core 职责（自然人、雇佣经历、组织职务与协议关系）；[07-人员档案领域规范](../01-foundation/07-人员档案领域规范.md)
> 依赖功能：[WFC-LABEL-F001 员工标签 Tab](../WFC-workforce-core/WFC-label/WFC-LABEL-F001-person-label-tab.md)（员工档案 Drawer 的一个页签，独立成功能文档）
> 最后更新：2026-10-24

## 1. 背景与期望结果

- 当前问题：后端已经存在完整的人员档案数据面（`persons` 主档 + `employments` 劳动关系 + `employment_legal_entity_relations` 四类主体版本 + `employment_assignments` 组织职务 + `agreement_relationships` 协议关系，`apps/api/src/hris/modules/workforce/extended_api.py`、`extended_service.py`），前端也已有「人员中心」宿主页与「员工档案」Drawer（`apps/web/src/business/features/workforce/PeopleWorkspace.tsx`）。2026-10-24 前端按 Pencil 画板 `JN45s` 对齐落地后，按《模块功能需求文档规范》§10.2 / D-087，缺少功能需求文档登记画板 ID 时前端开发任务没有合法依据，画板状态也无处落档；此外画板要求的三列与主组织筛选在当前列表接口中无数据来源（待确认清单 P-21）。
- 用户价值：HR 维护者可以在一个列表找到员工并打开其完整档案，查看分层保存的自然人、雇佣经历、组织职务与协议关系；主数据维护者可以在同一页面更正基础信息。
- 本功能完成后可观察的业务结果：
  1. 侧栏「人员中心」进入宿主页，列出「姓名 / 工号 / 主组织 / 职位 / 在职状态 / 入职日期 / 操作」七列（`PeopleWorkspace.tsx:263-289`）。
  2. 点击「查看档案」或整行打开 Drawer，标题「{姓名} · {工号}」、副标题「员工档案 · 人员中心」，内含 7 个页签（`PeopleWorkspace.tsx:302-393`）。
  3. Drawer 的「基础信息」页签以两列描述列表展示人员主档字段；「更正基础信息」打开 Modal 提交更正（`PeopleWorkspace.tsx:314`、`:417-428`）。
  4. 每次新建人员与更正基础信息在审计日志中留下记录。
- 不做本功能的影响：员工信息只能靠直接写库维护；雇佣经历、组织职务、协议关系无法在同一处核对；人员档案的敏感子记录与员工标签各自为政。

## 2. 范围

### 2.1 纳入范围

- 人员中心宿主页：页头与「新建法人 / 新建人员」操作、扁平筛选栏（姓名或工号 / 在职状态 / 重置 / 查询）、人员表格与前端分页（`PeopleWorkspace.tsx:215-300`）。
- 员工档案 Drawer（`size="large"`）：标题 / 副标题 / 「更正基础信息」入口，7 个页签的装配与展示（`PeopleWorkspace.tsx:302-395`）。
  - 「基础信息」页签：两列描述列表，展示法定姓名、姓名、曾用名、性别、出生日期、国籍、国家/地区、民族代码、婚姻状况代码、政治面貌代码（`:319-333`）。
  - 「劳动关系 N」「四类主体版本 N」「组织职务 N」「协议关系 N」四个只读子表及其计数标题（`:348-392`）。
- 新建人员档案与更正基础档案的 Modal 表单（`PeopleWorkspace.tsx:397-472`、`:417-428`）。
- 建立劳动关系、调整四类法人主体、新增组织职务关系、登记协议关系、新建法人主体五个 Modal 表单（`PeopleWorkspace.tsx:429-469`）。
- 本功能的 Pencil 画板登记（见 §10.4）。

### 2.2 不纳入范围

- 员工标签页签：独立成 [WFC-LABEL-F001 员工标签 Tab](../WFC-workforce-core/WFC-label/WFC-LABEL-F001-person-label-tab.md) 与 [WFC-LABEL-F002 批量新增标签 Modal](../WFC-workforce-core/WFC-label/WFC-LABEL-F002-batch-label-create-modal.md)。
- 「敏感与经历档案」页签（`PersonnelSubrecordsPanel`，`PeopleWorkspace.tsx:334-338`）：涉及证件、联系方式、地址、紧急联系人、教育经历、工作经历、家庭成员的脱敏与明文查看，属于人员档案敏感子记录能力，本轮未建立对应功能文档，见 §18 Q-04。
- 人员列表的「主组织 / 职位 / 入职日期」三列与「主组织」筛选：当前列表接口不返回这三项，页面按空值占位显示「—」（`PeopleWorkspace.tsx:256-258`、`:266-278`），见 §18 Q-01。
- 人员的批量导入、导出与删除：人员中心页面没有导出入口（`apps/web/src/business/features/workforce/api.ts:37-182` 无下载调用），也没有删除入口（`extended_api.py` 的人员路由只有 GET / POST / PATCH）。
- 员工自助门户、招聘、生命周期、编制等其他工作区的页面需求（各自独立成功能文档）。

### 2.3 假设与约束

| ID | 状态 | 内容 | 假设不成立时的处理 |
|---|---|---|---|
| ASM-01 | `CONFIRMED` | 人员档案读取要求 `PERSON_VIEW` + `PERSON_SENSITIVE_VIEW`（两个码都要持有），基础信息更正额外要求 `PERSON_EDIT_BASIC`（`extended_api.py:62-75`） | 若企业只发放 `PERSON_VIEW`，该账号看不到人员档案；权限发放口径见 §18 Q-05 |
| ASM-02 | `CONFIRMED` | 人员列表按「工号升序（空值在后）+ 姓名升序」排序（`extended_service.py:1167`）；前端一次性拉取最多 200 条后在浏览器内分页与筛选（`api.ts:38-42`、`PeopleWorkspace.tsx:94-103`） | 企业人员规模超过 200 条时，超出部分在页面上不可达；规模上限见 §18 Q-02 |
| ASM-03 | `CONFIRMED` | 「在职状态」在前端映射到后端 `persons.status` 的启停取值（`active` → 在职，`inactive` → 停用），不是劳动关系状态（`PeopleWorkspace.tsx:47-52`） | 若要改成劳动关系口径，需先改后端列表响应（见 §18 Q-03） |
| ASM-04 | `CONFIRMED` | 人员档案 Drawer 的「更正基础信息」走 `PATCH /api/v1/workforce/persons/{id}`，写入的是**更正记录**（`PersonCorrectionService`），`person` 返回当前生效结果、`registered_person` 返回主档登记值（`extended_api.py:256-279`） | 本文档只描述页面行为与端点合同，更正记录的版本语义见人员档案领域规范 |
| ASM-05 | `PENDING` | 企业侧的正式人员编码规则、完整档案字段清单与国别码表尚未提供 | 页面按库内现有字段展示；企业码表补齐前不做结构性扩展，见 §18 Q-06 |
| ASM-06 | `CONFIRMED` | 页面上的「性别 / 民族 / 婚姻状况 / 政治面貌」是**代码**输入框（自由文本），没有字典下拉 | 企业码表到位后必须换成受控下拉，不得继续用自由文本写入 |

## 3. 参与者、权限边界和业务场景

| 参与者 | 目标 | 前置权限 | 数据范围 |
|---|---|---|---|
| 主管理员 | 维护全部人员档案与主体数据 | `*`（`apps/api/src/hris/modules/platform/dependencies.py:90` 对 `*` 短路放行） | 全部人员；本模块无行级数据范围 |
| 人力编制维护者 | 新建 / 更正人员档案、建立劳动关系、登记协议关系 | `WORKFORCE_ADMIN`（`extended_api.py:61`）或 `PERSON_VIEW` + `PERSON_EDIT_BASIC` + `PERSON_SENSITIVE_VIEW`（`extended_api.py:66-75`） | 全部人员；本模块无行级数据范围 |
| 人员档案查看者 | 查看人员列表与员工档案 | `PERSON_VIEW` + `PERSON_SENSITIVE_VIEW`（`extended_api.py:62-65`） | 全部人员；本模块无行级数据范围 |
| 未登录 / 会话失效访问者 | —— | 无有效会话 | 401 `AUTHENTICATION_REQUIRED` / `SESSION_INVALID`（`dependencies.py:32`、`:47`） |

场景边界说明：本功能只有一个业务结果——「找到员工并维护其档案」。列表检索与档案维护是同一结果的不同参与深度；「员工标签」页签虽然在同一 Drawer 内，但触发方式、权限判定与失败补偿都独立（标签读写都要求 `WORKFORCE_ADMIN`，见 WFC-LABEL-F001），按规范 §2.2 拆成独立功能文档。

## 4. 名词与依赖

| 名词/依赖 | 定义或引用 | 数据所有者 |
|---|---|---|
| 人员档案（Person） | `persons` 表的一行：自然人主档 | Workforce Core（`apps/api/src/hris/modules/workforce/models.py:324-348`） |
| 员工档案 Drawer | 前端以 Drawer 承载的员工档案视图，含 7 个页签 | 前端（`PeopleWorkspace.tsx:302-395`） |
| 劳动关系（Employment） | `employments` 表：人员类型、状态、计划 / 实际入职日、合同 / 发薪 / 社保 / 个税主体 | Workforce Core |
| 四类主体版本 | `employment_legal_entity_relations` 表：`contract` / `payroll` / `social_insurance` / `tax` 四类主体及版本 | Workforce Core |
| 组织职务 | `employment_assignments` 表：组织、职务、关系类型与生效区间 | Workforce Core |
| 协议关系 | `agreement_relationships` 表：协议类型、法人主体、合作方与生效区间 | Workforce Core |
| 法人主体 | `legal_entities` 表：本功能只读引用（列表与下拉），可新建 | Workforce Core |
| 组织 | `organizations` 表：本功能只读引用（抽屉内组织职务表的下拉候选） | Workforce Core |
| 职位 | `job_catalog` / `job_catalog_versions`：本功能只读引用（组织职务表的职务下拉） | Workforce Core（见 [WFC-POSITION-F001](../WFC-workforce-core/WFC-position/WFC-POSITION-F001-position-management.md)） |
| 工号 | `persons.employee_number`，6 位数字，库级唯一（`models.py:327-337`） | Workforce Core |
| 更正记录 | 人员字段的带生效日期的更正版本，由 `PersonCorrectionService` 管理 | Workforce Core |

## 5. 用户故事

### WFC-PEOPLE-F001-US01 检索人员并查看列表

作为人员档案查看者，我希望按姓名或工号找到员工，从而进入其档案。

- 触发条件：进入「人员中心」，或在筛选区输入关键词后点击「查询」。
- 前置条件：账号具备 `PERSON_VIEW` + `PERSON_SENSITIVE_VIEW` 或 `*`。
- 主路径：页面加载 → 并行请求 `GET /api/v1/workforce/persons?limit=200&offset=0`、`GET /api/v1/workforce/legal-entities?limit=200&offset=0`、`GET /api/v1/workforce/jobs?limit=200&offset=0`、`GET /api/v1/organizations/tree`（`PeopleWorkspace.tsx:71-92`）→ 表格按七列展示，姓名取 `display_name`、工号为空时显示「待分配」、在职状态按 `active` → 绿色「在职」Tag（`PeopleWorkspace.tsx:263-289`）。
- 结束状态：表格显示人员列表，分页器显示「共 N 名员工」；无数据时显示空态「暂无人员档案」（`:290`）；任一请求失败时显示顶部错误条「人员中心加载失败」（`:86`）。

### WFC-PEOPLE-F001-US02 打开员工档案

作为人员档案查看者，我希望以抽屉形式查看单个员工的分层档案，从而不必离开列表页。

- 触发条件：点击表格行或「查看档案」链接。
- 前置条件：账号具备 `PERSON_VIEW` + `PERSON_SENSITIVE_VIEW` 或 `*`。
- 主路径：点击 → 请求 `GET /api/v1/workforce/persons/{person_id}`（`PeopleWorkspace.tsx:105-112`）→ 打开 Drawer，标题「{display_name} · {employee_number ?? "待分配"}」，副标题「员工档案 · 人员中心」（`:302-311`）→ 7 个页签依次装配，其中四个页签标题带计数（如「劳动关系 2」「四类主体版本 3」）（`:348-392`）。
- 结束状态：Drawer 展示该员工的档案；请求失败时抽屉不打开，页面显示顶部错误条「人员档案加载失败」（`:110`）。

### WFC-PEOPLE-F001-US03 更正基础信息

作为人力编制维护者，我希望更正员工的基础信息，从而让档案反映最新事实。

- 触发条件：在 Drawer 右上角点击「更正基础信息」。
- 前置条件：账号具备 `PERSON_EDIT_BASIC`（连同 `PERSON_VIEW` 与 `PERSON_SENSITIVE_VIEW`）；`canAdmin` 为真（`PeopleWorkspace.tsx:314`）。
- 主路径：点击 → 打开 Modal（标题「更正基础档案」）→ 表单预填档案当前值（`:129-145`）→ 修改后点击「保存」→ 提交 `PATCH /api/v1/workforce/persons/{person_id}`（`:162-165`）。
- 结束状态：服务端写入更正记录并返回当前生效结果，Drawer 重新拉取档案，列表刷新；失败时 Modal 保留输入并显示顶部错误条「人员档案保存失败」（`:186`）。

### WFC-PEOPLE-F001-US04 新建人员档案

作为人力编制维护者，我希望登记一个新的自然人，从而为其后续建立劳动关系。

- 触发条件：点击页头「新建人员」。
- 前置条件：账号具备 `PERSON_EDIT_BASIC`（连同 `PERSON_VIEW` 与 `PERSON_SENSITIVE_VIEW`）；`canAdmin` 为真（`PeopleWorkspace.tsx:220-222`）。
- 主路径：点击 → 打开 Modal（标题「新建人员档案」）→ 填写法定姓名等字段，变更原因必填 → 点击「保存」→ 提交 `POST /api/v1/workforce/persons` 并请求预留工号（`PeopleWorkspace.tsx:152-161`）。
- 结束状态：服务端创建人员主档并按 `reserve_employee_number=true` 预留工号，Drawer 直接打开新员工的档案（`:160-161`）；失败时 Modal 保留输入并显示错误条。

### WFC-PEOPLE-F001-US05 维护档案下的劳动关系与关系

作为人力编制维护者，我希望在档案内建立劳动关系、调整四类法人主体、登记组织职务与协议关系，从而把员工与组织、主体、协议连接起来。

- 触发条件：在对应页签点击「建立劳动关系」「新增主体版本」「新增关系」「登记协议关系」。
- 前置条件：账号具备 `WORKFORCE_ADMIN`（这些端点用 `AdminUser`，`extended_api.py:61`、`:323-326`）；「新增主体版本」与「新增关系」要求该员工已有劳动关系（按钮 `disabled={!archive.employments.length}`，`PeopleWorkspace.tsx:362`、`:374`）。
- 主路径：打开 Modal → 填写字段（人员类型、计划入职日期、合同 / 发薪 / 社保 / 个税主体、生效日期等，`:429-461`）→ 点击「保存」→ 提交对应 POST（`:166-178`）→ 成功后重新拉取档案。
- 结束状态：对应子表出现新记录，计数标题加一；失败时 Modal 保留输入并显示错误条。

## 6. 业务流程与状态机

```text
人员主档（persons）
  新建（POST /persons，预留工号）──► 人员主档 + 工号
        │
        └─► 更正（PATCH /persons/{id}）──► 追加一条带生效日期的更正记录
              │
              ├─► 建立劳动关系（POST /employments）
              ├─► 调整四类法人主体（POST /employments/{id}/legal-entity-relations）
              ├─► 新增组织职务（POST /employment-assignments）
              └─► 登记协议关系（POST /agreement-relationships）

员工档案 Drawer（只读视图）
  列表行点击 ──► GET /persons/{id} ──► 7 个页签
  关闭 ──► 回到宿主页，保留筛选与分页状态
```

| 当前状态 | 操作 | 条件 | 下一状态 | 失败结果 |
|---|---|---|---|---|
| 列表未加载 | `GET /persons` 等四个并行请求 | 权限满足 | 表格显示人员 | 顶部错误条「人员中心加载失败」 |
| 列表已加载 | 点击行 / 「查看档案」 | 权限满足 | 打开 Drawer | 顶部错误条「人员档案加载失败」 |
| Drawer 未打开 | 「新建人员」 | `canAdmin` | 打开 Modal | 提交失败时 Modal 保留输入 |
| Drawer 已打开 | 「更正基础信息」 | `canAdmin` 且账号具备 `PERSON_EDIT_BASIC` | 打开 Modal 并预填当前值 | 提交失败时 Modal 保留输入 |
| Drawer 已打开 | 「建立劳动关系」等 | `canAdmin` 且（主体版本 / 组织职务要求已有劳动关系） | 提交写操作 | 提交失败时 Modal 保留输入 |
| 任意写操作 | 提交请求 | 权限满足 | 数据与审计在同一事务内提交（`apps/api/src/hris/core/database.py:18-25`） | 403 `PERMISSION_DENIED`；422 `REQUEST_VALIDATION_FAILED` |

## 7. 业务规则

状态约定：`CONFIRMED` 表示该规则已有已确认决策、已交付能力或服务端强制的合同约束支撑；`PENDING` 表示该规则取决于尚未签字的产品决策，开发者不得自行猜测；`NOT_APPLICABLE` 表示经核查本功能不涉及，并写明依据。

| ID | 状态 | 规则 | 规则来源 | 验证方式 |
|---|---|---|---|---|
| WFC-PEOPLE-F001-BR001 | `CONFIRMED` | 人员档案的读取要求同时持有 `PERSON_VIEW` 与 `PERSON_SENSITIVE_VIEW`；基础信息更正额外要求 `PERSON_EDIT_BASIC` | 实现 `extended_api.py:62-75`；D-053 | AC005 |
| WFC-PEOPLE-F001-BR002 | `CONFIRMED` | 人员列表按「工号升序（空值在后）+ 姓名升序」排序；`search` 对显示名与工号做大小写不敏感的模糊匹配，`status` 精确匹配 | 实现 `extended_service.py:1155-1173` | AC002 |
| WFC-PEOPLE-F001-BR003 | `CONFIRMED` | 工号是 6 位数字、全库唯一；为空时页面显示「待分配」；新建人员时前端固定传 `reserve_employee_number=true` | 实现 `models.py:327-337`、契约 `extended_schemas.py:179`；前端 `PeopleWorkspace.tsx:155-159`、`:265` | AC004 |
| WFC-PEOPLE-F001-BR004 | `CONFIRMED` | 法定姓名必填；显示姓名留空时后端取法定姓名 | 契约 `extended_schemas.py:169-170`、`:183-187`；前端「显示姓名（留空则同法定姓名）」（`PeopleWorkspace.tsx:419`） | AC004 |
| WFC-PEOPLE-F001-BR005 | `CONFIRMED` | 新建人员与所有写操作必须填写变更原因（1–500 字符），写入审计记录的 `reason` | 契约 `extended_schemas.py:181`；前端必填项「变更原因」（`PeopleWorkspace.tsx:470`） | AC007 |
| WFC-PEOPLE-F001-BR006 | `CONFIRMED` | 「更正基础信息」写入的是**更正记录**而非原地改写主档；`GET /persons/{id}` 返回的 `person` 是当前生效结果（主档登记值 + 生效日期 ≤ 查询日期的最后一条更正） | 实现 `extended_api.py:256-279` | AC007 |
| WFC-PEOPLE-F001-BR007 | `CONFIRMED` | 员工档案 Drawer 的 7 个页签中，「员工标签」页签只在 `canAdmin` 为真时挂载，避免给出必然 403 的入口 | 实现 `PeopleWorkspace.tsx:339-347`；HR-LABEL-016 | AC006 |
| WFC-PEOPLE-F001-BR008 | `CONFIRMED` | 「四类主体版本」与「组织职务」两个页签的新增按钮在没有劳动关系时禁用 | 实现 `PeopleWorkspace.tsx:362`、`:374` | AC003 |
| WFC-PEOPLE-F001-BR009 | `CONFIRMED` | 筛选是草稿式：改值不立即查询，点「查询」才生效；「重置」清空全部筛选并重新加载第一页 | 实现 `PeopleWorkspace.tsx:114-127`；D-091 | AC008 |
| WFC-PEOPLE-F001-BR010 | `CONFIRMED` | 人员列表的「在职状态」在前端由已加载结果过滤（后端列表支持 `status` 参数，但页面当前不带该参数） | 实现 `PeopleWorkspace.tsx:94-98`、`:115-119`；后端支持见 `extended_api.py:233` | AC008 |
| WFC-PEOPLE-F001-BR011 | `CONFIRMED` | 人员列表的「主组织 / 职位 / 入职日期」三列当前显示为「—」占位，页面明确注明这三项属于人员档案数据（组织职务与劳动关系），列表接口当前不返回 | 实现 `PeopleWorkspace.tsx:256-258`、`:266-278` | AC002、AC009 |
| WFC-PEOPLE-F001-BR012 | `CONFIRMED` | Drawer 标题格式固定为「{姓名} · {工号}」，工号为空时用「待分配」；副标题固定为「员工档案 · 人员中心」 | 实现 `PeopleWorkspace.tsx:304-310` | AC003 |
| WFC-PEOPLE-F001-BR013 | `CONFIRMED` | 「性别 / 民族 / 婚姻状况 / 政治面貌」以自由文本代码录入，页面不做字典映射与校验 | 实现 `PeopleWorkspace.tsx:420-427` | AC004 |
| WFC-PEOPLE-F001-BR014 | `PENDING` | 人员列表的「主组织 / 职位 / 入职日期」三列与「主组织」筛选是否由后端补齐：(a) 后端列表接口补字段（推荐）；(b) 前端删掉这 3 列与主组织筛选 | 现状实现 `PeopleWorkspace.tsx:256-258`；待确认清单 P-21 | 见 §18 Q-01 |
| WFC-PEOPLE-F001-BR015 | `PENDING` | 「在职状态」的字段口径：(a) 改用 `employment.status`（劳动关系状态）定义「在职」（推荐）；(b) 保留 `persons.status` 并把列名改成「状态」 | 现状实现 `PeopleWorkspace.tsx:47-52`；待确认清单 P-22 | 见 §18 Q-03 |
| WFC-PEOPLE-F001-BR016 | `PENDING` | 人员档案入口的载体：当前用 Drawer（与实现一致）；是否升级为 NEW_TAB | 待确认清单 P-03；D-068 的升级线为「超过 20 字段、超过 3 分组、存在页内标签或历史对比」 | 见 §18 Q-07 |
| WFC-PEOPLE-F001-BR017 | `PENDING` | 「敏感与经历档案」页签的完整需求（证件、联系方式、地址、紧急联系人、教育、工作、家庭成员的脱敏与明文查看）尚未建立功能文档 | 现状实现 `PeopleWorkspace.tsx:334-338`、`apps/web/src/business/features/workforce/PersonnelSubrecordsPanel.tsx` | 见 §18 Q-04 |
| WFC-PEOPLE-F001-BR018 | `PENDING` | 企业侧的正式人员编码规则、完整档案字段清单与国别 / 民族码表尚未提供 | 依据 `docs/01-foundation/99-待确认问题.md` 与本轮输入包缺口 | 见 §18 Q-06 |

规则写法自查（对照规范 §8.1 / §8.2）：所有 `CONFIRMED` 规则都写明了适用对象与时间点、条件与唯一性维度、成功与拒绝结果，不使用「合理处理」「一般情况」「尽量」等表述；不包含未说明配置范围的「支持灵活配置」、未说明幂等与最终状态的「失败后重试」、未说明下游与历史保留的「可以回退」。

## 8. 数据要求

### 8.1 数据所有权与关系

- 本功能拥有的数据：
  - `persons`（人员主档，字段 `employee_number`、`legal_name`、`display_name`、`former_name`、`gender_code`、`birth_date`、`ethnicity_code`、`nationality_code`、`country_code`、`marital_status_code`、`political_status_code`、`status`）。
  - 归属模块：Workforce Core；表定义见 `apps/api/src/hris/modules/workforce/models.py:324-348`。
- 引用但不拥有的数据：
  - `employments`、`employment_legal_entity_relations`、`employment_assignments`、`agreement_relationships`（档案子表，由 Workforce Core 拥有）。
  - `legal_entities`、`organizations`、`job_catalog` / `job_catalog_versions`（下拉候选与只读引用）。
  - `user_accounts`（操作人，审计关联）。
- 业务唯一键：
  - `persons.id` 是稳定身份 UUID。
  - `persons.employee_number` 全库唯一且必须匹配 `^[0-9]{6}$`（DB CheckConstraint `employee_number_format`，`models.py:327-331`）。
  - `persons.legal_name` / `display_name` 建有索引但**不唯一**（`models.py:338-339`）。
- 有效日期/版本/快照要求：
  - 人员主档本身没有生效区间；「当前生效结果」由更正记录的生效日期推导（`extended_api.py:256-279`）。
  - 子表（劳动关系、四类主体版本、组织职务、协议关系）各自带 `effective_from` / `effective_to` 与 `version` 列，本功能的 Drawer 只读展示。

### 8.2 字段合同

「来源」列中的文件均位于 `apps/api/src/hris/modules/workforce/extended_schemas.py`（契约）或 `apps/web/src/business/features/workforce/types.ts`（前端类型），行号在括号内注明。

| ID | 字段 | 类型/格式 | 必填 | 来源 | 默认值 | 校验 | 敏感级别 | 历史策略 |
|---|---|---|---|---|---|---|---|---|
| WFC-PEOPLE-F001-DAT001 | `id` | UUID | 响应只读 | `PersonResponse.id`（:193）、`Person.id`（`types.ts:10`） | — | — | 非敏感 | 稳定身份，跨更正不变 |
| WFC-PEOPLE-F001-DAT002 | `employee_number` | string(6)，`^[0-9]{6}$` | 否 | `PersonCreate.employee_number`（:179）、`PersonResponse.employee_number`（:194） | 新建时由 `reserve_employee_number=true` 预留（`extended_schemas.py:180`） | 全库唯一；格式由 DB CheckConstraint 兜底（`models.py:327-331`） | 非敏感 | 主档字段，不随更正变化 |
| WFC-PEOPLE-F001-DAT003 | `legal_name` | string(200) | 是 | `PersonCreate.legal_name`（:169）、`PersonResponse.legal_name`（:195） | 无 | 1–200 字符 | 个人信息（法定姓名） | 可被更正记录覆盖 |
| WFC-PEOPLE-F001-DAT004 | `display_name` | string(200) | 否（留空则同法定姓名） | `PersonCreate.display_name`（:170）、`PersonResponse.display_name`（:196） | 后端取 `legal_name`（`extended_schemas.py:183-187`） | 1–200 字符 | 个人信息（姓名） | 可被更正记录覆盖 |
| WFC-PEOPLE-F001-DAT005 | `former_name` | string(200)，可空 | 否 | `PersonCreate.former_name`（:171）、`PersonResponse.former_name`（:197） | 空 | ≤200 字符 | 个人信息（曾用名） | 可被更正记录覆盖 |
| WFC-PEOPLE-F001-DAT006 | `gender_code` | string(30)，可空 | 否 | `PersonCreate.gender_code`（:172）、`PersonResponse.gender_code`（:198） | 空 | **自由文本，无字典校验** | 个人信息 | 可被更正记录覆盖 |
| WFC-PEOPLE-F001-DAT007 | `birth_date` | date，可空 | 否 | `PersonCreate.birth_date`（:173）、`PersonResponse.birth_date`（:199） | 空 | — | 个人信息（出生日期） | 可被更正记录覆盖 |
| WFC-PEOPLE-F001-DAT008 | `ethnicity_code` | string(50)，可空 | 否 | `PersonCreate.ethnicity_code`（:174）、`PersonResponse.ethnicity_code`（:200） | 空 | **自由文本** | 个人信息（民族） | 可被更正记录覆盖 |
| WFC-PEOPLE-F001-DAT009 | `nationality_code` | string(2–3)，可空 | 否 | `PersonCreate.nationality_code`（:175）、`PersonResponse.nationality_code`（:201） | 空 | 长度 2–3 | 个人信息（国籍） | 可被更正记录覆盖 |
| WFC-PEOPLE-F001-DAT010 | `country_code` | string(2–3)，可空 | 否 | `PersonCreate.country_code`（:176）、`PersonResponse.country_code`（:202） | 空 | 长度 2–3 | 个人信息（国家/地区） | 可被更正记录覆盖 |
| WFC-PEOPLE-F001-DAT011 | `marital_status_code` | string(50)，可空 | 否 | `PersonCreate.marital_status_code`（:177）、`PersonResponse.marital_status_code`（:203） | 空 | **自由文本** | 个人信息 | 可被更正记录覆盖 |
| WFC-PEOPLE-F001-DAT012 | `political_status_code` | string(50)，可空 | 否 | `PersonCreate.political_status_code`（:178）、`PersonResponse.political_status_code`（:204） | 空 | **自由文本** | 个人信息 | 可被更正记录覆盖 |
| WFC-PEOPLE-F001-DAT013 | `status` | string(30) | 响应只读 | `PersonResponse.status`（:205） | 后端默认 `active`（`models.py:348`） | 启停语义 | 非敏感 | 主档字段 |
| WFC-PEOPLE-F001-DAT014 | `change_reason` | string(500) | 是（写操作） | `PersonCreate.change_reason`（:181） | 无 | 1–500 字符 | 非敏感 | 不进业务字段；写入审计 `reason` |
| WFC-PEOPLE-F001-DAT015 | `created_at` / `updated_at` | datetime | 响应只读 | `PersonResponse.created_at`（:206）、`updated_at`（:207） | — | — | 非敏感 | 主档审计时间戳 |
| WFC-PEOPLE-F001-DAT016 | `employments` | `Employment[]` | 响应只读 | `PersonArchive.employments`（`types.ts:81`） | — | — | 个人信息（劳动关系） | 只读展示 |
| WFC-PEOPLE-F001-DAT017 | `legal_entity_relations` | `EmploymentLegalEntityRelation[]` | 响应只读 | `PersonArchive.legal_entity_relations`（`types.ts:82`） | — | — | 非敏感 | 只读展示 |
| WFC-PEOPLE-F001-DAT018 | `assignments` | `EmploymentAssignment[]` | 响应只读 | `PersonArchive.assignments`（`types.ts:83`） | — | — | 非敏感 | 只读展示 |
| WFC-PEOPLE-F001-DAT019 | `agreements` | `AgreementRelationship[]` | 响应只读 | `PersonArchive.agreements`（`types.ts:84`） | — | — | 非敏感（可能含合作方名称） | 只读展示 |

### 8.3 数据生命周期

- 创建：新建人员写入 `persons` 一行并预留工号（`extended_api.py:218-222`）；随后可在同一 Drawer 内建立劳动关系等子表。
- 修改/更正：基础信息更正**不改写主档**，而是追加一条带生效日期的更正记录；主档保留登记值（`extended_api.py:256-279`）。
- 生效/失效：`persons` 无生效区间；子表各自带生效区间，本功能只读展示。
- 保留：人员主档与子表永久保留，本功能没有删除入口；审计日志另表保存。
- 删除：`NOT_APPLICABLE`。依据：人员中心页面没有删除入口，`extended_api.py` 的人员路由只有 GET / POST / PATCH（`:218-318`），物理删除与离职处理属于员工生命周期模块，不在本功能范围。
- 迁移与兼容：本轮无结构变更；`persons` 表结构自第一阶段人员档案交付以来未变。

## 9. 权限要求

| ID | 状态 | 参与者 | 功能/动作权限 | 数据范围 | 字段权限 | 拒绝结果 |
|---|---|---|---|---|---|---|
| WFC-PEOPLE-F001-PERM001 | `CONFIRMED` | 持有 `PERSON_VIEW` + `PERSON_SENSITIVE_VIEW` 或 `*` 的账号 | 查看人员列表（`GET /api/v1/workforce/persons`） | 全部人员，无行级过滤 | 列表字段（DAT001–DAT013、DAT015） | 403 `PERMISSION_DENIED`「没有执行此操作的权限」（`dependencies.py:80`）；前端显示顶部错误条「人员中心加载失败」（`PeopleWorkspace.tsx:86`） |
| WFC-PEOPLE-F001-PERM002 | `CONFIRMED` | 同上 | 查看员工档案（`GET /api/v1/workforce/persons/{id}`） | 单个员工 | 档案字段（DAT001–DAT019） | 同 PERM001；前端显示「人员档案加载失败」（`:110`） |
| WFC-PEOPLE-F001-PERM003 | `CONFIRMED` | 持有 `PERSON_VIEW` + `PERSON_EDIT_BASIC` + `PERSON_SENSITIVE_VIEW` 或 `*` 的账号 | 新建人员（`POST /api/v1/workforce/persons`）、更正基础信息（`PATCH /api/v1/workforce/persons/{id}`） | 全部人员 | 可写 DAT002–DAT012、DAT014；DAT001、DAT013 只读 | 同 PERM001；无权限时页头不渲染「新建人员 / 新建法人」、Drawer 不渲染「更正基础信息」（`PeopleWorkspace.tsx:220-222`、`:314`） |
| WFC-PEOPLE-F001-PERM004 | `CONFIRMED` | 持有 `WORKFORCE_ADMIN` 或 `*` 的账号 | 建立劳动关系、调整四类法人主体、新增组织职务关系、登记协议关系、新建法人主体 | 全部人员与主体 | 对应子表业务字段 | 同 PERM001；无权限时对应页签不渲染新增按钮（`PeopleWorkspace.tsx:351`、`:362`、`:374`、`:385`） |
| WFC-PEOPLE-F001-PERM005 | `CONFIRMED` | 持有 `WORKFORCE_ADMIN` 或 `*` 的账号 | 「员工标签」页签的挂载与页内写操作 | 单个员工 | 见 WFC-LABEL-F001 | 无 `WORKFORCE_ADMIN` 时该页签不出现（`PeopleWorkspace.tsx:339-347`） |
| WFC-PEOPLE-F001-PERM006 | `CONFIRMED` | 持有 `WORKFORCE_ADMIN` 或 `*` 的账号 | 侧栏入口可见性：侧栏「人员中心」按 `WORKFORCE_ADMIN` 过滤 | — | — | 无权限时侧栏入口不出现（`apps/web/src/business/navigation.ts:57`、`AppShell.tsx:184-187` 的 `visibleWorkspaces` 过滤） |
| WFC-PEOPLE-F001-PERM007 | `CONFIRMED` | 持有 `PERSON_VIEW` + `PERSON_SENSITIVE_VIEW` 但没有 `WORKFORCE_ADMIN` 的账号 | 侧栏入口不出现，但可直接访问 `#people` hash 路由；页面列表与档案可读，写操作按钮全部不可见 | — | — | 直接访问时页面可用（只读态）；写操作由服务端 403 兜底 |
| WFC-PEOPLE-F001-PERM008 | `CONFIRMED` | 未登录或会话失效账号 | 任何接口 | — | — | 401 `AUTHENTICATION_REQUIRED`「需要登录」或 `SESSION_INVALID`「登录状态无效或已过期」（`dependencies.py:32`、`:47`） |

代办与代理说明：

- 主管理员（持 `*`）可以直接执行全部读写操作，不需要额外审批（`dependencies.py:90` 对 `*` 短路放行）。
- 每次写操作必须填写业务变更原因 `change_reason`，该值原样写入审计 `reason`，因此原因不是可选元数据（契约 `extended_schemas.py:181`）。
- 本功能**没有代办 / 代理身份机制**：审计只记录操作者本人 `actor_id`，没有 `on_behalf_of` 字段。
- 未知范围默认拒绝：权限判定为「不具备所需权限码即拒绝」，不做任何隐式放行（`dependencies.py:79-80`）。

## 10. 交互与页面要求

### 10.1 入口与可见性

- 菜单/页面/按钮：
  - 侧栏：「人员中心」（`navigation.ts:57`）。
  - 面包屑：「组织管理 / 人员中心」（画板面包屑为「组织管理 / 人员中心」，画板登记表 `breadcrumb`）。
  - 页内操作：页头次按钮「新建法人」+ 主按钮「新建人员」（`PeopleWorkspace.tsx:220-222`）；行内「查看档案」链接（`:279-288`）；抽屉右上「更正基础信息」（`:314`）。
  - 页面标题与副标题（宿主页页头，逐字复用实现）：标题「人员中心」；副标题「自然人、雇佣经历、主组织职务和协议关系分层保存。」（`PeopleWorkspace.tsx:217-219`）。
  - 筛选区文案：标签「姓名或工号」「在职状态」（`:236`、`:245`）；占位符「搜索姓名或工号」「全部状态」。
- 无权限或未启用模块时：侧栏不渲染该入口（`navigation.ts:57`）；直接访问且接口 403 时显示顶部可关闭错误条，本页面**没有**整页 `WorkspaceDenied` 拒绝态（与职位管理、汇报关系不同，见 §10.2）。
- 宿主页：列表。人员中心分组下的独立宿主页；员工档案以 Drawer 承载在同一宿主页上下文内。
- 交互载体：`DRAWER`（员工档案）+ `MODAL`（新建人员、更正基础档案、建立劳动关系、调整四类主体、新增组织职务、登记协议关系、新建法人）。主载体为 `DRAWER`——员工档案是一个独立于宿主页列表的结果视图，用 Drawer 保留列表上下文。
- 选择理由：员工档案含 7 个页签与分组字段，按 [Ant Design 页面与交互载体规范](../design/antd-page-interaction-standard.md) §3 的升级线（超过 20 字段、超过 3 分组、存在页内标签或历史对比）本应升级为 `NEW_TAB`，但当前实现是 Drawer 且已获用户授权按画板落地（P-03 记录「用 Drawer（与实现一致）」）；本文件按已实现形态登记，并在 §18 Q-07 把「是否升级为 NEW_TAB」列为待确认项，不在本功能内自行改载体。Drawer 的 `size="large"`（`PeopleWorkspace.tsx:303`）与画板登记的 `carrierSize: large` 一致。
- 路由或深链接：宿主页为 hash 路由 `#people`（`navigation.ts:126-132`）；Drawer 不占用独立路由，关闭后回到宿主页并保留筛选与分页状态（宿主页组件未被卸载）。当前 Drawer 无深链接定位能力（不刷新、不带 URL 参数）。
- Pencil源文件：`C:\Users\83289\Documents\HRMS\coreHR.pen`（Pencil 2.17）。
- 画板ID/名称/原型版本：`JN45s` / 「人员中心 · 员工档案 v1.0」 / `v1.0`（画板 1440×960）。
- 原型状态：`PROTOTYPE_APPROVED`。2026-10-24 产品决策人确认全部画板并签字，规范 §10.1 的状态枚举中对应 `PROTOTYPE_APPROVED`；按规范 §10.2 与 D-087，前端开发门禁已解除，本功能可按画板继续开发（见 §19 T002 状态与 §18 Q-08）。

### 10.2 页面状态

| 状态 | 页面表现 | 可执行操作 |
|---|---|---|
| 首次/空数据 | 表格空态「暂无人员档案」（`PeopleWorkspace.tsx:290`），由 `DataTable` 的 `emptyText` 承载；分页器显示「共 0 名员工」 | 调整筛选、点击「查询」 |
| 加载中 | 表格 `loading` 态（`PeopleWorkspace.tsx:262`）；四个并行请求全部完成后才填充数据（`:75-84`） | 等待 |
| 正常 | 筛选栏 + 表格 + 分页器，分页文案「共 N 名员工」（`:296`）；在职状态用绿色「在职」/ 灰色「停用」Tag（`:268-277`） | 筛选、查询、重置、翻页、打开档案 |
| 部分失败 | 四个并行请求用 `Promise.all`，任一失败则整体进入 catch 分支（`PeopleWorkspace.tsx:75-89`）：**人员、法人主体、职位、组织四项是全有或全无**，不会出现「人员表空、其它有数据」的半状态；失败时显示顶部错误条 | 关闭错误条、重新查询 |
| 完全失败 | 同上，表现为顶部错误条「人员中心加载失败」或「人员档案加载失败」（`:86`、`:110`） | 关闭错误条或联系管理员 |
| 无权限 | 侧栏入口不渲染；已打开页面时列表请求 403 → 顶部错误条 | 退出登录或联系主管理员 |

### 10.3 表单与确认

- 字段顺序与联动：
  - 新建人员 / 更正基础档案：「法定姓名」→「显示姓名（留空则同法定姓名）」→「曾用名」→「性别代码」→「出生日期」→「国籍代码」→「国家/地区代码」→「民族代码」→「婚姻状况代码」→「政治面貌代码」→（所有写操作）→「变更原因」（`PeopleWorkspace.tsx:417-428`、`:470`）。
  - 联动：新建人员时填写「法定姓名」会自动带出尚未填写的「显示姓名」（`PeopleWorkspace.tsx:410-414`）。
  - 建立劳动关系：「人员类型」→「计划入职日期」（默认今天）→「劳动合同主体」→「发薪主体（留空则同合同主体）」→「社保主体（留空则同合同主体）」→「个税主体（留空则同合同主体）」（`:429-435`）。
  - 调整四类法人主体：「劳动关系」→「主体类型」→「法人主体」→「生效日期」（`:437-444`）。
  - 新增组织职务：「劳动关系」→「关系类型」→「组织」→「职务」→「生效日期」→「失效日期」（`:445-454`）。
  - 登记协议关系：「协议关系类型」→「关联法人」→「合作方名称」→「生效日期」→「失效日期」（`:455-461`）。
  - 新建法人主体：「法人编码」→「法人名称」→「注册名称」→「国家/地区代码」（默认 `CN`）→「注册号」→「生效日期」（`:462-469`）。
- 即时校验与提交校验：前端 antd Form 必填规则（法定姓名、变更原因、人员类型、计划入职日期、劳动合同主体、主体类型、法人主体、生效日期、关系类型、组织、协议关系类型、法人编码、法人名称、国家/地区代码等）；后端 pydantic 校验失败返回 422 `REQUEST_VALIDATION_FAILED`，逐字段 `details` 返回（`apps/api/src/hris/core/errors.py:41-61`）。
- 高风险二次确认：**当前所有写操作都没有二次确认**（无 Popconfirm）。规范 §5 要求高风险操作说明具体对象、影响与是否可恢复——「更正基础信息」会写入一条不可删除的更正记录、「登记协议关系」会建立对外协议关系，属于高风险；是否补二次确认见 §18 Q-09。
- 成功反馈与下一步：保存成功后关闭 Modal，并按动作类型重新拉取档案与列表（`PeopleWorkspace.tsx:160-178`）；新建人员成功后直接打开新员工的档案（`:161`）；失败时 Modal 保留用户输入，页面顶部显示错误条「人员档案保存失败」（`:186`）。
- 打开、关闭和焦点返回：Modal 使用 `destroyOnHidden`（`:398`），关闭即销毁表单；antd 默认在打开后把焦点移入容器、关闭后焦点回到触发元素。Drawer 关闭由「×」或遮罩触发（`:313`），关闭后焦点回到打开它的表格行。
- 未保存变更与重复提交保护：未保存变更**不拦截**关闭（当前实现没有脏检查）；保存期间 `confirmLoading={saving}` 使「保存」按钮进入加载态，阻止重复提交（`:402`、`:151`、`:188`）。
- 弹窗关闭后表单重置或保留策略：关闭即销毁；打开「更正基础档案」时由 `openAction("edit")` 预填档案当前值（`:129-145`），打开其它 Modal 时 `form.resetFields()`（`:131`）。

### 10.4 Pencil原型登记

| 原型ID | 页面/交互载体 | Pencil文件 | 画板ID与名称 | 版本 | 状态 | 批准人/日期 |
|---|---|---|---|---|---|---|
| WFC-PEOPLE-F001-PROT001 | `DRAWER`（宿主页「人员中心 · 员工档案 v1.0」含七列表格，画板 `JN45s` 1440×960；员工档案 Drawer 的 7 个页签与新建 / 更正 Modal 尚未单独出画板） | `C:\Users\83289\Documents\HRMS\coreHR.pen` | 画板ID `JN45s`；画板名称「人员中心 · 员工档案 v1.0」 | v1.0 | `PROTOTYPE_APPROVED` | 2026-10-24 产品决策人签字确认（见 §18 Q-08 / §20） |

登记说明（按事实记录，不做美化）：

- 画板状态 `PROTOTYPE_APPROVED`（2026-10-24 产品决策人签字确认）依据 `docs/review/pen-prototype-spec-2026-10-24.md` 头部状态标注与 §7 后续动作第 3 条；预览图为 `docs/review/pen-prototypes/04-人员中心.png`。
- 画板登记表记录的差异：第 1 条「员工标签不是独立页面，入口是『查看档案』打开的 Drawer」对应 §2.2 的拆分说明与 §9 PERM005；第 2 条「主组织 / 职位 / 入职日期三列在画板中有值，列表接口当前不返回，页面按空值占位」对应 BR011 与 §18 Q-01。
- 画板规格中的 `filters` 列出「姓名或工号 / 在职状态 / 主组织 / 查询 / 重置」五项，实际实现的筛选区只有「姓名或工号 / 在职状态」两项（`PeopleWorkspace.tsx:226-255`），**「主组织」筛选未实现**——这是画板与实现之间的实质差异，不是「有意保留」，对应 BR014 / §18 Q-01。
- 规范 §10.4 要求「显著不同的加载、空数据、失败、无权限和冲突状态应在原型中可Review」，这些状态目前只存在于实现（`PeopleWorkspace.tsx:256-300`），没有对应的 Pencil 画板——见 §18 Q-08。

## 11. API与事件合同

### 11.1 同步API

| ID | 方法与路径 | 调用者 | 请求摘要 | 响应摘要 | 权限 | 幂等 | 事务边界 |
|---|---|---|---|---|---|---|---|
| WFC-PEOPLE-F001-API001 | `GET /api/v1/workforce/persons`（`extended_api.py:225-246`） | 人员中心宿主页 | 查询参数：`search`（≤200，可选）、`status`（别名，≤30，可选）、`limit`（1–200，缺省 50，前端传 200）、`offset`（≥0，前端传 0） | `PageResponse`：`items`（`PersonResponse` 列表）、`total`、`limit`、`offset` | `PERSON_VIEW` + `PERSON_SENSITIVE_VIEW` | 天然幂等（只读） | 单请求单事务，`get_db` 在响应前提交（`apps/api/src/hris/core/database.py:18-25`） |
| WFC-PEOPLE-F001-API002 | `GET /api/v1/workforce/persons/{person_id}`（`extended_api.py:249-298`） | 人员中心宿主页（打开档案） | 路径参数 `person_id`（UUID）；查询参数 `effective_at`（date，可选，缺省业务当天） | `PersonArchiveResponse`：`person`（当前生效结果）、`registered_person`（主档登记值）、`corrections`、`employments`、`legal_entity_relations`、`assignments`、`agreements` | `PERSON_VIEW` + `PERSON_SENSITIVE_VIEW` | 天然幂等 | 单请求单事务 |
| WFC-PEOPLE-F001-API003 | `POST /api/v1/workforce/persons`（`extended_api.py:218-222`，201） | 人员中心宿主页「新建人员」 | `PersonCreate`：DAT002–DAT012、DAT014 + `reserve_employee_number` | `PersonResponse`（201） | `PERSON_VIEW` + `PERSON_EDIT_BASIC` + `PERSON_SENSITIVE_VIEW` | 不幂等：工号唯一，重复预留返回冲突；同一人重复创建产生第二条主档 | 单请求单事务；主档、更正记录与审计行同事务 |
| WFC-PEOPLE-F001-API004 | `PATCH /api/v1/workforce/persons/{person_id}`（`extended_api.py:302-312`） | 员工档案 Drawer「更正基础信息」 | `PersonUpdate`：可写字段 + `change_reason` | `PersonResponse` | 同 API003 | 不幂等：每次提交追加一条更正记录；同生效日重复提交按更正服务的版本规则处理 | 单请求单事务；更正记录与审计行同事务 |
| WFC-PEOPLE-F001-API005 | `POST /api/v1/workforce/employments`（`extended_api.py:323-326`，201） | Drawer「建立劳动关系」 | `EmploymentCreate` | `EmploymentResponse`（201） | `WORKFORCE_ADMIN` | 不幂等：同一人员同一生效日的重复劳动关系按服务层规则处理 | 单请求单事务 |
| WFC-PEOPLE-F001-API006 | `POST /api/v1/workforce/employments/{employment_id}/legal-entity-relations`（见 `apps/web/src/business/features/workforce/api.ts:114-115`） | Drawer「新增主体版本」 | 四类主体版本载荷 | 主体版本响应 | `WORKFORCE_ADMIN` | 不幂等：每次追加一个版本 | 单请求单事务 |
| WFC-PEOPLE-F001-API007 | `POST /api/v1/workforce/employment-assignments`（见 `api.ts:116-117`） | Drawer「新增关系」 | 组织职务载荷 | 组织职务响应 | `WORKFORCE_ADMIN` | 不幂等：每次追加一段区间 | 单请求单事务 |
| WFC-PEOPLE-F001-API008 | `POST /api/v1/workforce/agreement-relationships`（见 `api.ts:118-119`） | Drawer「登记协议关系」 | 协议关系载荷 | 协议关系响应 | `WORKFORCE_ADMIN` | 不幂等：每次追加一段区间 | 单请求单事务 |
| WFC-PEOPLE-F001-API009 | `GET /api/v1/workforce/legal-entities?limit=200&offset=0`（`extended_api.py:99-115`） | 人员中心宿主页（法人下拉候选） | 分页参数 | `PageResponse`：`items`（`LegalEntityResponse`）等 | `WORKFORCE_ADMIN` | 天然幂等 | 单请求单事务 |
| WFC-PEOPLE-F001-API010 | `GET /api/v1/workforce/jobs?limit=200&offset=0`（`extended_api.py:139-158`） | 人员中心宿主页（职务下拉候选） | 分页参数 + 可选 `effective_at` | `PageResponse`：`items`（`JobResponse`）等 | `WORKFORCE_ADMIN` | 天然幂等 | 单请求单事务 |
| WFC-PEOPLE-F001-API011 | `GET /api/v1/organizations/tree`（`apps/api/src/hris/modules/workforce/organization_api.py:124-152`） | 人员中心宿主页（组织下拉候选） | 可选 `as_of`（date） | `list[OrganizationTreeNode]` | `ORGANIZATION_VIEW` | 天然幂等 | 单请求单事务 |
| WFC-PEOPLE-F001-API012 | `POST /api/v1/workforce/legal-entities`（`extended_api.py:90-96`，201） | 人员中心宿主页「新建法人」 | `LegalEntityCreate` | `LegalEntityResponse`（201） | `WORKFORCE_ADMIN` | 不幂等 | 单请求单事务 |

调用者与所有权说明：上述接口由 Workforce Core 模块提供（`apps/api/src/hris/modules/workforce/`）；前端调用封装在 `apps/web/src/business/features/workforce/api.ts:37-182`，认证统一使用 Bearer Token（`apps/web/src/business/client.ts`）。

### 11.2 异步事件与任务

`NOT_APPLICABLE`。依据：本功能的所有写路径（`extended_service.py` 的 `create_person` / `update_person` / `create_employment` / `create_legal_entity_relation_version` / `create_assignment` / `create_agreement`）只做数据库写入与审计写入，模块内没有消息发布或领域事件调用（`apps/api/src/hris/modules/workforce/extended_service.py` 全文件检索 `publish` / `emit` 无命中）；人员数据的下游消费（编制、生命周期、考勤）由引用方在自己的事务内按 id 引用完成。若后续引入消息引擎（待确认清单 P-10～P-12），「员工入职事件」等由生命周期模块发布，不在本功能范围。

### 11.3 兼容与废弃

- 当前合同版本：v1。人员列表、档案、创建与更正四个接口的路径与响应字段自第一阶段人员档案交付以来未变（`docs/delivery/` 下的第一阶段交付记录）。
- 向后兼容策略：`PersonResponse` 的字段集合不变；人员主档与更正记录分层保存（`extended_api.py:256-279`），更正机制不改变主档结构。
- 废弃通知和截止版本：当前无废弃项。若后续按企业码表把「性别 / 民族 / 婚姻状况 / 政治面貌」从自由文本改为字典引用，必须先在本节登记字段语义变更并同步 `docs/01-foundation/03-项目决策.md`，不得直接删除旧列（规范 §13 变更控制）。

## 12. 异常、并发与回退

| ID | 状态 | 场景 | 系统结果 | 用户提示/错误码 | 是否重试 | 补偿/回退 |
|---|---|---|---|---|---|---|
| WFC-PEOPLE-F001-ERR001 | `CONFIRMED` | 请求体不满足 schema（如 `legal_name` 为空、`employee_number` 非 6 位数字） | 请求被拒 | 422 `REQUEST_VALIDATION_FAILED`「请求参数校验失败」，`details` 逐字段给出（`apps/api/src/hris/core/errors.py:41-61`） | 否——需改输入 | 不适用 |
| WFC-PEOPLE-F001-ERR002 | `CONFIRMED` | 工号已被占用 | 服务层按唯一约束拒绝；预留工号接口 409 | 409（工号冲突错误码由服务层定义） | 否——需换工号或让系统重新预留 | 不适用 |
| WFC-PEOPLE-F001-ERR003 | `CONFIRMED` | 更正目标人员不存在 | 拒绝 | 404（服务层的「人员不存在」错误码） | 否 | 不适用 |
| WFC-PEOPLE-F001-ERR004 | `CONFIRMED` | 建立劳动关系时引用的法人主体不存在 | 拒绝 | 422 / 404（服务层按引用校验返回） | 否 | 不适用 |
| WFC-PEOPLE-F001-ERR005 | `CONFIRMED` | 无权限访问或写入 | 请求被拒 | 403 `PERMISSION_DENIED`「没有执行此操作的权限」（`dependencies.py:80`） | 否 | 不适用 |
| WFC-PEOPLE-F001-ERR006 | `CONFIRMED` | 会话无效或过期 | 请求被拒 | 401 `AUTHENTICATION_REQUIRED` / `SESSION_INVALID`（`dependencies.py:32`、`:47`） | 重新登录后重试 | 不适用 |
| WFC-PEOPLE-F001-ERR007 | `CONFIRMED` | 四个并行加载请求中任一失败 | 整个 `Promise.all` 进入 catch，人员、法人、职位、组织四项都不写入 state；页面显示顶部错误条 | 「人员中心加载失败」（`PeopleWorkspace.tsx:86`） | 是——修正失败项后重新查询 | 无需补偿：只读请求无副作用 |
| WFC-PEOPLE-F001-ERR008 | `CONFIRMED` | 同一人员被两人同时更正基础信息 | 两次提交各自追加一条更正记录；「当前生效结果」按生效日期取最后一条（`extended_api.py:273-279`），同生效日时以服务层的版本规则决定 | 前端展示后端 message（`PeopleWorkspace.tsx:186`） | 视错误码 | 业务纠错靠追加更正记录，历史不被覆盖；同生效日冲突的口径见 §18 Q-10 |
| WFC-PEOPLE-F001-ERR009 | `CONFIRMED` | 写入过程中数据库异常 | 整个请求事务回滚，主档 / 更正记录 / 子表行与审计行都不落库 | 前端展示「人员档案保存失败」（`PeopleWorkspace.tsx:186`） | 可在修复原因后重试 | 自动回滚（`apps/api/src/hris/core/database.py:23-25`） |
| WFC-PEOPLE-F001-ERR010 | `CONFIRMED` | 后台任务中断 | `NOT_APPLICABLE`：本功能没有后台任务（依据 §11.2） | — | — | — |
| WFC-PEOPLE-F001-ERR011 | `CONFIRMED` | 下游系统失败 | `NOT_APPLICABLE`：本功能不调用外部系统（依据 §11.2） | — | — | — |
| WFC-PEOPLE-F001-ERR012 | `CONFIRMED` | 误建人员后的撤销 | 当前没有删除或停用入口：只能追加更正记录把状态改回 | 现状无对应提示 | — | 建议路径是追加更正记录；是否提供「删除 / 作废人员」见 §18 Q-11 |
| WFC-PEOPLE-F001-ERR013 | `PENDING` | 列表数据量超过前端一次性拉取上限 | 当前前端固定 `limit=200`；超出部分在页面上不可达且没有任何提示 | 现状无对应提示 | — | 规模上限见 §18 Q-02 |

## 13. 审计与数据保护

| ID | 状态 | 动作 | 审计内容 | 禁止记录内容 | 保留要求 |
|---|---|---|---|---|---|
| WFC-PEOPLE-F001-AUD001 | `CONFIRMED` | 新建人员档案 | `action=create`、`object_type=person`、`object_id=人员 id`、`reason=change_reason`、操作者与 `trace_id` | 不记录证件号、联系方式等敏感字段；审计载荷只含业务标识 | 审计行随 `audit_logs` 表保留，无删除入口 |
| WFC-PEOPLE-F001-AUD002 | `CONFIRMED` | 更正基础信息 | `action=update`、`object_type=person`、`object_id=人员 id`、`reason=change_reason`、更正前后的字段值 | 同上 | 同上 |
| WFC-PEOPLE-F001-AUD003 | `CONFIRMED` | 建立劳动关系 / 调整四类主体 / 新增组织职务 / 登记协议关系 | 各写路径在服务层内写入 `audit_logs`，`object_type` 分别为对应业务对象，`reason` 取业务原因 | 不记录敏感字段 | 同上 |
| WFC-PEOPLE-F001-AUD004 | `CONFIRMED` | 读取人员档案 | 读取行为本身不产生审计行；档案的敏感子记录有独立的查看审计（见「敏感与经历档案」能力） | — | — |

- 敏感字段加密：`NOT_APPLICABLE`（就本功能的写入表而言）。依据：本功能写入的 `persons` 主档只包含姓名、性别代码、出生日期、国籍、码值等**登记值**，不含证件号、银行账号等加密列；证件、联系方式、地址等敏感子记录存放在独立的子记录表，其加密与脱敏要求属于 `docs/01-foundation/07-人员档案领域规范.md` 与 ADR-0004，不在本功能范围（对应 §2.2 与 §18 Q-04）。
- 页面脱敏：基础信息页签展示的是非敏感登记字段（`PeopleWorkspace.tsx:321-332`）；证件号、联系方式等由「敏感与经历档案」页签按掩码展示，本功能不涉及。
- 明文访问：本功能没有「明文才能读取」的字段。
- 导出与临时文件：`NOT_APPLICABLE`。依据：人员中心页面没有导出入口（`api.ts:37-182` 无下载调用），也不产生临时文件；人员数据的批量导出属于数据治理模块（`apps/api/src/hris/modules/platform/master_data_export.py`），不在本功能范围。
- 非生产数据：验收使用合成数据；现有自动化测试即采用合成 fixture（`apps/web/src/business/features/workforce/PeopleWorkspace.test.tsx`）。

## 14. 非功能需求

| ID | 状态 | 类别 | 可验证要求 | 环境/数据量 | 验证证据 |
|---|---|---|---|---|---|
| WFC-PEOPLE-F001-NFR001 | `CONFIRMED` | 性能 | 人员列表前端分页固定每页 20 条且 `showSizeChanger=false`；后端一次最多拉取 200 条 | 本机开发库；数据量由企业人员规模决定 | 前端 `PeopleWorkspace.tsx:44`、`:291-298`、`:100-103`；后端 `api.ts:40` |
| WFC-PEOPLE-F001-NFR002 | `PENDING` | 性能 | 页面首屏（人员 + 法人主体 + 职位 + 组织树四个并行请求）的响应时间目标 | 需要容量输入：本机并发用户数、人员档案条数、主体与组织条数 | 缺容量输入，暂不可验收；输入模板见 `docs/input-packs/templates/07-capacity-scenarios.csv`，容量场景见 `docs/input-packs/09-nonfunctional-acceptance-input.md` |
| WFC-PEOPLE-F001-NFR003 | `CONFIRMED` | 可用性 / 可访问性 | 筛选控件具备可访问名称（`aria-label="搜索姓名或工号"`、`"在职状态"`）；表格行键为 `id`；整行可点击且行内有等价的「查看档案」链接；在职状态 Tag 同时输出「在职 / 停用」文字 | 键盘与屏幕阅读器人工检查 | `PeopleWorkspace.tsx:238`、`:247`、`:261`、`:268-277`、`:299`；规范 §7 状态不只依赖颜色的要求 |
| WFC-PEOPLE-F001-NFR004 | `CONFIRMED` | 兼容 | 页面使用仓库锁定的 Ant Design 6.5.2 组件，不使用已废弃属性 | 生产构建 `npm run build` | D-090；`docs/design/antd-page-interaction-standard.md` §2；`node scripts/check-antd-usage.mjs` 0 违规 |
| WFC-PEOPLE-F001-NFR005 | `CONFIRMED` | 复用 | 页面骨架、筛选栏与表格统一使用 `WorkspaceShell`、`FilterBar`、`DataTable`，不在本能力域内出现第二套写法 | 全站一致性 | D-091；`apps/web/src/business/components/WorkspaceShell.tsx`、`FilterBar.tsx`、`DataTable.tsx` |
| WFC-PEOPLE-F001-NFR006 | `CONFIRMED` | 可观测 | 每次请求返回 `trace_id`，写入审计行的 `trace_id` 与响应一致 | 本机开发库 | `apps/api/src/hris/core/errors.py:24-38`、`models.py:997` |
| WFC-PEOPLE-F001-NFR007 | `CONFIRMED` | 安全 | 本功能不展示也不写入任何个人敏感字段；写操作要求 `PERSON_EDIT_BASIC` 且必须填写变更原因 | 本机开发库 | §9 权限表、§13 敏感字段条目 |
| WFC-PEOPLE-F001-NFR008 | `CONFIRMED` | 可用性 | 员工档案以 Drawer 承载，关闭后宿主页的筛选与分页状态不丢失 | 本机开发库 | `PeopleWorkspace.tsx:302-315`（宿主页组件未被卸载） |

## 15. 验收场景

### WFC-PEOPLE-F001-AC001 按姓名或工号检索人员

- 类型：正常
- 前置数据：至少 2 个人员档案，其中 1 个的 `employee_number` 为空。
- Given：账号具备 `PERSON_VIEW` + `PERSON_SENSITIVE_VIEW`，进入「人员中心」，在「姓名或工号」输入框输入某个工号片段。
- When：点击「查询」。
- Then：请求为 `GET /api/v1/workforce/persons?limit=200&offset=0&search=<关键词>`；表格只显示命中的人员；工号为空的人员在「工号」列显示「待分配」。
- 数据库/事件/审计证据：无数据写入，无审计行。
- 自动化层级：前端单元测试 + 后端集成测试。

### WFC-PEOPLE-F001-AC002 列表列与排序、空值占位

- 类型：正常 / 边界
- 前置数据：3 个人员，其中 1 个 `status=inactive`。
- Given：进入「人员中心」。
- When：页面加载完成。
- Then：表格含七列「姓名 / 工号 / 主组织 / 职位 / 在职状态 / 入职日期 / 操作」；`status=active` 显示绿色「在职」Tag、`inactive` 显示灰色「停用」Tag；「主组织 / 职位 / 入职日期」三列显示「—」；列表按工号升序（空值在后）再按姓名升序。
- 数据库/事件/审计证据：无数据变化。
- 自动化层级：前端单元测试 + 后端集成测试。

### WFC-PEOPLE-F001-AC003 打开员工档案并看到页签计数

- 类型：正常
- 前置数据：一个员工有 2 条劳动关系、3 条四类主体版本、1 条组织职务、2 条协议关系。
- Given：查看者在列表点击该员工的「查看档案」。
- When：请求 `GET /api/v1/workforce/persons/{id}` 返回。
- Then：Drawer 标题为「{姓名} · {工号}」，副标题为「员工档案 · 人员中心」；页签依次为「基础信息」「敏感与经历档案」「员工标签」「劳动关系 2」「四类主体版本 3」「组织职务 1」「协议关系 2」；「基础信息」页签以两列描述列表展示 10 个字段。
- 数据库/事件/审计证据：无数据写入，无审计行。
- 自动化层级：前端单元测试 + 后端集成测试。

### WFC-PEOPLE-F001-AC004 新建人员档案并预留工号

- 类型：正常
- 前置数据：账号具备 `PERSON_VIEW` + `PERSON_EDIT_BASIC` + `PERSON_SENSITIVE_VIEW`。
- Given：维护者点击「新建人员」，填写法定姓名「测试员工」、变更原因「新员工入职」。
- When：点击「保存」。
- Then：请求为 `POST /api/v1/workforce/persons`，载荷含 `legal_name`、`reserve_employee_number=true`、`change_reason`；服务端返回 201 且 `employee_number` 为 6 位数字；Drawer 打开新员工档案。
- 数据库/事件/审计证据：`persons` 新增一行且工号为 6 位数字；审计中有一条 `action=create`、`object_type=person` 的记录。
- 自动化层级：后端集成测试 + 前端单元测试。

### WFC-PEOPLE-F001-AC005 权限——只读账号可读不可写

- 类型：权限
- 前置数据：账号持有 `PERSON_VIEW` + `PERSON_SENSITIVE_VIEW`，不持有 `PERSON_EDIT_BASIC` 与 `WORKFORCE_ADMIN`。
- Given：该账号访问 `#people`。
- When：页面加载并尝试写操作。
- Then：列表与档案读取成功；页头不渲染「新建人员 / 新建法人」；Drawer 不渲染「更正基础信息」；直接调用 `POST /persons` 或 `PATCH /persons/{id}` 返回 403 `PERMISSION_DENIED`。
- 数据库/事件/审计证据：无数据写入，无审计行。
- 自动化层级：后端集成测试 + 前端单元测试。

### WFC-PEOPLE-F001-AC006 权限——员工标签页签只对有权限者挂载

- 类型：权限
- 前置数据：账号具备 `PERSON_VIEW` + `PERSON_SENSITIVE_VIEW` 但无 `WORKFORCE_ADMIN`。
- Given：该账号打开员工档案。
- When：查看 Drawer 页签。
- Then：页签列表中**没有**「员工标签」；其余页签（劳动关系、四类主体版本、组织职务、协议关系）存在但不渲染新增按钮。
- 数据库/事件/审计证据：无数据变化。
- 自动化层级：前端单元测试。

### WFC-PEOPLE-F001-AC007 审计证据核对——更正基础信息写入更正记录

- 类型：审计
- 前置数据：账号具备 `PERSON_EDIT_BASIC`；员工主档的显示名为「旧名」。
- Given：维护者在 Drawer 点击「更正基础信息」，把显示名改为「新名」，变更原因填「更名」。
- When：点击「保存」。
- Then：请求为 `PATCH /api/v1/workforce/persons/{id}`；重新拉取档案后 `person.display_name` 为「新名」，而 `registered_person.display_name` 仍为「旧名」；`corrections` 中多出一条记录。
- 数据库/事件/审计证据：`audit_logs` 有一条 `action=update`、`object_type=person`、`reason=更名` 的记录。
- 自动化层级：后端集成测试 + 前端单元测试。

### WFC-PEOPLE-F001-AC008 筛选草稿与重置语义

- 类型：正常 / 边界
- 前置数据：至少 3 个人员，其中 2 个 `status=active`、1 个 `status=inactive`。
- Given：查看者在「在职状态」选择「在职」但**不点「查询」**。
- When：观察表格，再点击「查询」，再点击「重置」。
- Then：未点「查询」时表格仍是上一次的结果（草稿式筛选不触发请求）；点「查询」后请求带 `search` 参数且表格只显示 `active` 的人员（在职状态在前端已加载结果上过滤）；点「重置」后筛选清空、页码回到 1、重新拉取全量。
- 数据库/事件/审计证据：无数据变化。
- 自动化层级：前端单元测试。

### WFC-PEOPLE-F001-AC009 画板列在列表接口无数据源时的表现

- 类型：边界
- 前置数据：任意人员数据。
- Given：人员中心列表加载完成。
- When：观察「主组织 / 职位 / 入职日期」三列。
- Then：三列一律显示「—」；页面不显示任何假数据，也不做 N+1 档案拉取去凑这三列。
- 数据库/事件/审计证据：无数据变化；除列表请求外没有额外的档案请求。
- 自动化层级：前端单元测试。

### WFC-PEOPLE-F001-AC010 业务规则拒绝——必填与格式

- 类型：异常 / 规则拒绝
- 前置数据：无。
- Given：维护者提交「新建人员」时不填法定姓名与变更原因；再提交一个 `employee_number` 为 7 位数字的人员。
- When：请求到达服务端。
- Then：前两项返回 422 `REQUEST_VALIDATION_FAILED` 且 `details` 指明字段；第三项同样被拒（工号格式由契约正则与 DB CheckConstraint 双重约束）；`persons` 行数不变。
- 数据库/事件/审计证据：无数据写入，无审计行。
- 自动化层级：后端集成测试。

### WFC-PEOPLE-F001-AC011 后台任务中断与下游失败

- 类型：异常
- 前置数据：无。
- Given：审查本功能的写路径。
- When：检查是否存在异步任务或外部依赖调用。
- Then：不存在——写路径只有数据库写入与审计写入（模块内无 `publish` / `emit` 调用），因此没有任务中断或下游失败场景需要验收。
- 数据库/事件/审计证据：不适用。
- 自动化层级：人工 UAT（代码核对，核对点已记录在 §11.2）。

## 16. 迁移、发布与回滚

- 现有数据影响：本功能管理的 `persons` 与四张档案子表已存在于本机库，本轮无结构变更、无数据迁移。
- 数据迁移与校验：不适用——本功能不提供导入功能；人员数据批量导入属于数据治理模块（`apps/api/src/hris/modules/platform/import_api.py`）。
- 功能开关或模块启用：没有功能开关；入口按 `WORKFORCE_ADMIN` 过滤（`navigation.ts:57`）。
- 发布顺序：后端接口已在库；前端页面随 Web 构建发布。页面依赖 `GET /persons`、`GET /persons/{id}`、`GET /legal-entities`、`GET /jobs`、`GET /organizations/tree` 五个既有接口，发布不改变接口合同。
- 升级兼容：人员主档与更正记录分层保存，主档结构不变，既有消费者（编制、生命周期、考勤）继续按 `persons.id` 引用。
- 应用回滚：前端回滚到上一构建即可，接口未变更；后端回滚不涉及本功能的迁移。
- 数据不可逆时的恢复或前向修复：主档与更正记录只增不删，回滚不会删除数据；误建人员只能追加更正记录前向修正（见 §12 ERR012 与 §18 Q-11）。

## 17. 可观测与运行手册

- 指标：本功能不新增业务指标。现有可观测项：接口调用量与错误码分布（403 / 404 / 409 / 422）、列表查询的 `total` 规模。
- 日志和Trace：每次请求带 `trace_id`（`apps/api/src/hris/core/errors.py:24-38`），审计行 `trace_id` 与之对应；排查具体一次更正时，用 `trace_id` 关联审计记录与请求日志。
- 告警：本功能不定义专属告警；接口 5xx 与事务回滚沿用平台内核既有告警口径。
- 后台任务：无（依据 §11.2）。
- 人工补偿：写入失败时事务自动回滚（`apps/api/src/hris/core/database.py:23-25`），无需人工补偿；业务纠错通过追加更正记录前向修正（§16）。
- 健康检查：页面可用性依赖 `GET /api/v1/workforce/persons` 的可用性（`api.ts:38-42`）。

## 18. 待确认问题

| ID | 问题 | 影响规则/场景 | Owner | 期望日期 | 不确认时的处理 |
|---|---|---|---|---|---|
| WFC-PEOPLE-F001-Q01 | 待确认清单 **P-21**「人员中心列表的『主组织 / 职位 / 入职日期』三列 + 『主组织』筛选」：(a) 后端列表接口补字段（推荐，一致性最好）；(b) 前端删掉这 3 列与主组织筛选，列表只剩「姓名或工号 + 在职状态」 | BR011、BR014、§2.2、AC002、AC009 | 产品决策人 | 2026-10-25 | 采用已实现行为：三列显示「—」，不实现「主组织」筛选；不擅自改模型 |
| WFC-PEOPLE-F001-Q02 | 人员规模上限：前端一次性拉取 `limit=200`，超出部分在页面上不可达且无提示；企业人员规模上限是多少，是否需要服务端分页 | ASM-02、NFR001、ERR013 | 产品决策人 + 企业规模输入方 | 企业 UAT 前 | 采用已实现行为：一次拉取 200 条 + 前端分页 |
| WFC-PEOPLE-F001-Q03 | 待确认清单 **P-22**「『在职状态』用哪个字段定义」：(a) 改用 `employment.status`（劳动关系状态）定义「在职」（推荐）；(b) 保留 `persons.status` 并把列名改成「状态」 | ASM-03、BR015、AC002 | 产品决策人 | 2026-10-25 | 采用已实现行为：沿用 `persons.status`，列名保持「在职状态」，并在 ASM-03 写明该口径不是劳动关系状态 |
| WFC-PEOPLE-F001-Q04 | 「敏感与经历档案」页签（`PersonnelSubrecordsPanel`）的完整功能需求文档尚未建立：证件、联系方式、地址、紧急联系人、教育、工作、家庭成员的脱敏展示与明文查看 | BR017、§2.2、§13 脱敏条目 | 产品决策人 | 2026-10-25 | 保持现状：该页签的功能合同不在本文件内，按 D-087 不为其新增前端结构改动 |
| WFC-PEOPLE-F001-Q05 | 权限发放口径：`PERSON_VIEW` 与 `PERSON_SENSITIVE_VIEW` 必须**同时**持有才能读人员档案（`require_permissions` 是「全部满足」语义），只发 `PERSON_VIEW` 的账号看不到任何人员 | ASM-01、§9 PERM001、AC005 | 产品决策人 | 企业 UAT 前 | 采用已实现行为：两个码都要求；发放时必须同时授予 |
| WFC-PEOPLE-F001-Q06 | 企业侧的正式人员编码规则、完整档案字段清单与国别 / 民族 / 婚姻状况 / 政治面貌码表尚未提供；当前这些字段是自由文本输入 | ASM-05、ASM-06、BR013、BR018 | 产品决策人 + 企业码表提供方 | 企业码表交付时 | 采用已实现行为：自由文本录入；码表到位后需按 §11.3 登记变更 |
| WFC-PEOPLE-F001-Q07 | 待确认清单 **P-03**「人员中心档案入口用 Drawer 还是新标签页」：按 D-068 的升级线（超过 20 字段、超过 3 分组、存在页内标签），员工档案的 7 个页签本应升级为 `NEW_TAB`；当前实现是 Drawer | §10.1 载体与选择理由、BR016、AC003 | 产品决策人 | 2026-10-25 | 采用已实现行为：保持 Drawer，不改载体 |
| WFC-PEOPLE-F001-Q08 | 待确认清单 **P-15**「画板通过后是否即授权前端按画板开发/替换」：是否确认把画板 `JN45s` 的 Review 状态从 `DRAFT_FOR_REVIEW` 改为 `PROTOTYPE_APPROVED`。**2026-10-24 产品决策人已确认全部画板并签字**，§10.4 状态升级为 `PROTOTYPE_APPROVED` | §10.1 原型状态、§10.4 PROT001、§19 T002、AC001–AC011 的页面形态验收 | 产品决策人 | 2026-10-25 | 已关闭：2026-10-24 产品决策人签字确认画板，规范 §10.2 的前端开发门禁解除，本功能可按画板继续开发|
| WFC-PEOPLE-F001-Q09 | 高风险写操作是否需要二次确认：「更正基础信息」（写入不可删除的更正记录）、「登记协议关系」（建立对外协议关系）、「建立劳动关系」当前都没有 Popconfirm | §10.3、ERR003、ERR004 | 产品决策人 | 2026-10-25 | 采用已实现行为：不做二次确认 |
| WFC-PEOPLE-F001-Q10 | 同一人员在同一生效日被两人并发更正时，「当前生效结果」取哪一条；更正记录是否需要显式版本号 | ERR008、BR006 | 产品决策人 | 企业 UAT 前 | 采用已实现行为：由更正服务按生效日期与版本规则决定 |
| WFC-PEOPLE-F001-Q11 | 是否需要「删除 / 作废人员」入口：当前只能追加更正记录，没有删除也没有停用 | ERR012、§8.3 删除、§16 | 产品决策人 | 企业 UAT 前 | 采用已实现行为：不做删除入口，纠错走更正记录 |
| WFC-PEOPLE-F001-Q12 | 待确认清单 **P-16**「`docs/requirements/` 模块功能需求文档」：本文件是本批次的第四份功能文档；是否继续扩展本文件覆盖「敏感与经历档案」页签 | §19 T001 的范围界定、§2.2 | 产品决策人 | 2026-10-25 | 本轮已按默认执行：敏感与经历档案另立功能文档（尚未建立），本文件只覆盖列表与档案主档 |

## 19. 开发任务与追踪

| 任务ID | 目标 | 依赖 | 文件/模块所有权 | 需求追踪注释 | 验收场景 | 状态 | 交付证据 |
|---|---|---|---|---|---|---|---|
| WFC-PEOPLE-F001-T001 | 按《模块功能需求文档规范》建立人员中心与员工档案功能需求文档，登记 Pencil 画板 `JN45s`、字段合同、权限、错误码与验收场景 | 无 | 仅新增 `docs/requirements/WFC-workforce-core/WFC-people/WFC-PEOPLE-F001-person-profile.md` | 文档头部登记规范 17 号；正文引用 D-053 / D-068 / D-090 / D-091 / HR-LABEL-016 / P-03 / P-15 / P-16 / P-21 / P-22 | AC001–AC011 的判定依据 | `IN_REVIEW` | 本文件（v0.1，2026-10-24） |
| WFC-PEOPLE-F001-T002 | 前端按已批准画板 `JN45s` 对齐人员中心宿主页与员工档案 Drawer | WFC-PEOPLE-F001-Q08（画板签字，`PROTOTYPE_APPROVED`） | `apps/web/src/business/features/workforce/PeopleWorkspace.tsx`、`api.ts`、`types.ts`、`apps/web/src/business/components/` | 在规则落点写 `Requirement: WFC-PEOPLE-F001-BRnnn — 原因` | AC001、AC002、AC003、AC008、AC009 | `READY`（2026-10-24 画板已签字，规范 §10.2 的前端开发门禁解除，按画板继续对齐） | — |
| WFC-PEOPLE-F001-T003 | 人员列表补齐「主组织 / 职位 / 入职日期」三列与「主组织」筛选 | WFC-PEOPLE-F001-Q01 | `apps/api/src/hris/modules/workforce/extended_api.py`、`extended_service.py`、`extended_schemas.py`、`apps/web/src/business/features/workforce/PeopleWorkspace.tsx`、`types.ts` | `Requirement: WFC-PEOPLE-F001-BR011 / BR014 — 原因` | AC002、AC009 | `BLOCKED`（阻塞原因：Q01 未拍板，选项 (b) 会删掉画板要求的列，不得由开发者自行选择） | — |
| WFC-PEOPLE-F001-T004 | 为「敏感与经历档案」页签建立独立功能需求文档 | WFC-PEOPLE-F001-Q04 | 仅新增 `docs/requirements/WFC-workforce-core/WFC-people/` 下的新文件 | 文档头部登记规范 17 号 | AC011 的判定依据 | `BLOCKED`（阻塞原因：Q04 未拍板） | — |

## 20. Review与批准记录

| 版本 | 日期 | 变更摘要 | 产品/业务结论 | 技术结论 | 批准人 |
|---|---|---|---|---|---|
| v0.1 | 2026-10-24 | 初稿：按 17 号规范建立人员中心与员工档案功能需求文档；登记 Pencil 画板 `JN45s`（初稿状态 `DRAFT_FOR_REVIEW`）；逐条对齐后端合同（字段、接口、权限码、错误码）与前端实现文案 | 已由产品决策人 Review 并签字，状态升级为 `PROTOTYPE_APPROVED`（Q08） | 字段、接口、权限与错误码全部指向实现文件与行号，未发明后端不存在的字段；画板要求但接口不返回的三列已如实标注为「—」占位 | 已批准（2026-10-24 产品决策人签字） |

现状说明（按事实记录）：

- 2026-10-24 用户已指示「按画板开发或替换已有的界面」，前端据此先行实现了该宿主页与员工档案 Drawer，并已获授权先行实现。
- 画板已于 **2026-10-24** 经产品决策人签字确认，§10.4 的 Review 状态升级为 `PROTOTYPE_APPROVED`。
- 在 Q08 关闭之前，按规范 §10.2 与 D-087，不得为本功能创建新的前端开发任务（T002 状态为 `BLOCKED`）。

### 20.1 规范 §15 文档 Review 检查表自查（2026-10-24）

| # | 检查项 | 自查结论 | 依据 |
|---|---|---|---|
| 1 | 文档是否只描述一个可独立验收的功能 | 是 | 全文只描述「找到员工并维护其档案」一个业务结果；「员工标签」页签因权限判定与失败补偿独立而拆出（§2.2、§3），「敏感与经历档案」页签列为范围外并登记 Q-04 |
| 2 | 是否能明确说出谁在什么条件下得到什么结果 | 是 | §3 参与者表（主管理员 / 人力编制维护者 / 人员档案查看者 / 未登录账号）+ §5 五条用户故事的触发条件、前置条件、主路径、结束状态 |
| 3 | 是否区分确认规则、待确认问题和推荐方案 | 是 | §7 规则表带 `CONFIRMED` / `PENDING` 状态列并写明状态约定；§18 全部为待确认项并给出「不确认时的处理」；本文件未代替产品决策人做结论 |
| 4 | 数据所有者、唯一键、有效日期和历史策略是否明确 | 是 | §8.1 数据所有权、工号唯一性与格式约束、更正记录的分层语义；§8.2 每行含「历史策略」列 |
| 5 | 是否覆盖动作、数据范围、字段和高风险操作 | 是 | §9 PERM001–PERM008 覆盖读 / 更正 / 子表写 / 页签挂载 / 入口可见性 / 字段可写性 / 403 拒绝结果；高风险写操作的二次确认缺口在 §10.3 与 Q-09 显式登记 |
| 6 | 接口是否明确幂等、事务、版本和失败补偿 | 是 | §11.1 十二个接口逐个写明幂等性与单请求单事务边界；§12 覆盖重复、并发、异常与回滚；§11.2 说明无异步事件及依据 |
| 7 | 是否覆盖异常、并发、回退、审计和敏感数据 | 是 | §12 ERR001–ERR013；§13 AUD001–AUD004 及加密、脱敏、明文访问、导出、非生产数据逐项结论；撤销缺口在 ERR012 / Q-11 登记 |
| 8 | NFR是否可以在指定环境中验证 | 部分通过 | NFR001、NFR003–NFR008 可在指定环境验证并给出证据；NFR002（首屏响应时间）因缺容量输入标记 `PENDING`，已在 §14 写明需要的输入文件与验收环境 |
| 9 | 验收场景是否包含明确输入、动作和预期证据 | 是 | §15 AC001–AC011，每条含类型、前置数据、Given / When / Then、数据库或审计证据、自动化层级 |
| 10 | 是否可以在不猜业务规则的情况下拆出最小任务 | 是 | §19 四个任务均声明所有权、依赖、追踪注释与验收场景；三个任务因 Q08 / Q01 / Q04 未决而 `BLOCKED`，未把 PENDING 规则写进任务 |
| 11 | 是否说明对已有数据、模块和部署的影响 | 是 | §16 覆盖现有数据影响、迁移与校验、开关、发布顺序、升级兼容、应用回滚与前向修复；§4 列出下游引用方 |
| 12 | 是否存在与父级PRD或已确认决策冲突的内容 | 是（无冲突） | 组件复用符合 D-091；原型门禁符合 D-087；权限分级符合 D-053；载体按已实现形态登记并把升级线冲突记入 Q-07；画板与实现的三列差异如实登记未美化 |
| 13 | 所有需求驱动的代码变化是否明确了追踪注释所引用的ID和预计代码落点 | 是 | §19 T002、T003 写明 `Requirement: WFC-PEOPLE-F001-BRnnn — 原因` 及预计落点文件；T004 写明文档落点；本轮不产生代码变化 |
| 14 | 涉及前端时，是否明确宿主页、`MODAL`/`DRAWER`/`NEW_TAB`载体及其打开、退出和状态恢复行为 | 是 | §10.1 宿主页=列表、主载体=`DRAWER`、选择理由与升级线冲突、hash 路由 `#people`、Drawer 无深链接、关闭后保留宿主页上下文；§10.3 打开 / 关闭 / 焦点 / 重置策略 |
| 15 | 涉及前端时，是否登记Pencil文件、画板ID、版本和`PROTOTYPE_APPROVED`证据 | 通过 | §10.4 已登记 Pencil 源文件、画板 ID `JN45s`、画板名称、版本 `v1.0` 与状态；`PROTOTYPE_APPROVED` 证据**已存在**（2026-10-24 产品决策人签字确认）；原缺口 Q08 登记 |

自查结论汇总：15 项中 14 项通过，1 项为「部分通过」——第 8 项因缺容量输入把 NFR002 标为 `PENDING`（不是编造）；第 15 项已随 2026-10-24 画板签字补齐 `PROTOTYPE_APPROVED` 证据。按规范 §15 末句「任一关键项为否时，不得进入 `READY_FOR_TASKS`」，本功能当前状态仍保持 `DRAFT`（余下 1 项为第 8 项 NFR002 容量输入待补），画板门禁已不再是阻塞项。
