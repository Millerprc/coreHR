# Moka 五项功能复刻：语义决策与实现边界

> 生成日期：2026-10-24
> 决策依据：产品决策人 2026-10-24 指令「有些moka的功能，你了解完，跟项目比较一下复刻过来，融合一起」+「其他的都按你的推荐继续搞」
> 权威决策条目：`docs/01-foundation/03-项目决策.md` §8.5（D-102 ~ D-107）
> 现状盘点来源：explore 取证报告（2026-10-24）、`docs/review/moka-vs-corehr-feature-gap.md`

---

## 0. 结论速览

| # | Moka 功能 | coreHR 现状 | 本轮结论 | 决策 ID |
|---|---|---|---|---|
| 1 | 历史花名册 | 8/9 张相关表已生效日期化，`persons` 未版本化 | **补查询层**，不新建人员版本表 | D-102 |
| 2 | 历史组织架构（按最后一次生效日期做生效切片） | 模型完全就位，API 层主动 422 拒绝 | **开放 `as_of` 参数**，不建独立页面 | D-103 |
| 3 | 汇报关系、兼岗 | 汇报关系已全通；兼岗挂在 employment 级，与规范要求的 person 级不符 | **兼岗改 person 级载体** | D-104 |
| 4 | 假期账户与余额 | 账户与流水已是一等实体，余额是真余额非汇总 | **补发假明细 + 时点余额 + leave_types 版本化** | D-107 |
| 5 | 各类排班 | 只有班次与排班结果两类实体 | **补排班类型、草稿发布、换班、批量排班** | D-107 |

---

## 1. D-A：历史花名册的语义

### 1.1 待决问题

- A1：是否允许查任意历史时点？
- A2：要不要还原「当时的姓名、证件号」？

### 1.2 取证事实

- `persons` 表**没有**生效日期化，也没有版本表（`apps/api/src/hris/modules/workforce/models.py:324-348`）。
- 但 8/9 张花名册相关表已区间化：`employments` / `employment_assignments` / `reporting_relations` / `organization_person_relations` / `employment_legal_entity_relations` / `person_labels` 等均带生效起止日期。
- 现成可复用的区间查询实现：`apps/api/src/hris/modules/workforce/extended_service.py:1343-1372` 的 `_count_people` 已按 `effective_from <= X AND (effective_to IS NULL OR effective_to > X)` 过滤。

### 1.3 结论（D-102）

| 问题 | 结论 | 理由 |
|---|---|---|
| A1 任意历史时点 | **允许** | 这是「历史花名册」的全部价值；底层表已具备区间化能力，缺的是对外查询层 |
| A2 还原当时的姓名/证件 | **允许，且不新建第二套版本表** | 复用本轮 W1 建设的 `person_field_versions` 修正版本表（带生效日期）。时点值 = 主档（登记值）＋生效日期 ≤ 查询日期的最后一条修正 |

### 1.4 时点取值规则（唯一口径）

```
人员字段时点值(person, field, as_of)
  = persons 主档值（登记值）
    若存在修正版本 v 满足 v.effective_from <= as_of
      取其中 effective_from 最大的一条 v 的 v.new_value
    否则取主档值

组织/雇佣/任职时点值
  = 区间化表中 effective_from <= as_of AND (effective_to IS NULL OR effective_to > as_of) 的记录
```

> **重要限制（必须如实实现，不得理想化）**：如果 `person_field_versions` 尚未落库或某人从未被修正过，则该人时点的姓名/证件**等于当前值**。这意味着历史花名册的「字段级历史」精度取决于修正记录覆盖率，**不是完整的历史回放**。界面上不得暗示「这是某年某月的完整档案快照」。

### 1.5 端点设计

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/workforce/people/roster-history?as_of=YYYY-MM-DD` | 时点花名册列表，复用现有 `people` 列表的筛选与分页契约 |

---

## 2. D-B：历史组织架构的语义

### 2.1 待决问题

能否解掉 D-059 的阻塞，按日期渲染组织树？

### 2.2 取证事实

- `organization_versions` 已区间化，`organization_events` 承载生效事件 —— **模型完全就位**。
- `apps/api/src/hris/modules/organization/organization_service.py:498-521` 的 `get_current_tree` 把日期写死为 `business_date()`，只需把它改成入参。
- `apps/api/src/hris/modules/organization/organization_api.py:133-138` 主动返回 422 `CURRENT_TREE_ONLY`。
- D-059 原文：「**不建设独立的待生效组织事件页面**；在组织详情中按生效日期查看版本、事件和快照信息」。

### 2.3 结论（D-103）

**开放时点渲染，但不建独立页面。**

- D-059 约束的是「**独立页面**」（一个专门列待生效事件的页面），并未禁止在既有页面上按日期渲染树。
- 因此：在**组织架构页**与**组织详情页**上增加「时点」参数（`as_of`），渲染该时点的组织树；不新建任何顶级菜单页，不新建「待生效组织事件」页。

### 2.4 端点设计

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/organization/tree?as_of=YYYY-MM-DD` | 不传 `as_of` = 当前树（保持现有行为不变）；传则返回该时点有效版本构成的树 |

前端在组织架构页头部增加「查看日期」控件（复用 `apps/web/src/business/components/EffectiveDatePicker.tsx`，D-091），切换后重取树。

---

## 3. D-C：兼岗的载体语义

### 3.1 取证事实

| 载体 | 位置 | 现状 |
|---|---|---|
| employment 级 | `EmploymentAssignment.relation_type = 'concurrent'`（`workforce/models.py:691-717`） | 已有写入路径（HR 事件 `CONCURRENT_ASSIGNMENT`），但把兼岗错误地绑定在某一段雇佣关系上 |
| person 级 | `organization_person_relations`（`workforce/models.py:720-745`） | 字段齐全（含生效起止日期、关系类型），但**无任何写入路径**（死模型） |

规范 `docs/01-foundation/05-*.md:172` 要求员工关系覆盖主组织、兼岗、借调、项目、虚拟组织、实线汇报和虚线汇报，且 D-026 规定「同一时间只有一个主组织，其他关系可以同时存在多个」。

### 3.2 结论（D-104）

**person 级为兼岗唯一权威载体。**

- 兼岗是「一个人在组织里的第二个位置」，与「雇佣关系」正交；挂在 employment 级会导致换雇佣/再入职时兼岗丢失或错挂。
- 保留 `EmploymentAssignment.relation_type` 的**任职类型**语义（主职/兼任/试用等），不再兼作兼岗载体。

### 3.3 迁移策略（避免数据搬迁）

不搬历史数据、不改已有 employment 级行：

1. 新增 person 级兼岗的**写入路径**（服务 + 端点）。
2. 修正 HR 事件 `CONCURRENT_ASSIGNMENT` 的执行器：审批通过后写 person 级 `organization_person_relations`（`relation_type='concurrent'`），**不再**新增 employment 级行。
3. employment 级既有行保留为历史记录，读取端点**不再**以 employment 级为兼岗来源。

---

## 4. 编辑 / 修正的载体决策（D-105、D-106）

### 4.1 语义

| 动作 | 行为 | 写入位置 |
|---|---|---|
| 【编辑】 | 直接修改并保存 | `persons` 主档（覆盖式），审计须记**变更前值与变更后值** |
| 【修正】 | 必须填写生效日期 | `person_field_versions` 修正版本，**不覆盖主档** |

### 4.2 载体

`docs/design/antd-page-interaction-standard.md` §4.3：「禁止嵌套两层业务 Modal/Drawer」。员工档案 Drawer 是预览容器，在其上叠加业务 Modal 属两层业务容器。

**结论：员工档案 Drawer 自身切换编辑态 / 修正态，不新增容器。**

- 【编辑】→ Drawer 隐藏 Tabs，内容区切为编辑表单，底部【取消】【保存】。
- 【修正】→ Drawer 同样整体切为修正表单（待修正字段 / 修正后值 / **生效日期必填** / 原因），并展示「登记值 / 当前生效值」对照；底部【取消】【提交修正】。
- Drawer 新增「修正记录」Tab，列出该员工的修正历史。

### 4.3 已知规范冲突（必须在需求文档中留痕）

`docs/01-foundation/07-*.md:249` 与 `08-*.md:169` 存在「引导使用更正事件」的旧表述，与本次拆分冲突。处理：按 D-105 拆分语义实现，同时**保留** `PERSON_CORRECTION` 事件类型作为修正的审计/流程载体（不删除事件通道），并在新需求文档中标注该冲突待产品决策人复核。

---

## 5. 假期账户与余额（复刻 Moka「当前余额 / 发假明细」）

### 5.1 现状（不是「没有」）

- `leave_balance_accounts`（账户）与 `leave_balance_transactions`（不可变流水）**已是一等实体**，且有 `balance_before / balance_after` 恒等 CHECK 约束（`attendance/models.py:159-241`）。
- `LeaveBalancePanel` 读的是**真余额**，不是接口层汇总。
- 真正缺的是 Moka 的「**发假明细**」（额度规则 / 发放批次）、自动计提调度器、时点余额查询。

### 5.2 本轮实现边界

| 项 | 状态 |
|---|---|
| 时点余额查询（`as_of`） | 本轮实现 |
| 发假明细（发放批次 `leave_grant_batches` + 发放明细行 `leave_grant_items` + 额度规则 `leave_grant_rules`） | 本轮实现骨架，**计提规则值留空待企业输入**（D-107） |
| 自动计提调度器 | 本轮实现**可配置开关 + 调度骨架**，默认关闭，不挂应用启动路径 |
| `leave_types` 版本化 | **不做** —— D-077 规定基础资料未明确包含生效日期则不维护有效期历史版本。需要版本化的是**发假额度规则**，它带生效起止日期 |
| 请假走审批流 | **本轮不做**（跨域，需 BPMS 引擎定稿后接入），在需求文档中登记为差距 |

### 5.3 D-107 约束

以下字段**只建可配置字段容器，不定义取值语义**：计提频率、工龄折算、封顶、清零、结转上限、有效期、离职处理。取值来源为 `docs/input-packs/07-attendance-rule-input.md` §4.1/§4.2，企业输入到位前一律留空并在界面上提示「规则待配置」。

---

## 6. 各类排班（复刻 Moka「排班管理 / 换班记录」）

### 6.1 现状

- 已有：`shifts`（班次）+ `schedule_assignments`（排班结果，UNIQUE employment+date）+ `GET /schedules`。
- 缺：轮班/弹性/自由班等排班类型、排班草稿与发布、月度发布、换班记录、批量排班。
- 缺陷：`shifts.rule_set_id` 指向非版本化规则集，**旧班次会静默跟随新规则**。

### 6.2 本轮实现边界

| 项 | 状态 |
|---|---|
| 排班类型（固定班 / 轮班 / 弹性 / 自由） | 本轮实现**类型骨架 + 规则字段容器**，轮班周期/弹性窗口取值待企业输入（D-107） |
| 排班草稿 → 发布（月度发布） | 本轮实现 |
| 换班记录 | 本轮实现 |
| 批量排班 | 本轮实现（上限 1000，与 D-097 批量异动的批量口径一致） |
| 同日多班次 | 本轮只留字段与唯一性约束的**占位**，规则待企业输入（D-107） |
| `shifts.rule_set_id` 改为指向版本化规则集 | 本轮实现（消除旧班次静默跟随新规则） |

---

## 7. 迁移编号与文件所有权（防并发冲突）

### 7.1 迁移链（2026-10-24 分配，不得自行占用）

```
f2f000000001  权限码补齐            已落库
f2g000000001  业务角色目录          已落库
f2h000000001  人员修正版本          W1 独占
f2i000000001  审批流转历史/状态机   W3 独占
f2j000000001  消息引擎             W4 独占
f2k000000001  假期发放批次/类型版本  M45 独占
f2l000000001  排班类型/草稿/换班    M45 独占
f2m000000001  历史花名册支撑        M1 独占（可能不需要新表）
f2n000000001  兼岗 person 级        M3 独占（预计不需要新表）
```

> 迁移链是单链，任何两个 worker 同时新建迁移都会产生分叉。**新迁移的 `down_revision` 必须指向上一条已分配的编号，不得跳号或并行分叉。**

### 7.2 文件所有权矩阵

| Worker | 后端独占文件 | 前端独占文件 | 共享文件 |
|---|---|---|---|
| W1 人员修正 | `alembic/versions/f2h000000001_*.py` | `features/workforce/PeopleWorkspace.tsx` | — |
| M2 历史组织架构 | `modules/organization/organization_service.py`、`organization_api.py` | `features/organization/Organization*.tsx` | — |
| M45 假期 + 排班 | `modules/attendance/**`、`alembic/versions/f2k*.py`、`f2l*.py` | `features/attendance/**` | — |
| M1 历史花名册 | `modules/workforce/historical_roster_*.py`、`alembic/versions/f2m*.py` | `features/workforce/HistoricalRosterWorkspace.tsx`（新建） | `navigation.ts`、`business_router.py` 由主 agent 统一改 |
| M3 兼岗 | `modules/workforce/concurrent_*.py`、`alembic/versions/f2n*.py` | `features/workforce/ConcurrentPositionPanel.tsx`（新建） | 同上 |

**硬规则**：

1. 新模型类必须放进**已被 `apps/api/src/hris/shared/db/models.py` 导入的模块**（`attendance/models.py`、`workforce/models.py`、`workflow/models.py`、`performance/models.py`），否则不会进 `Base.metadata`。**任何 worker 都不得改 `shared/db/models.py`**。
2. **不得新建 router 模块**；新端点加到既有 router 所属文件（`organization_api.py` / `attendance/extended_api.py` / `workforce/extended_api.py`）。确需新 router 的，报给主 agent，由主 agent 统一改 `business_router.py`。
3. `apps/web/src/business/navigation.ts` 由主 agent 统一改。
4. `apps/web/src/business/components/**` 是公共组件层，改动前先确认不与他人冲突，并在报告中列出。

---

## 8. 验收口径

- 后端：`alembic upgrade head` + `alembic check` 零漂移 + `pytest tests/integration` 全绿（临时库名必须含 `test`）。
- 前端：`node scripts/check-antd-usage.mjs` 零违规 + `npx tsc -b` exit 0 + `npm run test:run` 全绿。
- 新功能必须有集成测试，且**不得削弱既有测试**。
- 画板：新增/变更页面须先有 Pencil 画板并达到 `PROTOTYPE_APPROVED`（D-087）。本轮新增的「员工档案 Drawer 编辑态 / 修正态」「历史花名册」「时点组织树」「发假明细」「排班管理」均需补画板。
