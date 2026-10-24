# WFC-LABEL-F002 批量新增标签

> 模块：WFC / Workforce Core
> 能力域：WFC-LABEL / 员工标签管理
> 状态：`DRAFT`
> 版本：v0.1
> 产品Owner：MillerMax（产品决策人）
> 业务Owner：产品决策人 MillerMax 兼任（仓库内没有记录企业侧 HR 业务负责人；依据 `docs/01-foundation/03-项目决策.md` D-066）
> 上级需求：[16-coreHR产品总体PRD](../01-foundation/16-coreHR产品总体PRD.md) §5.3 Workforce Core 职责（人员档案扩展属性）；[07-人员档案领域规范](../01-foundation/07-人员档案领域规范.md)
> 依赖功能：[WFC-PEOPLE-F001 人员中心与员工档案](../WFC-workforce-core/WFC-people/WFC-PEOPLE-F001-person-profile.md)（宿主 Drawer）；[WFC-LABEL-F001 员工标签页签](../WFC-workforce-core/WFC-label/WFC-LABEL-F001-person-label-tab.md)（宿主页签与标签库数据源）
> 最后更新：2026-10-24

## 1. 背景与期望结果

- 当前问题：员工标签的写入能力已经存在（批量接口 `POST /api/v1/workforce/persons/{person_id}/labels/batch`，`apps/api/src/hris/modules/workforce/labels_api.py:109-125`），前端也已有「批量新增标签」Modal（`apps/web/src/business/features/people/PersonLabelPanel.tsx:275-332`）。但该 Modal 是本轮 2026-10-24 按 Pencil 画板 `FmBa4` 对齐落地的形态，此前没有按《模块功能需求文档规范》登记功能需求文档，画板状态无处落档；同时它的「整批原子」语义（任一条命中不到标签库则整批拒绝）需要在需求层明确，避免被当作「部分成功」。
- 用户价值：HR 维护者可以在一个弹窗里从企业标签库多选标签，一次性给一个员工批量打标签，并明确知道「要么全部成功，要么全部不生效」，不会出现只打了一半的标签状态。
- 本功能完成后可观察的业务结果：
  1. 员工档案「员工标签」页签点击「新增标签」打开 Modal，标题「批量新增标签」，宽 520（`PersonLabelPanel.tsx:275-281`）。
  2. 表单分两组：「从标签库选择」（标签类型下拉 + 标签多选）与「生效与来源」（生效日期 + 来源）（`PersonLabelPanel.tsx:302-330`）。
  3. 保存成功后整批标签落库、页签重新加载；任一条不命中标签库时整批拒绝、不落任何数据（`labels_service.py:217-281`）。
  4. 每条新建标签都写一条 `action=person_label.create` 的审计记录（`labels_service.py:273-281`）。
- 不做本功能的影响：给一个员工打多个标签需要重复调用单条接口，中途失败会留下「打了一半」的标签状态，无法解释。

## 2. 范围

### 2.1 纳入范围

- 批量新增标签 Modal：标题、宽 520、页脚「取消 / 保存」（`PersonLabelPanel.tsx:275-284`）。
- 表单第一组「从标签库选择」：标签类型下拉（可清空、按类型过滤标签库、默认占位「全部标签类型」）与标签多选（必填、占位「从标签库选择标签」）（`PersonLabelPanel.tsx:302-320`）。
- 表单第二组「生效与来源」：生效日期（必填、默认今天）与来源（必填、两项：人工标记 / AI 生成）（`PersonLabelPanel.tsx:321-330`）。
- 打开前的表单重置策略：每次打开都是空表单、生效日期默认今天、来源默认人工标记、标签类型过滤清空（`PersonLabelPanel.tsx:85-95`）。
- 整批原子的写入语义与错误码（`labels_service.py:217-281`）。
- 本功能的 Pencil 画板登记（见 §10.4）。

### 2.2 不纳入范围

- 员工标签页签的读取与结束：独立成 [WFC-LABEL-F001 员工标签页签](../WFC-workforce-core/WFC-label/WFC-LABEL-F001-person-label-tab.md)。
- 单条新增标签的 API（`POST /persons/{person_id}/labels`）：契约与端点已存在，但页面无入口，本功能不描述该入口（见 WFC-LABEL-F001 §18 Q-03）。
- 标签库本身的维护：标签库是基础资料字典，维护走「基础资料」工作区（`label_library.py:34-38`）。
- 标签的「恢复」入口、AI 标签的生成链路：当前不存在（见 WFC-LABEL-F001 §18 Q-04、Q-07）。
- 跨员工的批量打标签（一次给多个人打标签）：当前接口只接受单个人员 id，本功能不扩展。

### 2.3 假设与约束

| ID | 状态 | 内容 | 假设不成立时的处理 |
|---|---|---|---|
| ASM-01 | `CONFIRMED` | 标签只能从标签库选，没有自由文本「标签名称」输入框；提交时提交的是标签库的「类型编码 + 标签项编码」组合，服务端再解析成落库的「类型编码 + 名称快照」（`PersonLabelPanel.tsx:168-179`、`label_library.py:86-122`） | 若要允许自由文本，必须新增契约与落库语义，并同步标签库唯一性规则 |
| ASM-02 | `CONFIRMED` | 批量写入是**整批原子**：任一条在标签库中找不到，整批拒绝且不落任何数据（`labels_service.py:222-225`、`:233-237`） | 若要改为部分成功，需要重写契约并补行级错误返回，本功能不自行放宽 |
| ASM-03 | `CONFIRMED` | 批量条数上限 100；同一批次内不允许出现重复的标签库编码组合（重复时后端 422，前端在下拉中也无法重复选中同一项） | 上限调整需同步前端多选上限与契约 |
| ASM-04 | `CONFIRMED` | 标签类型下拉是**筛选器**而不是必填项：选中类型后，标签多选的候选只剩该类型下的标签项；切换类型时若已选标签不在新范围内则被清掉（`PersonLabelPanel.tsx:146-157`、`:297-300`） | 若类型变为必填，需改表单规则并同步后端契约 |
| ASM-05 | `PENDING` | 企业侧的标签体系（类型清单、标签项、AI 标签生成规则）尚未提供；AI 来源当前只是一个手工选择项，没有生成链路 | 按库内现有标签库展示；企业标签体系补齐前不扩展，见 §18 Q-05 |

## 3. 参与者、权限边界和业务场景

| 参与者 | 目标 | 前置权限 | 数据范围 |
|---|---|---|---|
| 主管理员 | 给员工批量赋予标签 | `*`（`apps/api/src/hris/modules/platform/dependencies.py:90` 对 `*` 短路放行） | 全部员工；本模块无行级数据范围 |
| 人力编制维护者 / 编制管理员 / SSC 管理员 | 同上 | `WORKFORCE_ADMIN`（`labels_api.py:29`） | 全部员工；本模块无行级数据范围 |
| 人员档案查看者（无 `WORKFORCE_ADMIN`） | —— | 无 `WORKFORCE_ADMIN` | 「员工标签」页签不挂载，「新增标签」按钮不存在（`PeopleWorkspace.tsx:339-347`、`PersonLabelPanel.tsx:270`） |
| 未登录 / 会话失效访问者 | —— | 无有效会话 | 401 `AUTHENTICATION_REQUIRED` / `SESSION_INVALID`（`dependencies.py:32`、`:47`） |

场景边界说明：本功能只有一个业务结果——「一次性给一个员工批量赋予来自标签库的标签」。它是 WFC-LABEL-F001 页签内的写子动作，触发方式、载体与失败补偿都不同（整批原子 vs 单条软结束），按规范 §2.2 拆成独立功能文档。

## 4. 名词与依赖

| 名词/依赖 | 定义或引用 | 数据所有者 |
|---|---|---|
| 批量新增标签 | 一次提交多条标签的写操作，整批原子 | Workforce Core（`labels_service.py:217-281`） |
| 标签库 | 字典 `PERSON_LABEL_LIBRARY`：第 0 级为标签类型，第 1 级为标签项 | Platform Kernel（`label_library.py:11-13`） |
| 标签类型 | 标签的分组维度（如「技能」「关键岗位」「培养对象」） | Platform Kernel 基础资料字典 |
| 标签项 | 某个类型下的具体标签（如「核心开发」「技术骨干」「高潜人才」） | Platform Kernel 基础资料字典 |
| 来源（source） | `MANUAL`（人工标记）或 `AI`（AI 生成）；`is_ai_generated` 由来源推导 | Workforce Core（`labels_service.py:17-19`、`:266-267`） |
| 生效日期 | 批量标签共同的 `effective_from`；本功能不设置 `effective_to`（落库为 `null`，即长期有效） | Workforce Core（`labels_service.py:262`） |
| 人员档案 | `persons` 表，标签必须挂在已存在的人员档案上 | Workforce Core（`models.py:324-348`） |
| 审计记录 | `audit_logs` 表，`object_type=person_label`，每条新建标签一行 | Workforce Core（`models.py:992-1016`） |

## 5. 用户故事

### WFC-LABEL-F002-US01 从标签库多选标签

作为人力编制维护者，我希望按标签类型筛选标签库并多选标签，从而一次性给员工打上多个标签。

- 触发条件：在员工档案「员工标签」页签点击「新增标签」。
- 前置条件：账号具备 `WORKFORCE_ADMIN` 或 `*`；标签库中至少有一个启用中的标签类型与标签项。
- 主路径：打开 Modal（`PersonLabelPanel.tsx:275-281`）→「从标签库选择」分组 → 标签类型下拉（占位「全部标签类型」）→ 选一个类型 → 标签多选（占位「从标签库选择标签」）的候选只剩该类型下的标签项（`:302-320`、`:135-144`）→ 选中若干标签（多选以 Tag 形态并列展示）。
- 结束状态：多选框显示已选标签；切换标签类型时，不在新类型范围内的已选标签被自动清掉（`:146-157`）。

### WFC-LABEL-F002-US02 指定生效日期与来源

作为人力编制维护者，我希望为这批标签指定生效日期和来源，从而让标签的有效期与可信度可解释。

- 触发条件：在 Modal 的「生效与来源」分组填写字段。
- 前置条件：Modal 已打开。
- 主路径：生效日期默认为打开时的今天（`PersonLabelPanel.tsx:93`）；来源下拉两项「人工标记」「AI 生成」，默认「人工标记」（`:92`、`:325-329`）。
- 结束状态：提交载荷含 `effective_from` 与 `source`；落库时 `effective_to` 为 `null`（长期有效）、`status` 为 `active`、`is_ai_generated` 由来源推导（`labels_service.py:258-268`）。

### WFC-LABEL-F002-US03 保存并整批生效

作为人力编制维护者，我希望保存后这批标签要么全部生效、要么全部不生效，从而不留下无法解释的半成品标签。

- 触发条件：点击 Modal 页脚「保存」。
- 前置条件：至少选中一个标签；生效日期与来源已填。
- 主路径：点击「保存」→ 表单校验（标签必填、生效日期必填、来源必填）→ 提交 `POST /api/v1/workforce/persons/{person_id}/labels/batch`，载荷为 `{effective_from, source, labels: [{label_type_code, label_code}, ...]}`（`PersonLabelPanel.tsx:175-179`；`label-api.ts:222-237`）→ 服务端逐条解析标签库、去重预检、整批写入（`labels_service.py:217-281`）。
- 结束状态：成功时 Modal 关闭、页签重新加载、工具条计数加 N；失败时 Modal **保持打开并保留已填内容**，错误显示在 Modal 顶部（`PersonLabelPanel.tsx:180-188`、`:286-292`）。

### WFC-LABEL-F002-US04 取消

作为人力编制维护者，我希望取消时不留下任何标签，从而安全地放弃这次操作。

- 触发条件：点击 Modal 页脚「取消」或右上角关闭。
- 前置条件：Modal 已打开。
- 主路径：点击「取消」→ 清空表单错误 → 关闭 Modal（`PersonLabelPanel.tsx:284`）。
- 结束状态：Modal 关闭，不发出任何写请求，页签内容不变。

## 6. 业务流程与状态机

```text
批量新增标签（一次提交 1..100 条）
  提交
    │ 校验：人员存在？批次内标签项不重复？来源合法？
    ▼
  解析：逐条在标签库中查找「类型编码 + 标签项编码」
    │ 任一条查不到（类型或标签项不存在、或已停用）
    ├──────────────────────────► 整批拒绝 422 PERSON_LABEL_LIBRARY_ITEM_NOT_FOUND（不落任何数据）
    ▼ 全部命中
  去重预检：与库中已有「人员 + 类型 + 名称 + 生效日 + 来源」相同的标签
    │ 命中
    ├──────────────────────────► 整批拒绝 409 PERSON_LABEL_DUPLICATE（不落任何数据）
    ▼ 无冲突
  整批写入（同一事务、同一 savepoint）
    │ 写入过程中数据库异常
    ├──────────────────────────► 整批回滚（不落任何数据）
    ▼
  逐条写审计（action=person_label.create）
  返回 created 列表 → 前端关闭 Modal → 页签重新加载
```

| 当前状态 | 操作 | 条件 | 下一状态 | 失败结果 |
|---|---|---|---|---|
| Modal 未打开 | 点击「新增标签」 | `canAdmin` 为真 | 打开空表单 | 无权限时按钮置灰（`PersonLabelPanel.tsx:270`） |
| Modal 已打开 | 点击「保存」 | 至少选中一个标签、生效日期与来源已填 | 提交批量写请求 | 表单校验失败：不发请求，错误落在字段上 |
| 提交中 | 服务端校验 | 人员存在、批次内无重复、来源合法 | 进入解析阶段 | 422 `PERSON_LABEL_PERSON_NOT_FOUND` / `REQUEST_VALIDATION_FAILED` |
| 解析中 | 标签库查找 | 全部命中 | 进入去重预检 | 422 `PERSON_LABEL_LIBRARY_ITEM_NOT_FOUND`（整批不落数据） |
| 去重预检 | 与既有标签比对 | 无冲突 | 进入写入阶段 | 409 `PERSON_LABEL_DUPLICATE`（整批不落数据） |
| 写入阶段 | 事务提交 | 无异常 | 标签落库 + 审计落库 | 事务回滚，不落任何数据（`labels_service.py:256-271`） |

## 7. 业务规则

状态约定：`CONFIRMED` 表示该规则已有已确认决策、已交付能力或服务端强制的合同约束支撑；`PENDING` 表示该规则取决于尚未签字的产品决策，开发者不得自行猜测；`NOT_APPLICABLE` 表示经核查本功能不涉及，并写明依据。

| ID | 状态 | 规则 | 规则来源 | 验证方式 |
|---|---|---|---|---|
| WFC-LABEL-F002-BR001 | `CONFIRMED` | 标签只能从标签库选：提交的是「标签类型编码 + 标签项编码」组合，服务端解析成落库的「类型编码 + 名称快照」；解析不到返回 422 `PERSON_LABEL_LIBRARY_ITEM_NOT_FOUND`，整批拒绝 | 实现 `label_library.py:86-122`；`labels_service.py:233-237` | AC004 |
| WFC-LABEL-F002-BR002 | `CONFIRMED` | 整批原子：任一条在标签库中找不到，整批拒绝且不落任何数据 | 实现 `labels_service.py:222-225` | AC004 |
| WFC-LABEL-F002-BR003 | `CONFIRMED` | 单次批量赋予的标签条数上限 100，超出时契约校验失败 | 实现 `labels_service.py:25-26`、`:82` | AC005 |
| WFC-LABEL-F002-BR004 | `CONFIRMED` | 同一批次内不允许出现重复的「标签类型编码 + 标签项编码」组合，否则 422 | 实现 `labels_service.py:92-103` | AC005 |
| WFC-LABEL-F002-BR005 | `CONFIRMED` | 批量写入的标签与库中既有标签「人员 + 类型 + 名称 + 生效日 + 来源」相同的，整批拒绝并返回 409 `PERSON_LABEL_DUPLICATE` | 实现 `labels_service.py:238-253` | AC006 |
| WFC-LABEL-F002-BR006 | `CONFIRMED` | 批量新建的标签 `effective_to` 为 `null`（长期有效）、`status` 为 `active`；`is_ai_generated` 由来源推导，调用方不能直接指定 | 实现 `labels_service.py:258-268` | AC003 |
| WFC-LABEL-F002-BR007 | `CONFIRMED` | 来源仅允许 `MANUAL` 或 `AI`（大小写不敏感，落库统一大写），否则 422 | 契约 `labels_service.py:84-90` | AC002 |
| WFC-LABEL-F002-BR008 | `CONFIRMED` | 标签必须挂在已存在的人员档案上；人员不存在返回 422 `PERSON_LABEL_PERSON_NOT_FOUND`，整批不落数据 | 实现 `labels_service.py:226-231` | AC007 |
| WFC-LABEL-F002-BR009 | `CONFIRMED` | 每条新建标签写一条审计记录：`action=person_label.create`、`object_type=person_label`、`reason=批量创建员工标签`；审计载荷只含标签业务字段，不写人员姓名 | 实现 `labels_service.py:273-281`、`:442-454` | AC008 |
| WFC-LABEL-F002-BR010 | `CONFIRMED` | 前端提交前自检：若已选标签在提交瞬间已不在标签库中（例如标签项被停用），前端直接报「选中的标签已不在标签库中，请重新选择」，不发请求 | 实现 `PersonLabelPanel.tsx:169-174` | AC009 |
| WFC-LABEL-F002-BR011 | `CONFIRMED` | 标签类型是筛选器不是必填项：选中类型后多选候选只剩该类型下的标签项；切换类型时不在新范围内的已选标签被清掉 | 实现 `PersonLabelPanel.tsx:146-157`、`:135-144`、`:297-300` | AC001 |
| WFC-LABEL-F002-BR012 | `CONFIRMED` | 每次打开 Modal 都是一份空表单：标签类型过滤清空、已选标签清空、来源默认「人工标记」、生效日期默认打开当天 | 实现 `PersonLabelPanel.tsx:85-95` | AC002 |
| WFC-LABEL-F002-BR013 | `CONFIRMED` | 标签只能从标签库选，没有自由文本「标签名称」输入框 | 实现 `PersonLabelPanel.tsx:302-320`；画板登记表 `implementationDeltas` 第 1 条 | AC001 |
| WFC-LABEL-F002-BR014 | `CONFIRMED` | 保存失败时 Modal 保持打开并保留用户输入，错误显示在 Modal 顶部的可关闭错误条上 | 实现 `PersonLabelPanel.tsx:182-185`、`:286-292` | AC004、AC006 |
| WFC-LABEL-F002-BR015 | `PENDING` | AI 来源的语义：当前「AI 生成」只是人工选择的一个来源标识，没有任何 AI 生成链路；企业是否要求自动推荐或自动打标 | ASM-05、BR006 | 见 §18 Q-04 |
| WFC-LABEL-F002-BR016 | `PENDING` | 是否需要「按人员分组批量打标签」（一次给多个人打同一批标签）：当前接口只接受单个人员 id | 现状实现 `labels_api.py:109-125` | 见 §18 Q-05 |

规则写法自查（对照规范 §8.1 / §8.2）：所有 `CONFIRMED` 规则都写明了适用对象与时间点、条件与唯一性维度、成功与拒绝结果、批量失败后的整体结果，不使用「合理处理」「一般情况」「尽量」等表述；不包含未说明配置范围的「支持灵活配置」、未说明幂等与最终状态的「失败后重试」、未说明下游与历史保留的「可以回退」。

## 8. 数据要求

### 8.1 数据所有权与关系

- 本功能拥有的数据：
  - `person_labels`（员工标签行，每条标签一行）。归属模块：Workforce Core；表定义见 `apps/api/src/hris/modules/workforce/models.py:351-379`。
- 引用但不拥有的数据：
  - `data_dictionaries` / `data_dictionary_items`（标签库）：归属 Platform Kernel（`apps/api/src/hris/modules/platform/models.py:105-137`）。
  - `persons`（人员档案）：归属 Workforce Core，只用于校验人员存在。
- 业务唯一键：
  - `person_labels` 的唯一性是「人员 + 类型 + 名称 + 生效日 + 来源」五元组（DB UniqueConstraint，`models.py:353-360`；服务层预检 `labels_service.py:238-253`）。
  - 批次内的唯一性是「标签类型编码 + 标签项编码」组合（契约层校验，`labels_service.py:92-103`）。
- 有效日期/版本/快照要求：
  - 批量新建的标签只写 `effective_from`（业务日期），`effective_to` 为 `null`。
  - `effective_to >= effective_from` 由 CheckConstraint `effective_period_order` 兜底（`models.py:361-364`）。
  - 快照：`label_name` 是标签项名称的**展示快照**，标签项改名不影响历史标签展示（`label_library.py:86-91`）。

### 8.2 字段合同

「来源」列中的文件均位于 `apps/api/src/hris/modules/workforce/labels_service.py`，行号在括号内注明。

| ID | 字段 | 类型/格式 | 必填 | 来源 | 默认值 | 校验 | 敏感级别 | 历史策略 |
|---|---|---|---|---|---|---|---|---|
| WFC-LABEL-F002-DAT001 | `labels[]` | 数组，1–100 项 | 是 | `PersonLabelBatchCreate.labels`（:82） | 无 | 至少 1 项、最多 100 项 | 非敏感 | 不落库（落库的是解析后的字段） |
| WFC-LABEL-F002-DAT002 | `labels[].label_type_code` | string(100) | 是 | `PersonLabelBatchItem.label_type_code`（:67） | 无 | 去空白后非空；必须是标签库中启用的第 0 级类型 | 非敏感 | 解析后落库为 `label_type` |
| WFC-LABEL-F002-DAT003 | `labels[].label_code` | string(255) | 是 | `PersonLabelBatchItem.label_code`（:68） | 无 | 去空白后非空；必须是该类型下启用的第 1 级标签项 | 非敏感 | 解析后落库为 `label_name`（名称快照） |
| WFC-LABEL-F002-DAT004 | `effective_from` | date（业务日期） | 是 | `PersonLabelBatchCreate.effective_from`（:80） | 无（前端默认今天，`PersonLabelPanel.tsx:93`） | 不得晚于 `effective_to`（批量场景 `effective_to` 恒为空） | 非敏感 | 落库为 `effective_from` |
| WFC-LABEL-F002-DAT005 | `source` | string(80)，`MANUAL` / `AI` | 是 | `PersonLabelBatchCreate.source`（:81） | `MANUAL`（契约 `:81`；前端默认「人工标记」，`PersonLabelPanel.tsx:92`） | 仅允许两个取值，否则 422 | 非敏感 | 落库为 `source` |
| WFC-LABEL-F002-DAT006 | `effective_to` | date，可空 | 否 | 批量契约**没有**该字段（`labels_service.py:79-90`） | 服务端固定写 `null`（`:262`） | — | 非敏感 | 落库为 `effective_to`（恒空 = 长期有效） |
| WFC-LABEL-F002-DAT007 | `status` | string(30)，`active` / `ended` | 响应只读 | `PersonLabelResponse.status`（:116） | 服务端固定写 `active`（`:265`） | 枚举内取值 | 非敏感 | 结束时改为 `ended` |
| WFC-LABEL-F002-DAT008 | `is_ai_generated` | boolean | 响应只读 | `PersonLabelResponse.is_ai_generated`（:117） | 由 `source == "AI"` 推导（`:266-267`） | 调用方不能直接指定 | 非敏感 | 与来源同步 |
| WFC-LABEL-F002-DAT009 | `id` | UUID | 响应只读 | `PersonLabelResponse.id`（:109） | — | — | 非敏感 | 稳定身份 |
| WFC-LABEL-F002-DAT010 | `person_id` | UUID | 响应只读 | `PersonLabelResponse.person_id`（:110） | 来自路径参数 | 必须指向已存在人员 | 非敏感 | 行级保存 |
| WFC-LABEL-F002-DAT011 | `created[]` | `PersonLabelResponse[]` | 响应只读 | `PersonLabelBatchResponse.created`（:120-121） | — | 长度等于本次实际创建的条数 | 非敏感 | — |

### 8.3 数据生命周期

- 创建：一次请求写入 1–100 行 `person_labels`，并逐条写审计行（`labels_service.py:255-281`）。
- 修改/更正：没有更新端点；标签的业务字段不可改写，纠错方式是「结束旧标签 + 重新赋予」。
- 生效/失效：新建即按 `effective_from` 生效（`effective_to` 为空 = 长期有效）；结束是软失效，由 WFC-LABEL-F001 的结束接口写 `effective_to` 与 `status`。
- 保留：标签行永久保留，本功能没有删除端点；审计日志另表保存。
- 删除：`NOT_APPLICABLE`。依据：本功能的写路径只创建不删除，模块内唯一的 DELETE 端点语义是「结束」（软失效），全模块无物理删除语句。
- 迁移与兼容：本轮无结构变更；`person_labels` 表结构自员工标签能力落地以来未变。

## 9. 权限要求

| ID | 状态 | 参与者 | 功能/动作权限 | 数据范围 | 字段权限 | 拒绝结果 |
|---|---|---|---|---|---|---|
| WFC-LABEL-F002-PERM001 | `CONFIRMED` | 持有 `WORKFORCE_ADMIN` 或 `*` 的账号 | 批量新增标签（`POST /api/v1/workforce/persons/{person_id}/labels/batch`） | 单个员工的标签 | 可写 DAT001–DAT005；DAT006–DAT008 由服务端计算 | 403 `PERMISSION_DENIED`「没有执行此操作的权限」（`dependencies.py:80`）；前端错误落在 Modal 顶部（`PersonLabelPanel.tsx:182-185`） |
| WFC-LABEL-F002-PERM002 | `CONFIRMED` | 同上 | 读取标签库以提供候选（`GET /api/v1/workforce/label-library`） | 启用中的类型与标签项 | 只读（DAT002、DAT003 的来源） | 同 PERM001；标签库取不到时多选候选为空（`PersonLabelPanel.tsx:75-79`） |
| WFC-LABEL-F002-PERM003 | `CONFIRMED` | 同上 | 「新增标签」按钮的可见性与点击行为 | — | — | 无权限时按钮置灰（`PersonLabelPanel.tsx:270`） |
| WFC-LABEL-F002-PERM004 | `CONFIRMED` | 同上 | 「员工标签」页签的挂载（宿主页签） | — | — | 无权限时该页签根本不出现（`PeopleWorkspace.tsx:339-347`） |
| WFC-LABEL-F002-PERM005 | `CONFIRMED` | 未登录或会话失效账号 | 任何接口 | — | — | 401 `AUTHENTICATION_REQUIRED`「需要登录」或 `SESSION_INVALID`「登录状态无效或已过期」（`dependencies.py:32`、`:47`） |

代办与代理说明：

- 主管理员（持 `*`）可以直接执行全部操作（`dependencies.py:90` 对 `*` 短路放行）。
- 本功能**没有代办 / 代理身份机制**：审计只记录操作者本人 `actor_id`，没有 `on_behalf_of` 字段（`labels_service.py:417-440`）。
- 未知范围默认拒绝：权限判定为「不具备所需权限码即拒绝」，不做任何隐式放行（`dependencies.py:79-80`）。

## 10. 交互与页面要求

### 10.1 入口与可见性

- 菜单/页面/按钮：
  - 入口：**没有独立菜单**。入口是员工档案 Drawer「员工标签」页签工具条右侧的主按钮「新增标签」（`PersonLabelPanel.tsx:267-271`）。
  - 页内操作：Modal 页脚「取消」「保存」（`PersonLabelPanel.tsx:280-281`）。
  - Modal 标题：「批量新增标签」（`PersonLabelPanel.tsx:278`）。
  - 分组标题：「从标签库选择」「生效与来源」（`PersonLabelPanel.tsx:302`、`:321`）。
  - 字段标签：「标签类型」「标签」「生效日期」「来源」（`:303`、`:312`、`:322`、`:325`）。
- 无权限或未启用模块时：无 `WORKFORCE_ADMIN` 时「员工标签」页签不挂载（`PeopleWorkspace.tsx:339-347`），「新增标签」按钮因此不存在；即使直接调用批量接口也会 403。
- 宿主页：列表。宿主页是「人员中心」列表，Modal 叠加在员工档案 Drawer 之上（见 WFC-PEOPLE-F001）。
- 交互载体：`MODAL`。宽 520，与 D-068 的轻量表单边界一致。
- 选择理由：批量新增标签是单任务、4 个字段、2 个分组、无页内标签、无多步骤、无并行参照需求，落在 [Ant Design 页面与交互载体规范](../design/antd-page-interaction-standard.md) §3 的 `MODAL` 默认边界内；不满足 `DRAWER`（无需保留宿主页预览并对照标签列表做多选核对）与 `NEW_TAB`（字段数与分组数均远低于升级线）的升级条件。画板登记的 `carrier: MODAL`、`carrierWidth: 520`、`nestedIn: BUE0c` 与实现一致。
- 路由或深链接：宿主页为 hash 路由 `#people`；Modal 不占用独立路由，关闭后回到宿主 Drawer 的「员工标签」页签并保留该页签的已加载内容（宿主组件未被卸载）。
- Pencil源文件：`C:\Users\83289\Documents\HRMS\coreHR.pen`（Pencil 2.17）。
- 画板ID/名称/原型版本：`FmBa4` / 「批量新增标签 Modal · D-068 v1.0」 / `v1.0`（画板 1440×960，`carrier: MODAL`、`carrierWidth: 520`、`nestedIn: BUE0c`）。
- 原型状态：`PROTOTYPE_APPROVED`。2026-10-24 产品决策人确认全部画板并签字，规范 §10.1 的状态枚举中对应 `PROTOTYPE_APPROVED`；按规范 §10.2 与 D-087，前端开发门禁已解除，本功能可按画板继续开发（见 §19 T002 状态与 §18 Q-01）。

### 10.2 页面状态

| 状态 | 页面表现 | 可执行操作 |
|---|---|---|
| 首次/空数据 | 标签类型下拉占位「全部标签类型」、标签多选占位「从标签库选择标签」、来源默认「人工标记」、生效日期默认当天 | 选择类型、多选标签、选来源、改日期 |
| 加载中 | 标签库在宿主页签加载时同步取回；Modal 打开期间若库尚未就绪，多选候选为空 | 等待宿主页签加载完成 |
| 正常 | 两组表单齐全；多选以 Tag 形态并列展示已选标签（画板示例「核心开发」「技术骨干 +1」） | 选类型、多选/清空标签、选来源、改日期、保存、取消 |
| 部分失败 | 标签库读取失败时多选候选为空（宿主页签已降级），Modal 仍可打开但无法选标签 | 关闭并重新进入宿主页签 |
| 完全失败 | 提交失败时 Modal 保持打开，顶部显示可关闭的错误条（整批失败的错误码原样展示，如 409 `PERSON_LABEL_DUPLICATE`） | 关闭错误条、修改后重试、取消 |
| 无权限 | 无 `WORKFORCE_ADMIN` 时页签不挂载，Modal 无法打开；直接调用接口返回 403 | 退出登录或联系主管理员 |

### 10.3 表单与确认

- 字段顺序与联动：
  - 分组一「从标签库选择」：「标签类型」→ 「标签」（`PersonLabelPanel.tsx:302-320`）。
  - 分组二「生效与来源」：「生效日期」→ 「来源」（`:321-330`）。
  - 联动：选择标签类型后，标签多选的候选只剩该类型的标签项（`:135-144`）；切换类型时不在新范围内的已选标签被清掉（`:146-157`、`:297-300`）。
  - 每次打开都是空表单：标签类型过滤清空、已选标签清空、来源默认「人工标记」、生效日期默认打开当天（`:85-95`）。
- 即时校验与提交校验：前端 antd Form 规则（标签必填提示「请至少选择一个标签」、生效日期必填提示「请选择生效日期」、来源必填）（`:312`、`:322`、`:325`）；提交前再做一次「已选标签是否仍在标签库中」的自检，不通过则报「选中的标签已不在标签库中，请重新选择」（`:169-174`）；后端 pydantic 校验失败返回 422 `REQUEST_VALIDATION_FAILED`，逐字段 `details` 返回（`apps/api/src/hris/core/errors.py:41-61`）。
- 高风险二次确认：**没有二次确认**。当前一次保存即可整批写入；虽然整批原子（要么全成要么全不成）降低了「打了一半」的风险，但一次批量写入仍属于不可删除的数据变更（标签只能结束、不能删除）。是否补二次确认见 §18 Q-06。
- 成功反馈与下一步：保存成功后关闭 Modal、页签重新加载、工具条计数更新（`PersonLabelPanel.tsx:180-181`）；失败时 Modal 保持打开并保留输入，错误落在 Modal 顶部（`:182-188`、`:286-292`）。
- 打开、关闭和焦点返回：Modal 使用 `destroyOnHidden`（`:276`），关闭即销毁表单；antd 默认在打开后把焦点移入容器、关闭后焦点回到触发它的「新增标签」按钮。
- 未保存变更与重复提交保护：未保存变更**不拦截**关闭（当前实现没有脏检查）；保存期间 `confirmLoading={saving}` 使「保存」按钮进入加载态，阻止重复提交（`:282`、`:165`、`:186`）。
- 弹窗关闭后表单重置或保留策略：关闭即销毁，下次打开时由 `form.setFieldsValue(...)` 重新写入初始值（`:85-95`），不保留上一批的输入。

### 10.4 Pencil原型登记

| 原型ID | 页面/交互载体 | Pencil文件 | 画板ID与名称 | 版本 | 状态 | 批准人/日期 |
|---|---|---|---|---|---|---|
| WFC-LABEL-F002-PROT001 | `MODAL`（宿主画板「批量新增标签 Modal · D-068 v1.0」，画板 `FmBa4` 1440×960，宽 520，嵌套在 `BUE0c` 员工档案 Drawer 内） | `C:\Users\83289\Documents\HRMS\coreHR.pen` | 画板ID `FmBa4`；画板名称「批量新增标签 Modal · D-068 v1.0」 | v1.0 | `PROTOTYPE_APPROVED` | 2026-10-24 产品决策人签字确认（见 §18 Q-01 / §20） |

登记说明（按事实记录，不做美化）：

- 画板状态 `PROTOTYPE_APPROVED`（2026-10-24 产品决策人签字确认）依据 `docs/review/pen-prototype-spec-2026-10-24.md` 头部状态标注与 §7 后续动作第 3 条；预览图为 `docs/review/pen-prototypes/06-批量新增标签Modal.png`。
- 画板与实现的有意差异已登记在画板登记表 `implementationDeltas`：「标签只能从标签库选，没有自由文本『标签名称』输入框」——对应 BR013 与 §2.1 的字段清单（画板的 `formGroups` 也只列了「标签类型」与「标签」两项）。
- 画板规格的 `footer` 为「取消 / 保存」，与实现的 `okText="保存"`、`cancelText="取消"` 一致（`PersonLabelPanel.tsx:280-281`）；`formGroups` 两组与实现的两个 `Divider` 分组一一对应（`:302`、`:321`）。
- 画板显示「生效日期（默认今天）」「来源（人工标记 / AI 生成）」，与实现一致（`:92-93`、`:322-329`）。
- 规范 §10.4 要求「显著不同的加载、空数据、失败、无权限和冲突状态应在原型中可Review」，这些状态目前只存在于实现（`PersonLabelPanel.tsx:243-262`、`:286-292`），没有对应的 Pencil 画板——见 §18 Q-01。

## 11. API与事件合同

### 11.1 同步API

| ID | 方法与路径 | 调用者 | 请求摘要 | 响应摘要 | 权限 | 幂等 | 事务边界 |
|---|---|---|---|---|---|---|---|
| WFC-LABEL-F002-API001 | `POST /api/v1/workforce/persons/{person_id}/labels/batch`（`labels_api.py:109-125`，201） | 批量新增标签 Modal | 路径参数 `person_id`（UUID）；请求体 `PersonLabelBatchCreate`：`effective_from`、`source`、`labels`（1–100 项，每项 `label_type_code` + `label_code`） | `PersonLabelBatchResponse`：`created`（`PersonLabelResponse[]`） | `WORKFORCE_ADMIN`；`*` 放行 | 不幂等：同组合第二次提交返回 409 `PERSON_LABEL_DUPLICATE`，不产生第二条记录 | 单请求单事务；标签行写入使用 savepoint（`labels_service.py:256-271`），标签行与审计行同事务提交或同事务回滚 |
| WFC-LABEL-F002-API002 | `GET /api/v1/workforce/label-library`（`labels_api.py:151-159`） | 宿主页签与本 Modal 的候选数据源 | 无查询参数 | `LabelLibraryListResponse`：`items`（`{type_code, type_name, items[]}`） | `WORKFORCE_ADMIN`；`*` 放行 | 天然幂等 | 单请求单事务 |
| WFC-LABEL-F002-API003 | `GET /api/v1/workforce/persons/{person_id}/labels`（`labels_api.py:40-60`） | 宿主页签（保存成功后重新加载） | 路径参数 `person_id`；查询参数 `effective_at`（可选） | `PersonLabelListResponse`：`items`、`total` | `WORKFORCE_ADMIN`；`*` 放行 | 天然幂等 | 单请求单事务 |

调用者与所有权说明：三个接口由 Workforce Core 模块提供（`apps/api/src/hris/modules/workforce/`）；标签库读取复用 Platform Kernel 的基础资料字典，本模块只读。前端调用封装在 `apps/web/src/business/features/people/label-api.ts:190-240`，认证统一使用 Bearer Token（`apps/web/src/business/client.ts`）。

### 11.2 异步事件与任务

`NOT_APPLICABLE`。依据：本功能的写路径（`labels_service.py:217-281`）只做数据库写入与审计写入，模块内没有消息发布或领域事件调用（`apps/api/src/hris/modules/workforce/labels_service.py` 全文件检索 `publish` / `emit` 无命中）；AI 来源只是手工选择的一个标识，没有 AI 生成或异步打标链路。若后续引入消息引擎（待确认清单 P-10～P-12）或 AI 标签生成链路，本功能是否需要发布「标签赋予」事件需重新评审并补写本节。

### 11.3 兼容与废弃

- 当前合同版本：v1。批量接口的路径与请求 / 响应字段自员工标签能力落地以来未变；本轮无接口变更。
- 向后兼容策略：请求提交的是「标签库编码」而不是「标签名称」，因此标签项改名不影响接口形状，只影响解析出的名称快照（`label_library.py:86-91`）。
- 废弃通知和截止版本：当前无废弃项。若后续把标签库从基础资料字典迁移到独立表，必须先在本节登记并同步 `docs/01-foundation/03-项目决策.md`（规范 §13 变更控制）。

## 12. 异常、并发与回退

| ID | 状态 | 场景 | 系统结果 | 用户提示/错误码 | 是否重试 | 补偿/回退 |
|---|---|---|---|---|---|---|
| WFC-LABEL-F002-ERR001 | `CONFIRMED` | 标签所属人员不存在 | 整批拒绝，不落任何数据 | 422 `PERSON_LABEL_PERSON_NOT_FOUND`「人员档案不存在，无法创建员工标签」（`labels_service.py:226-231`） | 否 | 不适用 |
| WFC-LABEL-F002-ERR002 | `CONFIRMED` | 批次内标签项重复，或条数超出 1–100，或来源非法 | 契约校验失败，整批不落数据 | 422 `REQUEST_VALIDATION_FAILED`，`details` 指明字段（`apps/api/src/hris/core/errors.py:41-61`） | 否——需改批次内容 | 不适用 |
| WFC-LABEL-F002-ERR003 | `CONFIRMED` | 请求体不满足 schema（字段缺失、类型错误） | 请求被拒 | 422 `REQUEST_VALIDATION_FAILED`「请求参数校验失败」 | 否 | 不适用 |
| WFC-LABEL-F002-ERR004 | `CONFIRMED` | 批次中任一标签在标签库中找不到（类型或标签项不存在、或已停用） | **整批拒绝**，不落任何数据 | 422 `PERSON_LABEL_LIBRARY_ITEM_NOT_FOUND`「标签库中不存在启用的标签项：{type}/{code}」（`label_library.py:116-121`） | 否——需重新选择标签 | 不适用——整批原子，无需补偿 |
| WFC-LABEL-F002-ERR005 | `CONFIRMED` | 批次与库中既有标签「人员 + 类型 + 名称 + 生效日 + 来源」重复 | **整批拒绝**，不落任何数据 | 409 `PERSON_LABEL_DUPLICATE`「同一人员、类型、名称、生效日期与来源的标签已存在」（`labels_service.py:248-253`） | 否——需改生效日期或去掉重复项 | 不适用——整批原子，无需补偿 |
| WFC-LABEL-F002-ERR006 | `CONFIRMED` | 标签库字典 `PERSON_LABEL_LIBRARY` 未初始化 | 整批拒绝 | 404 `PERSON_LABEL_LIBRARY_NOT_FOUND`「员工标签库尚未初始化，请在基础资料中创建标签库」（`label_library.py:130-135`） | 否——需先在基础资料中创建字典 | 不适用 |
| WFC-LABEL-F002-ERR007 | `CONFIRMED` | 无权限执行批量写入 | 请求被拒 | 403 `PERMISSION_DENIED`「没有执行此操作的权限」（`dependencies.py:80`） | 否 | 不适用 |
| WFC-LABEL-F002-ERR008 | `CONFIRMED` | 会话无效或过期 | 请求被拒 | 401 `AUTHENTICATION_REQUIRED` / `SESSION_INVALID`（`dependencies.py:32`、`:47`） | 重新登录后重试 | 不适用 |
| WFC-LABEL-F002-ERR009 | `CONFIRMED` | 两人同时给同一员工批量打同一批标签 | 两批各自执行去重预检；若两批的生效日不同则两条都落库（同日则后到者命中重复返回 409 `PERSON_LABEL_DUPLICATE`） | 前端展示后端 message（`PersonLabelPanel.tsx:184`） | 视错误码：409 需改生效日期后重试 | 无需补偿：失败批次整批未落库 |
| WFC-LABEL-F002-ERR010 | `CONFIRMED` | 批量写入过程中数据库异常 | savepoint 内的标签行全部回滚；同一请求内的审计行也随事务回滚，不落任何数据 | 前端展示「标签保存失败」（`PersonLabelPanel.tsx:184`） | 可在修复原因后重试 | 自动回滚（`labels_service.py:256-271`、`apps/api/src/hris/core/database.py:23-25`） |
| WFC-LABEL-F002-ERR011 | `CONFIRMED` | 提交瞬间已选标签被停用（前端与服务端之间的时间差） | 前端自检拦截，不发请求 | 「选中的标签已不在标签库中，请重新选择」（`PersonLabelPanel.tsx:173`） | 否——需重新选择 | 不适用 |
| WFC-LABEL-F002-ERR012 | `CONFIRMED` | 误打标签后的撤销 | 当前没有删除或撤销入口：只能逐个「结束」，历史标签永久保留 | 现状无对应提示 | — | 建议路径是逐个结束；见 §18 Q-07 |
| WFC-LABEL-F002-ERR013 | `CONFIRMED` | 后台任务中断 | `NOT_APPLICABLE`：本功能没有后台任务（依据 §11.2） | — | — | — |
| WFC-LABEL-F002-ERR014 | `CONFIRMED` | 下游系统失败 | `NOT_APPLICABLE`：本功能不调用外部系统（依据 §11.2） | — | — | — |
| WFC-LABEL-F002-ERR015 | `PENDING` | 批量打错标签后需要整批回退 | 当前没有「批量结束」入口，只能逐个结束；是否需要提供批量结束 | ERR012、§12 ERR012 | 产品决策人 | 企业 UAT 前 | 采用已实现行为：逐个结束 |

## 13. 审计与数据保护

| ID | 状态 | 动作 | 审计内容 | 禁止记录内容 | 保留要求 |
|---|---|---|---|---|---|
| WFC-LABEL-F002-AUD001 | `CONFIRMED` | 批量创建员工标签 | 每条标签一条审计行：`action=person_label.create`、`object_type=person_label`、`object_id=标签 id`、`reason=批量创建员工标签`、`before_payload={}`、`after_payload` 为标签业务字段快照、`actor_id`、`trace_id`、`source=api`（`labels_service.py:273-281`、`:417-440`） | **不写入人员姓名等个人信息**，只写 `person_id`（`labels_service.py:442-454`） | 审计行随 `audit_logs` 表保留，无删除入口 |
| WFC-LABEL-F002-AUD002 | `CONFIRMED` | 批量失败时不写审计 | 整批失败（解析失败、去重冲突、数据库异常）时不落任何标签行，也**不写**任何审计行 | — | — |
| WFC-LABEL-F002-AUD003 | `CONFIRMED` | 读取标签库 | 读取行为本身不产生审计行 | — | — |

- 敏感字段加密：`NOT_APPLICABLE`。依据：本功能写入的表 `person_labels` 没有任何个人敏感列（`models.py:351-379`），字段集合仅为人员 id、标签类型与名称、来源、生效区间、状态与 AI 标记；人员档案的加密要求属于 `docs/01-foundation/07-人员档案领域规范.md`。
- 页面脱敏：Modal 只展示标签类型、标签名称、生效日期与来源，不含个人敏感信息；人员姓名只出现在宿主 Drawer 的标题里（`PeopleWorkspace.tsx:307`），不进入标签接口。
- 明文访问：`NOT_APPLICABLE`。依据：本功能不存在「明文才能读取」的字段。
- 导出与临时文件：`NOT_APPLICABLE`。依据：本功能没有导出入口（`label-api.ts:190-240` 无下载调用），也不产生临时文件。
- 非生产数据：验收使用合成数据；现有自动化测试即采用合成 fixture（`apps/web/src/business/features/people/PersonLabelPanel.test.tsx`）。

## 14. 非功能需求

| ID | 状态 | 类别 | 可验证要求 | 环境/数据量 | 验证证据 |
|---|---|---|---|---|---|
| WFC-LABEL-F002-NFR001 | `CONFIRMED` | 性能 | 单次批量写入上限 100 条；savepoint 内一次 flush，整批一次事务提交 | 本机开发库 | `labels_service.py:25-26`、`:256-271` |
| WFC-LABEL-F002-NFR002 | `PENDING` | 性能 | 批量保存的响应时间目标 | 需要容量输入：本机并发用户数、单次批量条数、标签库项总数 | 缺容量输入，暂不可验收；输入模板见 `docs/input-packs/templates/07-capacity-scenarios.csv`，容量场景见 `docs/input-packs/09-nonfunctional-acceptance-input.md` |
| WFC-LABEL-F002-NFR003 | `CONFIRMED` | 可用性 / 可访问性 | 表单字段具备可见标签（「标签类型」「标签」「生效日期」「来源」）；分组标题用 `Divider` 明确分隔；必填项有中文提示文案 | 键盘与屏幕阅读器人工检查 | `PersonLabelPanel.tsx:302-330` |
| WFC-LABEL-F002-NFR004 | `CONFIRMED` | 兼容 | 页面使用仓库锁定的 Ant Design 6.5.2 组件，不使用已废弃属性 | 生产构建 `npm run build` | D-090；`docs/design/antd-page-interaction-standard.md` §2；`node scripts/check-antd-usage.mjs` 0 违规 |
| WFC-LABEL-F002-NFR005 | `CONFIRMED` | 复用 | Modal 内的错误提示统一使用 `WorkspaceError`，不在本能力域内出现第二套写法 | 全站一致性 | D-091；`PersonLabelPanel.tsx:16-17`、`:286-292` |
| WFC-LABEL-F002-NFR006 | `CONFIRMED` | 可观测 | 每次请求返回 `trace_id`，每条新建标签的审计行 `trace_id` 与响应一致 | 本机开发库 | `apps/api/src/hris/core/errors.py:24-38`、`labels_service.py:417-440`、`models.py:997` |
| WFC-LABEL-F002-NFR007 | `CONFIRMED` | 安全 | 页面与审计载荷都不写入人员姓名等个人信息；写入受 `WORKFORCE_ADMIN` 约束 | 本机开发库 | §9 权限表、§13 AUD001 |
| WFC-LABEL-F002-NFR008 | `CONFIRMED` | 可靠性 | 批量写入是整批原子：任一条失败则本批零落库，且不产生半截审计记录 | 本机开发库 | `labels_service.py:222-225`、`:256-281`；AC004、AC005、AC006 |

## 15. 验收场景

### WFC-LABEL-F002-AC001 从标签库多选并按类型筛选

- 类型：正常
- 前置数据：标签库中有 2 个启用中的类型，各有若干启用中的标签项。
- Given：维护者在「批量新增标签」Modal 的标签类型下拉选择其中一个类型。
- When：下拉选择生效。
- Then：标签多选的候选只剩该类型下的标签项；标签多选为必填，未选时保存报「请至少选择一个标签」；标签类型下拉可清空（清空后候选回到全部类型）。
- 数据库/事件/审计证据：无数据写入，无审计行。
- 自动化层级：前端单元测试 + 后端集成测试。

### WFC-LABEL-F002-AC002 表单初值与来源枚举

- 类型：正常
- 前置数据：账号具备 `WORKFORCE_ADMIN`。
- Given：维护者打开 Modal，然后取消，再次打开。
- When：观察表单。
- Then：两次打开都是空表单：标签类型过滤为空、已选标签为空、来源默认「人工标记」、生效日期默认打开当天；来源下拉只有「人工标记」「AI 生成」两项。
- 数据库/事件/审计证据：无数据写入。
- 自动化层级：前端单元测试。

### WFC-LABEL-F002-AC003 保存后整批生效且 AI 标记由来源推导

- 类型：正常
- 前置数据：某员工无标签；标签库中有启用中的「技能 / 核心开发」与「关键岗位 / 技术骨干」。
- Given：维护者选中「核心开发」「技术骨干」，来源选「AI 生成」，生效日期设为今天。
- When：点击「保存」。
- Then：请求为 `POST /api/v1/workforce/persons/{person_id}/labels/batch`，载荷为 `{effective_from, source: "AI", labels: [{label_type_code, label_code}, ...]}`；返回 201 且 `created` 长度为 2；两条标签的 `source` 为 `AI`、`is_ai_generated` 为 `true`、`effective_to` 为 `null`、`status` 为 `active`。
- 数据库/事件/审计证据：`person_labels` 新增 2 行；审计中新增 2 条 `action=person_label.create`、`reason=批量创建员工标签` 的记录。
- 自动化层级：后端集成测试 + 前端单元测试。

### WFC-LABEL-F002-AC004 业务规则拒绝——标签不在标签库中则整批不落数据

- 类型：异常 / 规则拒绝
- 前置数据：标签库中某标签项已停用（`is_active=false`）。
- Given：维护者在前端选中该标签项并提交。
- When：请求到达服务端。
- Then：返回 422 `PERSON_LABEL_LIBRARY_ITEM_NOT_FOUND`；`person_labels` 行数不变；审计中**没有**新增 `person_label.create` 记录。
- 数据库/事件/审计证据：`select count(*) from person_labels` 与调用前一致。
- 自动化层级：后端集成测试。

### WFC-LABEL-F002-AC005 业务边界——批次条数与批次内重复

- 类型：边界 / 规则拒绝
- 前置数据：账号具备 `WORKFORCE_ADMIN`。
- Given：提交 101 条标签；再提交 2 条完全相同的标签项。
- When：请求到达服务端。
- Then：两次都返回 422 `REQUEST_VALIDATION_FAILED`（前者是条数超限，后者是批次内重复）；`person_labels` 行数不变。
- 数据库/事件/审计证据：无数据写入，无审计行。
- 自动化层级：后端集成测试。

### WFC-LABEL-F002-AC006 业务规则拒绝——与既有标签重复则整批不落数据

- 类型：异常 / 规则拒绝
- 前置数据：该员工已有一条「技能 / 核心开发 / 生效日今天 / MANUAL」的标签。
- Given：维护者再次提交同样的组合（可与另一条不重复的标签同批）。
- When：请求到达服务端。
- Then：返回 409 `PERSON_LABEL_DUPLICATE`；**整批**不落数据（同批的另一条标签也不落库）；审计中**没有**新增 `person_label.create` 记录。
- 数据库/事件/审计证据：`person_labels` 行数与调用前一致。
- 自动化层级：后端集成测试。

### WFC-LABEL-F002-AC007 业务规则拒绝——人员不存在

- 类型：异常 / 规则拒绝
- 前置数据：一个不存在的人员 id。
- Given：维护者对该人员提交批量打标签。
- When：请求到达服务端。
- Then：返回 422 `PERSON_LABEL_PERSON_NOT_FOUND`；不落任何数据。
- 数据库/事件/审计证据：`person_labels` 行数不变，无审计行。
- 自动化层级：后端集成测试。

### WFC-LABEL-F002-AC008 审计证据核对——每条标签一条审计且不含个人信息

- 类型：审计
- 前置数据：维护者具备 `WORKFORCE_ADMIN`；一次批量赋予 3 条标签。
- Given：批量保存成功。
- When：查看审计记录。
- Then：`audit_logs` 新增 3 行，`action` 均为 `person_label.create`、`object_type` 均为 `person_label`、`reason` 均为「批量创建员工标签」；每行的 `after_payload` 只含 `person_id`、`label_type`、`label_name`、`source`、`status`、`effective_from`、`effective_to`、`is_ai_generated`，**不含**人员姓名。
- 数据库/事件/审计证据：`audit_logs` 查询结果。
- 自动化层级：后端集成测试。

### WFC-LABEL-F002-AC009 前端提交前的标签库自检

- 类型：边界
- 前置数据：维护者已选中一个标签项，随后该标签项在标签库中被停用（模拟提交瞬间的变化）。
- Given：维护者点击「保存」。
- When：前端组装载荷时。
- Then：前端自检发现已选标签不在标签库中，报「选中的标签已不在标签库中，请重新选择」，**不发出**写请求；Modal 保持打开并保留输入。
- 数据库/事件/审计证据：无数据写入，无审计行。
- 自动化层级：前端单元测试。

### WFC-LABEL-F002-AC010 权限——无 `WORKFORCE_ADMIN` 时不可写入

- 类型：权限
- 前置数据：账号不持有 `WORKFORCE_ADMIN` 与 `*`。
- Given：该账号直接调用批量接口。
- When：请求到达服务端。
- Then：返回 403 `PERMISSION_DENIED`；不落任何数据，不写审计行；页面上「员工标签」页签不挂载、「新增标签」按钮不存在。
- 数据库/事件/审计证据：无数据写入，无审计行。
- 自动化层级：后端集成测试 + 前端单元测试。

### WFC-LABEL-F002-AC011 失败反馈——Modal 保持打开并保留输入

- 类型：异常
- 前置数据：维护者在 Modal 中已选好标签、生效日期与来源。
- Given：服务端返回 409 `PERSON_LABEL_DUPLICATE`。
- When：错误回到前端。
- Then：Modal 保持打开；已选标签、生效日期与来源都还在；Modal 顶部出现可关闭的错误条，错误文案为服务端 message。
- 数据库/事件/审计证据：无数据写入。
- 自动化层级：前端单元测试。

### WFC-LABEL-F002-AC012 后台任务中断与下游失败

- 类型：异常
- 前置数据：无。
- Given：审查本功能的写路径。
- When：检查是否存在异步任务或外部依赖调用。
- Then：不存在——写路径只有数据库写入与审计写入（`labels_service.py:217-281`，模块内无 `publish` / `emit` 调用），因此没有任务中断或下游失败场景需要验收。
- 数据库/事件/审计证据：不适用。
- 自动化层级：人工 UAT（代码核对，核对点已记录在 §11.2）。

## 16. 迁移、发布与回滚

- 现有数据影响：本功能管理的 `person_labels` 表已存在于本机库，本轮无结构变更、无数据迁移。
- 数据迁移与校验：不适用——标签只能通过页面赋予；标签库的初始化由「基础资料」工作区负责（`f2c000000001_seed_person_label_library.py`）。
- 功能开关或模块启用：没有功能开关；页签挂载按 `WORKFORCE_ADMIN` 判定（`PeopleWorkspace.tsx:339-347`）。
- 发布顺序：后端接口已在库；前端 Modal 随 Web 构建发布。页面依赖 `GET /persons/{id}/labels`、`GET /label-library`、`GET /label-types` 三个既有接口与 `POST /persons/{id}/labels/batch`，发布不改变接口合同。
- 升级兼容：请求提交标签库编码而非名称，标签项改名不影响接口形状；既有标签数据不受影响。
- 应用回滚：前端回滚到上一构建即可，接口未变更；后端回滚不涉及本功能的迁移。
- 数据不可逆时的恢复或前向修复：标签行只增不删，回滚不会删除数据；误打标签只能逐个结束（见 §12 ERR012 与 §18 Q-07）。

## 17. 可观测与运行手册

- 指标：本功能不新增业务指标。现有可观测项：接口调用量与错误码分布（403 / 404 / 409 / 422）、批量写入条数（响应 `created` 长度）。
- 日志和Trace：每次请求带 `trace_id`（`apps/api/src/hris/core/errors.py:24-38`），每条新建标签的审计行 `trace_id` 与之对应（`labels_service.py:273-281`）；排查一次具体批量操作时，用 `trace_id` 关联审计记录与请求日志。
- 告警：本功能不定义专属告警；接口 5xx 与事务回滚沿用平台内核既有告警口径。
- 后台任务：无（依据 §11.2）。
- 人工补偿：批量失败时整批回滚，不留半截数据（`labels_service.py:256-271`），无需人工补偿；业务纠错通过逐个结束前向修正（§16）。
- 健康检查：Modal 可用性依赖 `GET /api/v1/workforce/label-library` 与 `POST /api/v1/workforce/persons/{id}/labels/batch` 的可用性（`label-api.ts:203-205`、`:222-237`）。

## 18. 待确认问题

| ID | 问题 | 影响规则/场景 | Owner | 期望日期 | 不确认时的处理 |
|---|---|---|---|---|---|
| WFC-LABEL-F002-Q01 | 待确认清单 **P-15**「画板通过后是否即授权前端按画板开发/替换」：是否确认把画板 `FmBa4` 的 Review 状态从 `DRAFT_FOR_REVIEW` 改为 `PROTOTYPE_APPROVED`。**2026-10-24 产品决策人已确认全部画板并签字**，§10.4 状态升级为 `PROTOTYPE_APPROVED` | §10.1 原型状态、§10.4 PROT001、§19 T002、AC001–AC012 的页面形态验收 | 产品决策人 | 2026-10-25 | 已关闭：2026-10-24 产品决策人签字确认画板，规范 §10.2 的前端开发门禁解除，本功能可按画板继续开发|
| WFC-LABEL-F002-Q02 | 待确认清单 **P-16**「`docs/requirements/` 模块功能需求文档」：本文件是本批次建立的第六份功能文档；标签能力是否还需要「标签库管理」「全局标签检索」「批量结束」三份独立文档 | §19 T001 的范围界定、§2.2 | 产品决策人 | 2026-10-25 | 采用已实现行为：这三项当前都没有页面入口，不为其建文档；相应问题按 WFC-LABEL-F001 的 Q02、Q05 登记 |
| WFC-LABEL-F002-Q03 | 标签类型下拉是否应改为必填：当前它是筛选器，不选类型也能从全部类型里选标签 | BR011、AC001 | 产品决策人 | 2026-10-25 | 采用已实现行为：类型可空，作为候选过滤器 |
| WFC-LABEL-F002-Q04 | AI 来源的语义：当前「AI 生成」只是人工选择的一个来源标识，没有 AI 生成链路；企业是否要求自动推荐或自动打标 | ASM-05、BR015、§11.2 | 产品决策人 + 企业输入方 | 企业标签体系交付时 | 采用已实现行为：AI 只作为来源标识，不新增生成链路 |
| WFC-LABEL-F002-Q05 | 是否需要「按人员分组批量打标签」（一次给多个人打同一批标签）：当前接口只接受单个人员 id | BR016、§2.2 | 产品决策人 | 企业 UAT 前 | 采用已实现行为：接口只接受单个人员 id，不扩展 |
| WFC-LABEL-F002-Q06 | 高风险写操作是否需要二次确认：批量打标签是不可删除的数据变更（只能结束），当前没有 Popconfirm | §10.3 | 产品决策人 | 2026-10-25 | 采用已实现行为：不做二次确认 |
| WFC-LABEL-F002-Q07 | 是否需要「批量结束」入口用于撤销一次误操作：当前只能逐个结束 | ERR012、ERR015、§16 | 产品决策人 | 企业 UAT 前 | 采用已实现行为：逐个结束，不做批量结束 |
| WFC-LABEL-F002-Q08 | 单次批量的条数上限 100 是否符合企业实际使用规模（一个员工一次打超过 100 个标签是否现实） | BR003、NFR001 | 产品决策人 + 企业输入方 | 企业 UAT 前 | 采用已实现行为：上限 100，前端不做额外限制提示 |

## 19. 开发任务与追踪

| 任务ID | 目标 | 依赖 | 文件/模块所有权 | 需求追踪注释 | 验收场景 | 状态 | 交付证据 |
|---|---|---|---|---|---|---|---|
| WFC-LABEL-F002-T001 | 按《模块功能需求文档规范》建立批量新增标签功能需求文档，登记 Pencil 画板 `FmBa4`、字段合同、权限、错误码与验收场景 | 无 | 仅新增 `docs/requirements/WFC-workforce-core/WFC-label/WFC-LABEL-F002-batch-label-create-modal.md` | 文档头部登记规范 17 号；正文引用 HR-LABEL-001～015 / ADR-0002 / D-067 / D-068 / D-069 / D-090 / D-091 / P-15 / P-16 | AC001–AC012 的判定依据 | `IN_REVIEW` | 本文件（v0.1，2026-10-24） |
| WFC-LABEL-F002-T002 | 前端按已批准画板 `FmBa4` 对齐批量新增标签 Modal | WFC-LABEL-F002-Q01（画板签字，`PROTOTYPE_APPROVED`） | `apps/web/src/business/features/people/PersonLabelPanel.tsx`、`label-api.ts` | 在规则落点写 `Requirement: WFC-LABEL-F002-BRnnn — 原因` | AC001、AC002、AC003、AC009、AC011 | `READY`（2026-10-24 画板已签字，规范 §10.2 的前端开发门禁解除，按画板继续对齐） | — |
| WFC-LABEL-F002-T003 | 为批量写入补「按人员分组」的批量结束能力 | WFC-LABEL-F002-Q07 | `apps/api/src/hris/modules/workforce/labels_api.py`、`labels_service.py`、`apps/web/src/business/features/people/PersonLabelPanel.tsx` | `Requirement: WFC-LABEL-F002-ERR012 / ERR015 — 原因` | AC003、AC006 | `BLOCKED`（阻塞原因：Q07 未拍板；新增写接口会改变审计与权限面） | — |

## 20. Review与批准记录

| 版本 | 日期 | 变更摘要 | 产品/业务结论 | 技术结论 | 批准人 |
|---|---|---|---|---|---|
| v0.1 | 2026-10-24 | 初稿：按 17 号规范建立批量新增标签功能需求文档；登记 Pencil 画板 `FmBa4`（初稿状态 `DRAFT_FOR_REVIEW`）；逐条对齐后端合同（字段、接口、权限码、错误码）与前端实现文案 | 已由产品决策人 Review 并签字，状态升级为 `PROTOTYPE_APPROVED`（Q01） | 字段、接口、权限与错误码全部指向实现文件与行号，未发明后端不存在的字段；「整批原子」语义已按实现原文登记，未弱化为部分成功 | 已批准（2026-10-24 产品决策人签字） |

现状说明（按事实记录）：

- 2026-10-24 用户已指示「按画板开发或替换已有的界面」，前端据此先行实现了该 Modal，并已获授权先行实现。
- 画板已于 **2026-10-24** 经产品决策人签字确认，§10.4 的 Review 状态升级为 `PROTOTYPE_APPROVED`。
- 在 Q01 关闭之前，按规范 §10.2 与 D-087，不得为本功能创建新的前端开发任务（T002 状态为 `BLOCKED`）。

### 20.1 规范 §15 文档 Review 检查表自查（2026-10-24）

| # | 检查项 | 自查结论 | 依据 |
|---|---|---|---|
| 1 | 文档是否只描述一个可独立验收的功能 | 是 | 全文只描述「一次性给一个员工批量赋予来自标签库的标签」；页签的读取与结束、标签库管理、全局检索各自独立（§2.2、§3） |
| 2 | 是否能明确说出谁在什么条件下得到什么结果 | 是 | §3 参与者表（主管理员 / 人力编制维护者 / 无权限账号 / 未登录账号）+ §5 四条用户故事的触发条件、前置条件、主路径、结束状态 |
| 3 | 是否区分确认规则、待确认问题和推荐方案 | 是 | §7 规则表带 `CONFIRMED` / `PENDING` 状态列并写明状态约定；§18 全部为待确认项并给出「不确认时的处理」；本文件未代替产品决策人做结论 |
| 4 | 数据所有者、唯一键、有效日期和历史策略是否明确 | 是 | §8.1 数据所有权、五元组与批次内两组唯一性、生效区间与展示快照语义；§8.2 每行含「历史策略」列 |
| 5 | 是否覆盖动作、数据范围、字段和高风险操作 | 是 | §9 PERM001–PERM005 覆盖写 / 读候选 / 按钮可见性 / 页签挂载 / 403 拒绝结果；高风险操作的二次确认缺口在 §10.3 与 Q-06 显式登记 |
| 6 | 接口是否明确幂等、事务、版本和失败补偿 | 是 | §11.1 三个接口逐个写明幂等性与事务边界（批量写入用 savepoint）；§12 覆盖重复、并发、异常与回退；§11.2 说明无异步事件及依据 |
| 7 | 是否覆盖异常、并发、回退、审计和敏感数据 | 是 | §12 ERR001–ERR015；§13 AUD001–AUD003 及加密、脱敏、明文访问、导出、非生产数据逐项结论；撤销缺口在 ERR012 / Q-07 登记 |
| 8 | NFR是否可以在指定环境中验证 | 部分通过 | NFR001、NFR003–NFR008 可在指定环境验证并给出证据；NFR002（批量保存响应时间）因缺容量输入标记 `PENDING`，已在 §14 写明需要的输入文件与验收环境 |
| 9 | 验收场景是否包含明确输入、动作和预期证据 | 是 | §15 AC001–AC012，每条含类型、前置数据、Given / When / Then、数据库或审计证据、自动化层级 |
| 10 | 是否可以在不猜业务规则的情况下拆出最小任务 | 是 | §19 三个任务均声明所有权、依赖、追踪注释与验收场景；两个任务因 Q01 / Q07 未决而 `BLOCKED`，未把 PENDING 规则写进任务 |
| 11 | 是否说明对已有数据、模块和部署的影响 | 是 | §16 覆盖现有数据影响、迁移与校验、开关、发布顺序、升级兼容、应用回滚与前向修复；§4 列出标签库与人员档案的引用关系 |
| 12 | 是否存在与父级PRD或已确认决策冲突的内容 | 是（无冲突） | 载体选择符合 D-068 / D-069 与交互载体规范 §3（画板标题也写明「D-068 v1.0」）；组件复用符合 D-091；标签库模型符合 ADR-0002 / D-067；原型门禁符合 D-087 |
| 13 | 所有需求驱动的代码变化是否明确了追踪注释所引用的ID和预计代码落点 | 是 | §19 T002、T003 写明 `Requirement: WFC-LABEL-F002-BRnnn / ERRnnn — 原因` 及预计落点文件；本轮不产生代码变化 |
| 14 | 涉及前端时，是否明确宿主页、`MODAL`/`DRAWER`/`NEW_TAB`载体及其打开、退出和状态恢复行为 | 是 | §10.1 宿主页=人员中心列表、主载体=`MODAL`（宽 520，嵌套在员工档案 Drawer 内）、选择理由、hash 路由 `#people`、关闭后回到宿主页签；§10.3 打开 / 关闭 / 焦点 / 重置策略 |
| 15 | 涉及前端时，是否登记Pencil文件、画板ID、版本和`PROTOTYPE_APPROVED`证据 | 通过 | §10.4 已登记 Pencil 源文件、画板 ID `FmBa4`、画板名称、版本 `v1.0`、嵌套宿主画板 `BUE0c` 与状态；`PROTOTYPE_APPROVED` 证据**已存在**（2026-10-24 产品决策人签字确认）；原缺口 Q01 登记 |

自查结论汇总：15 项中 14 项通过，1 项为「部分通过」——第 8 项因缺容量输入把 NFR002 标为 `PENDING`（不是编造）；第 15 项已随 2026-10-24 画板签字补齐 `PROTOTYPE_APPROVED` 证据。按规范 §15 末句「任一关键项为否时，不得进入 `READY_FOR_TASKS`」，本功能当前状态仍保持 `DRAFT`（余下 1 项为第 8 项 NFR002 容量输入待补），画板门禁已不再是阻塞项。
