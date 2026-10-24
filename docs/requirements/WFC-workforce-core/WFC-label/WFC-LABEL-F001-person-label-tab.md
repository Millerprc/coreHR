# WFC-LABEL-F001 员工标签页签

> 模块：WFC / Workforce Core
> 能力域：WFC-LABEL / 员工标签管理
> 状态：`DRAFT`
> 版本：v0.1
> 产品Owner：MillerMax（产品决策人）
> 业务Owner：产品决策人 MillerMax 兼任（仓库内没有记录企业侧 HR 业务负责人；依据 `docs/01-foundation/03-项目决策.md` D-066）
> 上级需求：[16-coreHR产品总体PRD](../01-foundation/16-coreHR产品总体PRD.md) §5.3 Workforce Core 职责（人员档案扩展属性）；[07-人员档案领域规范](../01-foundation/07-人员档案领域规范.md)
> 依赖功能：[WFC-PEOPLE-F001 人员中心与员工档案](../WFC-workforce-core/WFC-people/WFC-PEOPLE-F001-person-profile.md)（宿主 Drawer 与宿主页）；[WFC-LABEL-F002 批量新增标签 Modal](../WFC-workforce-core/WFC-label/WFC-LABEL-F002-batch-label-create-modal.md)（本页签内的写入口，独立成功能文档）
> 最后更新：2026-10-24

## 1. 背景与期望结果

- 当前问题：后端已经存在员工标签的数据面（`person_labels` 表，`apps/api/src/hris/modules/workforce/models.py:351-379`）、标签服务（`labels_service.py`）与标签库读取（`label_library.py`，标签库复用基础资料字典而非新建表），前端也已有员工标签面板（`apps/web/src/business/features/people/PersonLabelPanel.tsx`），挂在员工档案 Drawer 的「员工标签」页签内。2026-10-24 前端按 Pencil 画板 `BUE0c` 对齐落地后，按《模块功能需求文档文档规范》§10.2 / D-087，缺少功能需求文档登记画板 ID 时前端开发任务没有合法依据，画板状态也无处落档。
- 用户价值：HR 维护者可以在员工档案内按标签类型分组查看该员工的有效标签，看清每个标签的来源（人工标记 / AI 生成）、有效期与有效性，并在标签失效时软结束它。
- 本功能完成后可观察的业务结果：
  1. 员工档案 Drawer 的「员工标签」页签显示工具条「共 N 个标签」与「新增标签」按钮（`PersonLabelPanel.tsx:267-271`）。
  2. 标签按类型分组渲染，每组一个标题（画板示例为「技能」「关键岗位」「培养对象」），每个标签两行结构：上行是标签本体 Tag（人工=蓝、AI=紫并带 🤖），下行是「来源 · 有效期 · 有效性」与「结束」操作（`PersonLabelPanel.tsx:203-241`）。
  3. 结束标签是软失效：记录保留、结束日期记为业务当天，页面上该标签不再显示「结束」按钮（`PersonLabelPanel.tsx:227`、`:390-404`）。
  4. 每次结束在审计日志中留下 `object_type=person_label` 的记录（`labels_service.py:409-415`）。
- 不做本功能的影响：员工的能力、关键岗位、培养身份只能靠散落在各处的备注维护；标签失效没有统一口径，历史标签与当前标签无法区分。

## 2. 范围

### 2.1 纳入范围

- 员工标签页签的读取与展示：工具条计数与「新增标签」按钮、按标签类型分组的标签列表、两行标签结构、来源与有效期文案、有效性文案（`PersonLabelPanel.tsx:264-272`、`:243-262`、`:203-241`）。
- 标签类型清单与标签库读取：页签加载时并行取「本人标签」「标签类型清单」「标签库」（`PersonLabelPanel.tsx:56-81`）。
- 结束标签：行内「结束」链接按钮 + Popconfirm 二次确认（`PersonLabelPanel.tsx:227-237`）。
- 无权限时的页签挂载规则（`PeopleWorkspace.tsx:339-347`）。
- 本功能的 Pencil 画板登记（见 §10.4）。

### 2.2 不纳入范围

- 批量新增标签的 Modal：独立成 [WFC-LABEL-F002 批量新增标签 Modal](../WFC-workforce-core/WFC-label/WFC-LABEL-F002-batch-label-create-modal.md)。
- 单条新增标签的 API（`POST /persons/{person_id}/labels`）：契约与端点已存在，但页面上没有入口（`PersonLabelPanel.tsx:175-179` 只调用批量接口），本功能不描述该入口。
- 标签库本身的维护（新增标签类型、扩展标签项、停用）：标签库是基础资料字典，运维走「基础资料」工作区，本功能只读（`label_library.py:34-38`）。
- 独立的「标签库管理」页面：待确认清单 P-04「员工标签是否需要独立『标签库管理』页面」，见 §18 Q-05。
- 标签的「恢复」入口：标签结束后不可恢复，见 §18 Q-04。
- AI 标签的生成与推荐：当前 AI 标签只由来源字段标识（`is_ai_generated` 由 `source == "AI"` 推导，`labels_service.py:194-195`），没有生成链路。

### 2.3 假设与约束

| ID | 状态 | 内容 | 假设不成立时的处理 |
|---|---|---|---|
| ASM-01 | `CONFIRMED` | 标签的读写在后端都要求 `WORKFORCE_ADMIN`，因此页签只对具备该权限的用户挂载（`labels_api.py:29`、`PeopleWorkspace.tsx:339-347`） | 若要放开只读角色，需要新增只读标签权限码并同步页签挂载规则（不得新增未落库的权限码，见 §18 Q-06） |
| ASM-02 | `CONFIRMED` | 标签库是基础资料字典 `PERSON_LABEL_LIBRARY` 的第 0 级（标签类型）与第 1 级（标签项），不新建独立表；只返回启用中的类型与启用中的标签项（`label_library.py:11-13`、`:65-76`） | 若要独立建表，必须先在 ADR 与领域规范中登记，且本功能的字段合同要整体重做 |
| ASM-03 | `CONFIRMED` | 「标签类型」没有独立字典表，类型名称沿用类型编码（`labels_service.py:375-377`） | 企业提供类型名称表后需同步本功能的字段合同 |
| ASM-04 | `CONFIRMED` | 页签加载时三个请求用 `Promise.allSettled` 并行发起：标签列表失败显示错误条，标签类型清单失败退回显示编码，标签库失败退化为空（`PersonLabelPanel.tsx:59-79`） | 标签库失败会让「新增标签」无候选（见 WFC-LABEL-F002），但不影响标签展示 |
| ASM-05 | `PENDING` | 企业侧的标签体系（类型清单、标签项、命名规范、AI 标签的生成规则）尚未提供 | 页面按库内现有标签库展示；企业标签体系补齐前不做结构性扩展，见 §18 Q-07 |

## 3. 参与者、权限边界和业务场景

| 参与者 | 目标 | 前置权限 | 数据范围 |
|---|---|---|---|
| 主管理员 | 查看与结束员工标签 | `*`（`apps/api/src/hris/modules/platform/dependencies.py:90` 对 `*` 短路放行） | 全部员工标签；本模块无行级数据范围 |
| 人力编制维护者 / 编制管理员 / SSC 管理员 | 查看与结束员工标签 | `WORKFORCE_ADMIN`（`labels_api.py:29`） | 全部员工标签；本模块无行级数据范围 |
| 人员档案查看者（无 `WORKFORCE_ADMIN`） | 查看人员档案 | `PERSON_VIEW` + `PERSON_SENSITIVE_VIEW` | **看不到**「员工标签」页签（页签不挂载） |
| 未登录 / 会话失效访问者 | —— | 无有效会话 | 401 `AUTHENTICATION_REQUIRED` / `SESSION_INVALID`（`dependencies.py:32`、`:47`） |

场景边界说明：本功能只描述「查看与结束员工标签」。新增标签是另一个动作（批量、整批原子、失败补偿规则不同），按规范 §2.2 拆成独立功能文档 WFC-LABEL-F002。

## 4. 名词与依赖

| 名词/依赖 | 定义或引用 | 数据所有者 |
|---|---|---|
| 员工标签 | `person_labels` 表的一行：某个人员在某标签类型下的某个标签，带生效区间、来源与状态 | Workforce Core（`apps/api/src/hris/modules/workforce/models.py:351-379`） |
| 标签类型 | 标签的分组维度（如「技能」「关键岗位」「培养对象」），落在标签库字典的第 0 级 | Platform Kernel 基础资料字典（`label_library.py:11-13`） |
| 标签库 | 字典 `PERSON_LABEL_LIBRARY`：第 0 级为标签类型，第 1 级为该类型下的标签项 | Platform Kernel（`apps/api/src/hris/modules/platform/models.py:105-137` 的 `DataDictionary` / `DataDictionaryItem`） |
| 来源（source） | `MANUAL`（人工标记）或 `AI`（AI 生成）；`is_ai_generated` 由来源推导，调用方不能直接指定 | Workforce Core（`labels_service.py:17-19`、`:194-195`） |
| 有效性 | 由生效区间决定：`effective_to` 为空表示当前有效；页面上显示为「当前有效」或「已结束」 | Workforce Core（`PersonLabelPanel.tsx:208-211`） |
| 人员档案 | `persons` 表，标签必须挂在已存在的人员档案上 | Workforce Core（`models.py:324-348`） |
| 审计记录 | `audit_logs` 表，`object_type=person_label` | Workforce Core（`models.py:992-1016`） |

## 5. 用户故事

### WFC-LABEL-F001-US01 在员工档案中查看标签

作为人力编制维护者，我希望在员工档案里按类型分组查看该员工的有效标签，从而快速判断这个人的能力与培养状态。

- 触发条件：在人员中心打开某个员工的「员工标签」页签。
- 前置条件：账号具备 `WORKFORCE_ADMIN` 或 `*`；该员工已有标签。
- 主路径：切换页签 → 并行请求 `GET /api/v1/workforce/persons/{person_id}/labels`、`GET /api/v1/workforce/label-types`、`GET /api/v1/workforce/label-library`（`PersonLabelPanel.tsx:56-81`）→ 工具条显示「共 N 个标签」→ 标签按类型分组渲染，每组一个 `Divider` 标题，组内按标签顺序列出（`PersonLabelPanel.tsx:115-125`、`:250-260`）。
- 结束状态：展示该员工当前有效的标签；无标签时显示空态「暂无标签」（`PersonLabelPanel.tsx:246-248`）；标签列表加载失败时显示错误条而不是空态（`:247`）。

### WFC-LABEL-F001-US02 看清每个标签的来源与有效期

作为人力编制维护者，我希望每个标签都显示来源、有效期和当前有效性，从而区分人工标记与 AI 生成，并知道标签何时生效、何时失效。

- 触发条件：查看标签列表中的任意一个标签。
- 前置条件：标签已加载。
- 主路径：渲染两行结构——上行是标签本体 Tag（人工=蓝 `blue`、AI=紫 `purple` 且带 🤖 前缀），Tag 的 Tooltip 写明「标签类型：{类型} · 来源：{来源} · 有效期：{起} 至 {止 ?? 当前有效}」（`PersonLabelPanel.tsx:203-221`）；下行是「人工标记 / AI 生成」、「{起} 至 {止}」或「{起} 起」、「当前有效 / 已结束」三段文本（`PersonLabelPanel.tsx:208-211`、`:223-226`）。
- 结束状态：标签的来源、有效期与有效性一眼可辨；已结束的标签不再显示「结束」按钮（`:227`）。

### WFC-LABEL-F001-US03 结束一个标签

作为人力编制维护者，我希望结束一个不再适用的标签，从而让它不再计入当前有效标签，同时保留历史记录。

- 触发条件：点击标签行右侧的「结束」链接按钮。
- 前置条件：账号具备 `WORKFORCE_ADMIN` 或 `*`；该标签当前有效（`effective_to` 为空）。
- 主路径：点击「结束」→ 弹出 Popconfirm「结束标签「{标签名}」」，描述「结束为软失效：标签记录保留，仅不再生效，可由管理员重新维护。」→「确认结束」→ 提交 `DELETE /api/v1/workforce/person-labels/{label_id}`（`PersonLabelPanel.tsx:227-237`、`:190-201`）。
- 结束状态：服务端把结束日期置为业务当天并把状态置为 `ended`，页签重新加载，该标签不再出现在有效标签列表中；重复结束返回 409 `PERSON_LABEL_ALREADY_ENDED`（`labels_service.py:391-397`）。

## 6. 业务流程与状态机

```text
员工标签（person_labels 一行 = 一段生效区间）
  创建（见 WFC-LABEL-F002）──► 生效中（status=active，effective_to 为空）
              │ 结束（软失效）
              ▼
           已结束（status=ended，effective_to = 业务当天，记录保留）
              │ 再次结束
              ▼
           409 PERSON_LABEL_ALREADY_ENDED

标签库（基础资料字典 PERSON_LABEL_LIBRARY）
  第 0 级 = 标签类型（type_code / type_name）
  第 1 级 = 标签项（code / name，父级指向类型）
  只有启用中的类型与启用中的标签项可被赋予；标签项改名不影响历史标签的展示
```

| 当前状态 | 操作 | 条件 | 下一状态 | 失败结果 |
|---|---|---|---|---|
| 标签生效中 | `DELETE /person-labels/{id}` | 标签存在、`effective_to` 为空、已生效 | 已结束 | 404 `PERSON_LABEL_NOT_FOUND`；409 `PERSON_LABEL_ALREADY_ENDED`；409 `PERSON_LABEL_NOT_EFFECTIVE` |
| 标签尚未生效 | `DELETE /person-labels/{id}` | `effective_from` 晚于业务当天 | 不变 | 409 `PERSON_LABEL_NOT_EFFECTIVE`「员工标签尚未生效，无法结束」 |
| 任意读请求 | `GET /persons/{id}/labels` 等 | 持有 `WORKFORCE_ADMIN` 或 `*` | 返回结果 | 403 `PERMISSION_DENIED`；404 `PERSON_LABEL_LIBRARY_NOT_FOUND`（标签库未初始化） |
| 任意写请求 | `POST /persons/{id}/labels`、`POST /persons/{id}/labels/batch` | 持有 `WORKFORCE_ADMIN` 或 `*` | 写入标签行与审计行 | 403 `PERMISSION_DENIED`；422 / 409（见 WFC-LABEL-F002） |

## 7. 业务规则

状态约定：`CONFIRMED` 表示该规则已有已确认决策、已交付能力或服务端强制的合同约束支撑；`PENDING` 表示该规则取决于尚未签字的产品决策，开发者不得自行猜测；`NOT_APPLICABLE` 表示经核查本功能不涉及，并写明依据。

| ID | 状态 | 规则 | 规则来源 | 验证方式 |
|---|---|---|---|---|
| WFC-LABEL-F001-BR001 | `CONFIRMED` | 标签只能挂在已存在的人员档案上；人员不存在时返回 422 `PERSON_LABEL_PERSON_NOT_FOUND`，读与写都适用 | 实现 `labels_service.py:161-167`、`:226-231`、`:288-294` | AC002 |
| WFC-LABEL-F001-BR002 | `CONFIRMED` | 标签名称与标签类型去除首尾空白后不能为空，否则 422 `REQUEST_VALIDATION_FAILED` | 契约 `labels_service.py:40-47` | AC003 |
| WFC-LABEL-F001-BR003 | `CONFIRMED` | 来源只允许 `MANUAL` 或 `AI`（大小写不敏感，落库统一大写）；`is_ai_generated` 由来源推导，调用方不能直接指定 | 契约 `labels_service.py:49-56`；实现 `labels_service.py:194-195` | AC004 |
| WFC-LABEL-F001-BR004 | `CONFIRMED` | 标签结束日期不得早于生效日期，否则 422 | 契约 `labels_service.py:58-63`；DB CheckConstraint `effective_period_order`（`models.py:361-364`） | AC003 |
| WFC-LABEL-F001-BR005 | `CONFIRMED` | 同一「人员 + 类型 + 名称 + 生效日 + 来源」的组合唯一；重复时返回 409 `PERSON_LABEL_DUPLICATE`，由服务层预检与 DB UniqueConstraint 双重保证 | 实现 `labels_service.py:169-184`、`:197-206`；`models.py:353-360` | AC005 |
| WFC-LABEL-F001-BR006 | `CONFIRMED` | 按人查询只返回生效区间覆盖查询日期的标签，区间左闭右开（`effective_from <= 查询日` 且（`effective_to` 为空或 `effective_to > 查询日`））；未指定查询日期时按业务当天判断 | 实现 `labels_service.py:51-56`、`:295-306` | AC001 |
| WFC-LABEL-F001-BR007 | `CONFIRMED` | 全局标签查询默认只返回当前有效标签（`include_expired` 缺省为 false），有效判定用业务当天 | 实现 `labels_service.py:71`、`:327-335` | AC001 |
| WFC-LABEL-F001-BR008 | `CONFIRMED` | 结束标签采用软失效：结束日期记为业务当天、状态置为 `ended`、记录保留；已结束的标签不能重复结束（409 `PERSON_LABEL_ALREADY_ENDED`）；尚未生效的标签不能结束（409 `PERSON_LABEL_NOT_EFFECTIVE`） | 实现 `labels_service.py:382-415`；契约 `labels_service.py:135-136` | AC006 |
| WFC-LABEL-F001-BR009 | `CONFIRMED` | 标签类型按现有数据聚合，当前有效数量多的排在前面；类型名称沿用类型编码（没有独立字典表） | 实现 `labels_service.py:357-380` | AC002 |
| WFC-LABEL-F001-BR010 | `CONFIRMED` | 人工赋予的标签必须命中标签库：类型与标签项都必须是启用中的，命中失败返回 422 `PERSON_LABEL_LIBRARY_ITEM_NOT_FOUND` | 实现 `label_library.py:86-122` | AC007（WFC-LABEL-F002） |
| WFC-LABEL-F001-BR011 | `CONFIRMED` | 标签库是一个基础资料字典（`PERSON_LABEL_LIBRARY`），不新建独立表；只返回启用中的标签类型与其启用中的标签项；标签库未初始化时返回 404 `PERSON_LABEL_LIBRARY_NOT_FOUND` | 实现 `label_library.py:11-13`、`:43-84`、`:124-136` | AC002 |
| WFC-LABEL-F001-BR012 | `CONFIRMED` | 标签项改名不影响历史标签的展示：`label_type` 存类型编码、`label_name` 存标签项名称（展示快照） | 实现 `label_library.py:86-91` | AC008 |
| WFC-LABEL-F001-BR013 | `CONFIRMED` | 审计日志只记录标签业务字段（人员 id、类型、名称、来源、状态、生效区间、AI 标记），不写入人员姓名等个人信息 | 实现 `labels_service.py:442-454` | AC009 |
| WFC-LABEL-F001-BR014 | `CONFIRMED` | 单个标签在页面上是**两行结构**：上行是标签本体 Tag（人工=蓝、AI=紫并带 🤖），下行是来源、有效期、有效性与「结束」操作；状态不只依赖颜色，同时输出「人工标记 / AI 生成」与「当前有效 / 已结束」文字 | 实现 `PersonLabelPanel.tsx:203-241`；D-091；画板 `BUE0c` 的 `labelRowStructure` | AC001、AC004 |
| WFC-LABEL-F001-BR015 | `CONFIRMED` | 「员工标签」页签只在账号具备 `WORKFORCE_ADMIN` 时挂载，避免给出必然 403 的入口 | 实现 `PeopleWorkspace.tsx:339-347`；HR-LABEL-016 | AC010 |
| WFC-LABEL-F001-BR016 | `PENDING` | 标签「结束」是否需要「恢复」入口：当前结束后不可恢复，只能重新赋予 | 现状实现 `labels_service.py:382-415`；待确认清单 P-05「标签『结束』是软失效，是否需要『恢复』入口」 | 见 §18 Q-04 |
| WFC-LABEL-F001-BR017 | `PENDING` | 是否需要独立的「标签库管理」页面：当前标签库只在 Drawer 内被消费，无管理页 | 待确认清单 P-04 | 见 §18 Q-05 |
| WFC-LABEL-F001-BR018 | `PENDING` | 标签的读取权限是否要放开给只读角色：当前读写同权，都要求 `WORKFORCE_ADMIN` | 现状实现 `labels_api.py:29`；ASM-01 | 见 §18 Q-06 |
| WFC-LABEL-F001-BR019 | `PENDING` | 企业侧的标签体系（类型清单、标签项命名规范、AI 标签生成规则）尚未提供 | 依据 ASM-05 与本轮输入包缺口 | 见 §18 Q-07 |

规则写法自查（对照规范 §8.1 / §8.2）：所有 `CONFIRMED` 规则都写明了适用对象与时间点、条件与唯一性维度、成功与拒绝结果、历史记录影响，不使用「合理处理」「一般情况」「尽量」等表述；不包含未说明配置范围的「支持灵活配置」、未说明幂等与最终状态的「失败后重试」、未说明下游与历史保留的「可以回退」。

## 8. 数据要求

### 8.1 数据所有权与关系

- 本功能拥有的数据：**无（只读）**。本功能只读 `person_labels` 与标签库字典，只向 `audit_logs` 追加一条结束审计行；标签的创建归 WFC-LABEL-F002。
- 引用但不拥有的数据：
  - `person_labels`（员工标签）：归属 Workforce Core（`apps/api/src/hris/modules/workforce/models.py:351-379`）。
  - `data_dictionaries` / `data_dictionary_items`（标签库）：归属 Platform Kernel（`apps/api/src/hris/modules/platform/models.py:105-137`）。
  - `persons`（人员档案）：归属 Workforce Core，只用于校验人员存在。
- 业务唯一键：
  - `person_labels` 的唯一性是「人员 + 类型 + 名称 + 生效日 + 来源」五元组（DB UniqueConstraint，`models.py:353-360`；服务层预检 `labels_service.py:169-184`）。
  - 标签库内：同一字典内 `code` 唯一、层级由 `parent_item_id` 表达（`models.py:117`）。
- 有效日期/版本/快照要求：
  - 标签的生效区间左闭右开，`effective_to` 为空表示当前有效（`labels_service.py:295-306`）。
  - `effective_to >= effective_from` 由 CheckConstraint `effective_period_order` 兜底（`models.py:361-364`）。
  - 快照：`label_name` 是标签项名称的**展示快照**，标签项改名不影响历史标签展示（`label_library.py:86-91`）。

### 8.2 字段合同

「来源」列中的文件均位于 `apps/api/src/hris/modules/workforce/labels_service.py`，行号在括号内注明。

| ID | 字段 | 类型/格式 | 必填 | 来源 | 默认值 | 校验 | 敏感级别 | 历史策略 |
|---|---|---|---|---|---|---|---|---|
| WFC-LABEL-F001-DAT001 | `id` | UUID | 响应只读 | `PersonLabelResponse.id`（:109） | — | — | 非敏感 | 稳定身份，结束后不变 |
| WFC-LABEL-F001-DAT002 | `person_id` | UUID | 是 | `PersonLabelResponse.person_id`（:110） | 无 | 必须指向已存在人员，否则 422 `PERSON_LABEL_PERSON_NOT_FOUND` | 非敏感（内部 id） | 行级保存 |
| WFC-LABEL-F001-DAT003 | `label_name` | string(255) | 是 | `PersonLabelResponse.label_name`（:111） | 无 | 去空白后非空 | 非敏感（分类标签，非个人信息） | 快照，标签项改名不影响 |
| WFC-LABEL-F001-DAT004 | `label_type` | string(100) | 是 | `PersonLabelResponse.label_type`（:112） | 无 | 去空白后非空；人工赋予时必须命中标签库类型 | 非敏感 | 稳定类型编码，结束后不变 |
| WFC-LABEL-F001-DAT005 | `source` | string(80)，`MANUAL` / `AI` | 是 | `PersonLabelResponse.source`（:113） | `MANUAL`（契约 `:32-36`） | 仅允许两个取值，否则 422 | 非敏感 | 行级保存 |
| WFC-LABEL-F001-DAT006 | `effective_from` | date（业务日期） | 是 | `PersonLabelResponse.effective_from`（:114） | 新建时由调用方给（前端默认今天，`PersonLabelPanel.tsx:93`） | 不得晚于 `effective_to` | 非敏感 | 区间起点，结束后不变 |
| WFC-LABEL-F001-DAT007 | `effective_to` | date，可空 | 否 | `PersonLabelResponse.effective_to`（:115） | 空 = 长期有效 | 不得早于 `effective_from`；结束时写业务当天 | 非敏感 | 结束时写入，保留 |
| WFC-LABEL-F001-DAT008 | `status` | string(30)，`active` / `ended` | 响应只读 | `PersonLabelResponse.status`（:116） | `active`（实现 `:193`） | 枚举内取值 | 非敏感 | 结束时置 `ended` |
| WFC-LABEL-F001-DAT009 | `is_ai_generated` | boolean | 响应只读 | `PersonLabelResponse.is_ai_generated`（:117） | 由 `source == "AI"` 推导（`:194-195`） | 调用方不能直接指定 | 非敏感 | 与来源同步 |
| WFC-LABEL-F001-DAT010 | `code`（标签库项） | string(100) | 响应只读 | `LabelLibraryItemResponse.code`（`label_library.py:18`） | — | 同一字典内唯一 | 非敏感 | 稳定编码 |
| WFC-LABEL-F001-DAT011 | `name`（标签库项） | string(200) | 响应只读 | `LabelLibraryItemResponse.name`（`label_library.py:19`） | — | — | 非敏感 | 改名只影响新赋予的标签 |
| WFC-LABEL-F001-DAT012 | `sort_order`（标签库项） | int | 响应只读 | `LabelLibraryItemResponse.sort_order`（`label_library.py:20`） | `0` | — | 非敏感 | — |
| WFC-LABEL-F001-DAT013 | `type_code`（标签库类型） | string(100) | 响应只读 | `LabelLibraryTypeResponse.type_code`（`label_library.py:24`） | — | 第 0 级且启用 | 非敏感 | 稳定编码 |
| WFC-LABEL-F001-DAT014 | `type_name`（标签库类型） | string(200) | 响应只读 | `LabelLibraryTypeResponse.type_name`（`label_library.py:25`） | — | — | 非敏感 | — |
| WFC-LABEL-F001-DAT015 | `code` / `name` / `count`（标签类型聚合） | string / string / int | 响应只读 | `LabelTypeItem`（:136-139） | `name` 沿用 `code`（`:375-377`） | 按当前有效数量倒序 | 非敏感 | 实时聚合 |

### 8.3 数据生命周期

- 创建：由 WFC-LABEL-F002 的批量接口写入 `person_labels` 一行或一批行（`labels_service.py:217-281`）。
- 修改/更正：本模块没有更新端点；标签的业务字段不可改写，纠错方式是「结束旧标签 + 重新赋予」。
- 生效/失效：新增即按 `effective_from` 生效；结束是软失效，写 `effective_to` 并把 `status` 置为 `ended`，行本身不删除（`labels_service.py:405-408`）。
- 保留：标签行永久保留，本模块没有删除端点；审计日志另表保存。
- 删除：`NOT_APPLICABLE`。依据：本模块的 DELETE 端点语义是「结束」（软失效），实现只写 `effective_to` 与 `status`，全模块无物理删除语句（`labels_api.py:128-137`、`labels_service.py:382-415`）。
- 迁移与兼容：本轮无结构变更；`person_labels` 表结构自员工标签能力落地以来未变。

## 9. 权限要求

| ID | 状态 | 参与者 | 功能/动作权限 | 数据范围 | 字段权限 | 拒绝结果 |
|---|---|---|---|---|---|---|
| WFC-LABEL-F001-PERM001 | `CONFIRMED` | 持有 `WORKFORCE_ADMIN` 或 `*` 的账号 | 查看本人的员工标签（`GET /api/v1/workforce/persons/{person_id}/labels`） | 单个员工的有效标签 | 只读字段（DAT001–DAT009） | 403 `PERMISSION_DENIED`「没有执行此操作的权限」（`dependencies.py:80`）；前端显示错误条「员工标签加载失败」（`PersonLabelPanel.tsx:67`） |
| WFC-LABEL-F001-PERM002 | `CONFIRMED` | 同上 | 读取标签类型清单（`GET /api/v1/workforce/label-types`） | 全部类型的当前有效计数 | 只读字段（DAT015） | 同 PERM001；前端取不到时退回显示类型编码（`PersonLabelPanel.tsx:69-74`） |
| WFC-LABEL-F001-PERM003 | `CONFIRMED` | 同上 | 读取标签库（`GET /api/v1/workforce/label-library`） | 启用中的类型与标签项 | 只读字段（DAT010–DAT014） | 同 PERM001；前端取不到时标签库退化为空（`PersonLabelPanel.tsx:75-79`） |
| WFC-LABEL-F001-PERM004 | `CONFIRMED` | 同上 | 结束员工标签（`DELETE /api/v1/workforce/person-labels/{label_id}`） | 单个标签 | 可写 DAT007、DAT008（由服务端计算，不由前端指定） | 同 PERM001；无权限时「结束」按钮置灰（`PersonLabelPanel.tsx:235`） |
| WFC-LABEL-F001-PERM005 | `CONFIRMED` | 持有 `WORKFORCE_ADMIN` 或 `*` 的账号 | 「新增标签」按钮的可见性与点击行为 | — | — | 无权限时按钮置灰（`PersonLabelPanel.tsx:270`）；弹窗内的写操作另由服务端 403 兜底 |
| WFC-LABEL-F001-PERM006 | `CONFIRMED` | 持有 `WORKFORCE_ADMIN` 或 `*` 的账号 | 「员工标签」页签的挂载 | — | — | 无权限时该页签根本不出现（`PeopleWorkspace.tsx:339-347`） |
| WFC-LABEL-F001-PERM007 | `CONFIRMED` | 未登录或会话失效账号 | 任何接口 | — | — | 401 `AUTHENTICATION_REQUIRED`「需要登录」或 `SESSION_INVALID`「登录状态无效或已过期」（`dependencies.py:32`、`:47`） |

代办与代理说明：

- 主管理员（持 `*`）可以直接执行全部操作（`dependencies.py:90` 对 `*` 短路放行）。
- 本功能**没有代办 / 代理身份机制**：审计只记录操作者本人 `actor_id`，没有 `on_behalf_of` 字段（`labels_service.py:417-440`）。
- 未知范围默认拒绝：权限判定为「不具备所需权限码即拒绝」，不做任何隐式放行（`dependencies.py:79-80`）。

## 10. 交互与页面要求

### 10.1 入口与可见性

- 菜单/页面/按钮：
  - 入口：**没有独立菜单**。入口是员工档案 Drawer 的「员工标签」页签（`PeopleWorkspace.tsx:339-347`）；宿主页是「人员中心」（`navigation.ts:57`）。
  - 页内操作：工具条主按钮「新增标签」（`PersonLabelPanel.tsx:270`）；标签行内「结束」链接按钮（`:235`）。
  - 工具条左侧文案：「共 N 个标签」（`:269`）。
  - 页签标题：「员工标签」（`PeopleWorkspace.tsx:344`）。
- 无权限或未启用模块时：账号不具备 `WORKFORCE_ADMIN` 时「员工标签」页签不挂载（`PeopleWorkspace.tsx:339-347`），不会出现必然 403 的空页签。
- 宿主页：列表。员工标签页签是员工档案 Drawer 内的页签，宿主页是「人员中心」列表（见 WFC-PEOPLE-F001）。
- 交互载体：`DRAWER`（宿主：员工档案 Drawer，`size="large"`）。本功能**不引入**额外载体——查看在页签内完成，结束是行内 Popconfirm（确认气泡，不构成独立载体）。
- 选择理由：员工标签是员工档案的一个属性分组，与其它 6 个页签共享同一次档案加载与同一个宿主 Drawer；单独开页或新标签页会割裂档案上下文并重复请求。按 [Ant Design 页面与交互载体规范](../design/antd-page-interaction-standard.md) §3，属性型子视图留在宿主页容器内是默认边界；新增标签的 Modal 载体见 WFC-LABEL-F002。
- 路由或深链接：宿主页为 hash 路由 `#people`；本页签**没有**独立路由或深链接定位（切换页签不改变 URL），刷新后回到页签默认态。
- Pencil源文件：`C:\Users\83289\Documents\HRMS\coreHR.pen`（Pencil 2.17）。
- 画板ID/名称/原型版本：`BUE0c` / 「员工档案 Drawer · 员工标签 Tab v1.0」 / `v1.0`（画板 1440×960，`carrier: DRAWER`、`carrierSize: large`、`overlayOpacity: 0.45`）。
- 原型状态：`PROTOTYPE_APPROVED`。2026-10-24 产品决策人确认全部画板并签字，规范 §10.1 的状态枚举中对应 `PROTOTYPE_APPROVED`；按规范 §10.2 与 D-087，前端开发门禁已解除，本功能可按画板继续开发（见 §19 T002 状态与 §18 Q-01）。

### 10.2 页面状态

| 状态 | 页面表现 | 可执行操作 |
|---|---|---|
| 首次/空数据 | 标签为空时显示空态「暂无标签」（`PersonLabelPanel.tsx:246-248`），由 `EmptyState` 承载；工具条计数显示「共 0 个标签」 | 切换到其它页签；有权限时可「新增标签」 |
| 加载中 | 首次加载且还没有标签时显示「加载中…」（`PersonLabelPanel.tsx:244-245`） | 等待 |
| 正常 | 工具条 + 按类型分组的标签列表，每组一个 `Divider` 标题，组内标签两行结构 | 查看、结束标签、打开新增标签 Modal |
| 部分失败 | 标签列表请求失败时显示错误条，且**不显示**「暂无标签」空态（避免把失败误报为空）；标签类型清单失败时分组标题退回显示类型编码；标签库失败时退化为空 | 关闭错误条、重新加载 |
| 完全失败 | 标签列表失败即页签内唯一的内容错误（`PersonLabelPanel.tsx:67`） | 关闭错误条或联系管理员 |
| 无权限 | 该页签根本不挂载 | 退出登录或联系主管理员 |

### 10.3 表单与确认

- 字段顺序与联动：本功能**没有表单**（新增标签的表单在 WFC-LABEL-F002）。页签内只有分组展示与结束操作。
- 即时校验与提交校验：结束操作没有输入项，无校验；失败时错误落在页签内的错误条上（`PersonLabelPanel.tsx:192-200`）。
- 高风险二次确认：**结束标签有 Popconfirm 二次确认**，标题「结束标签「{标签名}」」、描述「结束为软失效：标签记录保留，仅不再生效，可由管理员重新维护。」、确认按钮「确认结束」（`PersonLabelPanel.tsx:228-234`）。
- 成功反馈与下一步：结束成功后页签重新加载（`PersonLabelPanel.tsx:196`），该标签从有效标签列表中消失；失败时错误条显示后端 message。
- 打开、关闭和焦点返回：结束操作用 Popconfirm（确认气泡），关闭后焦点回到触发它的「结束」链接按钮；本页签无其它弹窗。
- 未保存变更与重复提交保护：本页签没有表单，无未保存变更；结束请求期间「结束」按钮进入 `loading` 态（`PersonLabelPanel.tsx:235`），阻止重复提交。
- 弹窗关闭后表单重置或保留策略：`NOT_APPLICABLE`。依据：本页签不使用弹窗（新增标签的 Modal 属于 WFC-LABEL-F002，其重置策略在该文档 §10.3 说明）。

### 10.4 Pencil原型登记

| 原型ID | 页面/交互载体 | Pencil文件 | 画板ID与名称 | 版本 | 状态 | 批准人/日期 |
|---|---|---|---|---|---|---|
| WFC-LABEL-F001-PROT001 | `DRAWER`（宿主画板「员工档案 Drawer · 员工标签 Tab v1.0」，画板 `BUE0c` 1440×960，overlay 0.45；结束标签的 Popconfirm 尚未单独出画板） | `C:\Users\83289\Documents\HRMS\coreHR.pen` | 画板ID `BUE0c`；画板名称「员工档案 Drawer · 员工标签 Tab v1.0」 | v1.0 | `PROTOTYPE_APPROVED` | 2026-10-24 产品决策人签字确认（见 §18 Q-01 / §20） |

登记说明（按事实记录，不做美化）：

- 画板状态 `PROTOTYPE_APPROVED`（2026-10-24 产品决策人签字确认）依据 `docs/review/pen-prototype-spec-2026-10-24.md` 头部状态标注与 §7 后续动作第 3 条；预览图为 `docs/review/pen-prototypes/05-员工档案Drawer-员工标签Tab.png`。
- 画板与实现的有意差异已登记在画板登记表 `implementationDeltas`：第 1 条「员工标签 Tab 仅在管理员可见时挂载」对应 BR015 / PERM006；第 2 条「已结束的标签不显示『结束』按钮」对应 BR008 / BR014。
- 画板规格的 `labelRowStructure` 写明「上行 Tag（人工=蓝 / AI=紫带 🤖）」「下行 来源 + 有效性 + 结束」，与实现的两行结构一致；实现的下行比画板多一段「有效期」文本（`PersonLabelPanel.tsx:208-210`），这是画板说明 §5 中记录的有意保留项（既有测试断言了该文案）。
- 画板规格的 `labelGroups` 列出「技能 / 关键岗位 / 培养对象」三个示例分组，实际实现的分组来自该员工的实际标签类型，不是固定枚举（`PersonLabelPanel.tsx:115-125`）。
- 规范 §10.4 要求「显著不同的加载、空数据、失败、无权限和冲突状态应在原型中可Review」，这些状态目前只存在于实现（`PersonLabelPanel.tsx:243-262`），没有对应的 Pencil 画板——见 §18 Q-01。

## 11. API与事件合同

### 11.1 同步API

| ID | 方法与路径 | 调用者 | 请求摘要 | 响应摘要 | 权限 | 幂等 | 事务边界 |
|---|---|---|---|---|---|---|---|
| WFC-LABEL-F001-API001 | `GET /api/v1/workforce/persons/{person_id}/labels`（`labels_api.py:40-60`） | 员工标签页签 | 路径参数 `person_id`（UUID）；查询参数 `effective_at`（date，可选，缺省业务当天） | `PersonLabelListResponse`：`items`（`PersonLabelResponse` 列表）、`total` | `WORKFORCE_ADMIN`；`*` 放行 | 天然幂等（只读） | 单请求单事务，`get_db` 在响应前提交（`apps/api/src/hris/core/database.py:18-25`） |
| WFC-LABEL-F001-API002 | `GET /api/v1/workforce/label-types`（`labels_api.py:140-148`） | 员工标签页签（分组标题） | 无查询参数 | `LabelTypeListResponse`：`items`（`{code, name, count}`） | `WORKFORCE_ADMIN`；`*` 放行 | 天然幂等 | 单请求单事务 |
| WFC-LABEL-F001-API003 | `GET /api/v1/workforce/label-library`（`labels_api.py:151-159`） | 员工标签页签与新增标签 Modal | 无查询参数 | `LabelLibraryListResponse`：`items`（`{type_code, type_name, items[]}`） | `WORKFORCE_ADMIN`；`*` 放行 | 天然幂等 | 单请求单事务 |
| WFC-LABEL-F001-API004 | `DELETE /api/v1/workforce/person-labels/{label_id}`（`labels_api.py:128-137`，204） | 员工标签页签「结束」 | 路径参数 `label_id`（UUID） | 空响应体（204） | `WORKFORCE_ADMIN`；`*` 放行 | 幂等边界：第一次调用生效并写审计；第二次返回 409 `PERSON_LABEL_ALREADY_ENDED` | 单请求单事务；结束写入与审计行同事务 |
| WFC-LABEL-F001-API005 | `GET /api/v1/workforce/labels`（`labels_api.py:63-89`） | （本功能页面当前无调用方；供全局标签检索使用） | 查询参数：`label_type`（≤100）、`source`（≤80）、`person_id`（UUID）、`include_expired`（bool，缺省 false）、`page`（≥1）、`page_size`（1–200，缺省 20） | `PageResponse`：`items`（`PersonLabelResponse` 列表）、`total`、`page`、`page_size` | `WORKFORCE_ADMIN`；`*` 放行 | 天然幂等 | 单请求单事务 |

调用者与所有权说明：上述接口由 Workforce Core 模块提供（`apps/api/src/hris/modules/workforce/`）；标签库读取复用 Platform Kernel 的基础资料字典，本模块只读。前端调用封装在 `apps/web/src/business/features/people/label-api.ts:190-240`，认证统一使用 Bearer Token（`apps/web/src/business/client.ts`）。

### 11.2 异步事件与任务

`NOT_APPLICABLE`。依据：本功能的写路径（`labels_service.py:382-415`）只做数据库写入与审计写入，模块内没有消息发布或领域事件调用（`apps/api/src/hris/modules/workforce/labels_service.py` 全文件检索 `publish` / `emit` 无命中）；AI 标签的生成链路当前不存在（AI 只作为来源标识，`labels_service.py:194-195`）。若后续引入消息引擎（待确认清单 P-10～P-12）或 AI 标签生成链路，本功能是否需要订阅「人员档案变更」需重新评审并补写本节。

### 11.3 兼容与废弃

- 当前合同版本：v1。标签读取与结束的接口路径与响应字段自员工标签能力落地以来未变；本轮无接口变更。
- 向后兼容策略：`label_type` 存稳定类型编码、`label_name` 存展示快照（`label_library.py:86-91`），标签库改名不影响历史标签。
- 废弃通知和截止版本：当前无废弃项。若后续把标签库从基础资料字典迁移到独立表，必须先在本节登记并同步 `docs/01-foundation/03-项目决策.md`，不得直接删除旧字典项（规范 §13 变更控制）。

## 12. 异常、并发与回退

| ID | 状态 | 场景 | 系统结果 | 用户提示/错误码 | 是否重试 | 补偿/回退 |
|---|---|---|---|---|---|---|
| WFC-LABEL-F001-ERR001 | `CONFIRMED` | 标签所属人员不存在 | 拒绝，不写入任何行 | 422 `PERSON_LABEL_PERSON_NOT_FOUND`「人员档案不存在，无法查询员工标签」（`labels_service.py:290-294`） | 否 | 不适用 |
| WFC-LABEL-F001-ERR002 | `CONFIRMED` | 结束不存在的标签 | 拒绝 | 404 `PERSON_LABEL_NOT_FOUND`「员工标签不存在」（`labels_service.py:384-389`） | 否 | 不适用 |
| WFC-LABEL-F001-ERR003 | `CONFIRMED` | 结束已结束的标签 | 拒绝，`effective_to` 与 `status` 不变 | 409 `PERSON_LABEL_ALREADY_ENDED`「员工标签已结束」（`labels_service.py:391-397`） | 否 | 不适用 |
| WFC-LABEL-F001-ERR004 | `CONFIRMED` | 结束尚未生效的标签 | 拒绝 | 409 `PERSON_LABEL_NOT_EFFECTIVE`「员工标签尚未生效，无法结束」（`labels_service.py:398-404`） | 否 | 不适用 |
| WFC-LABEL-F001-ERR005 | `CONFIRMED` | 标签库尚未初始化（字典 `PERSON_LABEL_LIBRARY` 不存在） | 拒绝，读取标签库时报错 | 404 `PERSON_LABEL_LIBRARY_NOT_FOUND`「员工标签库尚未初始化，请在基础资料中创建标签库」（`label_library.py:130-135`） | 否——需先在基础资料中创建字典 | 不适用 |
| WFC-LABEL-F001-ERR006 | `CONFIRMED` | 请求参数不满足 schema | 请求被拒 | 422 `REQUEST_VALIDATION_FAILED`「请求参数校验失败」，`details` 逐字段给出（`apps/api/src/hris/core/errors.py:41-61`） | 否 | 不适用 |
| WFC-LABEL-F001-ERR007 | `CONFIRMED` | 无权限访问或结束 | 请求被拒 | 403 `PERMISSION_DENIED`「没有执行此操作的权限」（`dependencies.py:80`） | 否 | 不适用 |
| WFC-LABEL-F001-ERR008 | `CONFIRMED` | 会话无效或过期 | 请求被拒 | 401 `AUTHENTICATION_REQUIRED` / `SESSION_INVALID`（`dependencies.py:32`、`:47`） | 重新登录后重试 | 不适用 |
| WFC-LABEL-F001-ERR009 | `CONFIRMED` | 两人同时结束同一个标签 | 服务端读改写同一行（`self._session.get`，`labels_service.py:383`），未加行锁；后写者覆盖前写者的结束日期与状态，但两行审计都会写入 | 前端展示后端 message（`PersonLabelPanel.tsx:197`） | 否——终态一致 | 无需补偿：标签终态仍是「已结束」；并发覆盖窗口见 §18 Q-08 |
| WFC-LABEL-F001-ERR010 | `CONFIRMED` | 标签类型清单或标签库读取失败 | 标签列表本身不受影响 | 标签类型取不到时分组标题退回显示类型编码；标签库取不到时退化为空（`PersonLabelPanel.tsx:69-79`） | 刷新页面可重试 | 不适用——辅助数据源失败不阻断标签展示 |
| WFC-LABEL-F001-ERR011 | `CONFIRMED` | 结束写入过程中数据库异常 | 整个请求事务回滚，标签的 `effective_to` / `status` 与审计行都不落库 | 前端展示「标签结束失败」（`PersonLabelPanel.tsx:197`） | 可在修复原因后重试 | 自动回滚（`apps/api/src/hris/core/database.py:23-25`） |
| WFC-LABEL-F001-ERR012 | `CONFIRMED` | 后台任务中断 | `NOT_APPLICABLE`：本功能没有后台任务（依据 §11.2） | — | — | — |
| WFC-LABEL-F001-ERR013 | `CONFIRMED` | 下游系统失败 | `NOT_APPLICABLE`：本功能不调用外部系统（依据 §11.2） | — | — | — |
| WFC-LABEL-F001-ERR014 | `PENDING` | 误结束标签后的恢复 | 当前没有恢复入口：结束后只能重新赋予一条新标签，旧标签永久停留在「已结束」 | 现状无对应提示 | — | 建议路径是重新赋予；是否提供「恢复」见 §18 Q-04 |

## 13. 审计与数据保护

| ID | 状态 | 动作 | 审计内容 | 禁止记录内容 | 保留要求 |
|---|---|---|---|---|---|
| WFC-LABEL-F001-AUD001 | `CONFIRMED` | 结束员工标签 | `action=person_label.end`、`object_type=person_label`、`object_id=标签 id`、`reason=结束员工标签`、`before_payload` / `after_payload` 为标签业务字段快照、`actor_id`、`trace_id`、`source=api`（`labels_service.py:409-415`、`:417-440`） | **不写入人员姓名等个人信息**，只写 `person_id`（`labels_service.py:442-454`） | 审计行随 `audit_logs` 表保留，无删除入口 |
| WFC-LABEL-F001-AUD002 | `CONFIRMED` | 读取员工标签 / 标签类型 / 标签库 | 读取行为本身不产生审计行 | — | — |
| WFC-LABEL-F001-AUD003 | `CONFIRMED` | 审计记录读取 | 审计查询接口 `GET /api/v1/platform/audit-logs` 要求 `DATA_GOVERNANCE_ADMIN`，读取不降级为 VIEW（`apps/api/src/hris/modules/platform/audit_api.py:23-27`） | 审计导出不含 `before_payload` / `after_payload`（`apps/api/src/hris/modules/platform/audit_service.py:19-29`） | 按审计模块既有保留策略执行 |

- 敏感字段加密：`NOT_APPLICABLE`。依据：本功能写入的表 `person_labels` 没有任何个人敏感列（`models.py:351-379`），字段集合仅为人员 id、标签类型与名称、来源、生效区间、状态与 AI 标记；人员档案的加密要求属于 `docs/01-foundation/07-人员档案领域规范.md`。
- 页面脱敏：页签展示的是标签、来源、生效区间与有效性文本，不含个人敏感信息；人员姓名只出现在宿主 Drawer 的标题里（`PeopleWorkspace.tsx:307`），不进入标签接口。
- 明文访问：`NOT_APPLICABLE`。依据：本功能不存在「明文才能读取」的字段。
- 导出与临时文件：`NOT_APPLICABLE`。依据：员工标签页签没有导出入口（`label-api.ts:190-240` 无下载调用），也不产生临时文件。
- 非生产数据：验收使用合成数据；现有自动化测试即采用合成 fixture（`apps/web/src/business/features/people/PersonLabelPanel.test.tsx`）。

## 14. 非功能需求

| ID | 状态 | 类别 | 可验证要求 | 环境/数据量 | 验证证据 |
|---|---|---|---|---|---|
| WFC-LABEL-F001-NFR001 | `CONFIRMED` | 性能 | 页签加载时三个请求并行发起（`Promise.allSettled`），不串行等待 | 本机开发库 | `PersonLabelPanel.tsx:59-63` |
| WFC-LABEL-F001-NFR002 | `PENDING` | 性能 | 页签首屏（标签 + 类型 + 标签库）的响应时间目标 | 需要容量输入：本机并发用户数、单员工标签条数、标签库项总数 | 缺容量输入，暂不可验收；输入模板见 `docs/input-packs/templates/07-capacity-scenarios.csv`，容量场景见 `docs/input-packs/09-nonfunctional-acceptance-input.md` |
| WFC-LABEL-F001-NFR003 | `CONFIRMED` | 可用性 / 可访问性 | 标签的状态不只依赖颜色：人工 / AI 同时输出「人工标记 / AI 生成」文字，有效性同时输出「当前有效 / 已结束」文字；每个标签带 Tooltip 说明类型、来源与有效期 | 键盘与屏幕阅读器人工检查 | `PersonLabelPanel.tsx:203-226`；规范 §7 状态不只依赖颜色的要求 |
| WFC-LABEL-F001-NFR004 | `CONFIRMED` | 兼容 | 页面使用仓库锁定的 Ant Design 6.5.2 组件，不使用已废弃属性 | 生产构建 `npm run build` | D-090；`docs/design/antd-page-interaction-standard.md` §2；`node scripts/check-antd-usage.mjs` 0 违规 |
| WFC-LABEL-F001-NFR005 | `CONFIRMED` | 复用 | 页签的空态与错误提示统一使用 `EmptyState` 与 `WorkspaceError`，不在本能力域内出现第二套写法 | 全站一致性 | D-091；`PersonLabelPanel.tsx:16-17`、`:248`、`:266` |
| WFC-LABEL-F001-NFR006 | `CONFIRMED` | 可观测 | 每次请求返回 `trace_id`，写入审计行的 `trace_id` 与响应一致 | 本机开发库 | `apps/api/src/hris/core/errors.py:24-38`、`labels_service.py:417-440`、`models.py:997` |
| WFC-LABEL-F001-NFR007 | `CONFIRMED` | 安全 | 页面与审计载荷都不写入人员姓名等个人信息；标签读写受 `WORKFORCE_ADMIN` 约束 | 本机开发库 | §9 权限表、§13 AUD001 |
| WFC-LABEL-F001-NFR008 | `CONFIRMED` | 容量 | 标签库一次返回全部启用中的类型与标签项，不分页：企业标签体系规模必须可控 | 本机开发库；标签项总数由企业标签体系决定 | `label_library.py:43-84`；规模上限见 §18 Q-09 |

## 15. 验收场景

### WFC-LABEL-F001-AC001 查看员工标签的分组与有效性

- 类型：正常
- 前置数据：某员工有 3 个有效标签，分属 2 个标签类型。
- Given：维护者打开该员工的「员工标签」页签。
- When：页面加载完成。
- Then：工具条显示「共 3 个标签」；标签按类型分组渲染，每组一个 `Divider` 标题；每个标签显示来源（人工标记 / AI 生成）、有效期与有效性（当前有效）；无标签时显示空态「暂无标签」。
- 数据库/事件/审计证据：只读操作，不产生审计行。
- 自动化层级：前端单元测试 + 后端集成测试。

### WFC-LABEL-F001-AC002 标签读取的边界——按查询日期过滤与人员不存在

- 类型：边界 / 异常
- 前置数据：某员工有 2 个标签，其中 1 个 `effective_to` 为昨天。
- Given：以 `effective_at=昨天` 与 `effective_at=今天` 分别查询；再以一个不存在的人员 id 查询。
- When：请求 `GET /api/v1/workforce/persons/{id}/labels`。
- Then：昨天返回 2 条、今天返回 1 条；不存在的人员 id 返回 422 `PERSON_LABEL_PERSON_NOT_FOUND`。
- 数据库/事件/审计证据：无数据变化。
- 自动化层级：后端集成测试。

### WFC-LABEL-F001-AC003 业务规则拒绝——空白名称与非法区间

- 类型：异常 / 规则拒绝
- 前置数据：无。
- Given：提交 `label_name="   "` 的标签；再提交 `effective_to < effective_from` 的标签。
- When：请求到达服务端。
- Then：两次都返回 422 `REQUEST_VALIDATION_FAILED`，`details` 指明字段；`person_labels` 行数不变。
- 数据库/事件/审计证据：无数据写入，无审计行。
- 自动化层级：后端集成测试。

### WFC-LABEL-F001-AC004 业务规则拒绝——来源枚举与 AI 标记推导

- 类型：异常 / 正常
- 前置数据：无。
- Given：提交 `source="auto"` 的标签（非法）；再提交 `source="ai"` 的标签（合法，规范化为大写）。
- When：请求到达服务端。
- Then：第一次返回 422；第二次返回 201，且 `source` 为 `AI`、`is_ai_generated` 为 `true`——`is_ai_generated` 由来源推导，调用方不能直接指定。
- 数据库/事件/审计证据：`person_labels.source = "AI"`、`is_ai_generated = true`。
- 自动化层级：后端集成测试。

### WFC-LABEL-F001-AC005 重复请求——同组合标签重复赋予

- 类型：幂等
- 前置数据：已存在一条「人员 + 类型 + 名称 + 生效日 + 来源」完全相同的标签。
- Given：再次赋予同样的组合。
- When：请求到达服务端。
- Then：返回 409 `PERSON_LABEL_DUPLICATE`；`person_labels` 行数不变。
- 数据库/事件/审计证据：该五元组仍只有 1 行；审计中只有 1 条 `person_label.create`。
- 自动化层级：后端集成测试。

### WFC-LABEL-F001-AC006 结束标签——软失效与重复结束

- 类型：正常 / 异常
- 前置数据：一条当前生效的标签。
- Given：维护者点击「结束」并在 Popconfirm 中确认；随后再次结束。
- When：请求依次到达服务端。
- Then：第一次返回 204，`effective_to` 变为业务当天、`status` 变为 `ended`；第二次返回 409 `PERSON_LABEL_ALREADY_ENDED`；对不存在的 id 返回 404 `PERSON_LABEL_NOT_FOUND`。
- 数据库/事件/审计证据：标签行仍在表中；审计中有一条 `action=person_label.end`、`object_type=person_label` 的记录，且 `after_payload.effective_to` 为结束日期。
- 自动化层级：后端集成测试 + 前端单元测试。

### WFC-LABEL-F001-AC007 标签库未初始化时的错误码

- 类型：异常
- 前置数据：基础资料中没有字典 `PERSON_LABEL_LIBRARY`。
- Given：维护者请求 `GET /api/v1/workforce/label-library`。
- When：请求到达服务端。
- Then：返回 404 `PERSON_LABEL_LIBRARY_NOT_FOUND`，消息提示「请在基础资料中创建标签库」。
- 数据库/事件/审计证据：无数据变化。
- 自动化层级：后端集成测试。

### WFC-LABEL-F001-AC008 标签项改名不影响历史标签展示

- 类型：边界
- 前置数据：标签库中某标签项 code=`SKILL_01`、name=`核心开发`；某员工已有一条 `label_name=核心开发` 的标签。
- Given：把标签项 name 改为 `核心开发（已更名）`。
- When：重新读取该员工的标签。
- Then：该历史标签的 `label_name` 仍是 `核心开发`（展示快照）；只有新赋予的标签使用新名称。
- 数据库/事件/审计证据：`person_labels.label_name` 未被改写。
- 自动化层级：后端集成测试。

### WFC-LABEL-F001-AC009 审计证据核对——结束标签的载荷不含个人信息

- 类型：审计
- 前置数据：维护者具备 `WORKFORCE_ADMIN`。
- Given：其结束某员工的一个标签。
- When：操作成功。
- Then：`audit_logs` 出现一行 `action=person_label.end`、`object_type=person_label`、`object_id=<标签 id>`、`reason=结束员工标签`；`before_payload` 与 `after_payload` 只含 `person_id`、`label_type`、`label_name`、`source`、`status`、`effective_from`、`effective_to`、`is_ai_generated`，**不含**人员姓名。
- 数据库/事件/审计证据：`audit_logs` 查询结果。
- 自动化层级：后端集成测试。

### WFC-LABEL-F001-AC010 权限——无 `WORKFORCE_ADMIN` 时页签不挂载

- 类型：权限
- 前置数据：账号具备 `PERSON_VIEW` + `PERSON_SENSITIVE_VIEW`，不持有 `WORKFORCE_ADMIN` 与 `*`。
- Given：该账号打开员工档案。
- When：查看 Drawer 页签。
- Then：页签列表中没有「员工标签」；直接调用 `GET /api/v1/workforce/persons/{id}/labels` 返回 403 `PERMISSION_DENIED`。
- 数据库/事件/审计证据：无数据变化。
- 自动化层级：前端单元测试 + 后端集成测试。

### WFC-LABEL-F001-AC011 辅助数据源失败时标签展示不中断

- 类型：异常 / 边界
- 前置数据：标签列表接口正常，标签类型清单接口返回 500。
- Given：维护者打开「员工标签」页签。
- When：页面加载完成。
- Then：标签列表正常展示；分组标题退回显示类型编码而不是中文名；页面**不出现**错误条（类型清单失败被静默降级）。
- 数据库/事件/审计证据：无数据变化。
- 自动化层级：前端单元测试。

### WFC-LABEL-F001-AC012 后台任务中断与下游失败

- 类型：异常
- 前置数据：无。
- Given：审查本功能的写路径。
- When：检查是否存在异步任务或外部依赖调用。
- Then：不存在——写路径只有数据库写入与审计写入（`labels_service.py:382-415`，模块内无 `publish` / `emit` 调用），因此没有任务中断或下游失败场景需要验收。
- 数据库/事件/审计证据：不适用。
- 自动化层级：人工 UAT（代码核对，核对点已记录在 §11.2）。

## 16. 迁移、发布与回滚

- 现有数据影响：本功能管理的 `person_labels` 表已存在于本机库，本轮无结构变更、无数据迁移。
- 数据迁移与校验：不适用——本功能不提供导入功能；标签的批量赋予通过页面完成（见 WFC-LABEL-F002）。
- 功能开关或模块启用：没有功能开关；页签挂载按 `WORKFORCE_ADMIN` 判定（`PeopleWorkspace.tsx:339-347`）。
- 发布顺序：后端接口已在库；前端页面随 Web 构建发布。页面依赖 `GET /persons/{id}/labels`、`GET /label-types`、`GET /label-library` 三个既有接口，发布不改变接口合同。
- 升级兼容：`label_type` / `label_name` 的语义不变（类型编码 + 名称快照），既有消费者不受影响。
- 应用回滚：前端回滚到上一构建即可，接口未变更；后端回滚不涉及本功能的迁移。
- 数据不可逆时的恢复或前向修复：标签行只增不删（结束也是写 `effective_to` 与 `status`），回滚不会删除数据；误结束只能重新赋予（见 §12 ERR014 与 §18 Q-04）。

## 17. 可观测与运行手册

- 指标：本功能不新增业务指标。现有可观测项：接口调用量与错误码分布（403 / 404 / 409 / 422）、单员工标签条数（工具条计数 `共 N 个标签`）。
- 日志和Trace：每次请求带 `trace_id`（`apps/api/src/hris/core/errors.py:24-38`），审计行 `trace_id` 与之对应（`labels_service.py:417-440`）；排查一次具体的结束操作时，用 `trace_id` 关联审计记录与请求日志。
- 告警：本功能不定义专属告警；接口 5xx 与事务回滚沿用平台内核既有告警口径。
- 后台任务：无（依据 §11.2）。
- 人工补偿：结束失败时事务自动回滚（`apps/api/src/hris/core/database.py:23-25`），无需人工补偿；业务纠错通过重新赋予前向修正（§16）。
- 健康检查：页签可用性依赖 `GET /api/v1/workforce/persons/{id}/labels` 的可用性（`label-api.ts:191-198`）。

## 18. 待确认问题

| ID | 问题 | 影响规则/场景 | Owner | 期望日期 | 不确认时的处理 |
|---|---|---|---|---|---|
| WFC-LABEL-F001-Q01 | 待确认清单 **P-15**「画板通过后是否即授权前端按画板开发/替换」：是否确认把画板 `BUE0c` 的 Review 状态从 `DRAFT_FOR_REVIEW` 改为 `PROTOTYPE_APPROVED`。**2026-10-24 产品决策人已确认全部画板并签字**，§10.4 状态升级为 `PROTOTYPE_APPROVED` | §10.1 原型状态、§10.4 PROT001、§19 T002、AC001–AC012 的页面形态验收 | 产品决策人 | 2026-10-25 | 已关闭：2026-10-24 产品决策人签字确认画板，规范 §10.2 的前端开发门禁解除，本功能可按画板继续开发|
| WFC-LABEL-F001-Q02 | 待确认清单 **P-16**「`docs/requirements/` 模块功能需求文档」：本文件是本批次的第五份功能文档；是否继续扩展本文件覆盖「员工标签」的全局检索页 | §19 T001 的范围界定、§11.1 API005 | 产品决策人 | 2026-10-25 | 采用已实现行为：`GET /labels` 端点保留但页面无入口，不为其新建页面 |
| WFC-LABEL-F001-Q03 | 单条新增标签的接口 `POST /persons/{person_id}/labels` 已存在但页面无入口：是否保留该端点（供外部系统集成） | §2.2、§11.1 | 产品决策人 | 企业 UAT 前 | 采用已实现行为：保留端点不新增入口；前端只走批量接口 |
| WFC-LABEL-F001-Q04 | 待确认清单 **P-05**「标签『结束』是软失效，是否需要『恢复』入口」：当前结束后只能重新赋予 | BR016、ERR014、§8.3、§16 | 产品决策人 | 2026-10-25 | 采用已实现行为：不提供恢复入口，纠错走重新赋予 |
| WFC-LABEL-F001-Q05 | 待确认清单 **P-04**「员工标签是否需要独立『标签库管理』页面」：当前标签库只在 Drawer 内被消费，维护走基础资料 | BR017、§2.2 | 产品决策人 | 企业 UAT 前 | 采用已实现行为：不新建标签库管理页；标签库维护归属基础资料工作区 |
| WFC-LABEL-F001-Q06 | 标签的读取权限是否放开给只读角色：当前读写同权（都要求 `WORKFORCE_ADMIN`）。若放开需要新增只读权限码并补迁移 seed（**不得**使用未落库的权限码） | ASM-01、BR018、§9 | 产品决策人 + 权限负责人 | 企业 UAT 前 | 采用已实现行为：读写同权，页签只对 `WORKFORCE_ADMIN` 账号挂载 |
| WFC-LABEL-F001-Q07 | 企业侧的标签体系（类型清单、标签项命名规范、AI 标签生成规则）尚未提供；AI 当前只作为来源标识，没有生成链路 | ASM-05、BR019、§11.2 | 产品决策人 + 企业输入方 | 企业标签体系交付时 | 采用已实现行为：按库内现有标签库展示，不新增 AI 生成链路 |
| WFC-LABEL-F001-Q08 | 两人同时结束同一个标签时，服务端未加行锁（`labels_service.py:383` 直接 `session.get`），后写者会覆盖先写者的结束日期与状态；是否需要加行锁并把结束日期固定为首次结束日 | ERR009 | 产品决策人 | 企业 UAT 前 | 采用已实现行为：不加行锁，终态仍是「已结束」 |
| WFC-LABEL-F001-Q09 | 标签库一次返回全部启用中的类型与标签项、不分页：企业标签体系规模上限是多少 | NFR008 | 产品决策人 + 企业输入方 | 企业标签体系交付时 | 采用已实现行为：一次返回全部启用项 |

## 19. 开发任务与追踪

| 任务ID | 目标 | 依赖 | 文件/模块所有权 | 需求追踪注释 | 验收场景 | 状态 | 交付证据 |
|---|---|---|---|---|---|---|---|
| WFC-LABEL-F001-T001 | 按《模块功能需求文档规范》建立员工标签页签功能需求文档，登记 Pencil 画板 `BUE0c`、字段合同、权限、错误码与验收场景 | 无 | 仅新增 `docs/requirements/WFC-workforce-core/WFC-label/WFC-LABEL-F001-person-label-tab.md` | 文档头部登记规范 17 号；正文引用 HR-LABEL-001～016 / ADR-0002 / D-067 / D-068 / D-069 / D-090 / D-091 / P-04 / P-05 / P-15 / P-16 | AC001–AC012 的判定依据 | `IN_REVIEW` | 本文件（v0.1，2026-10-24） |
| WFC-LABEL-F001-T002 | 前端按已批准画板 `BUE0c` 对齐员工标签页签 | WFC-LABEL-F001-Q01（画板签字，`PROTOTYPE_APPROVED`） | `apps/web/src/business/features/people/PersonLabelPanel.tsx`、`label-api.ts`、`apps/web/src/business/features/workforce/PeopleWorkspace.tsx` | 在规则落点写 `Requirement: WFC-LABEL-F001-BRnnn — 原因` | AC001、AC004、AC006、AC010、AC011 | `READY`（2026-10-24 画板已签字，规范 §10.2 的前端开发门禁解除，按画板继续对齐） | — |
| WFC-LABEL-F001-T003 | 标签结束操作加行锁，使并发结束时结束日期固定为首次结束日 | WFC-LABEL-F001-Q08 | `apps/api/src/hris/modules/workforce/labels_service.py` | `Requirement: WFC-LABEL-F001-ERR009 — 并发结束需串行化` | AC006 | `BLOCKED`（阻塞原因：Q08 未拍板；改动会改变并发下的结束日期语义） | — |

## 20. Review与批准记录

| 版本 | 日期 | 变更摘要 | 产品/业务结论 | 技术结论 | 批准人 |
|---|---|---|---|---|---|
| v0.1 | 2026-10-24 | 初稿：按 17 号规范建立员工标签页签功能需求文档；登记 Pencil 画板 `BUE0c`（初稿状态 `DRAFT_FOR_REVIEW`）；逐条对齐后端合同（字段、接口、权限码、错误码）与前端实现文案 | 已由产品决策人 Review 并签字，状态升级为 `PROTOTYPE_APPROVED`（Q01） | 字段、接口、权限与错误码全部指向实现文件与行号，未发明后端不存在的字段；标签库复用基础资料字典的事实已如实登记 | 已批准（2026-10-24 产品决策人签字） |

现状说明（按事实记录）：

- 2026-10-24 用户已指示「按画板开发或替换已有的界面」，前端据此先行实现了该页签，并已获授权先行实现。
- 画板已于 **2026-10-24** 经产品决策人签字确认，§10.4 的 Review 状态升级为 `PROTOTYPE_APPROVED`。
- 在 Q01 关闭之前，按规范 §10.2 与 D-087，不得为本功能创建新的前端开发任务（T002 状态为 `BLOCKED`）。

### 20.1 规范 §15 文档 Review 检查表自查（2026-10-24）

| # | 检查项 | 自查结论 | 依据 |
|---|---|---|---|
| 1 | 文档是否只描述一个可独立验收的功能 | 是 | 全文只描述「查看与结束员工标签」；批量新增标签因动作、载体与失败补偿不同而拆出（§2.2、§3）；标签库管理归属基础资料，不在本功能内 |
| 2 | 是否能明确说出谁在什么条件下得到什么结果 | 是 | §3 参与者表（主管理员 / 人力编制维护者 / 人员档案查看者 / 未登录账号）+ §5 三条用户故事的触发条件、前置条件、主路径、结束状态 |
| 3 | 是否区分确认规则、待确认问题和推荐方案 | 是 | §7 规则表带 `CONFIRMED` / `PENDING` 状态列并写明状态约定；§18 全部为待确认项并给出「不确认时的处理」；本文件未代替产品决策人做结论 |
| 4 | 数据所有者、唯一键、有效日期和历史策略是否明确 | 是 | §8.1 数据所有权（本功能只读）、五元组唯一性、标签库字典层级与展示快照语义；§8.2 每行含「历史策略」列 |
| 5 | 是否覆盖动作、数据范围、字段和高风险操作 | 是 | §9 PERM001–PERM007 覆盖读 / 结束 / 页签挂载 / 按钮可见性 / 403 拒绝结果；高风险操作的二次确认在 §10.3 明确 |
| 6 | 接口是否明确幂等、事务、版本和失败补偿 | 是 | §11.1 五个接口逐个写明幂等性与单请求单事务边界；§12 覆盖重复、并发、异常与回滚；§11.2 说明无异步事件及依据 |
| 7 | 是否覆盖异常、并发、回退、审计和敏感数据 | 是 | §12 ERR001–ERR014；§13 AUD001–AUD003 及加密、脱敏、明文访问、导出、非生产数据逐项结论；恢复缺口在 ERR014 / Q04 登记 |
| 8 | NFR是否可以在指定环境中验证 | 部分通过 | NFR001、NFR003–NFR008 可在指定环境验证并给出证据；NFR002（页签首屏响应时间）因缺容量输入标记 `PENDING`，已在 §14 写明需要的输入文件与验收环境 |
| 9 | 验收场景是否包含明确输入、动作和预期证据 | 是 | §15 AC001–AC012，每条含类型、前置数据、Given / When / Then、数据库或审计证据、自动化层级 |
| 10 | 是否可以在不猜业务规则的情况下拆出最小任务 | 是 | §19 三个任务均声明所有权、依赖、追踪注释与验收场景；两个任务因 Q01 / Q08 未决而 `BLOCKED`，未把 PENDING 规则写进任务 |
| 11 | 是否说明对已有数据、模块和部署的影响 | 是 | §16 覆盖现有数据影响、迁移与校验、开关、发布顺序、升级兼容、应用回滚与前向修复；§4 列出标签库与人员档案的引用关系 |
| 12 | 是否存在与父级PRD或已确认决策冲突的内容 | 是（无冲突） | 载体选择符合 D-068 / D-069 与交互载体规范 §3；组件复用符合 D-091；标签库模型符合 ADR-0002 / D-067；原型门禁符合 D-087 |
| 13 | 所有需求驱动的代码变化是否明确了追踪注释所引用的ID和预计代码落点 | 是 | §19 T002、T003 写明 `Requirement: WFC-LABEL-F001-BRnnn / ERR009 — 原因` 及预计落点文件；本轮不产生代码变化 |
| 14 | 涉及前端时，是否明确宿主页、`MODAL`/`DRAWER`/`NEW_TAB`载体及其打开、退出和状态恢复行为 | 是 | §10.1 宿主页=人员中心列表、主载体=`DRAWER`（宿主员工档案 Drawer）、选择理由、hash 路由 `#people`、本页签无独立路由；§10.3 结束操作的 Popconfirm 打开 / 关闭 / 焦点行为 |
| 15 | 涉及前端时，是否登记Pencil文件、画板ID、版本和`PROTOTYPE_APPROVED`证据 | 通过 | §10.4 已登记 Pencil 源文件、画板 ID `BUE0c`、画板名称、版本 `v1.0` 与状态；`PROTOTYPE_APPROVED` 证据**已存在**（2026-10-24 产品决策人签字确认）；原缺口 Q01 登记 |

自查结论汇总：15 项中 14 项通过，1 项为「部分通过」——第 8 项因缺容量输入把 NFR002 标为 `PENDING`（不是编造）；第 15 项已随 2026-10-24 画板签字补齐 `PROTOTYPE_APPROVED` 证据。按规范 §15 末句「任一关键项为否时，不得进入 `READY_FOR_TASKS`」，本功能当前状态仍保持 `DRAFT`（余下 1 项为第 8 项 NFR002 容量输入待补），画板门禁已不再是阻塞项。
