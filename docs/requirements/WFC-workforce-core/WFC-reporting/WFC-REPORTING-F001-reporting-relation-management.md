# WFC-REPORTING-F001 汇报关系管理

> 模块：WFC / Workforce Core
> 能力域：WFC-REPORTING / 汇报关系维度管理
> 状态：`DRAFT`
> 版本：v0.1
> 产品Owner：MillerMax（产品决策人）
> 业务Owner：产品决策人 MillerMax 兼任（仓库内没有记录企业侧 HR 业务负责人；依据 `docs/01-foundation/03-项目决策.md` D-066「用户负责业务规则、优先级和最终UAT确认」）
> 上级需求：[16-coreHR产品总体PRD](../01-foundation/16-coreHR产品总体PRD.md) §5.3 Workforce Core 职责（人员与组织关系）；[组织管理产品需求输入稿](../input-packs/10-organization-management-product-input.md) §5.10 汇报关系
> 依赖功能：[WFC-POSITION-F001 职位管理](../WFC-workforce-core/WFC-position/WFC-POSITION-F001-position-management.md)（同属人力编制域的职务维度；汇报关系本身不引用职位，但同一宿主页分组内并列）
> 最后更新：2026-10-24

## 1. 背景与期望结果

- 当前问题：后端已经存在生效日期化的汇报关系表（`reporting_relations`，`apps/api/src/hris/modules/workforce/models.py:748-775`）与完整的服务层（`apps/api/src/hris/modules/workforce/reporting_service.py`），前端也已有「组织管理 › 汇报关系」宿主页（`apps/web/src/business/features/organization/ReportingWorkspace.tsx`）。但 2026-10-24 前端按 Pencil 画板 `b5PHy` 对齐落地后，按《模块功能需求文档规范》§10.2 / D-087，缺少功能需求文档登记画板 ID 时前端开发任务没有合法依据，画板状态也无处落档；同时该页面的权限模型此前是「读写同权」（读接口与写接口同为 `WORKFORCE_ADMIN`），只读账号看不到任何汇报关系。
- 用户价值：产品决策人和人力编制维护者可以在一个页面维护员工的上级与下级汇报关系，按生效日期查看当前组织结构；只读角色可以查关系结构但不能改数据；每一条关系变更都留下审计痕迹。
- 本功能完成后可观察的业务结果：
  1. 侧栏「组织管理 › 汇报关系」进入宿主页，按生效日期、上级、下级筛选出关系列表，表格列出「上级 / 下级 / 关系类型 / 生效日期 / 失效日期 / 操作」六列（`ReportingWorkspace.tsx:530-581`）。
  2. 「新增关系」在 Modal 内完成，保存后关系列表出现新行；「结束」为软失效，结束后历史记录保留、不再计入当前结构。
  3. 每次创建与结束在审计日志中留下 `object_type=reporting_relation` 的记录（`reporting_service.py:327-357`）。
  4. 持有 `ORGANIZATION_VIEW` 的只读账号可以打开该页面并查询关系，界面明确提示「当前账号为只读权限，不能新增或结束汇报关系。」（`ReportingWorkspace.tsx:450-456`）。
- 不做本功能的影响：编制月度版本、员工生命周期异动、组织树派生等依赖汇报结构的下游无法解释「谁向谁汇报」；关系数据只能靠直接写库变更，缺少生效日期口径与审计证据。

## 2. 范围

### 2.1 纳入范围

- 汇报关系宿主页：页头、两个页签（关系管理 / 关系图）、扁平筛选栏（生效日期 / 上级 / 下级 / 重置 / 查询）、关系表格与服务端分页（`ReportingWorkspace.tsx:433-611`）。
- 新增汇报关系：Modal 表单「上级 / 下级 / 关系类型 / 生效日期 / 失效日期」五项（`ReportingWorkspace.tsx:613-695`）。
- 结束汇报关系：行内「结束」链接按钮 + Popconfirm 二次确认（`ReportingWorkspace.tsx:566-580`）。
- 关系图页签：按今天的生效日期在前端把关系列表构造成组织树（`ReportingWorkspace.tsx:135-213`、`:586-609`）。
- 读写权限分级：读放宽到 `ORGANIZATION_VIEW`，写保持 `WORKFORCE_ADMIN`（`reporting_api.py:19-26`、`:88-98`）。
- 审计写入、无权限拒绝态、加载失败与空态、本功能的 Pencil 画板登记（见 §10.4）。

### 2.2 不纳入范围

- 汇报关系与职位、组织编制、薪酬的联动校验：当前服务层只校验人员存在性、同类型成环与组合重复（`reporting_service.py:60-105`），不检查上级下级是否同组织、是否存在编制缺口。
- 汇报关系的历史版本链：`reporting_relations` 是「一段生效区间一行」的扁平表，没有 `version` 列（`models.py:748-775`），因此不存在「新增版本」语义。
- 关系图的图形化形态选择（组织树 / 力导向图 / 甘特）：当前实现是 antd `Tree` 组织树（`ReportingWorkspace.tsx:597-603`），形态选择仍待产品拍板，见 §18 Q-04。
- 汇报关系的批量导入与导出：本模块没有任何导出端点，`reporting_api.py` 只定义 1 组 POST + 1 组 GET + 1 组 DELETE。
- 人员中心、操作日志、人员档案 Drawer 等其他工作区的页面需求（各自独立成功能文档）。

### 2.3 假设与约束

| ID | 状态 | 内容 | 假设不成立时的处理 |
|---|---|---|---|
| ASM-01 | `CONFIRMED` | 关系类型只有实线 `direct` 与虚线 `dotted` 两种，其余取值一律 422（`reporting_service.py:16-18`、`:61-66`） | 需要扩展关系类型时必须先改服务层枚举与前端选项（`ReportingWorkspace.tsx:90-93`），不在前端单方面放开 |
| ASM-02 | `CONFIRMED` | 软结束日期取业务时区当天；尚未生效的关系以生效开始日作为结束日，保证 `effective_to >= effective_from`（`reporting_service.py:208-210`） | 若企业要求「结束日期可指定」，需新增字段并走版本变更；当前实现不接受前端指定结束日期 |
| ASM-03 | `CONFIRMED` | 上级与下级的选择依赖 `GET /api/v1/workforce/persons`，该接口要求 `PERSON_VIEW` + `PERSON_SENSITIVE_VIEW`（`apps/api/src/hris/modules/workforce/extended_api.py:61-64`、`:225-246`），与汇报关系本身的读权限是两套 | 只持 `ORGANIZATION_VIEW` 的账号可用列表与关系图，但人员筛选下拉与「新增关系」表单取不到候选项；按 §18 Q-05 处理 |
| ASM-04 | `PENDING` | 企业正式的汇报关系口径（是否允许一人多实线上级、虚线是否计入编制）尚未提供 | 页面按库内现有关系类型与有效期语义展示；口径确认前不做结构性扩展 |
| ASM-05 | `CONFIRMED` | 读权限放宽采用「并集」语义：持有 `ORGANIZATION_VIEW` **或** `WORKFORCE_ADMIN` 任一即可读取（`reporting_api.py:21-26`、`:118` `require_any_permission`） | 若产品要求改为「必须同时持有两者」，需同步调整 `require_any_permission` 的实参并重写只读角色验收 |

## 3. 参与者、权限边界和业务场景

| 参与者 | 目标 | 前置权限 | 数据范围 |
|---|---|---|---|
| 主管理员 | 维护并查看全部汇报关系 | `*`（`apps/api/src/hris/modules/platform/dependencies.py:90` 对 `*` 短路放行） | 全部汇报关系；本模块无行级数据范围 |
| 编制管理员 / SSC 管理员 | 新增、结束汇报关系并查看列表 | `WORKFORCE_ADMIN`（`reporting_api.py:19-20`） | 全部汇报关系；本模块无行级数据范围 |
| 只读组织查看者 | 查看汇报关系列表与关系图 | `ORGANIZATION_VIEW`（`reporting_api.py:21-26`） | 全部汇报关系（只读）；无行级过滤 |
| 未登录 / 会话失效访问者 | —— | 无有效会话 | 401 `AUTHENTICATION_REQUIRED` / `SESSION_INVALID`（`dependencies.py:32`、`:47`） |

场景边界说明：本功能只有一个业务结果——「维护员工之间的汇报关系」。查看与编辑是同一结果的不同参与深度，不拆成两个功能；关系图与关系列表是同一份数据的两种呈现，也不拆。

## 4. 名词与依赖

| 名词/依赖 | 定义或引用 | 数据所有者 |
|---|---|---|
| 汇报关系 | 一条「上级 → 下级」关系及其生效区间，落在 `reporting_relations` 表 | Workforce Core（`apps/api/src/hris/modules/workforce/models.py:748-775`） |
| 实线（direct） | 主要业务管理关系，前端标签为「直属」 | Workforce Core（`reporting_service.py:16`） |
| 虚线（dotted） | 兼岗、项目、专业或协同关系，前端标签为「虚线」 | Workforce Core（`reporting_service.py:17`） |
| 生效区间 | `[effective_from, effective_to)` 左闭右开；`effective_to` 为空表示当前有效 | Workforce Core（`models.py:773-775`、`reporting_service.py:133-141`） |
| 上级 / 下级 | 指向 `persons.id` 的外键；服务层通过 `Person.display_name` 联表补出姓名（`reporting_service.py:150-173`） | Workforce Core |
| 人员档案 | `persons` 表，本功能只读引用 | Workforce Core（`models.py:324-348`） |
| 审计记录 | `audit_logs` 表，`object_type=reporting_relation` | Workforce Core（`models.py:992-1016`） |

## 5. 用户故事

### WFC-REPORTING-F001-US01 按生效日期查看汇报关系

作为编制管理员，我希望按生效日期和上下级人员筛选汇报关系，从而确认某一天的组织汇报结构。

- 触发条件：进入「组织管理 › 汇报关系」，或修改筛选区后点击「查询」。
- 前置条件：账号具备 `ORGANIZATION_VIEW` 或 `WORKFORCE_ADMIN` 或 `*`；后端 `reporting_relations` 已有数据。
- 主路径：页面加载 → 请求 `GET /api/v1/workforce/reporting-relations?page=1&page_size=20`（`ReportingWorkspace.tsx:318-336`）→ 表格按「上级 / 下级 / 关系类型 / 生效日期 / 失效日期 / 操作」展示，关系类型渲染为「直属 / 虚线」双态 Tag，失效日期为空时渲染「长期有效」（`ReportingWorkspace.tsx:543-564`）。
- 结束状态：表格显示该条件下的关系；无数据时显示空态「没有符合条件的汇报关系」（`:521`）；接口 403 时整页替换为「无权查看汇报关系」拒绝态（`:422-431`）。

### WFC-REPORTING-F001-US02 新增汇报关系

作为编制管理员，我希望登记一条上级与下级之间的汇报关系并指定生效区间，从而让组织结构可以被解释。

- 触发条件：在页头点击「新增关系」。
- 前置条件：账号具备 `WORKFORCE_ADMIN` 或 `*`；上级与下级均为已存在的员工档案。
- 主路径：打开 Modal（标题「新增汇报关系」，`ReportingWorkspace.tsx:613-623`）→ 填写「上级」「下级」（远程搜索人员下拉，默认 250ms 防抖，`:97`、`:216-294`）→「关系类型」（默认「直属（实线汇报）」，`:362`）→「生效日期」（默认今天，`:362`）→ 可选「失效日期」→ 点击「保存」→ 提交 `POST /api/v1/workforce/reporting-relations`（`:383-407`）。
- 结束状态：服务端写入关系行与审计行，Modal 关闭，列表刷新；校验失败时 Modal 保留已填内容并在页面顶部显示错误（`:402-404`）。

### WFC-REPORTING-F001-US03 结束汇报关系

作为编制管理员，我希望结束一条已经不适用的汇报关系，从而让它不再计入当前组织结构但保留历史记录。

- 触发条件：在关系表格「操作」列点击「结束」。
- 前置条件：账号具备 `WORKFORCE_ADMIN` 或 `*`；该关系尚未结束。
- 主路径：弹出 Popconfirm「确认结束这条汇报关系？」→「确认结束」→ 提交 `DELETE /api/v1/workforce/reporting-relations/{relation_id}`（`ReportingWorkspace.tsx:566-580`、`:409-420`）。
- 结束状态：服务端把 `effective_to` 置为业务当天并把 `status` 保持原值，列表刷新；已结束的关系再次结束返回 409 `REPORTING_RELATION_ALREADY_ENDED`（`reporting_service.py:201-207`）。

### WFC-REPORTING-F001-US04 以关系图查看当前汇报结构

作为只读查看者，我希望以树形结构看到当前的汇报层级，从而快速理解组织结构而不必逐行读表。

- 触发条件：切换到「关系图」页签。
- 前置条件：账号具备 `ORGANIZATION_VIEW` 或 `WORKFORCE_ADMIN` 或 `*`。
- 主路径：切换页签 → 请求 `GET /api/v1/workforce/reporting-relations?page=1&page_size=200`（`ReportingWorkspace.tsx:338-348`）→ 前端按今天的生效日期过滤、同一「上级|下级|类型」组合只保留生效日期最新的一条，再构造成树（`:121-213`）→ 渲染 antd `Tree`，节点上标注关系类型 Tag（`:597-603`）。
- 结束状态：树形结构展示当前生效关系；无生效关系时显示空态「暂无生效的汇报关系」（`:605`）。

## 6. 业务流程与状态机

```text
汇报关系（reporting_relations 一行 = 一段生效区间）
  新增 ──► 生效中（effective_from ≤ 今天 < effective_to，或 effective_to 为空）
              │ 结束（软失效，effective_to = max(业务当天, effective_from)）
              ▼
           已结束（effective_to 已落值，仍保留在表中）
              │ 再次结束
              ▼
           409 REPORTING_RELATION_ALREADY_ENDED
```

| 当前状态 | 操作 | 条件 | 下一状态 | 失败结果 |
|---|---|---|---|---|
| 关系不存在 | `POST /reporting-relations` | 类型合法、上下级不同、员工存在、区间合法、无环、无重复 | 生效中 | 422 `REPORTING_RELATION_TYPE_INVALID` / `REPORTING_SELF_REFERENCE_INVALID` / `REPORTING_PERSON_NOT_FOUND` / `REPORTING_PERIOD_INVALID` / `REPORTING_CYCLE_DETECTED`；409 `REPORTING_RELATION_DUPLICATE` |
| 生效中 | `DELETE /reporting-relations/{id}` | 关系存在且 `effective_to` 为空 | 已结束 | 404 `REPORTING_RELATION_NOT_FOUND`；409 `REPORTING_RELATION_ALREADY_ENDED` |
| 任意读请求 | `GET /reporting-relations` | 持有 `ORGANIZATION_VIEW` 或 `WORKFORCE_ADMIN` 或 `*` | 返回分页结果 | 403 `PERMISSION_DENIED` |
| 任意写请求 | `POST` / `DELETE` | 持有 `WORKFORCE_ADMIN` 或 `*` | 写入关系行与审计行 | 403 `PERMISSION_DENIED` |

## 7. 业务规则

状态约定：`CONFIRMED` 表示该规则已有已确认决策、已交付能力或服务端强制的合同约束支撑；`PENDING` 表示该规则取决于尚未签字的产品决策，开发者不得自行猜测；`NOT_APPLICABLE` 表示经核查本功能不涉及，并写明依据。

| ID | 状态 | 规则 | 规则来源 | 验证方式 |
|---|---|---|---|---|
| WFC-REPORTING-F001-BR001 | `CONFIRMED` | 关系类型只允许 `direct`（实线 / 直属）与 `dotted`（虚线）；其它取值返回 422 `REPORTING_RELATION_TYPE_INVALID`，不写入任何行 | 实现 `reporting_service.py:16-18`、`:60-66`；前端同规则收敛为两个选项（`ReportingWorkspace.tsx:90-93`） | AC003 |
| WFC-REPORTING-F001-BR002 | `CONFIRMED` | 上级与下级不能是同一个员工；相同则返回 422 `REPORTING_SELF_REFERENCE_INVALID` | 实现 `reporting_service.py:67-76`；DB CheckConstraint `different_people`（`models.py:751-754`）；前端即时校验（`ReportingWorkspace.tsx:641-650`） | AC003 |
| WFC-REPORTING-F001-BR003 | `CONFIRMED` | 上级与下级必须是已存在的人员档案；不存在则返回 422 `REPORTING_PERSON_NOT_FOUND`，并指明是 `manager_person_id` 还是 `subordinate_person_id` 出错 | 实现 `reporting_service.py:77-79`、`:219-229` | AC003 |
| WFC-REPORTING-F001-BR004 | `CONFIRMED` | 失效日期不得早于生效日期；不满足返回 422 `REPORTING_PERIOD_INVALID` | 实现 `reporting_service.py:80-89`；DB CheckConstraint `effective_period_order`（`models.py:755-758`）；前端即时校验（`ReportingWorkspace.tsx:679-688`） | AC003、AC004 |
| WFC-REPORTING-F001-BR005 | `CONFIRMED` | 同类型汇报关系不得成环：环检测只在同类型边之间进行，虚线指向实线上级（虚线实线并存）是合法场景；检测到同类型环返回 422 `REPORTING_CYCLE_DETECTED` | 实现 `reporting_service.py:90-98`、`:231-266` | AC005 |
| WFC-REPORTING-F001-BR006 | `CONFIRMED` | 同一「上级 + 下级 + 类型 + 生效日」组合不得重复；重复返回 409 `REPORTING_RELATION_DUPLICATE` | 实现 `reporting_service.py:99-105`、`:268-289` | AC006 |
| WFC-REPORTING-F001-BR007 | `CONFIRMED` | 读端点按生效日期过滤时使用左闭右开区间：`effective_from <= effective_at` 且（`effective_to` 为空或 `effective_to > effective_at`）；结束日当天不再生效 | 实现 `reporting_service.py:132-141`；前端关系图同口径（`ReportingWorkspace.tsx:112-118`） | AC007 |
| WFC-REPORTING-F001-BR008 | `CONFIRMED` | 软结束保留历史记录，只把结束日期设为业务当天；尚未生效的关系以生效开始日作为结束日期，保证结束日期不早于开始日期；已结束的关系再次结束返回 409 `REPORTING_RELATION_ALREADY_ENDED` | 实现 `reporting_service.py:189-217` | AC008 |
| WFC-REPORTING-F001-BR009 | `CONFIRMED` | 列表按 `effective_from` 倒序、其次 `created_at` 倒序、最后 `id` 升序排列，同一条件下分页稳定 | 实现 `reporting_service.py:165-171` | AC001 |
| WFC-REPORTING-F001-BR010 | `CONFIRMED` | 读端点权限放宽到 `ORGANIZATION_VIEW`，且并集持有 `WORKFORCE_ADMIN` 的角色读取能力不变；写端点（新增、结束）权限一字不放宽，仍要求 `WORKFORCE_ADMIN` | 决策：待确认清单 P-14（方案 b，已决策）；实现 `reporting_api.py:19-26`、`:88-98`、`:114-125` | AC009、AC010、AC011 |
| WFC-REPORTING-F001-BR011 | `CONFIRMED` | 关系类型在页面上用双态 Tag 呈现：直属为蓝色、虚线为紫色，两者一眼可辨，不只依赖颜色（同时输出中文文字） | 实现 `ReportingWorkspace.tsx:79-89`、`:544-552`；D-093；画板 `b5PHy` 规格 `relationTypeTags` | AC001 |
| WFC-REPORTING-F001-BR012 | `PENDING` | 「结束」是否保留 Popconfirm 二次确认：当前实现保留，画板未画该状态 | 现状实现 `ReportingWorkspace.tsx:570-578`；待确认清单 P-01「汇报关系『结束』是否保留二次确认弹窗」 | 见 §18 Q-03 |
| WFC-REPORTING-F001-BR013 | `PENDING` | 关系图的可视化形态：当前实现为 antd `Tree` 组织树；组织树 / 力导向图 / 甘特三选一尚未拍板 | 现状实现 `ReportingWorkspace.tsx:135-213`；待确认清单 P-07 | 见 §18 Q-04 |
| WFC-REPORTING-F001-BR014 | `PENDING` | 生效日期筛选的默认值：画板默认 `2026-10-24`（等于只看当前生效关系），实现保留原「不限日期」默认值 | 现状实现 `ReportingWorkspace.tsx:62-63`、`:370-374`；待确认清单 P-24（推荐保留「不限日期」） | 见 §18 Q-06 |
| WFC-REPORTING-F001-BR015 | `PENDING` | 关系列表是否需要「按当前生效关系过滤」的开关，或直接沿用生效日期筛选表达同一语义 | 现状实现 `ReportingWorkspace.tsx:480-489`；产品语义未确认 | 见 §18 Q-06 |
| WFC-REPORTING-F001-BR016 | `PENDING` | 上级是否允许同时存在多条实线关系（矩阵式管理）：当前服务端不限制，只限制同类型成环 | 现状实现 `reporting_service.py:231-266`；企业口径未提供 | 见 §18 Q-07 |
| WFC-REPORTING-F001-BR017 | `PENDING` | 关系与编制、职位的联动校验：当前新增关系不检查上级下级是否同组织、是否占用编制 | 现状实现 `reporting_service.py:60-105`；组织管理输入稿 §5.10 | 见 §18 Q-08 |

规则写法自查（对照规范 §8.1 / §8.2）：所有 `CONFIRMED` 规则都写明了适用对象与时间点、条件与唯一性维度、成功与拒绝结果、历史记录影响，不使用「合理处理」「一般情况」「尽量」等表述；不包含未说明配置范围的「支持灵活配置」、未说明幂等与最终状态的「失败后重试」、未说明下游与历史保留的「可以回退」。

## 8. 数据要求

### 8.1 数据所有权与关系

- 本功能拥有的数据：
  - `reporting_relations`（汇报关系行，字段 `manager_person_id`、`subordinate_person_id`、`relation_type`、`effective_from`、`effective_to`）。
  - 归属模块：Workforce Core；表定义见 `apps/api/src/hris/modules/workforce/models.py:748-775`。
- 引用但不拥有的数据：人员档案（`persons`，用于校验存在性与联表出姓名）、审计日志（`audit_logs`，写入审计行）。
- 业务唯一键：
  - 服务层的业务唯一性是「上级 + 下级 + 类型 + 生效日」组合（`reporting_service.py:99-105`、`:268-277`）；该组合在数据库层**没有**唯一约束，属于服务层唯一性。
  - `reporting_relations.id` 是稳定身份 UUID（`models.py:761-772` 由 `UuidPrimaryKeyMixin` 提供）。
- 有效日期/版本/快照要求：
  - 生效区间左闭右开，`effective_to` 为空表示当前有效（`reporting_service.py:133-141`）。
  - `effective_to >= effective_from` 由 CheckConstraint `effective_period_order` 兜底（`models.py:755-758`）。
  - 快照：本功能不产生快照数据；下游按目标日期查询当前区间。

### 8.2 字段合同

「来源」列中的文件均位于 `apps/api/src/hris/modules/workforce/reporting_api.py`，行号在括号内注明。

| ID | 字段 | 类型/格式 | 必填 | 来源 | 默认值 | 校验 | 敏感级别 | 历史策略 |
|---|---|---|---|---|---|---|---|---|
| WFC-REPORTING-F001-DAT001 | `manager_person_id` | UUID | 是 | `ReportingRelationCreate.manager_person_id`（:32）、`ReportingRelationResponse.manager_person_id`（:41） | 无 | 必须指向已存在人员，否则 422 `REPORTING_PERSON_NOT_FOUND`；不得等于 `subordinate_person_id` | 非敏感（内部 id） | 行级保存，结束后保留 |
| WFC-REPORTING-F001-DAT002 | `subordinate_person_id` | UUID | 是 | `ReportingRelationCreate.subordinate_person_id`（:33）、`ReportingRelationResponse.subordinate_person_id`（:43） | 无 | 同 DAT001 | 非敏感（内部 id） | 行级保存，结束后保留 |
| WFC-REPORTING-F001-DAT003 | `relation_type` | string(20)，取值 `direct` / `dotted` | 是 | `ReportingRelationCreate.relation_type`（:34）、`ReportingRelationResponse.relation_type`（:44） | 前端默认 `direct`（`ReportingWorkspace.tsx:362`） | 枚举内取值，否则 422 `REPORTING_RELATION_TYPE_INVALID` | 非敏感 | 行级保存；结束后仍保留原类型 |
| WFC-REPORTING-F001-DAT004 | `effective_from` | date（业务日期） | 是 | `ReportingRelationCreate.effective_from`（:35）、`ReportingRelationResponse.effective_from`（:46） | 前端默认今天（`ReportingWorkspace.tsx:362`） | 不得晚于 `effective_to` | 非敏感 | 区间起点，结束后不变 |
| WFC-REPORTING-F001-DAT005 | `effective_to` | date，可空 | 否 | `ReportingRelationCreate.effective_to`（:36）、`ReportingRelationResponse.effective_to`（:47） | 空 = 长期有效；前端留空提示「留空表示长期有效」（`ReportingWorkspace.tsx:677`） | 不得早于 `effective_from` | 非敏感 | 结束时写入业务当天；未生效关系写生效开始日 |
| WFC-REPORTING-F001-DAT006 | `manager_name` | string，可空 | 响应只读 | `ReportingRelationResponse.manager_name`（:42） | — | 由 `persons.display_name` 联表得出，关联不到时为 `null` | 个人信息（姓名） | 不落库，读取时实时联表 |
| WFC-REPORTING-F001-DAT007 | `subordinate_name` | string，可空 | 响应只读 | `ReportingRelationResponse.subordinate_name`（:45） | — | 同 DAT006 | 个人信息（姓名） | 不落库，读取时实时联表 |
| WFC-REPORTING-F001-DAT008 | `id` | UUID | 响应只读 | `ReportingRelationResponse.id`（:40） | — | — | 非敏感 | 稳定身份，结束后不变 |
| WFC-REPORTING-F001-DAT009 | `relation_type`（前端枚举标签） | `"direct"` → 「直属」；`"dotted"` → 「虚线」 | 响应只读 | 前端 `RELATION_TYPE_LABELS`（`ReportingWorkspace.tsx:79-82`） | — | 历史数据中的其它写法在前端按实线处理（`reporting-api.ts:93-97`） | 非敏感 | — |

### 8.3 数据生命周期

- 创建：新增一行 `reporting_relations`，同时写入一条审计行（`reporting_service.py:106-120`、`:327-357`）。
- 修改/更正：本模块没有原地改写端点；更正方式是「结束旧关系 + 新增新关系」两步。
- 生效/失效：新增即生效（按 `effective_from`）；结束是软失效，只写 `effective_to`，行本身不删除（`reporting_service.py:206-211`）。
- 保留：关系行永久保留，本模块没有删除端点；审计日志另表保存（`models.py:992-1016`）。
- 删除：`NOT_APPLICABLE`。依据：本模块只定义 DELETE 语义的「结束」，其实现是写 `effective_to` 而非物理删除（`reporting_service.py:206-211`），全模块无物理删除语句。
- 迁移与兼容：表由第一阶段迁移建立，本轮无结构变更；`relation_type` 的取值集合自第一阶段起未变。

## 9. 权限要求

| ID | 状态 | 参与者 | 功能/动作权限 | 数据范围 | 字段权限 | 拒绝结果 |
|---|---|---|---|---|---|---|
| WFC-REPORTING-F001-PERM001 | `CONFIRMED` | 持有 `ORGANIZATION_VIEW` 或 `WORKFORCE_ADMIN` 或 `*` 的账号 | 查看汇报关系列表（`GET /api/v1/workforce/reporting-relations`） | 全部汇报关系，无行级过滤 | 全部只读字段（DAT001–DAT009） | 403 `PERMISSION_DENIED`「没有执行此操作的权限」（`dependencies.py:118`）；前端整页渲染「无权查看汇报关系」「请联系主管理员分配组织查看权限。」（`ReportingWorkspace.tsx:422-431`） |
| WFC-REPORTING-F001-PERM002 | `CONFIRMED` | 持有 `WORKFORCE_ADMIN` 或 `*` 的账号 | 新增汇报关系（`POST /api/v1/workforce/reporting-relations`） | 全部汇报关系 | 可写 DAT001–DAT005 | 同 PERM001；无权限时「新增关系」按钮置灰（`ReportingWorkspace.tsx:440-444`） |
| WFC-REPORTING-F001-PERM003 | `CONFIRMED` | 持有 `WORKFORCE_ADMIN` 或 `*` 的账号 | 结束汇报关系（`DELETE /api/v1/workforce/reporting-relations/{relation_id}`） | 全部汇报关系 | 可写 DAT005（服务端计算，不由前端指定） | 同 PERM001；无权限时「结束」按钮置灰（`ReportingWorkspace.tsx:577`） |
| WFC-REPORTING-F001-PERM004 | `CONFIRMED` | 只读账号（`ORGANIZATION_VIEW`） | 页面只读态提示 | — | — | 页面顶部显示「当前账号为只读权限，不能新增或结束汇报关系。」（`ReportingWorkspace.tsx:450-456`）；写操作仍由服务端 403 兜底 |
| WFC-REPORTING-F001-PERM005 | `CONFIRMED` | 持有 `WORKFORCE_ADMIN` 或 `*` 的账号 | 侧栏入口可见性：侧栏「组织管理 › 汇报关系」按 `WORKFORCE_ADMIN` 过滤，无权限时不渲染 | — | — | 无权限时侧栏入口不出现（`apps/web/src/business/navigation.ts:51-56`、`AppShell.tsx:184-187` 的 `visibleWorkspaces` 过滤） |
| WFC-REPORTING-F001-PERM006 | `PENDING` | 只持 `ORGANIZATION_VIEW` 的账号 | 侧栏入口是否应当出现：当前侧栏仍按 `WORKFORCE_ADMIN` 过滤，只读账号即使接口已放开也看不到入口 | — | — | 现状：只读账号无法从侧栏进入该页（`navigation.ts:51-56`）；需产品确认后调整前端入口过滤，见 §18 Q-02 |
| WFC-REPORTING-F001-PERM007 | `CONFIRMED` | 未登录或会话失效账号 | 任何接口 | — | — | 401 `AUTHENTICATION_REQUIRED`「需要登录」或 `SESSION_INVALID`「登录状态无效或已过期」（`dependencies.py:32`、`:47`） |
| WFC-REPORTING-F001-PERM008 | `CONFIRMED` | 只持 `ORGANIZATION_VIEW` 的账号 | 人员下拉数据源：上级 / 下级选择调用 `GET /api/v1/workforce/persons`，该接口要求 `PERSON_VIEW` + `PERSON_SENSITIVE_VIEW` | — | — | 该请求 403 时下拉静默退化为「未找到匹配人员」（`ReportingWorkspace.tsx:246-248`）；不影响关系列表与关系图读取 |

代办与代理说明：

- 主管理员（持 `*`）可以直接执行全部写操作，不需要额外审批（`dependencies.py:118` 对 `*` 短路放行）。
- 本功能**没有代办 / 代理身份机制**：审计只记录操作者本人 `actor_id`，没有 `on_behalf_of` 或代理角色字段（`reporting_service.py:327-357`）。
- 未知范围默认拒绝：权限判定为「不具备所需权限码即拒绝」，不做任何隐式放行（`dependencies.py:117-120`）。

## 10. 交互与页面要求

### 10.1 入口与可见性

- 菜单/页面/按钮：
  - 侧栏：「组织管理 › 汇报关系」（`navigation.ts:51-56`、`:79-85`）。
  - 面包屑：「组织管理 / 汇报关系」。
  - 页内操作：页头主按钮「新增关系」（`ReportingWorkspace.tsx:438-446`）；行内「结束」链接按钮（`:566-580`）；筛选栏「重置」「查询」。
  - 页面标题与副标题（宿主页页头，逐字复用实现）：标题「汇报关系」；副标题「维护员工的上级与下级汇报关系；实线表示主要业务管理关系，虚线表示兼岗、项目、专业或协同关系。」（`ReportingWorkspace.tsx:436-437`）。
  - 筛选区文案：标签「生效日期」「上级」「下级」（`:480`、`:490`、`:503`）；上级占位符「全部上级」、下级占位符「全部下级」（`:494`、`:507`）。
- 无权限或未启用模块时：侧栏不渲染该入口（`navigation.ts:51-56`）；直接进入且接口返回 403 时整页替换为 `WorkspaceDenied`，标题「汇报关系」、提示「无权查看汇报关系」、说明「请联系主管理员分配组织查看权限。」（`ReportingWorkspace.tsx:422-431`；`apps/web/src/business/components/WorkspaceShell.tsx` 的 `WorkspaceDenied`）。
- 宿主页：列表。组织管理分组下的独立宿主页，内部以「关系管理 / 关系图」两个页签承载同一宿主页上下文（`ReportingWorkspace.tsx:457-611`）。
- 交互载体：`MODAL`。新增汇报关系使用 Modal；结束关系使用行内 Popconfirm（确认气泡，不构成独立载体）。
- 选择理由：新增关系是单任务、5 个字段、无页内标签、无多步骤、无并行参照需求，落在 [Ant Design 页面与交互载体规范](../design/antd-page-interaction-standard.md) §3 的 `MODAL` 默认边界内；不满足 `DRAWER`（无需保留宿主页预览并对照表格）与 `NEW_TAB`（字段数与分组数均远低于升级线）的升级条件。载体为已实现形态，选择理由在此登记以便评审复核。
- 路由或深链接：宿主页为 hash 路由 `#reporting`（`navigation.ts:126-132` 的 `workspaceFromHash` 统一处理）；Modal 不占用独立路由，关闭后回到宿主页并保留筛选、分页与页签状态（宿主页组件未被卸载）。
- Pencil源文件：`C:\Users\83289\Documents\HRMS\coreHR.pen`（Pencil 2.17）。
- 画板ID/名称/原型版本：`b5PHy` / 「汇报关系 · 组织管理 v1.0」 / `v1.0`（画板 1440×960）。
- 原型状态：`PROTOTYPE_APPROVED`。2026-10-24 产品决策人确认全部画板并签字，规范 §10.1 的状态枚举中对应 `PROTOTYPE_APPROVED`；按规范 §10.2 与 D-087，前端开发门禁已解除，本功能可按画板继续开发（见 §19 T002 状态与 §18 Q-01）。

### 10.2 页面状态

| 状态 | 页面表现 | 可执行操作 |
|---|---|---|
| 首次/空数据 | 表格空态「没有符合条件的汇报关系」（`ReportingWorkspace.tsx:521`），由 `DataTable` 的 `emptyText` 承载；关系图页签空态「暂无生效的汇报关系」（`:605`），由 `EmptyState` 承载 | 调整筛选、切换页签；有权限时可「新增关系」 |
| 加载中 | 关系表格 `loading` 态（`ReportingWorkspace.tsx:519`）；关系图显示「关系图加载中…」（`:595`） | 等待；可切换页签 |
| 正常 | 筛选栏 + 表格 + 分页器，分页文案「共 N 条汇报关系」（`:527`）；关系图为展开的树 | 筛选、查询、翻页、新增、结束 |
| 部分失败 | 关系图加载失败时页面顶部显示可关闭的错误条「汇报关系图加载失败」（`:344`），关系列表仍可用 | 关闭错误条、切换页签重试 |
| 完全失败 | 列表接口返回 403 时整页替换为「无权查看汇报关系」拒绝态（`:331`、`:422-431`）；其它错误表现为顶部错误条「汇报关系加载失败」（`:332`） | 关闭错误条或联系管理员 |
| 无权限 | 同上；侧栏入口同时不可见 | 退出登录或联系主管理员 |

### 10.3 表单与确认

- 字段顺序与联动：
  - 「上级」→ 「下级」→ 「关系类型」→ 「生效日期」→ 「失效日期」（`ReportingWorkspace.tsx:625-693`）。
  - 联动：「下级」依赖「上级」做同一人校验（`:637-651`）；「失效日期」依赖「生效日期」做先后校验（`:674-690`）。
  - 表单每次打开都是空白表单，默认「关系类型 = 直属」「生效日期 = 今天」（`:358-363`）。
- 即时校验与提交校验：前端 antd Form 规则（必填提示如「请选择上级」「请选择下级」「请选择关系类型」「请选择生效日期」；同一人提示「上级和下级不能是同一人」；区间提示「失效日期不能早于生效日期」）；后端 pydantic 校验失败返回 422 `REQUEST_VALIDATION_FAILED`，逐字段 `details` 返回（`apps/api/src/hris/core/errors.py:41-61`）。
- 高风险二次确认：**结束关系**有 Popconfirm 二次确认，标题「确认结束这条汇报关系？」、描述「结束后保留历史记录，不再计入当前汇报结构。」、确认按钮「确认结束」（`ReportingWorkspace.tsx:570-576`）。**新增关系**没有二次确认（单条新增、可通过结束纠错）。
- 成功反馈与下一步：新增成功后关闭 Modal 并刷新列表（`ReportingWorkspace.tsx:400-401`）；结束后刷新列表（`:414`）；失败时页面顶部显示错误条，Modal 保留已填内容（`:402-404`）。
- 打开、关闭和焦点返回：Modal 使用 `destroyOnHidden`（`:616`），关闭即销毁表单；antd 默认在打开后把焦点移入容器、关闭后焦点回到触发元素。
- 未保存变更与重复提交保护：未保存变更**不拦截**关闭（当前实现没有脏检查）；保存期间 `confirmLoading={saving}` 使「保存」按钮进入加载态，阻止重复提交（`:618`、`:392`、`:406`）。
- 弹窗关闭后表单重置或保留策略：关闭即销毁，下次打开时由 `form.resetFields()` + `form.setFieldsValue(...)` 重新写入初始值（`:358-363`），不保留上一条记录的输入。

### 10.4 Pencil原型登记

| 原型ID | 页面/交互载体 | Pencil文件 | 画板ID与名称 | 版本 | 状态 | 批准人/日期 |
|---|---|---|---|---|---|---|
| WFC-REPORTING-F001-PROT001 | `MODAL`（宿主页「汇报关系 · 组织管理 v1.0」含关系管理与关系图两个页签，画板 `b5PHy` 1440×960；新增关系 Modal 与结束关系 Popconfirm 尚未单独出画板） | `C:\Users\83289\Documents\HRMS\coreHR.pen` | 画板ID `b5PHy`；画板名称「汇报关系 · 组织管理 v1.0」 | v1.0 | `PROTOTYPE_APPROVED` | 2026-10-24 产品决策人签字确认（见 §18 Q-01 / §20） |

登记说明（按事实记录，不做美化）：

- 画板状态 `PROTOTYPE_APPROVED`（2026-10-24 产品决策人签字确认）依据 `docs/review/pen-prototype-spec-2026-10-24.md` 头部状态标注与 §7 后续动作第 3 条；预览图为 `docs/review/pen-prototypes/02-汇报关系.png`。
- 画板与实现的有意差异已登记在画板登记表 `implementationDeltas`：第 1 条「『结束』保留 Popconfirm 二次确认（画板未画该状态）」对应 BR012 / Q-03；第 2 条「上级/下级为远程搜索 PersonSelect，画板用下拉形态示意」对应 §10.3 的远程搜索说明。
- 画板登记表另记录了该画板 2026-10-24 的三处修订（关系类型 Tag 文字移入标签内部、筛选区补「下级」并纠正「上级」占位文案、总数由「共 4 条」改为「共 2 条」），`.pen` 源文件与预览图已同步更新。
- 规范 §10.4 要求「显著不同的加载、空数据、失败、无权限和冲突状态应在原型中可Review」，这些状态目前只存在于实现（`ReportingWorkspace.tsx:513-543`），没有对应的 Pencil 画板——见 §18 Q-01。

## 11. API与事件合同

### 11.1 同步API

| ID | 方法与路径 | 调用者 | 请求摘要 | 响应摘要 | 权限 | 幂等 | 事务边界 |
|---|---|---|---|---|---|---|---|
| WFC-REPORTING-F001-API001 | `GET /api/v1/workforce/reporting-relations`（`reporting_api.py:88-111`） | 汇报关系宿主页（列表与关系图） | 查询参数：`effective_at`（date，可选）、`manager_person_id`（UUID，可选）、`subordinate_person_id`（UUID，可选）、`page`（≥1，缺省 1）、`page_size`（1–200，缺省 20；关系图传 200） | `ReportingRelationPage`：`items`（`ReportingRelationResponse` 列表）、`total`、`page`、`page_size` | `ORGANIZATION_VIEW` 或 `WORKFORCE_ADMIN`（并集）；`*` 放行 | 天然幂等（只读） | 单请求单事务，`get_db` 在响应前提交（`apps/api/src/hris/core/database.py:18-25`） |
| WFC-REPORTING-F001-API002 | `POST /api/v1/workforce/reporting-relations`（`reporting_api.py:67-85`，201） | 汇报关系宿主页「新增关系」 | `ReportingRelationCreate`：`manager_person_id`、`subordinate_person_id`、`relation_type`、`effective_from`、`effective_to?` | `ReportingRelationResponse`（201） | `WORKFORCE_ADMIN`；`*` 放行 | 不幂等：同组合第二次调用返回 409 `REPORTING_RELATION_DUPLICATE`，不产生第二条记录 | 单请求单事务；关系行与审计行同事务提交或同事务回滚 |
| WFC-REPORTING-F001-API003 | `DELETE /api/v1/workforce/reporting-relations/{relation_id}`（`reporting_api.py:114-125`，204） | 汇报关系宿主页「结束」 | 路径参数 `relation_id`（UUID） | 空响应体（204） | `WORKFORCE_ADMIN`；`*` 放行 | 幂等边界：第一次调用生效并写审计；第二次返回 409 `REPORTING_RELATION_ALREADY_ENDED` | 单请求单事务；结束日期写入与审计行同事务 |
| WFC-REPORTING-F001-API004 | `GET /api/v1/workforce/persons`（`apps/api/src/hris/modules/workforce/extended_api.py:225-246`） | 上级 / 下级下拉与筛选 | 查询参数：`search`（可选，≤200）、`limit`（1–200，前端传 200）、`offset`（≥0，前端传 0） | `PageResponse`：`items`（`PersonResponse` 列表）、`total`、`limit`、`offset` | `PERSON_VIEW` + `PERSON_SENSITIVE_VIEW` | 天然幂等 | 单请求单事务 |

调用者与所有权说明：上述前三接口由 Workforce Core 模块提供（`apps/api/src/hris/modules/workforce/`）；第四接口是同模块的人员档案查询，只被本功能作为下拉数据源引用，本功能不写入人员数据。前端调用封装在 `apps/web/src/business/features/organization/reporting-api.ts:145-180`，认证统一使用 Bearer Token（`apps/web/src/business/client.ts`）。

### 11.2 异步事件与任务

`NOT_APPLICABLE`。依据：本功能的所有写路径（`reporting_service.py:51-120`、`:189-217`）只做数据库写入与审计写入，模块内没有消息发布或领域事件调用（`apps/api/src/hris/modules/workforce/reporting_service.py` 全文件检索 `publish` / `emit` 无命中）；关系数据的下游消费由引用方在自己的事务内按生效日期查询完成，不存在本功能发出的异步消息。若后续引入消息引擎（待确认清单 P-10～P-12），本功能是否需要发布「汇报关系生效」事件需重新评审并补写本节。

### 11.3 兼容与废弃

- 当前合同版本：v1。接口路径与响应字段自第一阶段汇报关系交付以来未变。
- 向后兼容策略：`relation_type` 的取值集合不变；`effective_to` 语义（空 = 长期有效）不变。
- 废弃通知和截止版本：当前无废弃项。若后续要新增关系类型（如「项目汇报」），必须先在本节登记取值集合变更并同步 `docs/01-foundation/03-项目决策.md`，不得在前端单方面放开（规范 §13 变更控制）。

## 12. 异常、并发与回退

| ID | 状态 | 场景 | 系统结果 | 用户提示/错误码 | 是否重试 | 补偿/回退 |
|---|---|---|---|---|---|---|
| WFC-REPORTING-F001-ERR001 | `CONFIRMED` | 关系类型取值非法 | 拒绝，不写入任何行 | 422 `REPORTING_RELATION_TYPE_INVALID`「汇报关系类型只支持 direct（直属）或 dotted（虚线）」（`reporting_service.py:61-66`） | 否——需改类型 | 不适用 |
| WFC-REPORTING-F001-ERR002 | `CONFIRMED` | 上级与下级为同一人 | 拒绝 | 422 `REPORTING_SELF_REFERENCE_INVALID`「上级与下级不能为同一人」（`reporting_service.py:68-76`） | 否 | 不适用 |
| WFC-REPORTING-F001-ERR003 | `CONFIRMED` | 上级或下级人员不存在 | 拒绝，`details` 指明出错字段 | 422 `REPORTING_PERSON_NOT_FOUND`「上级或下级员工不存在」（`reporting_service.py:221-229`） | 否 | 不适用 |
| WFC-REPORTING-F001-ERR004 | `CONFIRMED` | 结束日期早于开始日期 | 拒绝 | 422 `REPORTING_PERIOD_INVALID`「结束日期不能早于开始日期」（`reporting_service.py:81-89`） | 否 | 不适用 |
| WFC-REPORTING-F001-ERR005 | `CONFIRMED` | 同类型汇报关系成环 | 拒绝 | 422 `REPORTING_CYCLE_DETECTED`「汇报关系不能形成循环」（`reporting_service.py:257-262`） | 否 | 不适用 |
| WFC-REPORTING-F001-ERR006 | `CONFIRMED` | 重复提交同一「上级+下级+类型+生效日」 | 拒绝，不产生第二条记录 | 409 `REPORTING_RELATION_DUPLICATE`「相同的汇报关系在同一天已存在」（`reporting_service.py:283-289`） | 否——需改组合或生效日 | 不适用 |
| WFC-REPORTING-F001-ERR007 | `CONFIRMED` | 结束一条不存在的关系 | 拒绝 | 404 `REPORTING_RELATION_NOT_FOUND`「汇报关系不存在」（`reporting_service.py:193-198`） | 否 | 不适用 |
| WFC-REPORTING-F001-ERR008 | `CONFIRMED` | 结束一条已结束的关系 | 拒绝，`effective_to` 不变 | 409 `REPORTING_RELATION_ALREADY_ENDED`「汇报关系已结束」（`reporting_service.py:201-207`） | 否 | 不适用 |
| WFC-REPORTING-F001-ERR009 | `CONFIRMED` | 请求体不满足 schema | 请求被拒 | 422 `REQUEST_VALIDATION_FAILED`「请求参数校验失败」，`details` 逐字段给出（`apps/api/src/hris/core/errors.py:41-61`） | 否 | 不适用 |
| WFC-REPORTING-F001-ERR010 | `CONFIRMED` | 无权限访问或写入 | 请求被拒 | 403 `PERMISSION_DENIED`「没有执行此操作的权限」（`dependencies.py:119`） | 否 | 不适用 |
| WFC-REPORTING-F001-ERR011 | `CONFIRMED` | 会话无效或过期 | 请求被拒 | 401 `AUTHENTICATION_REQUIRED` / `SESSION_INVALID`（`dependencies.py:32`、`:47`） | 重新登录后重试 | 不适用 |
| WFC-REPORTING-F001-ERR012 | `CONFIRMED` | 两人同时结束同一条关系 | 服务端对关系行加行锁（`with_for_update`，`reporting_service.py:190-192`），两个请求串行执行；后到者看到 `effective_to` 已落值，返回 409 `REPORTING_RELATION_ALREADY_ENDED` | 前端展示后端 message（`ReportingWorkspace.tsx:416`） | 视错误码：409 需刷新列表后重试 | 无需补偿：失败的请求未写入任何行 |
| WFC-REPORTING-F001-ERR013 | `CONFIRMED` | 两人同时新增会形成环的关系 | 环检测按「查询当前生效边」执行（`reporting_service.py:231-266`），后写入的一方若基于已提交数据检测到环则返回 422 `REPORTING_CYCLE_DETECTED`；若两侧各自检测时都看不到对方未提交的边，则可能形成环——服务端未对关系表加表级锁 | 前端展示后端 message | 是——需改组合后重试 | 事后可用「结束 + 重建」修正；并发成环的口径见 §18 Q-07 |
| WFC-REPORTING-F001-ERR014 | `CONFIRMED` | 写入过程中数据库异常 | 整个请求事务回滚，关系行与审计行都不落库 | 前端展示「汇报关系保存失败」（`ReportingWorkspace.tsx:403`） | 可在修复原因后重试 | 自动回滚（`apps/api/src/hris/core/database.py:23-25`） |
| WFC-REPORTING-F001-ERR015 | `CONFIRMED` | 后台任务中断 | `NOT_APPLICABLE`：本功能没有后台任务（依据 §11.2） | — | — | — |
| WFC-REPORTING-F001-ERR016 | `CONFIRMED` | 下游系统失败 | `NOT_APPLICABLE`：本功能不调用外部系统（依据 §11.2） | — | — | — |
| WFC-REPORTING-F001-ERR017 | `PENDING` | 误建关系后的撤销 | 当前没有撤销入口：只能「结束旧关系 + 新增新关系」两步完成，结束日期取业务当天，无法恢复到历史日期 | 现状无对应提示 | — | 建议路径是结束 + 重建；是否提供「按指定日期撤销」见 §18 Q-09 |

## 13. 审计与数据保护

| ID | 状态 | 动作 | 审计内容 | 禁止记录内容 | 保留要求 |
|---|---|---|---|---|---|
| WFC-REPORTING-F001-AUD001 | `CONFIRMED` | 创建汇报关系 | `action=create`、`object_type=reporting_relation`、`object_id=关系 id`、`reason=创建汇报关系`、`after_payload={manager_person_id, subordinate_person_id, relation_type, effective_from, effective_to}`、`actor_id`、`trace_id`、`source=api`（`reporting_service.py:115-119`、`:327-357`） | 不记录上下级人员姓名等个人信息，只记录 person id | 审计行随 `audit_logs` 表保留，无删除入口 |
| WFC-REPORTING-F001-AUD002 | `CONFIRMED` | 结束汇报关系 | `action=end`、`object_type=reporting_relation`、`object_id=关系 id`、`reason=结束汇报关系`、`after_payload` 同上（`effective_to` 为结束后的日期）（`reporting_service.py:212-216`、`:327-357`） | 同上 | 同上 |
| WFC-REPORTING-F001-AUD003 | `CONFIRMED` | 审计记录读取 | 审计查询接口 `GET /api/v1/platform/audit-logs` 要求 `DATA_GOVERNANCE_ADMIN`，读取不降级为 VIEW（`apps/api/src/hris/modules/platform/audit_api.py:23-27`） | 审计导出不含 `before_payload` / `after_payload`（`apps/api/src/hris/modules/platform/audit_service.py:19-29`） | 按审计模块既有保留策略执行 |

- 敏感字段加密：`NOT_APPLICABLE`。依据：本功能写入的表 `reporting_relations` 没有任何个人敏感列（`models.py:748-775`），字段集合仅为两个人员 id、关系类型与生效区间；人员姓名的加密要求属于 `docs/01-foundation/07-人员档案领域规范.md`。
- 页面脱敏：`NOT_APPLICABLE`。依据同上：页面展示的列只有关系类型、日期与人员姓名（姓名来自人员档案本身的显示名，不是敏感字段）。
- 明文访问：`NOT_APPLICABLE`。依据：本功能不存在「明文才能读取」的字段（区别于人员档案的敏感字段）。
- 导出与临时文件：`NOT_APPLICABLE`。依据：本模块没有导出端点（`reporting_api.py` 只定义 1 组 POST + 1 组 GET + 1 组 DELETE），页面也没有导出入口（`reporting-api.ts:145-180` 无下载调用）。
- 非生产数据：验收使用合成数据；现有自动化测试即采用合成 fixture（`apps/api/tests/integration/test_reporting_relations_api.py:53-64` 的 `_seed_people`）。

## 14. 非功能需求

| ID | 状态 | 类别 | 可验证要求 | 环境/数据量 | 验证证据 |
|---|---|---|---|---|---|
| WFC-REPORTING-F001-NFR001 | `CONFIRMED` | 性能 | 关系列表采用服务端分页，单页固定 20 条且 `showSizeChanger=false`；关系图按后端上限单次拉取 200 条 | 本机开发库；数据量由企业组织规模决定 | 前端 `ReportingWorkspace.tsx:94-96`、`:522-529`、`:341`；后端 `reporting_api.py:97` |
| WFC-REPORTING-F001-NFR002 | `PENDING` | 性能 | 页面首屏（关系列表 + 人员下拉候选）的响应时间目标 | 需要容量输入：本机并发用户数、汇报关系条数、人员档案条数 | 缺容量输入，暂不可验收；输入模板见 `docs/input-packs/templates/07-capacity-scenarios.csv`，容量场景见 `docs/input-packs/09-nonfunctional-acceptance-input.md` |
| WFC-REPORTING-F001-NFR003 | `CONFIRMED` | 可用性 / 可访问性 | 筛选区日期控件具备 `aria-label="按生效日期筛选"`，上级 / 下拉具备 `aria-label="按上级筛选"` / `aria-label="按下级筛选"`；关系图具备 `aria-label="汇报关系图"`；表格行键为 `id`；关系类型不只依赖颜色，同时输出「直属 / 虚线」文字 | 键盘与屏幕阅读器人工检查 | `ReportingWorkspace.tsx:482`、`:492`、`:505`、`:518`、`:598`；规范 §7 状态不只依赖颜色的要求 |
| WFC-REPORTING-F001-NFR004 | `CONFIRMED` | 兼容 | 页面使用仓库锁定的 Ant Design 6.5.2 组件，不使用已废弃属性 | 生产构建 `npm run build` | D-090；`docs/design/antd-page-interaction-standard.md` §2；`node scripts/check-antd-usage.mjs` 0 违规 |
| WFC-REPORTING-F001-NFR005 | `CONFIRMED` | 复用 | 页面骨架、筛选栏、表格与空态统一使用 `WorkspaceShell`、`FilterBar`、`DataTable`、`EmptyState`，不在本能力域内出现第二套写法 | 全站一致性 | D-091；`apps/web/src/business/components/WorkspaceShell.tsx`、`FilterBar.tsx`、`DataTable.tsx`、`EmptyState.tsx` |
| WFC-REPORTING-F001-NFR006 | `CONFIRMED` | 可观测 | 每次请求返回 `trace_id`，写入审计行的 `trace_id` 与响应一致，可用于按请求串起页面操作与审计记录 | 本机开发库 | `apps/api/src/hris/core/errors.py:24-38`、`reporting_service.py:327-357`、`models.py:997` |
| WFC-REPORTING-F001-NFR007 | `CONFIRMED` | 安全 | 页面不展示也不提交任何个人敏感数据；写操作受 `WORKFORCE_ADMIN` 约束，读操作放宽到 `ORGANIZATION_VIEW` | 本机开发库 | §9 权限表、§13 敏感字段条目 |
| WFC-REPORTING-F001-NFR008 | `CONFIRMED` | 性能 | 人员下拉为远程搜索，输入防抖 250ms，避免每次按键都打后端 | 本机开发库 | `ReportingWorkspace.tsx:97`、`:284-290` |

## 15. 验收场景

### WFC-REPORTING-F001-AC001 按生效日期查看汇报关系

- 类型：正常
- 前置数据：至少 1 条 `direct` 关系（上级 A、下级 B、`effective_from=2026-01-01`、`effective_to` 为空）。
- Given：账号具备 `ORGANIZATION_VIEW`，进入「组织管理 › 汇报关系」。
- When：页面加载完成。
- Then：请求为 `GET /api/v1/workforce/reporting-relations?page=1&page_size=20`；表格出现该关系，列「上级 / 下级 / 关系类型 / 生效日期 / 失效日期 / 操作」齐全；关系类型显示蓝色「直属」Tag；失效日期渲染为「长期有效」。
- 数据库/事件/审计证据：`reporting_relations` 中该行被返回；本次为只读操作，不产生审计行。
- 自动化层级：前端单元测试 + 后端集成测试。

### WFC-REPORTING-F001-AC002 关系图按今天生效日期呈现当前结构

- 类型：正常
- 前置数据：3 条关系，其中 1 条 `effective_to` 为昨天（已结束），2 条当前生效。
- Given：账号具备 `ORGANIZATION_VIEW`，切换到「关系图」页签。
- When：页面加载完成。
- Then：请求为 `GET /api/v1/workforce/reporting-relations?page=1&page_size=200`；树中只出现当前生效的关系，已结束的关系不出现在树里；同一「上级|下级|类型」的多段有效期只保留生效日期最新的一条。
- 数据库/事件/审计证据：无数据变化，无审计行。
- 自动化层级：前端单元测试。

### WFC-REPORTING-F001-AC003 业务规则拒绝——非法类型、同一人、人员不存在、区间非法

- 类型：异常 / 规则拒绝
- 前置数据：2 个已存在的人员档案。
- Given：维护者提交 `relation_type=indirect`；再提交上下级相同的关系；再提交不存在的人员 id；再提交 `effective_to < effective_from` 的关系。
- When：依次提交 `POST /api/v1/workforce/reporting-relations`。
- Then：分别返回 422 `REPORTING_RELATION_TYPE_INVALID`、422 `REPORTING_SELF_REFERENCE_INVALID`、422 `REPORTING_PERSON_NOT_FOUND`、422 `REPORTING_PERIOD_INVALID`；`reporting_relations` 行数不变。
- 数据库/事件/审计证据：`select count(*) from reporting_relations` 与调用前一致，无审计行写入。
- 自动化层级：后端集成测试。

### WFC-REPORTING-F001-AC004 边界——失效日期等于生效日期

- 类型：边界
- 前置数据：2 个已存在的人员档案。
- Given：维护者提交 `effective_from = effective_to = 今天` 的关系。
- When：提交。
- Then：返回 201；该关系在 `effective_at = 今天` 的查询中**不出现**（区间左闭右开，结束日当天不再生效）。
- 数据库/事件/审计证据：`reporting_relations` 新增一行，`effective_from = effective_to = 今天`；审计中有一条 `action=create`、`object_type=reporting_relation` 记录。
- 自动化层级：后端集成测试。

### WFC-REPORTING-F001-AC005 规则拒绝——同类型成环与虚线指向实线上级

- 类型：异常 / 规则拒绝
- 前置数据：3 个已存在的人员档案；已存在 A→B（direct）。
- Given：维护者提交 B→A（direct）；再提交 B→C（dotted）；再提交 C→A（dotted）。
- When：依次提交。
- Then：第一次返回 422 `REPORTING_CYCLE_DETECTED`；第二次返回 201（虚线指向实线上级是合法的矩阵汇报）；第三次返回 422 `REPORTING_CYCLE_DETECTED`（虚线自身成环）。
- 数据库/事件/审计证据：只有第二条关系落库；审计中只有一条 `action=create` 记录。
- 自动化层级：后端集成测试。

### WFC-REPORTING-F001-AC006 重复请求——同一组合重复新增

- 类型：幂等
- 前置数据：已存在一条「上级 A、下级 B、direct、生效日今天」的关系。
- Given：维护者再次提交完全相同的组合。
- When：请求到达服务端。
- Then：返回 409 `REPORTING_RELATION_DUPLICATE`；`reporting_relations` 行数不变。
- 数据库/事件/审计证据：该组合仍只有 1 行；审计中只有 1 条 `action=create` 记录。
- 自动化层级：后端集成测试。

### WFC-REPORTING-F001-AC007 生效时点查询——生效日前、生效日与历史时点

- 类型：边界
- 前置数据：关系 1 `effective_from=2026-01-01`、`effective_to=2026-06-30`；关系 2 `effective_from=2026-07-01`、`effective_to` 为空。
- Given：依次以 `2026-06-30`、`2026-07-01` 两个生效日期查询。
- When：调用 `GET /api/v1/workforce/reporting-relations?effective_at=...`。
- Then：`2026-06-30` 返回关系 1；`2026-07-01` 返回关系 2；不带 `effective_at` 时两条都返回。
- 数据库/事件/审计证据：两次查询的返回体 `items[0].id` 分别为关系 1 与关系 2。
- 自动化层级：后端集成测试。

### WFC-REPORTING-F001-AC008 结束关系——软失效与重复结束

- 类型：正常 / 异常
- 前置数据：已存在一条当前生效的关系。
- Given：维护者点击「结束」并在 Popconfirm 中确认；随后再次点击结束。
- When：请求依次到达服务端。
- Then：第一次返回 204，`effective_to` 变为业务当天；第二次返回 409 `REPORTING_RELATION_ALREADY_ENDED`；对不存在的 id 返回 404 `REPORTING_RELATION_NOT_FOUND`。
- 数据库/事件/审计证据：关系行仍在表中，`effective_to = 今天`；审计中有一条 `action=end` 记录。
- 自动化层级：后端集成测试 + 前端单元测试。

### WFC-REPORTING-F001-AC009 权限——只读角色可读不可写

- 类型：权限
- 前置数据：账号只持有 `ORGANIZATION_VIEW`，不持有 `WORKFORCE_ADMIN` 与 `*`。
- Given：该账号进入「组织管理 › 汇报关系」并直接调用接口。
- When：分别调用 GET、POST、DELETE。
- Then：GET 返回 200 并返回关系列表；POST 返回 403 `PERMISSION_DENIED`；DELETE 返回 403 `PERMISSION_DENIED`；页面上「新增关系」与「结束」按钮为禁用态，并显示「当前账号为只读权限，不能新增或结束汇报关系。」。
- 数据库/事件/审计证据：无数据写入，无审计行。
- 自动化层级：后端集成测试 + 前端单元测试。

### WFC-REPORTING-F001-AC010 权限——编制管理员读写皆可（放宽不放宽写）

- 类型：权限
- 前置数据：账号只持有 `WORKFORCE_ADMIN`，不持有 `ORGANIZATION_VIEW` 与 `*`。
- Given：该账号调用 GET、POST、DELETE。
- When：依次调用。
- Then：GET 返回 200（读权限放宽是并集语义，不能反过来收窄既有角色）；POST 返回 201；DELETE 返回 204。
- 数据库/事件/审计证据：关系行与审计行正常写入。
- 自动化层级：后端集成测试。

### WFC-REPORTING-F001-AC011 权限——无任何组织权限

- 类型：权限
- 前置数据：账号不持有 `ORGANIZATION_VIEW`、`WORKFORCE_ADMIN`、`*`。
- Given：该账号调用 `GET /api/v1/workforce/reporting-relations`。
- When：请求到达服务端。
- Then：返回 403 `PERMISSION_DENIED`；页面上渲染「无权查看汇报关系」拒绝态。
- 数据库/事件/审计证据：无数据变化，无审计行。
- 自动化层级：后端集成测试。

### WFC-REPORTING-F001-AC012 审计证据核对

- 类型：审计
- 前置数据：维护者具备 `WORKFORCE_ADMIN`。
- Given：其为 A→B 新增一条 direct 关系，随后结束该关系。
- When：两次操作都成功。
- Then：`audit_logs` 出现两行 `object_type=reporting_relation`、`object_id=<关系 id>` 的记录，`action` 分别为 `create` 与 `end`，`after_payload` 含 `manager_person_id`、`subordinate_person_id`、`relation_type`、`effective_from`、`effective_to`；两行 `trace_id` 与对应响应一致。
- 数据库/事件/审计证据：`audit_logs` 查询结果；页面错误条为空。
- 自动化层级：后端集成测试 + 人工 UAT（审计页核对）。

### WFC-REPORTING-F001-AC013 后台任务中断与下游失败

- 类型：异常
- 前置数据：无。
- Given：审查本功能的写路径。
- When：检查是否存在异步任务或外部依赖调用。
- Then：不存在——写路径只有数据库写入与审计写入（`reporting_service.py:51-120`、`:189-217`，模块内无 `publish` / `emit` 调用），因此没有任务中断或下游失败场景需要验收。
- 数据库/事件/审计证据：不适用。
- 自动化层级：人工 UAT（代码核对，核对点已记录在 §11.2）。

## 16. 迁移、发布与回滚

- 现有数据影响：本功能管理的 `reporting_relations` 表已存在于本机库，本轮无结构变更、无数据迁移。
- 数据迁移与校验：不适用——本功能不提供导入功能；关系数据只能通过页面新增与结束产生。
- 功能开关或模块启用：没有功能开关；入口按 `WORKFORCE_ADMIN` 权限显隐（`navigation.ts:51-56`）。
- 发布顺序：后端接口已在库；前端页面随 Web 构建发布。读权限放宽后端先发布、前端后发布不会造成中间态不一致（前端在放宽前就会 403，放宽后自动恢复）。
- 升级兼容：`relation_type` 取值集合与生效区间语义不变，既有消费者不受影响。
- 应用回滚：前端回滚到上一构建即可，接口未变更；后端回滚不涉及本功能的迁移。
- 数据不可逆时的恢复或前向修复：关系行只增不删（结束也是写 `effective_to`），回滚不会删除数据；若误建关系，只能「结束 + 重建」前向修正（见 §12 ERR017 与 §18 Q-09）。

## 17. 可观测与运行手册

- 指标：本功能不新增业务指标。现有可观测项：接口调用量与错误码分布（403 / 404 / 409 / 422）、列表查询的 `total` 规模。
- 日志和Trace：每次请求带 `trace_id`（`apps/api/src/hris/core/errors.py:24-38`），审计行 `trace_id` 与之对应（`reporting_service.py:327-357`）；排查具体一次关系变更时，用 `trace_id` 关联审计记录与请求日志。
- 告警：本功能不定义专属告警；接口 5xx 与事务回滚沿用平台内核既有告警口径。
- 后台任务：无（依据 §11.2）。
- 人工补偿：写入失败时事务自动回滚（`apps/api/src/hris/core/database.py:23-25`），无需人工补偿；业务纠错通过「结束 + 重建」前向修正（§16）。
- 健康检查：页面可用性依赖 `GET /api/v1/workforce/reporting-relations` 的可用性（`reporting-api.ts:146-155`）。

## 18. 待确认问题

| ID | 问题 | 影响规则/场景 | Owner | 期望日期 | 不确认时的处理 |
|---|---|---|---|---|---|
| WFC-REPORTING-F001-Q01 | 待确认清单 **P-15**「画板通过后是否即授权前端按画板开发/替换」：是否确认把画板 `b5PHy` 的 Review 状态从 `DRAFT_FOR_REVIEW` 改为 `PROTOTYPE_APPROVED`。**2026-10-24 产品决策人已确认全部画板并签字**，§10.4 状态升级为 `PROTOTYPE_APPROVED` | §10.1 原型状态、§10.4 PROT001、§19 T002、AC001–AC013 的页面形态验收 | 产品决策人 | 2026-10-25 | 已关闭：2026-10-24 产品决策人签字确认画板，规范 §10.2 的前端开发门禁解除，本功能可按画板继续开发|
| WFC-REPORTING-F001-Q02 | 只读角色的侧栏入口：读接口已放宽到 `ORGANIZATION_VIEW`，但侧栏「组织管理 › 汇报关系」仍按 `WORKFORCE_ADMIN` 过滤，只读账号看不到入口。是把入口过滤改为「`ORGANIZATION_VIEW` 或 `WORKFORCE_ADMIN` 任一可见」，还是维持现状（只读角色只能通过直接 hash 路由进入） | §9 PERM005、PERM006、AC009、AC011 | 产品决策人 | 2026-10-25 | 采用已实现行为：侧栏入口仍按 `WORKFORCE_ADMIN` 过滤；本轮不修改 `apps/web/src/business/navigation.ts`（不在本功能所有权范围） |
| WFC-REPORTING-F001-Q03 | 待确认清单 **P-01**「汇报关系『结束』是否保留二次确认弹窗」：当前实现保留 Popconfirm，画板未画该状态 | BR012、§10.3、AC008 | 产品决策人 | 2026-10-25 | 采用已实现行为：保留 Popconfirm 二次确认 |
| WFC-REPORTING-F001-Q04 | 待确认清单 **P-07**「汇报关系『关系图』Tab 的可视化形态」：当前实现是 antd `Tree` 组织树 | BR013、§10.1、AC002 | 产品决策人 | 2026-10-25 | 采用已实现行为：antd `Tree` 组织树，不引入图形库 |
| WFC-REPORTING-F001-Q05 | 只读角色的「上级 / 下级」人员下拉：数据源 `GET /api/v1/workforce/persons` 要求 `PERSON_VIEW` + `PERSON_SENSITIVE_VIEW`，只持 `ORGANIZATION_VIEW` 的账号取不到候选项（下拉静默显示「未找到匹配人员」）。是否给汇报关系页单独开一个只返回 id 与显示名的人员候选端点 | §9 PERM008、ASM-03、AC009 | 产品决策人 | 2026-10-25 | 采用已实现行为：只读账号的关系列表与关系图可用，人员下拉不可用；不做新的候选端点 |
| WFC-REPORTING-F001-Q06 | 待确认清单 **P-24**「汇报关系『生效日期』默认值」：画板默认 `2026-10-24`（只看当前生效关系），实现保留原「不限日期」默认值；同时确认「关系列表是否需要单独的『只看当前生效』开关」 | BR014、BR015、AC001、AC007 | 产品决策人 | 2026-10-25 | 采用已实现行为：生效日期默认不限，不新增「只看当前生效」开关 |
| WFC-REPORTING-F001-Q07 | 汇报关系的企业口径：一人是否允许多条实线上级（矩阵式管理）、虚线是否计入编制、并发新增是否需要表级锁防成环 | BR016、ERR013、§18 Q-08 | 产品决策人 + 企业口径提供方 | 企业 UAT 前 | 采用已实现行为：只限制同类型成环，虚线指向实线上级放行，不加表级锁 |
| WFC-REPORTING-F001-Q08 | 关系与编制、职位的联动校验：当前新增关系不检查上级下级是否同组织、是否占用编制 | BR017 | 产品决策人 | 企业 UAT 前 | 采用已实现行为：不做联动校验 |
| WFC-REPORTING-F001-Q09 | 是否需要「撤销」入口：当前只能「结束 + 重建」，结束日期取业务当天，无法恢复到历史日期 | ERR017、§16 | 产品决策人 | 企业 UAT 前 | 采用已实现行为：不做撤销入口，纠错走结束 + 重建 |
| WFC-REPORTING-F001-Q10 | 待确认清单 **P-16**「`docs/requirements/` 模块功能需求文档」：本文件是继职位管理之后的第二份功能文档；是否继续为操作日志、人员中心、员工档案 Drawer、批量新增标签 Modal 建立同规范文档 | §19 T001 的范围界定 | 产品决策人 | 2026-10-25 | 本轮已按默认执行：同批次建立其余 4 份同规范文档（`PLT-AUDIT-F001`、`WFC-PEOPLE-F001`、`WFC-LABEL-F001`、`WFC-LABEL-F002`），登记在 `docs/01-foundation/00-正式文档目录.md` §1.4 |

## 19. 开发任务与追踪

| 任务ID | 目标 | 依赖 | 文件/模块所有权 | 需求追踪注释 | 验收场景 | 状态 | 交付证据 |
|---|---|---|---|---|---|---|---|
| WFC-REPORTING-F001-T001 | 按《模块功能需求文档规范》建立汇报关系功能需求文档，登记 Pencil 画板 `b5PHy`、字段合同、权限、错误码与验收场景 | 无 | 仅新增 `docs/requirements/WFC-workforce-core/WFC-reporting/WFC-REPORTING-F001-reporting-relation-management.md` | 文档头部登记规范 17 号；正文引用 ORG-REPORT-001～009 / P-14 / D-090 / D-091 / D-093 / D-068 / D-069 | AC001–AC013 的判定依据 | `IN_REVIEW` | 本文件（v0.1，2026-10-24） |
| WFC-REPORTING-F001-T002 | 前端按已批准画板 `b5PHy` 对齐汇报关系宿主页与新增关系 Modal | WFC-REPORTING-F001-Q01（画板签字，`PROTOTYPE_APPROVED`） | `apps/web/src/business/features/organization/ReportingWorkspace.tsx`、`reporting-api.ts`、`apps/web/src/business/components/` | 在规则落点写 `Requirement: WFC-REPORTING-F001-BRnnn — 原因` | AC001、AC002、AC003、AC008、AC009 | `READY`（2026-10-24 画板已签字，规范 §10.2 的前端开发门禁解除，按画板继续对齐） | — |
| WFC-REPORTING-F001-T003 | 汇报关系读权限放宽到 `ORGANIZATION_VIEW`（并集语义），写权限保持 `WORKFORCE_ADMIN` | 待确认清单 P-14（已决策，方案 b） | `apps/api/src/hris/modules/workforce/reporting_api.py`、`apps/api/src/hris/modules/platform/dependencies.py`、`apps/api/tests/integration/test_reporting_relations_api.py` | `Requirement: P-14 — 读端点放宽到 ORGANIZATION_VIEW，写端点不放宽`（`reporting_api.py:19-26`） | AC009、AC010、AC011 | `DELIVERED` | 本轮提交：后端集成测试 3 条新用例通过（只读可读不可写、编制管理员读写皆可、无权限 403） |
| WFC-REPORTING-F001-T004 | 只读角色的侧栏入口可见性改为「`ORGANIZATION_VIEW` 或 `WORKFORCE_ADMIN` 任一可见」 | WFC-REPORTING-F001-Q02 | `apps/web/src/business/navigation.ts` | `Requirement: WFC-REPORTING-F001-PERM006 — 原因` | AC009 | `BLOCKED`（阻塞原因：Q02 未拍板，且 `navigation.ts` 不在本功能所有权范围） | — |

## 20. Review与批准记录

| 版本 | 日期 | 变更摘要 | 产品/业务结论 | 技术结论 | 批准人 |
|---|---|---|---|---|---|
| v0.1 | 2026-10-24 | 初稿：按 17 号规范建立汇报关系功能需求文档；登记 Pencil 画板 `b5PHy`（初稿状态 `DRAFT_FOR_REVIEW`）；逐条对齐后端合同（字段、接口、权限码、错误码）与前端实现文案 | 已由产品决策人 Review 并签字，状态升级为 `PROTOTYPE_APPROVED`（Q01） | 字段、接口、权限与错误码全部指向实现文件与行号，未发明后端不存在的字段；读权限放宽按 P-14 采用并集语义（`ORGANIZATION_VIEW` 或 `WORKFORCE_ADMIN`），写权限未放宽 | 已批准（2026-10-24 产品决策人签字） |

现状说明（按事实记录）：

- 2026-10-24 用户已指示「按画板开发或替换已有的界面」，前端据此先行实现了该宿主页，并已获授权先行实现。
- 画板已于 **2026-10-24** 经产品决策人签字确认，§10.4 的 Review 状态升级为 `PROTOTYPE_APPROVED`。
- 在 Q01 关闭之前，按规范 §10.2 与 D-087，不得为本功能创建新的前端开发任务（T002 状态为 `BLOCKED`）。

### 20.1 规范 §15 文档 Review 检查表自查（2026-10-24）

| # | 检查项 | 自查结论 | 依据 |
|---|---|---|---|
| 1 | 文档是否只描述一个可独立验收的功能 | 是 | 全文只描述「维护员工之间的汇报关系」一个业务结果；关系列表与关系图是同一份数据的两种呈现，在 §3 给出不拆分理由 |
| 2 | 是否能明确说出谁在什么条件下得到什么结果 | 是 | §3 参与者表（主管理员 / 编制管理员 / 只读组织查看者 / 未登录账号）+ §5 四条用户故事的触发条件、前置条件、主路径、结束状态 |
| 3 | 是否区分确认规则、待确认问题和推荐方案 | 是 | §7 规则表带 `CONFIRMED` / `PENDING` 状态列并写明状态约定；§18 全部为待确认项并给出「不确认时的处理」；本文件未代替产品决策人做结论 |
| 4 | 数据所有者、唯一键、有效日期和历史策略是否明确 | 是 | §8.1 数据所有权、业务唯一性（服务层组合唯一）、生效区间口径与 DB 约束；§8.2 每行含「历史策略」列 |
| 5 | 权限是否覆盖动作、数据范围、字段和高风险操作 | 是 | §9 PERM001–PERM008 覆盖读、写、入口可见性、字段可写性、只读提示态、403 拒绝结果与代办说明；只读账号的侧栏入口缺口在 PERM006 / Q02 显式登记 |
| 6 | 接口是否明确幂等、事务、版本和失败补偿 | 是 | §11.1 四个接口逐个写明幂等性与单请求单事务边界；§12 覆盖重复、并发、异常与回滚；§11.2 说明无异步事件及依据 |
| 7 | 是否覆盖异常、并发、回退、审计和敏感数据 | 是 | §12 ERR001–ERR017；§13 AUD001–AUD003 及敏感字段、页面脱敏、明文访问、导出、非生产数据逐项结论；撤销缺口在 ERR017 / Q09 登记 |
| 8 | NFR是否可以在指定环境中验证 | 部分通过 | NFR001、NFR003–NFR008 可在指定环境验证并给出证据；NFR002（首屏响应时间）因缺容量输入标记 `PENDING`，已在 §14 写明需要的输入文件与验收环境 |
| 9 | 验收场景是否包含明确输入、动作和预期证据 | 是 | §15 AC001–AC013，每条含类型、前置数据、Given / When / Then、数据库或审计证据、自动化层级 |
| 10 | 是否可以在不猜业务规则的情况下拆出最小任务 | 是 | §19 四个任务均声明所有权、依赖、追踪注释与验收场景；两个任务因 Q01 / Q02 未决而 `BLOCKED`，未把 PENDING 规则写进任务 |
| 11 | 是否说明对已有数据、模块和部署的影响 | 是 | §16 覆盖现有数据影响、迁移与校验、开关、发布顺序、升级兼容、应用回滚与前向修复；§4 列出引用方 |
| 12 | 是否存在与父级PRD或已确认决策冲突的内容 | 是（无冲突） | 载体选择符合 D-068/D-069 与交互载体规范 §3；组件复用符合 D-091；双态 Tag 符合 D-093；原型门禁符合 D-087；读权限放宽符合待确认清单 P-14 已决策的方案 b |
| 13 | 所有需求驱动的代码变化是否明确了追踪注释所引用的ID和预计代码落点 | 是 | §19 T003 写明 `Requirement: P-14 — 读端点放宽到 ORGANIZATION_VIEW，写端点不放宽` 及实际落点 `reporting_api.py:19-26`、`:88-98`、`:114-125` 与 `dependencies.py:101-122`；T002/T004 写明待建的追踪注释格式 |
| 14 | 涉及前端时，是否明确宿主页、`MODAL`/`DRAWER`/`NEW_TAB`载体及其打开、退出和状态恢复行为 | 是 | §10.1 宿主页=列表、主载体=`MODAL`、选择理由与升级条件、hash 路由 `#reporting`、Modal 无独立路由且关闭后保留宿主页上下文；§10.3 打开 / 关闭 / 焦点 / 重置策略 |
| 15 | 涉及前端时，是否登记Pencil文件、画板ID、版本和`PROTOTYPE_APPROVED`证据 | 通过 | §10.4 已登记 Pencil 源文件、画板 ID `b5PHy`、画板名称、版本 `v1.0` 与状态；`PROTOTYPE_APPROVED` 证据**已存在**（2026-10-24 产品决策人签字确认）；原缺口 Q01 登记 |

自查结论汇总：15 项中 14 项通过，1 项为「部分通过」——第 8 项因缺容量输入把 NFR002 标为 `PENDING`（不是编造）；第 15 项已随 2026-10-24 画板签字补齐 `PROTOTYPE_APPROVED` 证据。按规范 §15 末句「任一关键项为否时，不得进入 `READY_FOR_TASKS`」，本功能当前状态仍保持 `DRAFT`（余下 1 项为第 8 项 NFR002 容量输入待补），画板门禁已不再是阻塞项。
