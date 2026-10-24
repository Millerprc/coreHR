# WFC-ROSTER-F001 历史花名册

> 模块：WFC / Workforce Core
> 能力域：WFC-ROSTER / 历史花名册（按任意历史时点回看员工名册）
> 状态：`DRAFT`
> 版本：v0.2
> 产品Owner：MillerMax（产品决策人）
> 业务Owner：产品决策人 MillerMax 兼任（依据 `docs/01-foundation/03-项目决策.md` D-066「用户负责业务规则、优先级和最终UAT确认」）
> 上级需求：[16-coreHR产品总体PRD](../../../01-foundation/16-coreHR产品总体PRD.md)；[Moka 五项功能复刻语义决策](../../../review/moka-5-feature-decisions-2026-10-24.md) §1（D-102）；[Moka 与 coreHR 功能差距对照](../../../review/moka-vs-corehr-feature-gap.md) §3.12 ①
> 依赖功能：[WFC-PEOPLE-F001 人员档案](../WFC-people/WFC-PEOPLE-F001-person-profile.md)（人员【编辑 / 修正】语义见 D-105；本功能只读复用其修正版本表）；组织与职务的生效日期版本（`organization_versions` / `job_catalog_versions`）
> 最后更新：2026-10-24

## 1. 背景与期望结果

- 当前问题：花名册相关的 9 张表里已有 8 张完成生效日期化（`employments`、`employment_assignments`、`organization_versions`、`job_catalog_versions` 等），但对外只暴露「当前」视图；Moka 的「历史花名册」可以按任意时点回看当时的员工名册与当时的信息，coreHR 缺这一层查询。
- 用户价值：HR 可以在复核编制、核对历史汇报关系、追溯某时点在册人员时，按生效日期取数，而不是靠人记得当时的组织归属与姓名。
- 本功能完成后可观察的业务结果：
  1. 侧栏「人员中心」之后出现「历史花名册」入口（`apps/web/src/business/navigation.ts:74-80`，权限码 `PERSON_VIEW`），点击进入独立列表页（`apps/web/src/business/AppShell.tsx:307-309`）。
  2. 选择「查看日期」后，表格给出该时点的在册员工：工号、姓名（时点）、主组织（时点）、职位（时点）、在职状态（时点）、入职日期（时点）六列 + 操作列（`apps/web/src/business/features/workforce/HistoricalRosterWorkspace.tsx:233-281`）。
  3. 每行「查看时点信息」抽屉列出该行时点字段与「修正过的字段」，无修正时显示「无（该时点字段值等于当前登记值）」（`HistoricalRosterWorkspace.tsx:293-322`）。
  4. 页面顶部固定提示条写明「时点的人员字段值 = 登记值 + 生效日期不晚于该时点的最后一条修正；未被修正过的字段等于当前值。」（`HistoricalRosterWorkspace.tsx:20-21`、`:178`），接口响应顶层同步返回 `field_history_note`（`apps/api/src/hris/modules/workforce/historical_roster_service.py:49-52`）。
- 决策依据：D-102（`docs/01-foundation/03-项目决策.md` §8.5）确认「允许按任意历史时点查询；不新建第二套人员版本表」；实现依据见 `docs/review/moka-5-feature-decisions-2026-10-24.md` §1.3–§1.5。
- 不做本功能的影响：历史时点的名册只能靠线下导出与人工回忆，且无法解释「当时这个人叫什么、在哪个部门」。

## 2. 范围

### 2.1 纳入范围

- 读接口 `GET /api/v1/workforce/people/roster-history`（`apps/api/src/hris/modules/workforce/historical_roster_api.py:74-104`、`historical_roster_service.py:92-173`）。
- 独立列表页「历史花名册」，入口在侧栏「人员中心」之后（`apps/web/src/business/features/workforce/HistoricalRosterWorkspace.tsx`，导航登记 `apps/web/src/business/navigation.ts:74-80`）。
- 服务端筛选（工号 / 时点姓名、主组织、在职状态）与服务端分页（`historical_roster_service.py:119-149`、`:151-168`）。
- 字段级时点取值：主档登记值 + 生效日期 ≤ 该时点的最后一条修正（`historical_roster_service.py:389-416`）。
- 行内「查看时点信息」抽屉：展示该行时点字段与「修正过的字段」（`HistoricalRosterWorkspace.tsx:293-322`）。
- 「不是完整历史回放」的限制在接口层、界面层、文档层三处同时表达（见 §7 限制说明）。
- 本功能的 Pencil 画板登记（见 §10.4）。

### 2.2 不纳入范围

- 不新建第二套人员版本表（D-102）；`persons` 主档仍是人员基础信息的登记值来源。
- 不做写操作：本功能只有读接口，不提供修正、补录或导出（`historical_roster_api.py` 全文件只定义 1 组 GET）。
- 不做导出与批量动作：Moka 花名册的「导出 / 对比 / 批量」等其余动作本轮未实现（画板登记表 `implementationDeltas` 第 3 条），需要时另立项，见 §18 Q07。
- 不做「完整历史回放」：未被修正过的人的时点姓名 / 证件等于当前值（见 §7 限制说明）。
- 不做「按历史组织树筛选」：主组织下拉取当前组织树，历史时点已撤销的组织不在选项里，见 §18 Q02。
- 不改组织架构的 `as_of` 规则：组织树端点已按 D-103 支持 `as_of`（当前与历史时点；未来时点返回 422 `CURRENT_OR_HISTORY_TREE_ONLY`，`apps/api/src/hris/modules/workforce/organization_api.py:127-155`），本功能不改变该端点行为。
- 不做人员敏感子记录展示：接口不返回证件号、联系方式等敏感记录（`historical_roster_api.py:15-17`）。
- 不做人员中心、员工档案 Drawer、编制管理等其它工作区的页面需求（各自独立成功能文档）。

### 2.3 假设与约束

| ID | 状态 | 内容 | 假设不成立时的处理 |
|---|---|---|---|
| ASM-01 | `CONFIRMED` | `as_of` 必填，格式 `YYYY-MM-DD`；缺失或格式非法一律 422 `REQUEST_VALIDATION_FAILED`（`historical_roster_api.py:78`；`apps/api/tests/integration/test_historical_roster_api.py:186-210`） | 不得改为可选；「查今天」由前端默认填充 `as_of` 表达（`HistoricalRosterWorkspace.tsx:80-82`），不改变接口必填语义 |
| ASM-02 | `CONFIRMED` | 允许未来日期：未来时点没有数据时返回 200 + 空列表，不是 422（`historical_roster_api.py:87`、`:110-111`；`historical_roster_service.py:110-111`） | 与组织架构 `as_of` 的规则不同（D-013 / D-103：未来时点组织树返回 422）；两套规则不得互相套用 |
| ASM-03 | `CONFIRMED` | 读权限只要求 `PERSON_VIEW`，不要求 `PERSON_SENSITIVE_VIEW`（`historical_roster_api.py:40`、`:15-17`） | 若企业要求同时持有 `PERSON_SENSITIVE_VIEW`，须改 `historical_roster_api.py:40` 的依赖声明并重写只读角色验收；不得在前端单方面放开 |
| ASM-04 | `CONFIRMED` | 字段级历史只覆盖「被修正过的字段」；未被修正过的字段等于当前登记值（`historical_roster_service.py:47-52`、`:395-399`；`person_corrections_service.py:105-124`） | 若要提供完整历史回放，须新建独立的「人员字段历史」表并另立项，见 §18 Q01 |
| ASM-05 | `PENDING` | 企业是否接受「未被修正过的字段等于当前值」作为长期口径尚未拍板 | 采用已实现行为：保持当前口径并在界面明说，见 §18 Q01 |
| ASM-06 | `PENDING` | 主组织筛选的选项来源（当前组织树 / 历史时点组织树）尚未拍板 | 采用已实现行为：下拉取当前组织树，见 §18 Q02 |
| ASM-07 | `CONFIRMED` | 主组织下拉的数据源是 `GET /api/v1/organizations/tree`，该端点要求 `ORGANIZATION_VIEW`；缺该权限时下拉静默为空，名册列表仍可读（`apps/web/src/business/features/workforce/api.ts:159-160`；`HistoricalRosterWorkspace.tsx:131-136`；`organization_api.py:46-49`） | 只持 `PERSON_VIEW` 的账号可以读名册但没有组织下拉；是否为花名册单独开候选端点见 §18 Q04 |

## 3. 参与者、权限边界和业务场景

| 参与者 | 目标 | 前置权限 | 数据范围 |
|---|---|---|---|
| 主管理员 | 按任意时点回看名册 | `*`（`apps/api/src/hris/modules/platform/dependencies.py:93` 对 `*` 短路放行） | 全部在册人员；本模块无行级数据范围 |
| 人事 / 编制查看者 | 按时点核对在册人员与当时的组织归属 | `PERSON_VIEW`（`historical_roster_api.py:40`） | 全部在册人员；无行级过滤 |
| 组织查看者 | 在主组织下拉中看到当前组织 | `ORGANIZATION_VIEW`（`organization_api.py:46-49`） | 当前组织树；与名册读取是两套权限，互不替代 |
| 未登录 / 会话失效访问者 | —— | 无有效会话 | 401 `AUTHENTICATION_REQUIRED` / `SESSION_INVALID`（`dependencies.py:35`、`:50`） |

场景边界说明：本功能只有一个业务结果——「按任意历史时点回看在册员工名册与当时信息」。筛选、分页与行内抽屉是同一结果的不同操作深度，不拆成多个功能；写操作（人员修正、补录）属于 WFC-PEOPLE-F001，不在本功能内。

## 4. 名词与依赖

### 4.1 名词表

| 名词/依赖 | 定义或引用 | 数据所有者 |
|---|---|---|
| 时点（as_of） | 业务日期，格式 `YYYY-MM-DD`；前端默认今天（`HistoricalRosterWorkspace.tsx:73-82`） | —— |
| 登记值（主档） | `persons` 表当前登记的人员基础信息；`persons` 未版本化（`docs/review/moka-vs-corehr-feature-gap.md` §3.12 ①） | Workforce Core（`apps/api/src/hris/modules/workforce/models.py:327-352`） |
| 字段级修正 | `person_field_versions` 行，含 `field_code`、`effective_from`、`new_value`、`version`；由人员档案的【修正】动作写入（D-105） | Workforce Core（`workforce/models.py`） |
| 生效区间 | 区间化表的 `[effective_from, effective_to)` 左闭右开；`effective_to` 为空表示当前有效 | Workforce Core |
| 在册（雇佣） | `employments` 行：计划入职日 ≤ as_of、雇佣未结束、状态不是 `withdrawn` / `terminated`（`historical_roster_service.py:69`、`:113-118`） | Workforce Core（`workforce/models.py:660-678`） |
| 主组织 / 职位（时点） | 该时点有效的 `employment_assignments` 行中 `relation_type = 'primary'` 的组织与职务（`historical_roster_service.py:245-246`） | Workforce Core |
| 姓名（时点） | 登记姓名 + 生效日期 ≤ as_of 的最后一条 `display_name` 修正；无修正时等于登记姓名（`historical_roster_service.py:175-207`） | Workforce Core |
| 历史花名册 | 本功能的结果集；**不是完整历史回放**（见 §7 限制说明） | —— |

### 4.2 时点取值口径（唯一口径）

```text
人员字段时点值(person, field, as_of)
  = persons 主档值（登记值）
    若存在 person_field_versions 记录 v 满足 v.effective_from <= as_of
      取其中 effective_from 最大的一条 v 的 v.new_value
    否则取主档值

组织 / 雇佣 / 任职时点值
  = 区间化表中 effective_from <= as_of AND (effective_to IS NULL OR effective_to > as_of) 的记录
```

代码落点（2026-10-24 逐条回代码复核，函数名与行号均仍然成立）：

| 口径 | 实现位置 |
|---|---|
| 区间化表筛选 | `historical_roster_service.py:58-62` `interval_filters()`：`effective_from <= as_of` 且（`effective_to` 为空或 `effective_to > as_of`） |
| 在册口径（雇佣） | `historical_roster_service.py:113-118` `roster()` 的 `employment_conditions`（`Employment.planned_start_date <= as_of`、`end_date` 为空或 `>= as_of`、`status not in ('withdrawn','terminated')`）；`_build_rows()` 内同一口径在 `:218-226` 再写一次，保证「显示的在职状态就是被筛选的那个状态」 |
| 字段修正取值 | `historical_roster_service.py:389-416` `_field_overrides()`，直接复用 `person_corrections_service.PersonCorrectionService.effective_overrides()`（`person_corrections_service.py:105-124`，按 `(effective_from, version)` 升序取最后一条），保证与人员档案给出同一个时点结果 |
| 时点姓名（用于搜索） | `historical_roster_service.py:175-207` `_time_point_display_name()`：用 `CASE` 区分「有修正」与「无修正」，修正把姓名清空时不会被当成没有修正 |
| 组织名 / 职务名的时点值 | `historical_roster_service.py:336-358` `_organization_names()` / `:370-387` `_job_names()`：取该时点有效的 `organization_versions` / `job_catalog_versions`（`version` 倒序取第一条） |
| 组织 / 职务编码 | `historical_roster_service.py:324-334` `_organization_codes()` / `:360-368` `_job_codes()`：取 `organizations.code` / `job_catalog.code` 主档编码，不随时点变化 |

口径与实现的已知差异（按事实记录，不做美化）：

- 决策文档 `docs/review/moka-5-feature-decisions-2026-10-24.md` §1.4 的伪代码把「组织 / 雇佣 / 任职」统一写成区间式过滤；实现中只有**区间化表**（`employment_assignments`、`organization_versions`、`job_catalog_versions`）用区间式，**`employments` 本身不是区间表**，结束日沿用编制域的 `end_date >= as_of`（`historical_roster_service.py:54-57` 的注释已显式说明该差异）。
- 区间式过滤在本功能取严格大于（`effective_to > as_of`），与编制域 `_count_people` 的 `effective_to >= as_of` 不同；边界日以本功能的决策口径为准（`historical_roster_service.py:54-57`）。

### 4.3 依赖与引用方

- 上游数据表：`persons`、`employments`、`employment_assignments`、`organizations`、`organization_versions`、`job_catalog`、`job_catalog_versions`、`person_field_versions`（`historical_roster_service.py:34-43` 的导入清单）。
- 复用服务：`PersonCorrectionService.effective_overrides()`（`person_corrections_service.py:105-124`）——花名册与人员档案共用同一份时点取值实现，避免两处口径漂移。
- 前端复用组件：`WorkspaceShell`、`FilterBar`、`FilterField`、`DataTable`、`EmptyState`、`EffectiveDatePicker`（D-091；`apps/web/src/business/components/`）。

## 5. 用户故事

### WFC-ROSTER-F001-US01 按任意历史时点查看在册名册

作为人事查看者，我希望指定一个历史日期并看到当时的在册员工，从而核对某个时点到底有谁在册、在哪个部门。

- 触发条件：进入侧栏「历史花名册」（默认时点为今天），或在筛选区改「查看日期」后点「查询」。
- 前置条件：账号具备 `PERSON_VIEW`；后端已存在生效日期化的雇佣与任职数据。
- 主路径：页面加载 → 请求 `GET /api/v1/workforce/people/roster-history?as_of=<日期>&limit=20&offset=0`（`HistoricalRosterWorkspace.tsx:101-125`）→ 服务端按 as_of 切片区间化表、取主档登记值与已生效字段修正（`historical_roster_service.py:98-173`）→ 表格按「工号 / 姓名（时点）/ 主组织（时点）/ 职位（时点）/ 在职状态（时点）/ 入职日期（时点）/ 操作」展示，计数行显示「共 N 人（截至 <as_of>）」（`:233-291`）。
- 结束状态：表格显示该时点的名册；该时点无在册员工时显示空态「该时点没有在册员工」（`:282`，由 `DataTable` 的 `emptyText` → `EmptyState` 承载）。

### WFC-ROSTER-F001-US02 按主组织 / 在职状态 / 姓名工号筛选并翻页

作为人事查看者，我希望按主组织、在职状态和姓名或工号收窄结果，从而在名册里定位到具体的人。

- 触发条件：在筛选区选择「主组织」「在职状态」或输入「搜索姓名或工号」后点「查询」；或在分页器翻页。
- 前置条件：账号具备 `PERSON_VIEW`；筛选为草稿式，改值不立即请求（`HistoricalRosterWorkspace.tsx:93-95`、`:138-144`）。
- 主路径：点「查询」→ 提交 `as_of` + 可选 `organization_id` / `employment_status` / `search` + `limit=20` + `offset=(页码-1)*20`（`:105-112`）→ 服务端过滤（`historical_roster_service.py:119-149`）→ 表格与计数行按同一 `total` 刷新（`:117-119`、`:166`）。
- 结束状态：表格只显示符合条件的行，计数行与分页器取同一个 `total`；点「重置」清空全部筛选条件并把查看日期回到今天（`:146-153`）。

### WFC-ROSTER-F001-US03 查看某人在该时点的字段与修正说明

作为人事查看者，我希望看到某个人在该时点的字段值以及哪些字段被修正过，从而判断这一行的历史可信度。

- 触发条件：点击行内「查看时点信息」。
- 前置条件：账号具备 `PERSON_VIEW`；该行已在当前结果集中。
- 主路径：点击「查看时点信息」→ 打开 antd `Drawer`（标题为「<时点姓名> · <工号>」）（`HistoricalRosterWorkspace.tsx:293-297`）→ `Descriptions` 逐项列出查看时点、姓名（时点）、主组织（时点）、职位（时点）、在职状态（时点）、入职日期（时点）、修正过的字段（`:300-318`）→ 抽屉底部再放一条口径提示条（`:319`）。
- 结束状态：抽屉展示该行时点字段；「修正过的字段」为空时显示「无（该时点字段值等于当前登记值）」（`:313-317`）；关闭抽屉后回到宿主页，筛选与分页状态保留。

## 6. 业务流程与状态机

```text
历史花名册查询（只读，无写路径）
  输入 as_of（必填，可为未来日）+ 可选筛选条件
        │
        ▼
  服务端取数：按 as_of 切片区间化表 + 主档登记值 + 已生效字段修正
        │
        ├─ as_of 缺失 / 格式非法 ──► 422 REQUEST_VALIDATION_FAILED
        ├─ 账号缺 PERSON_VIEW ─────► 403 PERMISSION_DENIED
        ├─ 会话无效 ───────────────► 401 AUTHENTICATION_REQUIRED / SESSION_INVALID
        └─ 正常 ─► 200 { as_of, items, total, limit, offset, field_history_note }
                      │
                      ▼
              页面：计数行「共 N 人（截至 as_of）」+ 表格 + 分页器
                      │  行操作「查看时点信息」
                      ▼
                 抽屉：该行时点字段 + 「修正过的字段」+ 口径提示条
```

| 当前状态 | 操作 | 条件 | 下一状态 | 失败结果 |
|---|---|---|---|---|
| 未查询 | 进入页面 | 默认 `as_of` = 今天 | 加载中 | —— |
| 加载中 | 请求返回 | `items` 非空 | 正常 | 请求失败 → 顶部错误条 |
| 加载中 | 请求返回 | `items` 为空 | 空数据 | 请求失败 → 顶部错误条 |
| 正常 | 点「查询」/「重置」/ 翻页 | —— | 加载中 | 422 / 403 / 401 → 顶部错误条（`HistoricalRosterWorkspace.tsx:120-124`） |
| 正常 | 点「查看时点信息」 | 该行存在 | 抽屉打开 | —— |
| 抽屉打开 | 关闭抽屉 | —— | 正常（宿主页筛选、分页与列表状态保留） | —— |

状态说明：本功能没有写路径，因此不存在「草稿 → 生效 → 失效」类的业务状态机；上表描述的是页面状态迁移，与 §10.2 的页面状态表一一对应。

## 7. 业务规则

状态约定：`CONFIRMED` 表示该规则已有已确认决策、已交付能力或服务端强制的合同约束支撑；`PENDING` 表示该规则取决于尚未签字的产品决策，开发者不得自行猜测；`NOT_APPLICABLE` 表示经核查本功能不涉及，并写明依据。

**限制说明（必须如实呈现，不得理想化）**

历史花名册不是完整的历史回放。时点的人员字段值 = 登记值 + 生效日期不晚于该时点的最后一条修正；**未被修正过的字段等于当前值**。字段级历史的精度取决于 `person_field_versions` 的修正记录覆盖率。三处同时表达，避免被读成「某年某月的完整档案快照」：

1. 接口层：每行返回 `field_history_available`（该行是否有时点修正历史支撑）与 `corrected_fields`（已生效修正的字段代码列表）；响应顶层返回 `field_history_note` 固定说明（`historical_roster_service.py:49-52`、`:314-315`；`historical_roster_api.py:58-61`、`:70-71`、`:103`）。
2. 界面层：页头下的 info 提示条固定文案「时点的人员字段值 = 登记值 + 生效日期不晚于该时点的最后一条修正；未被修正过的字段等于当前值。」（`HistoricalRosterWorkspace.tsx:20-21`、`:176-178`）；行操作的时点信息里列出「修正过的字段」，没有修正时显示「无（该时点字段值等于当前登记值）」（`:313-317`）；抽屉底部再放同一条提示（`:319`）。
3. 文档层：本节与 §4.2 口径表。

| ID | 状态 | 规则 | 规则来源 | 验证方式 |
|---|---|---|---|---|
| WFC-ROSTER-F001-BR001 | `CONFIRMED` | `as_of` 必填，格式 `YYYY-MM-DD`；缺失、格式非法或非日期一律 422 `REQUEST_VALIDATION_FAILED`，不返回名册 | 实现 `historical_roster_api.py:78`；异常处理 `apps/api/src/hris/core/errors.py:46-67`；测试 `test_historical_roster_api.py:186-210` | AC008 |
| WFC-ROSTER-F001-BR002 | `CONFIRMED` | 允许未来日期：未来时点没有在册人员时返回 200 与空 `items`、`total=0`，**不是** 422 | 实现 `historical_roster_api.py:87`、`:110-111`；`historical_roster_service.py:110-111`；测试 `test_historical_roster_api.py:357-368` | AC004 |
| WFC-ROSTER-F001-BR003 | `CONFIRMED` | 在册口径（雇佣）：`employments.planned_start_date <= as_of` 且（`end_date` 为空或 `end_date >= as_of`）且 `status` 不在 `('withdrawn','terminated')` 内 | 实现 `historical_roster_service.py:69`、`:113-118`、`:218-223` | AC002、AC005 |
| WFC-ROSTER-F001-BR004 | `CONFIRMED` | 区间化表口径（任职 / 组织版本 / 职务版本）：`effective_from <= as_of` 且（`effective_to` 为空或 `effective_to > as_of`）；结束日当天不再生效。本功能取严格大于，与编制域 `_count_people` 的 `>=` 不同 | 实现 `historical_roster_service.py:54-62`（含差异注释）、`:136`、`:246`、`:350`、`:379` | AC002 |
| WFC-ROSTER-F001-BR005 | `CONFIRMED` | 主组织 / 职位取该时点有效的**主职**任职（`employment_assignments.relation_type = 'primary'`）；兼岗与其它任职类型不进入本结果 | 实现 `historical_roster_service.py:245-246`、`:134`、`:292-305` | AC002、AC006 |
| WFC-ROSTER-F001-BR006 | `CONFIRMED` | 同一时点存在多段雇佣（再入职）时取最新的一段，排序键为 `(planned_start_date, id)` | 实现 `historical_roster_service.py:231-236`、`:320-322` | AC002 |
| WFC-ROSTER-F001-BR007 | `CONFIRMED` | 同一段雇佣存在多段任职时取 `(effective_from, version)` 最大的一段 | 实现 `historical_roster_service.py:250-256` | AC002 |
| WFC-ROSTER-F001-BR008 | `CONFIRMED` | 组织名 / 职务名取该时点有效的 `organization_versions.name` / `job_catalog_versions.name`（`version` 倒序第一条）；组织编码 / 职务编码取主档 `code`，不随时点变化 | 实现 `historical_roster_service.py:324-334`、`:336-358`、`:360-368`、`:370-387` | AC002 |
| WFC-ROSTER-F001-BR009 | `CONFIRMED` | 人员字段时点值 = 主档登记值 + 生效日期 ≤ as_of 的最后一条字段修正（同一字段按 `(effective_from, version)` 取最后一条）；未被修正过的字段等于当前登记值 | 实现 `historical_roster_service.py:282-285`、`:389-416`；`person_corrections_service.py:105-124`；决策 D-105 | AC003 |
| WFC-ROSTER-F001-BR010 | `CONFIRMED` | 搜索按「时点姓名」而不是主档姓名匹配，并与工号一起做大小写不敏感的包含匹配；搜索关键字前后空白被去除 | 实现 `historical_roster_service.py:140-149`（`_time_point_display_name()` 参与匹配） | AC006 |
| WFC-ROSTER-F001-BR011 | `CONFIRMED` | 修正把姓名清空时，该时点姓名就是空值；实现用 `CASE` 区分「有修正」与「无修正」，不把「被清空」当成「没有修正」 | 实现 `historical_roster_service.py:175-207` | AC003 |
| WFC-ROSTER-F001-BR012 | `CONFIRMED` | 每行必须带 `field_history_available` 与 `corrected_fields`，响应顶层必须带 `field_history_note`；三者缺一即视为「把结果伪装成完整档案快照」 | 实现 `historical_roster_service.py:49-52`、`:314-315`；`historical_roster_api.py:58-71` | AC001、AC003、AC011 |
| WFC-ROSTER-F001-BR013 | `CONFIRMED` | 读权限复用 `PERSON_VIEW`（与人员档案读取同一枚权限码），不额外要求 `PERSON_SENSITIVE_VIEW`；本接口只返回花名册级别字段，不返回证件号、联系方式等敏感子记录 | 实现 `historical_roster_api.py:15-17`、`:40`；测试 `test_historical_roster_api.py:545-556` | AC009 |
| WFC-ROSTER-F001-BR014 | `CONFIRMED` | 在职状态取 `employments.status`；筛选条件与列表显示口径一致——被筛选出来的状态就是行上显示的状态 | 实现 `historical_roster_service.py:224-226`、`:306` | AC006 |
| WFC-ROSTER-F001-BR015 | `CONFIRMED` | 列表排序为「工号（空值排最后）→ 时点姓名 → 人员 id」，同一条件下分页稳定 | 实现 `historical_roster_service.py:159-163` | AC001、AC007 |
| WFC-ROSTER-F001-BR016 | `CONFIRMED` | 服务端分页：`limit` 取值 1–200、缺省 50；`offset` ≥ 0、缺省 0；前端固定每页 20 条（`limit=20`、`offset=(页码-1)*20`），计数行与分页器取同一个 `total` | 实现 `historical_roster_api.py:82-83`；`historical_roster_service.py:151-168`；`HistoricalRosterWorkspace.tsx:23`、`:105-108`、`:166`、`:284-291` | AC007 |
| WFC-ROSTER-F001-BR017 | `CONFIRMED` | 界面必须以固定文案提示「不是完整历史回放」；页头提示条与抽屉提示条文案一致，取值见 §7 限制说明第 2 条 | 实现 `HistoricalRosterWorkspace.tsx:20-21`、`:176-178`、`:319`；测试 `HistoricalRosterWorkspace.test.tsx:94-104` | AC001、AC003 |
| WFC-ROSTER-F001-BR018 | `CONFIRMED` | 筛选为草稿式：修改筛选值不立即请求，点「查询」才提交并回到第一页；点「重置」清空全部筛选条件且查看日期回到今天 | 实现 `HistoricalRosterWorkspace.tsx:93-95`、`:138-153`；D-091 | AC006 |
| WFC-ROSTER-F001-BR019 | `PENDING` | 企业是否接受「未被修正过的字段等于当前值」作为长期口径，或需要在后续批次补齐历史字段（补齐动作属 D-105 修正语义，不在本功能范围） | 待确认清单 A5；现状实现 `historical_roster_service.py:47-52`、`:389-416` | 见 §18 Q01 |
| WFC-ROSTER-F001-BR020 | `PENDING` | 主组织筛选的选项来源：当前组织树还是历史时点组织树 | 待确认清单 A22；现状实现 `apps/web/src/business/features/workforce/api.ts:159-160` | 见 §18 Q02 |
| WFC-ROSTER-F001-BR021 | `PENDING` | 搜索关键字中的 `%` 与 `_` 是否需要转义：当前实现直接拼成 `ilike` 通配符，用户输入的通配符会被当作匹配语义 | 现状实现 `historical_roster_service.py:140-149` | 见 §18 Q05 |
| WFC-ROSTER-F001-BR022 | `PENDING` | 搜索是否应同时匹配时点法定姓名（`legal_name`）：当前只匹配工号与时点显示姓名 | 现状实现 `historical_roster_service.py:140-149`、`:283-284` | 见 §18 Q06 |

规则写法自查（对照规范 §8.1 / §8.2）：所有 `CONFIRMED` 规则都写明了适用对象与时间点、条件与唯一性维度、成功与拒绝结果、历史记录影响，不使用「合理处理」「一般情况」「尽量」等表述；不包含未说明配置范围的「支持灵活配置」、未说明幂等与最终状态的「失败后重试」、未说明下游与历史保留的「可以回退」。

## 8. 数据要求

### 8.1 数据所有权与关系

- 本功能拥有的数据：**无**。本功能是纯读功能，不新建表、不写任何表（`historical_roster_service.py:92-96` 的类注释：「只读服务：不产生写操作，因此不需要 actor_id / trace_id」）。
- 引用但不拥有的数据：
  - 人员主档 `persons`（登记值来源）。
  - 雇佣 `employments`（在册口径与在职状态、入职日期）。
  - 任职 `employment_assignments`（时点主组织与职位）。
  - 组织与组织版本 `organizations` / `organization_versions`（组织编码与时点组织名）。
  - 职务与职务版本 `job_catalog` / `job_catalog_versions`（职务编码与时点职务名）。
  - 人员修正版本 `person_field_versions`（字段级时点值）。
  - 以上均属 Workforce Core 模块（`apps/api/src/hris/modules/workforce/models.py`）。
- 业务唯一键：
  - 行的稳定身份是 `persons.id`（前端 `rowKey="person_id"`，`HistoricalRosterWorkspace.tsx:230`）；同一 `as_of` 下每人至多一行。
  - 时点任职的唯一性是「同一雇佣下 `(effective_from, version)` 最大的一条主职任职」（`historical_roster_service.py:250-256`）；服务层唯一性，数据库层无唯一约束。
  - 时点字段值的唯一性是「同一字段按 `(effective_from, version)` 取最后一条修正」（`person_corrections_service.py:116-123`）；服务层唯一性。
- 有效日期/版本/快照要求：
  - 区间化表统一 `[effective_from, effective_to)` 左闭右开（`historical_roster_service.py:58-62`）。
  - `employments` 不是区间表，用 `planned_start_date` 与 `end_date` 表达（`historical_roster_service.py:54-57`、`:113-118`）。
  - 快照：**本功能不产生快照数据**，返回的是按 `as_of` 实时切片的结果；结果集本身不可回放（见 §7 限制说明）。

### 8.2 字段合同

「来源」列中的文件均位于 `apps/api/src/hris/modules/workforce/historical_roster_service.py`（响应模型在 `historical_roster_api.py`），行号在括号内注明。

| ID | 字段 | 类型/格式 | 必填 | 来源 | 默认值 | 校验 | 敏感级别 | 历史策略 |
|---|---|---|---|---|---|---|---|---|
| WFC-ROSTER-F001-DAT001 | `person_id` | UUID | 是 | `HistoricalRosterRow.person_id`（`:76`）；响应模型 `historical_roster_api.py:46` | 无 | 指向 `persons.id` | 非敏感（内部 id） | 稳定身份，不随时点变化 |
| WFC-ROSTER-F001-DAT002 | `employee_number` | string，可空 | 响应只读 | `persons.employee_number`（`:78`） | — | 主档登记值；为空时前端渲染「待分配」（`HistoricalRosterWorkspace.tsx:238`） | 个人信息（工号） | 主档登记值，不随时点变化 |
| WFC-ROSTER-F001-DAT003 | `display_name` | string，可空 | 响应只读 | 时点取值（`:283`） | — | 登记姓名 + 已生效 `display_name` 修正 | 个人信息（姓名） | 登记值 + 生效日期 ≤ as_of 的最后一条修正 |
| WFC-ROSTER-F001-DAT004 | `legal_name` | string，可空 | 响应只读 | 时点取值（`:284`） | — | 登记法定姓名 + 已生效 `legal_name` 修正 | 个人信息（法定姓名） | 同 DAT003 |
| WFC-ROSTER-F001-DAT005 | `organization_id` | UUID，可空 | 响应只读 | 该时点有效主职任职（`:292`） | — | 无主职任职时为 `null` | 非敏感（内部 id） | 随任职生效区间变化 |
| WFC-ROSTER-F001-DAT006 | `organization_code` | string，可空 | 响应只读 | `organizations.code`（`:293-297`、`:324-334`） | — | 主档编码，不随时点变化 | 非敏感 | 主档值 |
| WFC-ROSTER-F001-DAT007 | `organization_name` | string，可空 | 响应只读 | 该时点有效的 `organization_versions.name`（`:298-302`、`:336-358`） | — | 该时点无有效版本时为 `null` | 非敏感 | 随组织版本生效区间变化 |
| WFC-ROSTER-F001-DAT008 | `job_id` | UUID，可空 | 响应只读 | 该时点有效主职任职（`:303`） | — | 无主职任职或任职无职务时为 `null` | 非敏感（内部 id） | 随任职生效区间变化 |
| WFC-ROSTER-F001-DAT009 | `job_code` | string，可空 | 响应只读 | `job_catalog.code`（`:304`、`:360-368`） | — | 主档编码，不随时点变化 | 非敏感 | 主档值 |
| WFC-ROSTER-F001-DAT010 | `job_name` | string，可空 | 响应只读 | 该时点有效的 `job_catalog_versions.name`（`:305`、`:370-387`） | — | 该时点无有效版本时为 `null` | 非敏感 | 随职务版本生效区间变化 |
| WFC-ROSTER-F001-DAT011 | `employment_status` | string，可空 | 响应只读 | `employments.status`（`:306`） | — | 取值不含 `withdrawn` / `terminated`（`:69`、`:222`） | 非敏感（状态码） | 取该时点最新一段雇佣的状态 |
| WFC-ROSTER-F001-DAT012 | `hire_date` | date，可空 | 响应只读 | `actual_start_date` 优先，否则 `planned_start_date`（`:307-311`） | — | 无雇佣时为 `null` | 非敏感 | 取该时点最新一段雇佣的入职日期 |
| WFC-ROSTER-F001-DAT013 | `field_history_available` | bool | 是 | `bool(corrected_fields)`（`:314`） | `false` | 该行是否有已生效修正支撑 | 非敏感 | 随 as_of 变化 |
| WFC-ROSTER-F001-DAT014 | `corrected_fields` | string[] | 是 | 已生效修正的字段代码，按字典序（`:285`、`:315`） | `[]` | 字段代码取 `person_field_versions.field_code` | 非敏感 | 随 as_of 变化 |
| WFC-ROSTER-F001-DAT015 | `as_of` | date | 是 | 响应顶层，回显查询时点（`historical_roster_api.py:65`、`:98`） | 无 | 与请求参数一致 | 非敏感 | —— |
| WFC-ROSTER-F001-DAT016 | `total` | int | 是 | 该时点符合条件的人数（`:151-153`） | — | 与 `items` 长度无关，等于筛选后总数 | 非敏感 | 随 as_of 与筛选条件变化 |
| WFC-ROSTER-F001-DAT017 | `limit` / `offset` | int | 是 | 分页参数回显（`historical_roster_api.py:82-83`、`:100-101`） | `limit=50`、`offset=0` | `limit` ∈ [1,200]；`offset` ≥ 0 | 非敏感 | —— |
| WFC-ROSTER-F001-DAT018 | `field_history_note` | string | 是 | 固定限制说明常量 `FIELD_HISTORY_NOTE`（`historical_roster_service.py:49-52`；`historical_roster_api.py:71`、`:103`） | — | 文案固定，不随请求变化 | 非敏感 | —— |

### 8.3 数据生命周期

- 创建：`NOT_APPLICABLE`。依据：本功能无写路径，不新建任何数据。
- 修改/更正：`NOT_APPLICABLE`。依据：本功能不提供修正入口；人员字段的更正由 WFC-PEOPLE-F001 的【修正】动作写入 `person_field_versions`（D-105），本功能只读该结果。
- 生效/失效：`NOT_APPLICABLE`。依据：本功能不产生生效或失效动作，只按既有表的生效区间读。
- 保留：`NOT_APPLICABLE`（针对本功能）。依据：本功能不拥有数据，保留策略跟随被引用表（`persons`、`employments`、`employment_assignments`、`organization_versions`、`job_catalog_versions`、`person_field_versions`）各自的保留策略。
- 删除：`NOT_APPLICABLE`。依据：本功能没有删除端点，也没有删除语句（`historical_roster_api.py` 只定义 1 组 GET）。
- 迁移与兼容：本功能不需要新表，2026-10-24 实现轮次无结构变更；`alembic -c alembic-business.ini upgrade head` + `check` 零漂移（证据见 §16 发布前门禁）。

## 9. 权限要求

| ID | 状态 | 参与者 | 功能/动作权限 | 数据范围 | 字段权限 | 拒绝结果 |
|---|---|---|---|---|---|---|
| WFC-ROSTER-F001-PERM001 | `CONFIRMED` | 持有 `PERSON_VIEW` 或 `*` 的账号 | 查看历史花名册（`GET /api/v1/workforce/people/roster-history`） | 全部在册人员，无行级过滤 | 全部只读字段（DAT001–DAT018） | 403 `PERMISSION_DENIED`「没有执行此操作的权限」（`dependencies.py:94`）；前端在页面顶部显示可关闭的错误条（`HistoricalRosterWorkspace.tsx:120-124`、`apps/web/src/business/components/WorkspaceShell.tsx:22-25`） |
| WFC-ROSTER-F001-PERM002 | `CONFIRMED` | 持有 `PERSON_VIEW` 或 `*` 的账号 | 侧栏入口可见性：「历史花名册」按 `PERSON_VIEW` 过滤，无权限时不渲染 | —— | —— | 无权限时侧栏入口不出现（`navigation.ts:74-80`、`AppShell.tsx:219-222`） |
| WFC-ROSTER-F001-PERM003 | `CONFIRMED` | 持有 `ORGANIZATION_VIEW` 或 `*` 的账号 | 主组织下拉的数据源：`GET /api/v1/organizations/tree`（`apps/web/src/business/features/workforce/api.ts:159-160`） | 当前组织树（不带 `as_of`） | 只读 | 该请求 403 时下拉静默退化为空选项（`HistoricalRosterWorkspace.tsx:131-136`），名册列表与其它筛选项不受影响 |
| WFC-ROSTER-F001-PERM004 | `CONFIRMED` | 持有 `PERSON_VIEW` 或 `*` 的账号 | 本接口不返回证件号、联系方式等敏感子记录，因此不额外要求 `PERSON_SENSITIVE_VIEW` | —— | 不含敏感子记录 | 持有 `PERSON_VIEW` 即可读取全部花名册级别字段（`historical_roster_api.py:15-17`、`:40`） |
| WFC-ROSTER-F001-PERM005 | `CONFIRMED` | 未登录或会话失效账号 | 任何接口 | —— | —— | 401 `AUTHENTICATION_REQUIRED`「需要登录」或 `SESSION_INVALID`「登录状态无效或已过期」（`dependencies.py:35`、`:50`） |
| WFC-ROSTER-F001-PERM006 | `CONFIRMED` | 主管理员（持 `*`） | 本功能全部读操作 | 全部在册人员 | 全部只读字段 | `*` 对权限判定短路放行（`dependencies.py:93`） |

代办与代理说明：

- 主管理员（持 `*`）可以直接读取，不需要额外审批（`dependencies.py:93` 对 `*` 短路放行）。
- 本功能**没有代办 / 代理身份机制**：只读服务不产生写操作，因此不记录 `actor_id`，也没有 `on_behalf_of` 或代理角色字段（`historical_roster_service.py:93`）。
- **不适用**「是否需要填写原因」：本功能没有写操作，也就没有需要填写原因的动作。
- 未知范围默认拒绝：权限判定为「不具备所需权限码即拒绝」，不做任何隐式放行（`dependencies.py:90-95`）。

## 10. 交互与页面要求

### 10.1 入口与可见性

- 菜单/页面/按钮：
  - 侧栏：「历史花名册」，紧跟「人员中心」之后（`navigation.ts:73-80`）。
  - 面包屑：「人员中心 / 历史花名册」（画板登记表 `docs/review/pen-artboard-registry.json` `artboards[].breadcrumb`）。
  - 页内操作：筛选栏「重置」「查询」（`HistoricalRosterWorkspace.tsx:182-188`）；行内链接按钮「查看时点信息」（`:271-280`）。
  - 页面标题与副标题（宿主页页头，逐字复用实现）：标题「历史花名册」；副标题「按生效日期回看任意时点的员工名册与当时信息。」（`:171-172`）。
  - 筛选区文案：标签「查看日期」（`EffectiveDatePicker` 默认 label，`apps/web/src/business/components/EffectiveDatePicker.tsx:17`）、「主组织」（`:193`）、「在职状态」（`:205`）、「搜索姓名或工号」（`:217`）；占位符「全部组织」（`:196`）、「全部状态」（`:208`）、「搜索姓名或工号」（`:222`）。
- 无权限或未启用模块时：侧栏不渲染该入口（`navigation.ts:74-80` + `AppShell.tsx:219-222`）；通过 hash 路由 `#historical-roster` 直接进入且接口返回 403 时，页面顶部显示可关闭的错误条（`HistoricalRosterWorkspace.tsx:120-124`、`WorkspaceShell.tsx:22-25`），页面其余部分保留。
- 宿主页：列表。独立列表页，不挂在人员中心宿主页内部（`navigation.ts:165-171` 的 `workspaceFromHash` 处理 `#historical-roster`；挂载点 `AppShell.tsx:307-309`）。
- 交互载体：`DRAWER`。行内「查看时点信息」使用 antd `Drawer`（`HistoricalRosterWorkspace.tsx:293-322`）。
- 选择理由：抽屉承载的是「某个人的时点档案视图」，使用场景需要与宿主页列表并行参照（一边看列表一边看某人的时点信息），符合 [Ant Design 页面与交互载体规范](../../../design/antd-page-interaction-standard.md) 中 `DRAWER` 的适用条件；不选 `MODAL`（内容是 7 项只读描述、无表单输入，Modal 不提供列表侧的上下文保留）；不选 `NEW_TAB`（字段数与分组数均低于升级线，且不需要独立 URL 分享）。载体为已实现形态，选择理由在此登记以便评审复核。
- 路由或深链接：宿主页为 hash 路由 `#historical-roster`（`navigation.ts:165-171`）；抽屉不占用独立路由，关闭后回到宿主页并保留筛选、分页与列表状态（宿主页组件未被卸载）。
- Pencil源文件：`C:\Users\83289\Documents\HRMS\coreHR.pen`（Pencil 2.17；`docs/review/pen-prototype-spec-2026-10-24.md:5`）。
- 画板ID/名称/原型版本：`Gxgyj` / 「历史花名册 · 人员中心 v1.0」 / `v1.0`（画板 1440×960，载体 `HOST_PAGE`）。
- 原型状态：`PROTOTYPE_APPROVED`。2026-10-24 产品决策人签字确认；按规范 §10.1 与 D-087，前端开发门禁已解除（见 §18 Q03、§20）。

### 10.2 页面状态

| 状态 | 页面表现 | 可执行操作 |
|---|---|---|
| 首次/空数据 | 表格空态「该时点没有在册员工」（`HistoricalRosterWorkspace.tsx:282`，由 `DataTable` 的 `emptyText` → `EmptyState` 承载）；计数行显示「共 0 人（截至 <as_of>）」（`:166`） | 调整筛选、点「查询」或「重置」 |
| 加载中 | 表格 `loading` 态（`:231`） | 等待；可改筛选草稿 |
| 正常 | 顶部 info 提示条 + 筛选栏 + 计数行 + 表格 + 分页器，分页文案「共 N 人」（`:283-291`） | 筛选、查询、重置、翻页、打开行抽屉 |
| 部分失败 | 主组织下拉请求失败：下拉静默为空，其余功能正常（`:131-136`） | 照常查询；主组织筛选暂不可用 |
| 完全失败 | 名册接口失败：页面顶部显示可关闭的错误条，文案取后端 `message`（缺省「历史花名册加载失败」）（`:120-124`） | 关闭错误条、改条件后重试 |
| 无权限 | 同上——403 的错误条提示「没有执行此操作的权限」；同时侧栏入口不可见（`navigation.ts:74-80`） | 关闭错误条、联系主管理员 |

### 10.3 表单与确认

- 字段顺序与联动：
  - 筛选区顺序：查看日期 → 主组织 → 在职状态 → 搜索姓名或工号 →（右侧）重置 / 查询（`HistoricalRosterWorkspace.tsx:179-228`，与画板登记表的 `filters` 顺序一致）。
  - 无字段间联动：查看日期只作为时点参数，其余三项各自独立。
  - 在职状态为固定两项下拉：「在职」`active`、「待入职」`pending_start`（`:25-28`）。
  - 主组织下拉选项文案为「<组织名> (<组织编码>)」（`:161`）。
- 即时校验与提交校验：本功能是只读查询，没有提交表单，因此**没有**即时校验与提交校验；时点格式由服务端 pydantic 校验，非法值返回 422 `REQUEST_VALIDATION_FAILED`，逐字段 `details` 返回（`apps/api/src/hris/core/errors.py:46-67`）。
- 高风险二次确认：`NOT_APPLICABLE`。依据：本功能没有写操作，也没有删除、导出等高风险动作。
- 成功反馈与下一步：查询成功后表格与计数行按同一 `total` 刷新（`:117-119`）；失败时页面顶部显示错误条（`:120-124`）。
- 打开、关闭和焦点返回：抽屉由行内链接按钮打开（`:276-279`），关闭通过 `onClose` 把 `detail` 置空（`:296`）；antd `Drawer` 默认在打开后把焦点移入抽屉容器、关闭后焦点回到触发按钮。抽屉不销毁宿主页，列表状态保留。
- 未保存变更与重复提交保护：抽屉是纯只读展示，**没有**未保存变更，也没有提交动作，因此不存在重复提交保护需求；查询请求由 `loading` 态与筛选草稿机制约束（D-091 草稿式筛选，`:93-95`）。
- 弹窗关闭后表单重置或保留策略：不适用（无表单）。抽屉关闭后不保留任何输入，因为抽屉内没有输入控件。

### 10.4 Pencil原型登记

| 原型ID | 页面/交互载体 | Pencil文件 | 画板ID与名称 | 版本 | 状态 | 批准人/日期 |
|---|---|---|---|---|---|---|
| WFC-ROSTER-F001-PROT001 | `HOST_PAGE`（宿主页「历史花名册 · 人员中心 v1.0」，画板 `Gxgyj` 1440×960；行内「查看时点信息」抽屉尚未单独出画板） | `C:\Users\83289\Documents\HRMS\coreHR.pen` | 画板ID `Gxgyj`；画板名称「历史花名册 · 人员中心 v1.0」 | v1.0 | `PROTOTYPE_APPROVED` | 2026-10-24 产品决策人签字确认（见 §18 Q03 / §20） |

登记说明（按事实记录，不做美化）：

- Pencil 源文件与版本：`C:\Users\83289\Documents\HRMS\coreHR.pen`（Pencil 2.17，`docs/review/pen-prototype-spec-2026-10-24.md:5`）。
- 预览图：`docs/review/pen-prototypes/09-历史花名册.png`。
- 机器可读登记：`docs/review/pen-artboard-registry.json`（`artboards[].id = Gxgyj`，`reviewStatus = PROTOTYPE_APPROVED`，`carrier = HOST_PAGE`）。
- 画板与实现的有意差异已登记在画板登记表 `implementationDeltas`：第 1 条「画板演示的是历史时点 2024-01-01，实现的默认时点是今天」；第 2 条「『（时点）』后缀是本页专属写法」；第 3 条「该页对应 Moka 的『员工花名册』历史查询能力；本轮仅按 D-102 落时点查询，尚未实现 Moka 花名册的『导出 / 对比 / 批量』等其余动作」。
- 补充登记（2026-10-24 回代码核对）：画板登记表的 `rowAction` 记为「查看档案」，实现中的行内按钮文案是「查看时点信息」（`HistoricalRosterWorkspace.tsx:276-278`）；抽屉（`Drawer`）本身未单独出画板。
- 规范 §10.4 要求「显著不同的加载、空数据、失败、无权限和冲突状态应在原型中可Review」，这些状态目前只存在于实现（`HistoricalRosterWorkspace.tsx:120-124`、`:229-292`），没有对应的 Pencil 画板——见 §18 Q03。

## 11. API与事件合同

### 11.1 同步API

| ID | 方法与路径 | 调用者 | 请求摘要 | 响应摘要 | 权限 | 幂等 | 事务边界 |
|---|---|---|---|---|---|---|---|
| WFC-ROSTER-F001-API001 | `GET /api/v1/workforce/people/roster-history`（`historical_roster_api.py:74-104`） | 历史花名册宿主页 | 查询参数：`as_of`（date，必填）、`search`（string ≤ 200，可选）、`organization_id`（UUID，可选）、`employment_status`（string ≤ 30，可选）、`limit`（1–200，缺省 50）、`offset`（≥ 0，缺省 0） | `HistoricalRosterResponse`：`as_of`、`items`（`HistoricalRosterRow` 列表）、`total`、`limit`、`offset`、`field_history_note` | `PERSON_VIEW`；`*` 放行 | 天然幂等（只读） | 单请求单事务，`get_db` 在响应前提交（`apps/api/src/hris/core/database.py:21-28`） |
| WFC-ROSTER-F001-API002 | `GET /api/v1/organizations/tree`（`organization_api.py:127-155`） | 历史花名册页的主组织下拉（`apps/web/src/business/features/workforce/api.ts:159-160`） | 无查询参数（本功能不传 `as_of`，取当前树） | `list[OrganizationTreeNode]` | `ORGANIZATION_VIEW`；`*` 放行 | 天然幂等（只读） | 单请求单事务 |

调用者与所有权说明：API001 由 Workforce Core 模块提供，是本功能唯一的业务接口；API002 是同模块的组织树查询，只被本功能作为下拉数据源引用，本功能不写入组织数据。前端调用封装在 `apps/web/src/business/features/workforce/HistoricalRosterWorkspace.tsx:101-125`（名册）与 `api.ts:159-160`（组织树），认证统一使用 Bearer Token（`apps/web/src/business/client.ts:59-74`）。

### 11.2 异步事件与任务

`NOT_APPLICABLE`。依据：本功能所有路径都是数据库读取（`historical_roster_service.py:92-173`、`:209-318`），模块内没有消息发布、领域事件或后台任务调用（全文件检索 `publish` / `emit` / `BackgroundTasks` 无命中）；页面也没有轮询或推送通道（前端只在筛选提交与翻页时发请求，`HistoricalRosterWorkspace.tsx:101-125`、`:155-158`）。

### 11.3 兼容与废弃

- 当前合同版本：v1。`GET /api/v1/workforce/people/roster-history` 的路径与响应字段自 2026-10-24 实现轮次交付以来未变（`historical_roster_api.py:43-71` 定义响应模型）。
- 向后兼容策略：
  - `as_of` 必填语义不变；`limit` / `offset` / `search` / `organization_id` / `employment_status` 的缺省值与取值域不变。
  - 响应新增字段（如未来补充列）以追加方式提供，不删除既有字段；既有消费方只按字段名读取。
  - `field_history_available` / `corrected_fields` / `field_history_note` 属于「限制说明」合同的一部分，不得删除或改写（见 BR012）。
- 废弃通知和截止版本：当前无废弃项。若后续要修改时点取值口径（例如改用区间化的雇佣结束日），必须先在本节登记口径变更并同步 `docs/01-foundation/03-项目决策.md` §8.5 的 D-102，不得在服务层单方面改口径（规范 §13 变更控制）。

## 12. 异常、并发与回退

| ID | 状态 | 场景 | 系统结果 | 用户提示/错误码 | 是否重试 | 补偿/回退 |
|---|---|---|---|---|---|---|
| WFC-ROSTER-F001-ERR001 | `CONFIRMED` | `as_of` 缺失 | 请求被拒，不查库 | 422 `REQUEST_VALIDATION_FAILED`「请求参数校验失败」，`details` 逐字段给出（`errors.py:46-67`） | 否——需补参数 | 不适用 |
| WFC-ROSTER-F001-ERR002 | `CONFIRMED` | `as_of` 格式非法或不是日期 | 请求被拒，不查库 | 422 `REQUEST_VALIDATION_FAILED`（`errors.py:46-67`；测试 `test_historical_roster_api.py:198-210`） | 否 | 不适用 |
| WFC-ROSTER-F001-ERR003 | `CONFIRMED` | 账号不持有 `PERSON_VIEW` | 请求被拒 | 403 `PERMISSION_DENIED`「没有执行此操作的权限」（`dependencies.py:94`；测试 `test_historical_roster_api.py:545-556`） | 否 | 不适用 |
| WFC-ROSTER-F001-ERR004 | `CONFIRMED` | 会话无效或过期 | 请求被拒 | 401 `AUTHENTICATION_REQUIRED`「需要登录」或 `SESSION_INVALID`「登录状态无效或已过期」（`dependencies.py:35`、`:50`） | 重新登录后重试 | 不适用 |
| WFC-ROSTER-F001-ERR005 | `CONFIRMED` | `limit` 越界（< 1 或 > 200）或 `offset` 为负 | 请求被拒 | 422 `REQUEST_VALIDATION_FAILED`（`historical_roster_api.py:82-83`；`errors.py:46-67`） | 否 | 不适用 |
| WFC-ROSTER-F001-ERR006 | `CONFIRMED` | `search` 长度超过 200 | 请求被拒 | 422 `REQUEST_VALIDATION_FAILED`（`historical_roster_api.py:79`） | 否 | 不适用 |
| WFC-ROSTER-F001-ERR007 | `CONFIRMED` | `employment_status` 传入不在库内的取值 | **不报错**：按 `Employment.status == 该值` 过滤，结果为空列表 | 200 + 空 `items`、`total=0`（`historical_roster_service.py:119-120`、`:224-226`；后端对该参数只做长度校验，不做值域校验，`historical_roster_api.py:81`） | 否 | 不适用；取值集合的收敛见 §18 Q07 |
| WFC-ROSTER-F001-ERR008 | `CONFIRMED` | `as_of` 为未来日期 | **不报错**：返回 200 + 空列表（未来时点没有在册人员） | 200 + `items=[]`、`total=0`（`historical_roster_service.py:110-111`；测试 `test_historical_roster_api.py:357-368`） | 否 | 不适用 |
| WFC-ROSTER-F001-ERR009 | `CONFIRMED` | 主组织下拉请求被拒（账号缺 `ORGANIZATION_VIEW`） | 下拉静默退化为空选项；名册接口与其它筛选项不受影响 | 页面无报错文案（`HistoricalRosterWorkspace.tsx:131-136`） | 否 | 不适用；是否补只读候选端点见 §18 Q04 |
| WFC-ROSTER-F001-ERR010 | `CONFIRMED` | 名册接口 5xx 或网络异常 | 请求失败，事务回滚，无数据变化 | 页面顶部错误条，文案取后端 `message`，缺省「历史花名册加载失败」（`HistoricalRosterWorkspace.tsx:120-124`） | 是——改条件或重试 | 自动回滚（`apps/api/src/hris/core/database.py:26-28`） |
| WFC-ROSTER-F001-ERR011 | `CONFIRMED` | 同一 `as_of` 被并发重复查询 | 天然幂等：每次请求独立读取同一份时点快照，两次结果一致；本功能没有写操作，因此没有并发写冲突 | 正常 200 | —— | 不适用 |
| WFC-ROSTER-F001-ERR012 | `CONFIRMED` | 查询期间底层数据被并发修改 | 本功能不持有写锁、不做加锁读取；返回的是该次请求事务内的一致切片。跨请求的一致性由被引用表的生效区间语义保证（`historical_roster_service.py:58-62`） | 正常 200 | 是——需要稳定视图时按同一 `as_of` 重新查询 | 不适用 |
| WFC-ROSTER-F001-ERR013 | `CONFIRMED` | 后台任务中断 | `NOT_APPLICABLE`：本功能没有后台任务（依据 §11.2） | —— | —— | —— |
| WFC-ROSTER-F001-ERR014 | `CONFIRMED` | 下游系统失败 | `NOT_APPLICABLE`：本功能不调用外部系统（依据 §11.2） | —— | —— | —— |
| WFC-ROSTER-F001-ERR015 | `CONFIRMED` | 应用回滚时的数据影响 | 回滚不影响任何数据：本功能不写数据，被引用表不受本功能影响 | —— | —— | 回滚后接口与页面一并回到上一版本（见 §16） |
| WFC-ROSTER-F001-ERR016 | `PENDING` | 误把花名册结果当作完整档案快照使用（例如据此认定某人当时没有任何修正） | 当前只能靠界面提示条与 `field_history_available` 提醒，无法在结果层面阻止误用 | —— | —— | 是否引入「结果可信度」显式标记见 §18 Q01 |

## 13. 审计与数据保护

| ID | 状态 | 动作 | 审计内容 | 禁止记录内容 | 保留要求 |
|---|---|---|---|---|---|
| WFC-ROSTER-F001-AUD001 | `CONFIRMED` | 查询历史花名册 | **不写审计行**：本功能是纯读服务，服务层明确不产生写操作，因此不需要 `actor_id` / `trace_id`（`historical_roster_service.py:93`） | —— | —— |
| WFC-ROSTER-F001-AUD002 | `CONFIRMED` | 修正字段的写入审计 | 修正记录由 WFC-PEOPLE-F001 写入 `person_field_versions` 并留存审计；本功能只读该结果，不参与写入（`person_corrections_service.py:61-76`） | 不记录证件号等明文敏感值 | 跟随 WFC-PEOPLE-F001 的审计保留策略 |
| WFC-ROSTER-F001-AUD003 | `PENDING` | 「历史花名册读取」本身是否需要留痕（读审计） | 当前实现不写读审计；是否需要记录「谁在什么时点查了哪份历史名册」尚未拍板 | —— | 见 §18 Q08 |

- 敏感字段加密：`NOT_APPLICABLE`。依据：本功能不写入任何表（`historical_roster_service.py:92-96`），不产生需要加密存储的字段；人员姓名的加密要求属于 `docs/01-foundation/07-人员档案领域规范.md` 与 WFC-PEOPLE-F001 的范围。
- 页面脱敏：页面展示的字段为工号、姓名（时点）、主组织（时点）、职位（时点）、在职状态（时点）、入职日期（时点），均不是敏感子记录（证件号、联系方式等）；接口不返回敏感子记录（`historical_roster_api.py:15-17`）。因此本页不需要额外的脱敏处理。
- 明文访问：`NOT_APPLICABLE`。依据：本功能不存在「必须以明文才能读取」的字段（区别于人员档案的证件明文查看）。
- 导出与临时文件：`NOT_APPLICABLE`。依据：本模块没有导出端点（`historical_roster_api.py` 只定义 1 组 GET），页面也没有导出入口或下载调用（`HistoricalRosterWorkspace.tsx` 无 `apiDownload` 调用）。
- 非生产数据：验收使用合成数据；现有自动化测试即采用合成 fixture（`apps/api/tests/integration/test_historical_roster_api.py:33-183` 的 `_organization_type` / `_person` / `_employment` / `_assignment` / `_correction` 工厂），示例值一律使用「某员工 / 某部门」这类占位。

## 14. 非功能需求

| ID | 状态 | 类别 | 可验证要求 | 环境/数据量 | 验证证据 |
|---|---|---|---|---|---|
| WFC-ROSTER-F001-NFR001 | `CONFIRMED` | 性能 | 服务端分页，单页固定 20 条且 `showSizeChanger=false`；后端 `limit` 上限 200 | 本机开发库；数据量由企业组织规模决定 | `HistoricalRosterWorkspace.tsx:23`、`:284-291`；`historical_roster_api.py:82-83` |
| WFC-ROSTER-F001-NFR002 | `CONFIRMED` | 一致性 | 计数行与分页器取同一个 `total`（服务端一次 count、一次取页），不得出现两处口径不一致 | 本机开发库 | `historical_roster_service.py:151-173`；`HistoricalRosterWorkspace.tsx:166`、`:283-291`；测试 `test_historical_roster_api.py:495-542` |
| WFC-ROSTER-F001-NFR003 | `CONFIRMED` | 可用性 / 可访问性 | 筛选控件具备 `aria-label`（查看日期、主组织、在职状态、搜索姓名或工号）；表格行键为 `person_id`；在职状态不只依赖颜色，同时输出「在职 / 待入职」文字 | 键盘与屏幕阅读器人工检查 | `EffectiveDatePicker.tsx:23`；`HistoricalRosterWorkspace.tsx:195`、`:207`、`:219`、`:230`、`:256-263` |
| WFC-ROSTER-F001-NFR004 | `CONFIRMED` | 兼容 | 页面使用仓库锁定的 Ant Design 6.5.2 组件，不使用已废弃属性 | 生产构建 `npm run build` | D-090；`docs/design/antd-page-interaction-standard.md` §2；`node scripts/check-antd-usage.mjs` 0 违规（证据见 §16） |
| WFC-ROSTER-F001-NFR005 | `CONFIRMED` | 复用 | 页面骨架、筛选栏、表格与空态统一使用 `WorkspaceShell`、`FilterBar`、`FilterField`、`DataTable`、`EmptyState`、`EffectiveDatePicker`，不在本能力域内出现第二套写法 | 全站一致性 | D-091；`apps/web/src/business/components/`；`HistoricalRosterWorkspace.tsx:9-14` |
| WFC-ROSTER-F001-NFR006 | `CONFIRMED` | 可观测 | 每次响应返回 `trace_id`，可用于按请求串联页面操作与后端日志 | 本机开发库 | `apps/api/src/hris/core/errors.py:29-30`、`:42`、`:65` |
| WFC-ROSTER-F001-NFR007 | `CONFIRMED` | 安全 | 页面不展示也不提交任何个人敏感数据；本功能只读，无写路径 | 本机开发库 | §9 权限表、§13 敏感字段条目、`historical_roster_api.py:15-17` |
| WFC-ROSTER-F001-NFR008 | `PENDING` | 性能 | 页面首屏（名册 + 组织下拉）的响应时间目标 | 需要容量输入：本机并发用户数、单时点在册人数、人员档案条数、组织条数 | 缺容量输入，暂不可验收；输入模板见 `docs/input-packs/templates/07-capacity-scenarios.csv`，容量场景见 `docs/input-packs/09-nonfunctional-acceptance-input.md` |

## 15. 验收场景

### WFC-ROSTER-F001-AC001 按今天时点查在册名册

- 类型：正常
- 前置数据：1 名在职人员（工号 `990301`、姓名「某员工」、主组织「某部门」、职务「某职位」、计划入职日 ≤ 今天、状态 `active`），1 条 `relation_type='primary'` 的任职。
- Given：账号具备 `PERSON_VIEW`，进入侧栏「历史花名册」。
- When：页面加载完成。
- Then：请求为 `GET /api/v1/workforce/people/roster-history?as_of=<今天>&limit=20&offset=0`；表格出现该人员，列「工号 / 姓名（时点）/ 主组织（时点）/ 职位（时点）/ 在职状态（时点）/ 入职日期（时点）/ 操作」齐全；在职状态显示绿色「在职」Tag；计数行显示「共 1 人（截至 <今天>）」；页面顶部出现固定口径提示条。
- 数据库/事件/审计证据：只读操作，不产生审计行（`audit_logs` 行数不变）。
- 自动化层级：后端集成测试 + 前端单元测试。

### WFC-ROSTER-F001-AC002 边界——历史时点取当时的组织与职务

- 类型：边界
- 前置数据：同一段雇佣下两段主职任职：第一段 `effective_from=2026-01-01`、`effective_to=2026-06-30`（组织 A），第二段 `effective_from=2026-07-01`、`effective_to` 为空（组织 B）；两段任职同一职务。
- Given：依次以 `2026-05-01` 与 `2026-08-01` 两个时点查询。
- When：调用 `GET /api/v1/workforce/people/roster-history?as_of=...`。
- Then：`2026-05-01` 返回组织 A 的编码与名称，`2026-08-01` 返回组织 B 的编码与名称；两段的入职日期、在职状态一致；同一时点只返回一行。
- 数据库/事件/审计证据：两次查询的 `items[0].organization_code` 分别为 A 与 B；无审计行。
- 自动化层级：后端集成测试（`test_historical_roster_api.py:213-282`）。

### WFC-ROSTER-F001-AC003 边界——修正生效日前 / 生效日 / 生效后

- 类型：边界
- 前置数据：人员「某员工」有一条 `display_name` 修正，生效日 `2026-03-01`，新值为「某员工（修正后）」；另一名人员无任何修正记录。
- Given：依次以 `2026-02-01`（修正前）、`2026-04-01`（修正后）查询。
- When：调用接口。
- Then：`2026-02-01` 返回登记姓名，该行 `field_history_available=false`、`corrected_fields=[]`；`2026-04-01` 返回修正后姓名，该行 `field_history_available=true`、`corrected_fields=["display_name"]`；无修正记录的人员在两个时点都等于当前登记值；响应顶层 `field_history_note` 含「不是完整的历史档案快照」。
- 数据库/事件/审计证据：`person_field_versions` 行数不变；无审计行。
- 自动化层级：后端集成测试（`test_historical_roster_api.py:285-354`）。

### WFC-ROSTER-F001-AC004 边界——未来时点返回空列表而不是 422

- 类型：边界
- 前置数据：无。
- Given：账号具备 `PERSON_VIEW`。
- When：以今天 + 30 天为 `as_of` 调用接口。
- Then：返回 200，`items=[]`、`total=0`；页面显示空态「该时点没有在册员工」，不出现错误条。
- 数据库/事件/审计证据：无数据变化，无审计行。
- 自动化层级：后端集成测试（`test_historical_roster_api.py:357-368`）。

### WFC-ROSTER-F001-AC005 边界——该时点尚无在册员工

- 类型：边界
- 前置数据：1 名人员，计划入职日 `2026-06-01`（时点之前未入职）。
- Given：账号具备 `PERSON_VIEW`。
- When：分别以 `2026-03-01` 与 `2026-07-01` 查询。
- Then：`2026-03-01` 返回 200 且 `items=[]`、`total=0`；`2026-07-01` 返回该人员，`total=1`。
- 数据库/事件/审计证据：无数据变化，无审计行。
- 自动化层级：后端集成测试（`test_historical_roster_api.py:371-402`）。

### WFC-ROSTER-F001-AC006 正常——按主组织 / 在职状态 / 姓名工号筛选

- 类型：正常
- 前置数据：组织 A 下一名在职人员（`active`），组织 B 下一名待入职人员（`pending_start`）。
- Given：账号具备 `PERSON_VIEW`，在筛选区依次选择主组织、选择在职状态、输入搜索关键字。
- When：点「查询」。
- Then：按主组织筛选只返回该组织人员；按在职状态筛选只返回 `pending_start` 人员；按姓名关键字（时点姓名）搜索命中该人员；按工号搜索命中该人员；未点「查询」前不发请求；点「重置」后筛选清空且查看日期回到今天。
- 数据库/事件/审计证据：无数据变化，无审计行。
- 自动化层级：后端集成测试（`test_historical_roster_api.py:412-492`）+ 前端单元测试（`HistoricalRosterWorkspace.test.tsx:115-152`）。

### WFC-ROSTER-F001-AC007 正常——分页与计数行取同一个 total

- 类型：正常
- 前置数据：3 名在册人员。
- Given：账号具备 `PERSON_VIEW`。
- When：依次请求 `limit=2&offset=0` 与 `limit=2&offset=2`。
- Then：两次响应 `total` 均为 3；`items` 长度分别为 2 与 1；响应回显 `limit` / `offset`；页面计数行与分页器都显示 3。
- 数据库/事件/审计证据：无数据变化，无审计行。
- 自动化层级：后端集成测试（`test_historical_roster_api.py:495-542`）+ 前端单元测试。

### WFC-ROSTER-F001-AC008 异常——as_of 缺失或格式非法

- 类型：异常 / 规则拒绝
- 前置数据：无。
- Given：账号具备 `PERSON_VIEW`。
- When：分别不带 `as_of`、传 `as_of=2026-13-45`、传 `as_of=not-a-date` 调用接口。
- Then：三次都返回 422，`code` 均为 `REQUEST_VALIDATION_FAILED`；不查库、不返回名册。
- 数据库/事件/审计证据：无数据变化，无审计行。
- 自动化层级：后端集成测试（`test_historical_roster_api.py:186-210`）。

### WFC-ROSTER-F001-AC009 权限——无 `PERSON_VIEW` 被拒，缺 `ORGANIZATION_VIEW` 只影响下拉

- 类型：权限
- 前置数据：账号 A 不持有 `PERSON_VIEW`；账号 B 持有 `PERSON_VIEW` 但不持有 `ORGANIZATION_VIEW`。
- Given：账号 A 与账号 B 分别进入历史花名册。
- When：调用 `GET /api/v1/workforce/people/roster-history`；账号 B 同时触发主组织下拉请求。
- Then：账号 A 返回 403 `PERMISSION_DENIED`，侧栏不渲染「历史花名册」入口；账号 B 返回 200 并正常看到名册，但主组织下拉为空选项且不报错。
- 数据库/事件/审计证据：无数据变化，无审计行。
- 自动化层级：后端集成测试（`test_historical_roster_api.py:545-556`）+ 前端单元测试。

### WFC-ROSTER-F001-AC010 幂等——同一时点重复查询结果一致

- 类型：幂等
- 前置数据：与 AC002 相同的合成数据。
- Given：账号具备 `PERSON_VIEW`。
- When：对同一个 `as_of` 连续发起两次相同请求。
- Then：两次响应体的 `items`、`total`、`limit`、`offset` 完全一致；不产生任何写入或副作用。
- 数据库/事件/审计证据：`audit_logs` 与被引用表行数不变。
- 自动化层级：后端集成测试。

### WFC-ROSTER-F001-AC011 审计证据核对——只读不留痕、限制三处表达

- 类型：审计
- 前置数据：与 AC003 相同的合成数据（1 人有修正、1 人无修正）。
- Given：账号具备 `PERSON_VIEW`，查询 `as_of=2026-04-01`，并打开某行的「查看时点信息」抽屉。
- When：查询与查看抽屉均完成。
- Then：`audit_logs` 行数与查询前一致（只读功能不写审计）；响应顶层 `field_history_note` 含「不是完整的历史档案快照」；页面顶部提示条文案与抽屉底部提示条文案一致且含「未被修正过的字段等于当前值」；抽屉内「修正过的字段」对有修正的人显示字段中文名（`display_name` → 「显示姓名」），对无修正的人显示「无（该时点字段值等于当前登记值）」。
- 数据库/事件/审计证据：`audit_logs` 计数比对；接口响应体与页面 DOM 文案。
- 自动化层级：后端集成测试（`test_historical_roster_api.py:353-354`）+ 前端单元测试（`HistoricalRosterWorkspace.test.tsx:94-104`、`:154-164`）+ 人工 UAT。

### WFC-ROSTER-F001-AC012 审计证据核对——并发重复查询

- 类型：并发
- 前置数据：与 AC002 相同的合成数据。
- Given：两个请求同时到达服务端。
- When：两个请求查询同一个 `as_of`。
- Then：两个请求都返回 200，且各自的 `items` 一致；无写冲突、无锁等待、无数据变化（只读功能）。
- 数据库/事件/审计证据：`audit_logs` 与被引用表行数不变。
- 自动化层级：人工 UAT（代码核对，核对点已记录在 §12 ERR011 / ERR012）。

## 16. 迁移、发布与回滚

- 现有数据影响：本功能不拥有数据、不写数据，只读取 `persons`、`employments`、`employment_assignments`、`organizations`、`organization_versions`、`job_catalog`、`job_catalog_versions`、`person_field_versions`；本轮无结构变更、无数据迁移。
- 数据迁移与校验：不适用——本功能不提供导入功能，名册数据只能由既有的雇佣、任职与人员修正路径产生。
- 功能开关或模块启用：没有功能开关；入口按 `PERSON_VIEW` 权限显隐（`navigation.ts:74-80`）。
- 发布顺序：后端读接口与前端列表页一同交付；前端先发布、后端未发布时页面报 404 错误条，后端先发布、前端未发布时多出一个无人访问的接口——两种顺序都不产生数据不一致。
- 升级兼容：接口合同版本 v1，`as_of` 必填与各参数取值域不变（§11.3）；既有消费方不受影响。
- 应用回滚：前端回滚到上一构建即可；后端回滚不涉及本功能的迁移（本功能无迁移）。
- 数据不可逆时的恢复或前向修复：不适用——本功能不写数据，回滚不会删除或改变任何数据。

发布前门禁（2026-10-24 实现轮次的确定性检查证据，登记自交付报告；本轮只做文档补全，未重跑）：

| 项 | 命令 | 结果 |
|---|---|---|
| 迁移零漂移 | `alembic -c alembic-business.ini upgrade head` + `alembic -c alembic-business.ini check`（临时库 `corehr_test_m1`） | upgrade 成功；check 输出 `No new upgrade operations detected.` |
| 后端集成测试 | `pytest -q tests/integration/test_historical_roster_api.py` | 8 passed |
| 前端守卫 | `node scripts/check-antd-usage.mjs` | 0 处违规 |
| 前端类型 | `npx tsc -b` | exit 0 |
| 前端测试 | `npm run test:run` | 见交付报告 |

## 17. 可观测与运行手册

- 指标：本功能不新增业务指标。现有可观测项：接口调用量与错误码分布（401 / 403 / 422）、单次查询的 `total` 规模。
- 日志和Trace：每次响应带 `trace_id`（`apps/api/src/hris/core/errors.py:29-30`、`:42`、`:65`）；排查某一次查询时用 `trace_id` 关联请求日志。本功能不写审计行，因此审计页查不到「谁查了历史花名册」（见 §18 Q08）。
- 告警：本功能不定义专属告警；接口 5xx 沿用平台内核既有告警口径。
- 后台任务：无（依据 §11.2）。
- 人工补偿：不适用——只读功能没有写入失败需要补偿的场景；业务纠错由 WFC-PEOPLE-F001 的【修正】动作完成。
- 健康检查：页面可用性依赖 `GET /api/v1/workforce/people/roster-history` 的可用性；主组织下拉的可用性依赖 `GET /api/v1/organizations/tree`（下拉失败不阻断名册，见 ERR009）。

## 18. 待确认问题

| ID | 问题 | 影响规则/场景 | Owner | 期望日期 | 不确认时的处理 |
|---|---|---|---|---|---|
| WFC-ROSTER-F001-Q01 | 待确认清单 **A5**「历史花名册的『字段级历史』精度限制，是否接受」。**现状**：时点的人员字段值 = 登记值 + 生效日期 ≤ 查询日期的最后一条修正；**没被修正过的人，其时点的姓名/证件等于当前值**，精度取决于 `person_field_versions` 的修正记录覆盖率，界面已用提示条明说、未做「快照还原」。**需要你给**：是否接受当前口径作为长期方案，还是改为 ①新建独立的「人员字段历史」表（每次修改都留痕，与修正解耦，代价是每人每次改字段多一行写入）。**不拍板的后果**：用户可能误以为花名册能回看到任意历史字段，页面上的提示条不能替代口径共识 | BR019、ASM-05、§7 限制说明、§12 ERR016、AC003 | 产品决策人 + 企业口径提供方 | 企业 UAT 前 | 采用已实现行为：保持当前口径，界面与接口如实声明不是完整历史回放；补齐历史字段的动作属 D-105 修正语义，不在本功能范围 |
| WFC-ROSTER-F001-Q02 | 待确认清单 **A22**「历史花名册的『主组织』筛选按当前树还是历史树」。**现状**：主组织下拉取的是**当前**组织树（`/organizations/tree` 不带 `as_of`），因此历史时点已撤销的组织**不在选项里**；M2 已落地组织树 `as_of` 切片（`GET /api/v1/organizations/tree?as_of=`），技术上可支持历史树筛选，但前端尚未接。**需要你给**：是否要按历史时点取组织树。**不拍板的后果**：用户可能对「某时点的名册」下「按当前组织筛」，筛出与该时点无关的结果，且筛不到当时存在、现已撤销的组织 | BR020、ASM-06、§2.2、AC006 | 产品决策人 | 企业 UAT 前 | 采用已实现行为：下拉取当前组织树；历史树筛选待 D-103 能力在前端接入口后再评估 |
| WFC-ROSTER-F001-Q03 | 待确认清单 **P-15**「画板通过后是否即授权前端按画板开发/替换」：是否确认把画板 `Gxgyj` 的 Review 状态改为 `PROTOTYPE_APPROVED`。**2026-10-24 产品决策人已确认全部画板并签字**，§10.4 状态升级为 `PROTOTYPE_APPROVED` | §10.1 原型状态、§10.4 PROT001、§19 T003 | 产品决策人 | 2026-10-25 | 已关闭：2026-10-24 产品决策人签字确认画板，规范 §10.2 的前端开发门禁解除，本功能可按画板继续开发 |
| WFC-ROSTER-F001-Q04 | 主组织下拉依赖 `GET /api/v1/organizations/tree`（要求 `ORGANIZATION_VIEW`），只持 `PERSON_VIEW` 的账号看不到任何组织选项，且下拉失败时静默为空。**现状**：页面不提示「下拉为空是因为缺权限」。**需要你给**：是否为花名册单独开一个只返回 id 与名称的组织候选端点，或把下拉请求失败显式提示。**不拍板的后果**：只读账号会以为「该时点没有组织」，而不是「没有组织查看权限」 | ASM-07、§9 PERM003、§12 ERR009、AC009 | 产品决策人 | 企业 UAT 前 | 采用已实现行为：下拉静默为空，名册列表不受影响；不做新的候选端点 |
| WFC-ROSTER-F001-Q05 | 搜索关键字中的 SQL 通配符是否需要转义。**现状**：实现把关键字直接拼成 `ilike` 模式（`%关键字%`），用户输入的 `%` 与 `_` 会被当作通配符，而不是字面量。**需要你给**：是否转义 `%` / `_`（转义后 `%` 只匹配字面百分号）。**不拍板的后果**：搜 `%` 会匹配全部人员，搜 `a_b` 会额外命中 `axb`，搜索结果与用户预期不一致 | BR021、§12、AC006 | 产品决策人 | 企业 UAT 前 | 采用已实现行为：不转义，搜索按 `ilike` 通配符语义执行 |
| WFC-ROSTER-F001-Q06 | 搜索是否应同时匹配时点法定姓名。**现状**：搜索只匹配工号与**时点显示姓名**（`display_name`），不匹配时点法定姓名（`legal_name`），尽管响应体两个字段都返回。**需要你给**：是否把 `legal_name` 一并纳入搜索范围。**不拍板的后果**：以法定姓名（而非显示姓名）登记或展示的员工无法被搜到 | BR022、AC006 | 产品决策人 | 企业 UAT 前 | 采用已实现行为：只匹配工号与时点显示姓名 |
| WFC-ROSTER-F001-Q07 | 在职状态筛选的取值集合。**现状**：后端 `employment_status` 参数只做长度校验、不做值域校验（任意字符串都会命中过滤，通常表现为空结果）；前端下拉固定只有「在职」`active` 与「待入职」`pending_start` 两项，而 `withdrawn` / `terminated` 被在册口径永久排除。**需要你给**：筛选下拉是否需要覆盖其它状态，或后端是否需要对非法取值直接返回 422。**不拍板的后果**：用户选了后端不存在的状态会看到空结果却得不到任何解释 | BR014、§12 ERR007 | 产品决策人 | 企业 UAT 前 | 采用已实现行为：前端只提供两项；后端不做值域校验，非法取值返回空结果 |
| WFC-ROSTER-F001-Q08 | 「历史花名册读取」本身是否需要留痕。**现状**：本功能是纯读服务，不写任何审计行，因此审计页查不到「谁在什么时点查了哪份历史名册」。**需要你给**：是否需要为历史名册读取增加读审计（写审计会引入写入路径与保留期口径）。**不拍板的后果**：涉及编制复核、争议核查的场景无法追责到人 | §13 AUD003、§17 日志与 Trace、AC011 | 产品决策人 | 企业 UAT 前 | 采用已实现行为：不写读审计；排查只能靠 `trace_id` 关联请求日志 |
| WFC-ROSTER-F001-Q09 | Moka 花名册的其余动作（导出 / 对比 / 批量）是否单独立项。**现状**：本轮只按 D-102 落了时点查询，没有导出、没有跨时点对比、没有批量动作（画板登记表 `implementationDeltas` 第 3 条已登记）。**需要你给**：这些动作是否需要、优先级如何。**不拍板的后果**：用户在画板上看到导出等入口的预期会在 UAT 时变成缺口 | §2.2、§19 T006 | 产品决策人 | 企业 UAT 前 | 采用已实现行为：本轮只做时点查询，其余动作不在本功能范围 |

## 19. 开发任务与追踪

| 任务ID | 目标 | 依赖 | 文件/模块所有权 | 需求追踪注释 | 验收场景 | 状态 | 交付证据 |
|---|---|---|---|---|---|---|---|
| WFC-ROSTER-F001-T001 | 按《模块功能需求文档规范》补全历史花名册功能需求文档的 20 章模板，登记 Pencil 画板 `Gxgyj`、字段合同、权限、错误码与验收场景 | 无 | 仅 `docs/requirements/WFC-workforce-core/WFC-roster/WFC-ROSTER-F001-historical-roster.md` | 文档头部登记规范 17 号；正文引用 D-102 / D-105 / D-090 / D-091 / D-087 / A5 / A22 / P-15 | AC001–AC012 的判定依据 | `DELIVERED` | 本文件（v0.2，2026-10-24） |
| WFC-ROSTER-F001-T002 | 后端只读接口与领域服务：按 as_of 切片区间化表、取主档登记值与已生效字段修正、返回限制说明字段 | D-102 | `apps/api/src/hris/modules/workforce/historical_roster_api.py`、`historical_roster_service.py` | 已写 `Requirement: D-102 — …`（`historical_roster_api.py:6-17`；`historical_roster_service.py:6-24`、`:47-48`、`:54-57`、`:65-68`、`:397-399`） | AC001–AC005、AC008、AC010 | `DELIVERED` | 后端集成测试 8 条通过（见 §16 发布前门禁） |
| WFC-ROSTER-F001-T003 | 前端历史花名册宿主页：筛选栏、计数行、表格、行内「查看时点信息」抽屉与固定口径提示条 | WFC-ROSTER-F001-Q03（画板签字，`PROTOTYPE_APPROVED`） | `apps/web/src/business/features/workforce/HistoricalRosterWorkspace.tsx`、`HistoricalRosterWorkspace.test.tsx`、`apps/web/src/business/navigation.ts` | 已写 `Requirement: D-102 — …` 与 `Requirement: D-091 — …`（`HistoricalRosterWorkspace.tsx:17-19`、`:93`、`:138`、`:146`、`:176-177`；`navigation.ts:74`） | AC001、AC003、AC006、AC007、AC009、AC011 | `DELIVERED` | 前端单元测试通过；`check-antd-usage.mjs` 0 违规；`tsc -b` exit 0（见 §16） |
| WFC-ROSTER-F001-T004 | 后端集成测试与前端单元测试，覆盖必填校验、时点切片、修正生效前后、未来时点、筛选、分页、权限 | 无 | `apps/api/tests/integration/test_historical_roster_api.py`、`apps/web/src/business/features/workforce/HistoricalRosterWorkspace.test.tsx` | 测试函数 docstring 引用 `Requirement: D-102`（`test_historical_roster_api.py:190`、`:218`、`:290`、`:361`、`:375`、`:417`、`:500`、`:550`） | AC001–AC010 | `DELIVERED` | 后端 8 passed；前端用例逐条对应 AC001 / AC003 / AC006 / AC007 / AC009 / AC011 |
| WFC-ROSTER-F001-T005 | 主组织筛选改为按历史时点组织树取选项 | WFC-ROSTER-F001-Q02 | `apps/web/src/business/features/workforce/HistoricalRosterWorkspace.tsx`、`apps/web/src/business/features/workforce/api.ts` | 待写 `Requirement: WFC-ROSTER-F001-BR020 — 原因` | AC006 | `BLOCKED`（阻塞原因：Q02 未拍板） | — |
| WFC-ROSTER-F001-T006 | 搜索关键字的 SQL 通配符转义 | WFC-ROSTER-F001-Q05 | `apps/api/src/hris/modules/workforce/historical_roster_service.py`、`apps/api/tests/integration/test_historical_roster_api.py` | 待写 `Requirement: WFC-ROSTER-F001-BR021 — 原因` | AC006 | `BLOCKED`（阻塞原因：Q05 未拍板） | — |

### 19.1 任务卡

#### WFC-ROSTER-F001-T001 建立历史花名册功能需求文档

- 来源功能：WFC-ROSTER-F001
- 目标：把历史花名册从「实现口径说明」补全为《模块功能需求文档规范》§7 的 20 章功能需求文档，可逐条 Review 业务规则、数据、权限、接口、异常、审计、NFR 与验收场景。
- 状态：`DELIVERED`
- 依赖任务：无
- 所有权：`docs/requirements/WFC-workforce-core/WFC-roster/WFC-ROSTER-F001-historical-roster.md`
- 禁止修改：其它需求文档、`docs/01-foundation/` 下的规范与决策文档、后端与前端生产代码、测试文件。
- 业务规则：BR001–BR022
- 需求追踪注释：文档头部登记规范 17 号；正文引用 D-102 / D-105 / D-090 / D-091 / D-087 / A5 / A22 / P-15。
- 验收场景：AC001–AC012 的判定依据
- 前端交互载体：不适用（本任务不改前端）

- 输入与前置条件：
  - 已批准接口、数据和原型：接口合同见 §11.1；数据口径见 §4.2；原型 `Gxgyj`（`PROTOTYPE_APPROVED`，2026-10-24）见 §10.4。
  - 环境与测试数据：不涉及运行环境；文档中的示例值一律使用「某员工 / 某部门 / 某职位」占位。
  - 假设：不得包含 PENDING 业务假设——ASM-05 / ASM-06 与 Q01 / Q02 只登记问题，不写成结论。
- 实现要求：
  1. 20 章标题与顺序严格对齐规范 §7；不适用的章节写 `NOT_APPLICABLE` 及依据，不得删除。
  2. 每一条单条规则（业务规则 / 数据 / 权限 / 接口 / 异常 / 审计 / NFR）都带规范 §5.2 允许的状态词。
  3. 正文中的每个字段名、错误码、权限码、函数名与文件路径都能在实现代码中指出出处。
  4. 文档头部状态保持 `DRAFT`；画板签字与文档状态分开陈述。
- 测试与验证：
  - 单元：不适用（文档任务）。
  - 集成：不适用。
  - E2E/安全/性能：不适用。
  - 运行命令或确定性检查入口：按规范 §15 逐项自查并写入 §20.1；核对 20 章标题、编号连续性、UTF-8 无 BOM 与 LF 行尾。
- 数据与发布影响：
  - 迁移：无。
  - 兼容：无代码或接口变更。
  - 回滚/恢复：本文档为纯新增内容，回滚即删除本文件的本次改动。
- 交付回执：
  - 修改文件：`docs/requirements/WFC-workforce-core/WFC-roster/WFC-ROSTER-F001-historical-roster.md`
  - 需求追踪注释：文档头部登记规范 17 号；正文引用 D-102 / D-105 / D-090 / D-091 / D-087 / A5 / A22 / P-15
  - 测试结果：不适用（文档任务）
  - 迁移结果：不适用（无迁移）
  - 未完成项：Q01–Q09 仍待产品决策人拍板（业务验收未完成，功能状态保持 `DRAFT`）
  - 风险与后续：文档未经业务评审，不得据此把功能标记为 `APPROVED` 或 `ACCEPTED`
  - Commit/PR/构建证据：本次不执行任何 Git 操作

#### WFC-ROSTER-F001-T002 后端只读接口与领域服务

- 来源功能：WFC-ROSTER-F001
- 目标：`GET /api/v1/workforce/people/roster-history` 能按任意历史时点返回在册名册与当时信息，并在响应里声明「不是完整历史回放」。
- 状态：`DELIVERED`
- 依赖任务：无
- 所有权：`apps/api/src/hris/modules/workforce/historical_roster_api.py`、`apps/api/src/hris/modules/workforce/historical_roster_service.py`
- 禁止修改：其它模块拥有的数据表、迁移链、`apps/web/**`。
- 业务规则：BR001–BR005、BR008–BR016
- 需求追踪注释：`historical_roster_api.py:6-17`；`historical_roster_service.py:6-24`、`:47-48`、`:54-57`、`:65-68`、`:397-399`
- 验收场景：AC001–AC005、AC008、AC010
- 前端交互载体：不适用

- 输入与前置条件：
  - 已批准接口、数据和原型：时点口径见 §4.2；接口合同见 §11.1 API001。
  - 环境与测试数据：合成 fixture（`test_historical_roster_api.py:33-183`）。
  - 假设：不得包含 PENDING 业务假设——字段级历史覆盖率（Q01）与历史组织树筛选（Q02）不写进实现。
- 实现要求：
  1. 区间化表统一走 `interval_filters()`（`effective_from <= as_of` 且 `effective_to` 为空或 `> as_of`）。
  2. `employments` 不是区间表，结束日沿用编制域的 `end_date >= as_of`，并在代码注释里写明与编制域的差异。
  3. 字段修正取值复用 `PersonCorrectionService.effective_overrides()`，不另写一套排序。
  4. 搜索用 `_time_point_display_name()` 参与匹配，修正清空姓名不得被当成「没有修正」。
  5. 每行返回 `field_history_available` / `corrected_fields`，响应顶层返回 `field_history_note`。
  6. 只读服务不引入 `actor_id` / `trace_id`，不写审计行。
- 测试与验证：
  - 单元：不适用（无独立单元层）。
  - 集成：`pytest -q tests/integration/test_historical_roster_api.py`（8 条用例）。
  - E2E/安全/性能：不适用（无前端 E2E；权限用例覆盖 403）。
  - 运行命令或确定性检查入口：`pytest -q tests/integration/test_historical_roster_api.py`；`alembic -c alembic-business.ini check`。
- 数据与发布影响：
  - 迁移：无（本功能不需要新表）。
  - 兼容：接口为新增，响应模型字段自交付起未变（§11.3）。
  - 回滚/恢复：接口为新增，回滚后端即整体下线该端点，无数据残留。
- 交付回执：
  - 修改文件：`apps/api/src/hris/modules/workforce/historical_roster_api.py`、`apps/api/src/hris/modules/workforce/historical_roster_service.py`
  - 需求追踪注释：见上「需求追踪注释」行
  - 测试结果：后端集成测试 8 passed（§16 发布前门禁）
  - 迁移结果：`alembic check` 零漂移
  - 未完成项：无
  - 风险与后续：§11.2 未引入异步事件；若后续引入消息引擎需重新评审本节
  - Commit/PR/构建证据：见实现轮次交付报告

#### WFC-ROSTER-F001-T003 前端历史花名册宿主页

- 来源功能：WFC-ROSTER-F001
- 目标：侧栏「历史花名册」进入独立列表页，能按任意时点查看名册、筛选翻页，并能从行内打开时点信息抽屉。
- 状态：`DELIVERED`
- 依赖任务：WFC-ROSTER-F001-Q03（画板签字，`PROTOTYPE_APPROVED`）
- 所有权：`apps/web/src/business/features/workforce/HistoricalRosterWorkspace.tsx`、`HistoricalRosterWorkspace.test.tsx`、`apps/web/src/business/navigation.ts`、`apps/web/src/business/AppShell.tsx`
- 禁止修改：其它工作区的页面、公共组件的既有行为、后端代码。
- 业务规则：BR012、BR013、BR015–BR018、BR021、BR022
- 需求追踪注释：`HistoricalRosterWorkspace.tsx:17-19`、`:93`、`:138`、`:146`、`:176-177`；`navigation.ts:74`
- 验收场景：AC001、AC003、AC006、AC007、AC009、AC011
- 前端交互载体：`DRAWER`（引用 §10.1 的载体选择理由与 §10.4 的已批准画板 `Gxgyj`）

- 输入与前置条件：
  - 已批准接口、数据和原型：接口 `GET /api/v1/workforce/people/roster-history`；原型文件 `C:\Users\83289\Documents\HRMS\coreHR.pen`，画板 ID `Gxgyj`，版本 `v1.0`，状态 `PROTOTYPE_APPROVED`（2026-10-24 签字）。
  - 环境与测试数据：前端单测用 `fetch` stub（`HistoricalRosterWorkspace.test.tsx:53-55`）。
  - 假设：不得包含 PENDING 业务假设——下拉是否改历史树（Q02）、下拉失败是否提示（Q04）不在本任务内实现。
- 实现要求：
  1. 页面骨架、筛选栏、表格与空态统一复用 `WorkspaceShell` / `FilterBar` / `FilterField` / `DataTable` / `EmptyState` / `EffectiveDatePicker`（D-091）。
  2. 筛选为草稿式：改值不立即请求，点「查询」才提交并回到第一页；「重置」清空并把查看日期回到今天。
  3. 表头带「（时点）」后缀；计数行与分页器取同一个 `total`；时点以服务端回显的 `as_of` 为准。
  4. 顶部固定 info 提示条与抽屉底部提示条使用同一条文案常量；抽屉内「修正过的字段」用 `personFieldLabel` 转中文。
  5. 行内「查看时点信息」用 antd `Drawer`，关闭后宿主页筛选、分页与列表状态保留。
  6. 主组织下拉请求失败时静默退化为空选项，不阻断名册读取。
- 测试与验证：
  - 单元：`npm run test:run`（`HistoricalRosterWorkspace.test.tsx` 覆盖表头与筛选栏顺序、口径提示条、空态、草稿式筛选、重置、抽屉时点信息）。
  - 集成：不适用（前端不直连数据库）。
  - E2E/安全/性能：`node scripts/check-antd-usage.mjs` 0 违规；`npx tsc -b` exit 0。
  - 运行命令或确定性检查入口：见上。
- 数据与发布影响：
  - 迁移：无。
  - 兼容：新增页面与导航项，不改动既有路由行为；`workspaceFromHash` 对未知键回落到工作台（`navigation.ts:165-171`）。
  - 回滚/恢复：前端回滚到上一构建即可，无数据残留。
- 交付回执：
  - 修改文件：`apps/web/src/business/features/workforce/HistoricalRosterWorkspace.tsx`、`HistoricalRosterWorkspace.test.tsx`、`apps/web/src/business/navigation.ts`、`apps/web/src/business/AppShell.tsx`
  - 需求追踪注释：见上「需求追踪注释」行
  - 测试结果：前端用例通过；`check-antd-usage.mjs` 0 违规；`tsc -b` exit 0（§16 发布前门禁）
  - 迁移结果：不适用
  - 未完成项：抽屉未单独出画板（§10.4）
  - 风险与后续：主组织下拉的数据源与权限口径依赖 Q04
  - Commit/PR/构建证据：见实现轮次交付报告

#### WFC-ROSTER-F001-T004 自动化测试

- 来源功能：WFC-ROSTER-F001
- 目标：本功能的正常、边界、异常与权限路径都有确定性自动化证据，不依赖人工判断。
- 状态：`DELIVERED`
- 依赖任务：WFC-ROSTER-F001-T002、WFC-ROSTER-F001-T003
- 所有权：`apps/api/tests/integration/test_historical_roster_api.py`、`apps/web/src/business/features/workforce/HistoricalRosterWorkspace.test.tsx`
- 禁止修改：生产代码（发现缺陷时回写 T002 / T003）。
- 业务规则：BR001–BR016
- 需求追踪注释：测试函数 docstring 引用 `Requirement: D-102`（`test_historical_roster_api.py:190`、`:218`、`:290`、`:361`、`:375`、`:417`、`:500`、`:550`）
- 验收场景：AC001–AC010
- 前端交互载体：不适用

- 输入与前置条件：
  - 已批准接口、数据和原型：接口合同见 §11.1 API001。
  - 环境与测试数据：合成 fixture，示例值使用「合成花名册人员 / 合成原部门」等占位。
  - 假设：不得包含 PENDING 业务假设。
- 实现要求：
  1. 每条用例的 docstring 写明它守护的 `Requirement` ID。
  2. 覆盖必填与格式校验、时点切片、修正生效前后、未来时点、空名册、筛选、分页与权限拒绝。
  3. 断言必须落到具体字段值与错误码，不只断言状态码。
- 测试与验证：
  - 单元：前端 `npm run test:run`。
  - 集成：后端 `pytest -q tests/integration/test_historical_roster_api.py`。
  - E2E/安全/性能：不适用。
  - 运行命令或确定性检查入口：见上。
- 数据与发布影响：
  - 迁移：无。
  - 兼容：无。
  - 回滚/恢复：无数据影响。
- 交付回执：
  - 修改文件：`apps/api/tests/integration/test_historical_roster_api.py`、`apps/web/src/business/features/workforce/HistoricalRosterWorkspace.test.tsx`
  - 需求追踪注释：见上「需求追踪注释」行
  - 测试结果：后端 8 passed；前端用例通过（§16 发布前门禁）
  - 迁移结果：不适用
  - 未完成项：无
  - 风险与后续：并发与读审计场景目前靠人工 UAT + 代码核对（AC012）
  - Commit/PR/构建证据：见实现轮次交付报告

#### WFC-ROSTER-F001-T005 主组织筛选改按历史时点组织树

- 来源功能：WFC-ROSTER-F001
- 目标：主组织下拉给出该时点有效的组织，历史时点已撤销的组织也能被选到。
- 状态：`BLOCKED`
- 依赖任务：WFC-ROSTER-F001-Q02
- 所有权：`apps/web/src/business/features/workforce/HistoricalRosterWorkspace.tsx`、`apps/web/src/business/features/workforce/api.ts`
- 禁止修改：后端组织树端点（D-103 已落地 `as_of`，本任务只改前端接入口）。
- 业务规则：BR020
- 需求追踪注释：待写 `Requirement: WFC-ROSTER-F001-BR020 — 原因`
- 验收场景：AC006
- 前端交互载体：`DRAWER`（引用 §10.1 与 §10.4 的已批准画板）

- 输入与前置条件：
  - 已批准接口、数据和原型：依赖 `GET /api/v1/organizations/tree?as_of=`（`organization_api.py:127-155`，D-103 已落地）；原型沿用 `Gxgyj`。
  - 环境与测试数据：前端单测的 `fetch` stub 需能区分带 / 不带 `as_of` 的组织树请求。
  - 假设：不得包含 PENDING 业务假设——Q02 未拍板前不得开工。
- 实现要求：
  1. 组织树请求随「查看日期」带上 `as_of`，且 `as_of` 为未来日期时按后端 422 `CURRENT_OR_HISTORY_TREE_ONLY` 处理（组织树不接受未来时点，与花名册不同）。
  2. 下拉选项文案保持「<组织名> (<组织编码>)」。
  3. 加载 / 失败 / 空三种状态按 §10.2 表达。
- 测试与验证：
  - 单元：前端单测补「切换查看日期后组织树请求带 `as_of`」与「组织树失败时下拉为空且名册仍可读」两条用例。
  - 集成：不适用。
  - E2E/安全/性能：不适用。
  - 运行命令或确定性检查入口：`npm run test:run`；`node scripts/check-antd-usage.mjs`；`npx tsc -b`。
- 数据与发布影响：
  - 迁移：无。
  - 兼容：只改前端请求参数，不改接口。
  - 回滚/恢复：前端回滚即可。
- 交付回执：
  - 修改文件：（待开工）
  - 需求追踪注释：（待开工）
  - 测试结果：（待开工）
  - 迁移结果：不适用
  - 未完成项：全部
  - 风险与后续：阻塞原因——Q02 未拍板
  - Commit/PR/构建证据：（待开工）

#### WFC-ROSTER-F001-T006 搜索关键字的 SQL 通配符转义

- 来源功能：WFC-ROSTER-F001
- 目标：搜索把 `%` 与 `_` 当字面量处理，搜索结果与用户输入一致。
- 状态：`BLOCKED`
- 依赖任务：WFC-ROSTER-F001-Q05
- 所有权：`apps/api/src/hris/modules/workforce/historical_roster_service.py`、`apps/api/tests/integration/test_historical_roster_api.py`
- 禁止修改：前端页面、其它模块的查询实现。
- 业务规则：BR021
- 需求追踪注释：待写 `Requirement: WFC-ROSTER-F001-BR021 — 原因`
- 验收场景：AC006
- 前端交互载体：不适用（后端任务）

- 输入与前置条件：
  - 已批准接口、数据和原型：接口合同见 §11.1 API001；转义后的搜索语义需要产品确认后再改。
  - 环境与测试数据：合成 fixture。
  - 假设：不得包含 PENDING 业务假设——Q05 未拍板前不得开工。
- 实现要求：
  1. 转义 `\`、`%`、`_` 三个字符，并按数据库方言选择转义符。
  2. 转义不得影响工号与时点姓名的常规包含匹配。
  3. 补两条用例：搜 `%` 不再返回全部人员；搜 `a_b` 不再命中 `axb`。
- 测试与验证：
  - 单元：不适用。
  - 集成：`pytest -q tests/integration/test_historical_roster_api.py`。
  - E2E/安全/性能：不适用。
  - 运行命令或确定性检查入口：见上。
- 数据与发布影响：
  - 迁移：无。
  - 兼容：搜索结果集可能变小（原本被通配符放大的命中消失），属于修正而非破坏性变更，需在 §11.3 登记。
  - 回滚/恢复：纯代码改动，回滚即可。
- 交付回执：
  - 修改文件：（待开工）
  - 需求追踪注释：（待开工）
  - 测试结果：（待开工）
  - 迁移结果：不适用
  - 未完成项：全部
  - 风险与后续：阻塞原因——Q05 未拍板
  - Commit/PR/构建证据：（待开工）

## 20. Review与批准记录

| 版本 | 日期 | 变更摘要 | 产品/业务结论 | 技术结论 | 批准人 |
|---|---|---|---|---|---|
| v0.1 | 2026-10-24 | 初稿：历史花名册的「实现口径说明」——端点合同、时点取值口径、限制说明、页面合同、权限、验收证据与 Pencil 画板登记 | 未评审（文档自述为实现口径说明，非正式需求文档） | 接口与口径逐条指向实现文件；画板状态记为 `PROTOTYPE_APPROVED` | —— |
| v0.2 | 2026-10-24 | v0.2 补全 20 章模板（依据《模块功能需求文档规范》§7）：重排原有内容为 §4 名词与依赖（含时点取值口径与代码落点）、§5 用户故事、§7 业务规则、§8 数据要求、§9 权限要求、§10 交互与页面要求（10.4 归位）、§11–§17、§19 开发任务与追踪；新增 BR001–BR022、DAT001–DAT018、PERM001–PERM006、API001–API002、ERR001–ERR016、AUD001–AUD003、NFR001–NFR008、AC001–AC012 与 T001–T006；把原文件末尾两条游离 bullet 移入 §18 | 画板已于 2026-10-24 由产品决策人签字（`PROTOTYPE_APPROVED`，见 §10.4）；**业务验收尚未完成**，§18 Q01–Q09 仍待拍板，文档状态保持 `DRAFT`（规范 §5.1：不允许以自动化测试通过代替 `ACCEPTED`） | 全部字段名、错误码、权限码、函数名与文件路径均已回代码复核并标注行号；未发明实现中不存在的字段、权限码或错误码 | 文档未批准（画板已签字；文档待业务评审） |

现状说明（按事实记录）：

- 2026-10-24 产品决策人已确认全部 Pencil 画板并签字，本功能的画板 `Gxgyj` 状态为 `PROTOTYPE_APPROVED`（§10.4）。
- 文档本身**未**进入业务评审：§18 Q01–Q09 未拍板，其中 Q01（字段级历史覆盖率）与 Q02（主组织筛选选项来源）直接影响口径选择。
- 按规范 §5.1，自动化测试通过不等于 `ACCEPTED`；按规范 §15 末句「任一关键项为否时，不得进入 `READY_FOR_TASKS`」，本功能状态保持 `DRAFT`。

### 20.1 规范 §15 文档 Review 检查表自查（2026-10-24）

| # | 检查项 | 自查结论 | 依据 |
|---|---|---|---|
| 1 | 文档是否只描述一个可独立验收的功能 | 是 | 全文只描述「按任意历史时点回看在册名册与当时信息」一个业务结果；筛选、分页与行内抽屉是同一结果的不同操作深度，在 §3 给出不拆分理由 |
| 2 | 是否能明确说出谁在什么条件下得到什么结果 | 是 | §3 参与者表（主管理员 / 人事编制查看者 / 组织查看者 / 未登录账号）+ §5 三条用户故事的触发条件、前置条件、主路径、结束状态 |
| 3 | 是否区分确认规则、待确认问题和推荐方案 | 是 | §7 规则表带 `CONFIRMED` / `PENDING` 状态列并写明状态约定；§18 全部为待确认项并给出「不确认时的处理」；本文件未代替产品决策人做结论 |
| 4 | 数据所有者、唯一键、有效日期和历史策略是否明确 | 是 | §8.1 数据所有权（本功能不拥有数据）、唯一键（`persons.id`、任职与修正的服务层唯一性）、生效区间口径与 `employments` 的差异；§8.2 每行含「历史策略」列 |
| 5 | 权限是否覆盖动作、数据范围、字段和高风险操作 | 是 | §9 PERM001–PERM006 覆盖读、入口可见性、组织下拉数据源、敏感字段边界、401 与 `*` 放行；无写操作，已在代办说明中写明「不适用」的项 |
| 6 | 接口是否明确幂等、事务、版本和失败补偿 | 是 | §11.1 两个接口逐个写明幂等性与单请求单事务边界；§12 覆盖必填、越界、权限、并发与回滚；§11.2 说明无异步事件及依据 |
| 7 | 是否覆盖异常、并发、回退、审计和敏感数据 | 是 | §12 ERR001–ERR016；§13 AUD001–AUD003 及敏感字段、页面脱敏、明文访问、导出、非生产数据逐项结论；读审计缺口在 AUD003 / Q08 登记 |
| 8 | NFR是否可以在指定环境中验证 | 部分通过 | NFR001–NFR007 可在指定环境验证并给出证据；NFR008（首屏响应时间）因缺容量输入标记 `PENDING`，已在 §14 写明需要的输入文件与验收环境 |
| 9 | 验收场景是否包含明确输入、动作和预期证据 | 是 | §15 AC001–AC012，每条含类型、前置数据、Given / When / Then、数据库或审计证据、自动化层级；覆盖规范 §10 的最小集合（正常、边界、规则拒绝、权限、重复请求、审计证据）与生效日期场景 |
| 10 | 是否可以在不猜业务规则的情况下拆出最小任务 | 是 | §19 六个任务均声明所有权、依赖、追踪注释与验收场景；T005 / T006 因 Q02 / Q05 未决而 `BLOCKED`，未把 PENDING 规则写进任务 |
| 11 | 是否说明对已有数据、模块和部署的影响 | 是 | §16 覆盖现有数据影响、迁移与校验、开关、发布顺序、升级兼容、应用回滚与前向修复，并保留实现轮次的发布前门禁证据；§4.3 列出被引用的表与复用服务 |
| 12 | 是否存在与父级PRD或已确认决策冲突的内容 | 是（无冲突） | 载体选择符合 D-068 / D-069 与交互载体规范 §3；组件复用符合 D-091；原型门禁符合 D-087；时点口径符合 D-102；人员修正语义引用 D-105；权限口径统一为 `PERSON_VIEW`，不要求 `PERSON_SENSITIVE_VIEW`，与 WFC-PEOPLE-F001 的双码要求不冲突（本功能只读且不返回敏感子记录） |
| 13 | 所有需求驱动的代码变化是否明确了追踪注释所引用的ID和预计代码落点 | 是 | §19 T002 / T003 / T004 写明实际落点与已存在的 `Requirement: D-102` / `D-091` 注释；T005 / T006 写明待建的追踪注释格式 |
| 14 | 涉及前端时，是否明确宿主页、`MODAL`/`DRAWER`/`NEW_TAB`载体及其打开、退出和状态恢复行为 | 是 | §10.1 宿主页=列表、主载体=`DRAWER`、选择理由与不选其它载体的原因、hash 路由 `#historical-roster`、抽屉无独立路由且关闭后保留宿主页上下文；§10.3 打开 / 关闭 / 焦点 / 重置策略 |
| 15 | 涉及前端时，是否登记Pencil文件、画板ID、版本和`PROTOTYPE_APPROVED`证据 | 通过 | §10.4 已登记 Pencil 源文件、画板 ID `Gxgyj`、画板名称、版本 `v1.0`、尺寸、载体与状态；`PROTOTYPE_APPROVED` 证据**已存在**（2026-10-24 产品决策人签字确认，`docs/review/pen-artboard-registry.json` `artboards[].id = Gxgyj`）；抽屉未单独出画板，已在 §10.4 与 §18 Q03 登记 |

自查结论汇总：15 项中 14 项通过，1 项为「部分通过」——第 8 项因缺容量输入把 NFR008 标为 `PENDING`（不是编造）。按规范 §15 末句「任一关键项为否时，不得进入 `READY_FOR_TASKS`」，本功能当前状态保持 `DRAFT`：业务验收未完成，且 §18 Q01 / Q02 两项口径问题仍待产品决策人拍板。

### 20.2 修订记录

| 版本 | 日期 | 变更摘要 |
|---|---|---|
| v0.1 | 2026-10-24 | 初稿：历史花名册的实现口径说明（端点合同、时点取值口径、限制说明、页面合同、权限、验收证据、Pencil 画板登记） |
| v0.2 | 2026-10-24 | v0.2 补全 20 章模板（依据《模块功能需求文档规范》§7） |
