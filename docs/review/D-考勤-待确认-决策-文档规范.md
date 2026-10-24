# 分片 D：第三阶段需求规格 + 待确认问题 + 项目决策 + 文档规范 ↔ 实现 对账

> 审计对象：`docs/01-foundation/14-第三阶段需求规格.md`、`99-待确认问题.md`、`03-项目决策.md`、`17-模块功能需求文档规范.md`
> 审计方式：只读取证。实现证据取自工作区当前状态（含未提交改动）。
> 审计时间：2026-10-24 10:42 起
> 分片边界：不含 `16`、`01/05/06/07/08/12` 与 `docs/input-packs/`。
> 快照说明：审计期间工作区存在**并发写入**（`03-项目决策.md` 新增 §8 决策 D-088~D-101；`modules/workflow/extended_service.py` 新增批量异动审批回调分派）。本报告在结束前已复核全部受影响条目并按最新状态修正，受影响的行已就地标注"审计期间被并发修复"。

## 汇总

| 判定 | 任务一 考勤 | 任务二 待确认/决策 | 任务三 文档规范 | 合计 |
|---|---|---|---|---|
| 已实现 | 31 | 97 | 1 | 129 |
| 部分实现 | 12 | 11 | 0 | 23 |
| 未实现 | 2 | 2 | 1 | 5 |
| 与PRD冲突 | 2 | 5 | 1 | 8 |
| 待企业输入 | 19 | 2 | 0 | 21 |
| 待决策 | 0 | 0 | 0 | 0 |
| **小计（行数）** | **66** | **117** | **3** | **186** |

补充：另有 **3 条**（14号 §15 完成定义、§16 企业输入顺序、§17 开发任务生成规则）整体判定为"待企业输入/未落地"，已在任务一末尾单列，不计入上表行数。

---

## 任务一：考勤需求明细

### 1. 规则集、适用范围与时区（14号 §5）

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 14.md:86 `P3-RULE-001` | 规则集稳定代码＋草稿/版本/发布/生效日期/IANA时区 | 已实现 | `attendance/models.py:26-43`（code/name/timezone/version/status/effective_from/to/rules）；`attendance/service.py:47-76`（v1+draft）、`:133-162`（新版本）、`:164-195`（发布并归档旧版） | 规则集本身齐备；适用范围字段缺失见 P3-RULE-004 | P2 |
| 14.md:87 `P3-RULE-002` | 月份与日期边界按规则时区解释，不用服务器本地时区 | 部分实现 | `attendance/extended_service.py:1104` `ZoneInfo(rule_set.timezone)`、`:1105-1107` 班次起止按规则时区；`:1277-1293` 月报聚合直接用 `payload.period_month` 与 DATE 列，未读取规则集时区 | 日报已按规则时区；月报自然月边界未与规则时区绑定。建议在月报证据中写入 `rule_set_version/timezone`，或明确"月报按业务自然月"的书面口径 | P2 |
| 14.md:88 `P3-RULE-003` | 已发布版本不得原地修改 | 已实现 | `attendance/service.py:113-114` `ATTENDANCE_RULE_SET_NOT_DRAFT` | — | — |
| 14.md:89 `P3-RULE-004` | 适用范围支持国家/法人/组织/人员类型/个人例外 | 待企业输入 | `attendance/models.py:36-43` 无 scope 字段；检索 `scope\|applies_to\|person_exception` 在 `modules/attendance/` 无命中 | 正确等待企业输入。落地前需新增结构化适用范围列（不要塞进 `rules` JSON） | P2 |
| 14.md:90 `P3-RULE-005` | 工作日历、法定节假日、调休与地区来源 | 待企业输入 | `modules/attendance/` 无 work_calendar/holiday 模型；检索 `calendar\|holiday\|调休` 无命中 | 正确等待。注意：14号 §15 第1条把"工作日历"列为阶段完成前置，当前工程完全无载体 | P2 |
| 14.md:91 `P3-RULE-006` | 迟到/早退/缺卡/缺勤/取整/封顶/补卡规则从正式矩阵加载，不长期依赖开放JSON | 待企业输入 | 实现已用开放JSON：`attendance/extended_service.py:1109-1110` `rule_set.rules.get("late_grace_minutes"/"early_leave_grace_minutes")` | 正确等待企业矩阵，但**通用引擎已按 JSON 先行固化**。建议在企业矩阵确认前禁止新增 JSON key，或先把键名收敛为已评审常量 | P1 |
| 14.md:92 `P3-RULE-007` | 冻结历史不因新规则发布自动重算；解冻重算须有原因并产生新版本 | 已实现 | `attendance/extended_service.py:1079` 冻结拦截、`:184-222` `_assert_period_not_frozen`、`:149-182` 解冻必须 `reason`；`attendance/models.py:332-338` 释放态一致性 CHECK | — | — |

### 2. 班次与排班（14号 §6）

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 14.md:100 `P3-SHIFT-001` | 班次保存代码/名称/上下班/跨午夜/规则版本/状态 | 已实现 | `attendance/models.py:46-59`（code/name/start_time/end_time/crosses_midnight/rule_set_id/status）；`attendance/extended_service.py:272-332` 创建与时间区间校验 | 班次绑定的是**规则集**而非具体版本（`rule_set_id`），规则集发布新版本后旧班次静默跟随新规则。若要求"班次可复现"，需班次侧冗余 `rule_set_version` | P2 |
| 14.md:101 `P3-SHIFT-002` | 计划工时/休息段/弹性窗口/最早入卡/最晚出卡/取整规则 | 待企业输入 | `attendance/models.py:46-59` 无上述字段；取卡窗口硬编码于 `extended_service.py:1117-1118`（±6 小时） | 正确等待。落地需改表（新增计划工时/休息段列），不是加配置项 | P2 |
| 14.md:103 `P3-SHIFT-003` | 排班按劳动关系＋工作日期关联一个有效班次，记录来源与状态 | 已实现 | `attendance/models.py:62-81`；`attendance/extended_service.py:334-356`（来源、状态、重复校验） | — | — |
| 14.md:104 `P3-SHIFT-004` | 同日多班次/换班/临时取消/休息日加班/无排班打卡 | 待企业输入 | **提前固化**：`attendance/models.py:64-66` `UniqueConstraint("employment_id","work_date")`；`extended_service.py:339-346` 重复排班直接 409 `SCHEDULE_EXISTS` | 文档说"待确认"，DB 唯一约束已排除"同日多班次"。企业若确认允许同日多班次，需改表。建议现在就把该唯一约束标注为"待企业输入的临时口径" | P1 |
| 14.md:104/104-105 `P3-SHIFT-005` | 排班批量导入/排班周期模板/覆盖冲突策略 | 待企业输入 | `attendance/extended_api.py:188` 仅 `POST /schedules` 单条；检索 `bulk\|batch\|import` 在 `modules/attendance/` 无命中（`import_service.py` 属 platform 导入治理，不含排班） | 正确等待。无批量入口前不得声称"批量排班"已具备 | P2 |

### 3. 原始打卡（14号 §7）

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 14.md:112 `P3-PUNCH-001` | 保存劳动关系/带时区时间/可选进出类型/来源/来源记录ID/原始载荷 | 已实现 | `attendance/models.py:84-108`；`attendance/extended_schemas.py:123-135` 拒绝 naive datetime（`punched_at必须包含时区`） | — | — |
| 14.md:113 `P3-PUNCH-002` | `source+source_record_id` 幂等，重复内容返回原记录 | 部分实现 | `attendance/models.py:86-88` 唯一约束；`extended_service.py:415-423` 命中即返回原记录 | 命中后**不比对载荷内容**，内容不同的重复提交也静默返回旧记录。与 `17`号 §8.1 示例（冲突时返回 `PUNCH_IDEMPOTENCY_CONFLICT`）不一致。建议补 `request_checksum` 并按 17号 §8.1 返回冲突错误 | P1 |
| 14.md:114 `P3-PUNCH-003` | 冻结期间继续接收原始打卡证据，但不得自动改写已冻结日报/月报 | 已实现 | `extended_service.py:415-435` 打卡入口无冻结校验；日报版本只在 `calculate_daily` 内生成 | — | — |
| 14.md:115 `P3-PUNCH-004` | 来源认证/签名/防重放/设备位置证据/补传/乱序/失败重试 | 待企业输入 | `attendance/models.py:84-108` 无签名/时间窗字段；检索 `signature\|nonce\|replay` 无命中 | 正确等待。补传语义目前由幂等唯一约束近似覆盖，失败重试无接口契约 | P2 |
| 14.md:116 `P3-PUNCH-005` | 无类型/多次/跨班次/过早过晚/离线打卡的归属 | 待企业输入 | `extended_service.py:1111-1123` 取 ±6 小时窗口内全部打卡，`:1136-1139` 取首末条；与 14.md:106 自述的"工程演示口径"一致 | 正确等待，且文档已标注该口径不得进入企业基线 | P2 |
| 14.md:117 `P3-PUNCH-006` | API 不提供原始打卡物理删除 | 已实现 | `attendance/extended_api.py` 路由清单（`:63-499`）无 `DELETE /punches`；`attendance/models.py` 无删除服务 | — | — |
| 14.md:118 `P3-PUNCH-007` | 人工补卡/纠错需独立证据或更正记录、审批与审计 | 部分实现 | **前端已开正式入口**：`apps/web/src/business/features/attendance/SchedulePunchPanel.tsx:135-141` "手工补录打卡"弹窗，`:88-92` 直接以 `source="manual"`、`raw_payload:{entered_by:"attendance_admin"}` 写入；审计只有通用 `ingest` 动作（`extended_service.py:429-434`） | 文档自述"当前尚未实现正式闭环"，但前端已把无证据、无审批、无更正记录的补卡路径暴露给管理员。建议补卡必须带原因＋更正记录，并单独权限（14.md:185 要求"打卡补录…使用独立权限"，现状与其他考勤操作共用 `ATTENDANCE_ADMIN`） | P1 |
| 14.md:119 `P3-PUNCH-008` | `raw_payload` 敏感字段合同完成前只允许合成数据 | 待企业输入 | `extended_schemas.py:129` `raw_payload: dict` 接受任意键，无"仅合成数据"校验；前端补录会写入真实员工ID | 正确等待，但**当前后端不阻止真实敏感载荷入库**。建议在合同落地前对 `raw_payload` 做白名单键校验并拒绝位置/设备字段 | P1 |

### 4. 假期、请假与销假（14号 §8）

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 14.md:125 `P3-LEAVE-001` | 假期类型稳定代码，天/小时单位、状态、规则字段 | 已实现 | `attendance/models.py:111-118`；`extended_schemas.py:162-171` | — | — |
| 14.md:126 `P3-LEAVE-002` | 余额模式：不跟踪/可负/不足阻断 | 已实现 | `extended_service.py:837-846`（none/tracked/enforced）；`extended_schemas.py:9-15` 校验 | — | — |
| 14.md:127 `P3-LEAVE-003` | 请假保存劳动关系/假类/起止/数量/原因/状态/可选流程实例 | 已实现 | `attendance/models.py:121-156`；`extended_service.py:892-921`（单号 `LEAVE_REQUEST_NUMBER`、状态 draft/pending_approval） | — | — |
| 14.md:128 `P3-LEAVE-004` | 批准按幂等规则扣减余额；销假/取消形成反向流水不改原流水 | 已实现 | `extended_service.py:762-791`（usage，幂等键 `uuid5(...usage:{id})`）、`:793-835`（reversal，`-usage.amount`）；原流水无 UPDATE/DELETE | — | — |
| 14.md:129 `P3-LEAVE-005` | 自然日/工作日/排班分钟/半天/小时假/跨班次/跨时区计算 | 待企业输入 | `extended_schemas.py:212` `amount` 由客户端直填；`extended_service.py:770-775` 跨自然年直接 422 `LEAVE_BALANCE_CROSS_YEAR_UNSUPPORTED` | 正确等待。**已提前固化**"跨年必须拆分"这一企业口径；建议加配置开关或延后该校验 | P1 |
| 14.md:130 `P3-LEAVE-006` | 请假重叠/审批前预占/撤回/驳回/补录/与打卡并存 | 待企业输入 | **提前固化**：`extended_service.py:980-995` 批准时硬阻断重叠（`LEAVE_REQUEST_OVERLAPS`）；状态机 `:960-967` 只有 approved/rejected/cancelled | 正确等待，但重叠阻断已是硬规则；状态机只有"批准/驳回/取消"两义，与本轮新决策的"撤销/驳回/退回"三义不一致（见任务二） | P1 |
| 14.md:131 `P3-LEAVE-007` | 每类假期审批图/附件要求/可见范围 | 待企业输入 | `attendance/models.py:149-152` 预留 `workflow_instance_id`；但 `modules/workflow/extended_service.py:1356` 业务对象联动只处理 `hr_event` | 正确等待。注意：请假与流程是**单向挂载**，流程完成不会驱动请假状态；当前审批实际由前端直接改状态（`LeavePanel.tsx:166`），属主管理员手工批准 | P1 |
| 14.md:132 `P3-LEAVE-008` | 假期类型规则的独立版本、生效日期与历史查询 | 未实现 | `attendance/models.py:111-118` `LeaveType` 无 `version/effective_from/effective_to`；`attendance/api.py` 无假期类型版本接口 | 文档已自述"尚未实现"。企业规则确认时需改表新增版本列，不可只加配置 | P2 |

### 5. 假期余额、计提与结转（14号 §9）

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 14.md:138 `P3-BAL-001` | 按劳动关系＋假类＋年度建账户，存单位/余额/版本/状态 | 已实现 | `attendance/models.py:159-197`（含 4 个 CHECK）；`extended_service.py:693-704` 自动建户 | — | — |
| 14.md:139 `P3-BAL-002` | 不可变流水，存变动前后余额/类型/生效日/来源/原因/幂等键 | 已实现 | `attendance/models.py:199-241`（含 `balance_after = balance_before + amount` CHECK）；`extended_service.py:638-760` | — | — |
| 14.md:140 `P3-BAL-003` | 支持人工发放/调整/结转/计提；负数调整受控 | 已实现 | `attendance/models.py:203-205` 类型域；`extended_schemas.py:282-296`（仅 `adjustment` 可为负） | 计提类型 `accrual` 可人工录入，但无自动触发者（见 P3-BAL-004） | P2 |
| 14.md:141 `P3-BAL-004` | 自动计提触发频率/工龄/入职转正折算/员工类型/年度额度 | 待企业输入 | **无调度器**：全仓 `apps/` 检索 `celery\|apscheduler\|cron\|scheduler\|asyncio.create_task\|dramatiq` 零命中；`deploy/compose.yaml` 与 `compose.business.yaml` 无 worker 服务 | 正确等待企业口径，但**自动计提在当前架构下无任何触发机制**，属平台级缺口，非仅待输入 | P1 |
| 14.md:142 `P3-BAL-005` | 封顶/清零/结转上限/有效期/离职处理/跨年申请 | 待企业输入 | 无封顶/清零逻辑（检索 `cap\|ceiling\|clear` 在 `modules/attendance/` 无命中）；跨年被 `:770-775` 阻断 | 正确等待 | P2 |
| 14.md:143 `P3-BAL-006` | 历史修订新增调整流水，不修改或删除原流水 | 已实现 | `attendance/extended_api.py:317-382` 仅 POST/GET 余额与流水；无 UPDATE/DELETE；修订走 `create_leave_balance_transaction` | — | — |

### 6. 日报计算（14号 §10）

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 14.md:162 `P3-DAY-001` | 日报按劳动关系＋工作日期版本化，只有一个当前版本 | 部分实现 | `extended_service.py:1195-1220`（旧版本 `is_current=False`，新版本 `version+1`）；`attendance/models.py:246-248` 唯一约束仅 `(employment_id, work_date, version)` | DB 层无"唯一当前版本"约束（依赖应用层置位）。并发重算理论上可出现两条 `is_current=true`。建议加部分唯一索引 | P1 |
| 14.md:163 `P3-DAY-002` | 保存状态/计划分钟/工作分钟/迟到分钟/早退分钟/异常码/证据 | 已实现 | `attendance/models.py:257-271` | — | — |
| 14.md:164 `P3-DAY-003` | 重算创建新版本不覆盖原结果；相同输入重复任务结果一致 | 已实现 | `extended_service.py:1205-1220` | 相同输入会新增版本（版本号增长）但数值一致，符合"不产生不一致结果" | P2 |
| 14.md:165 `P3-DAY-004` | 最早入/最晚出/缺卡/无卡/请假并存仅为通用算法 | 待企业输入 | `extended_service.py:1136-1179` | 正确等待，文档已声明正式规则以企业案例为准 | P2 |
| 14.md:166 `P3-DAY-005` | 半天/小时/出差/外勤/加班与精细异常码 | 待企业输入 | 异常码全集仅 `NO_SCHEDULE`(:1096)、`NO_PUNCH`(:1166)、`MISSING_PUNCH`(:1169)、`LATE`(:1177)、`EARLY_LEAVE`(:1179) | 正确等待；异常码目前是硬编码字面量而非配置枚举 | P2 |
| 14.md:167 `P3-DAY-006` | 命中有效冻结范围禁止生成新日报版本 | 已实现 | `extended_service.py:1079` 调用 `_assert_period_not_frozen`（`:184-222`）返回 409 `ATTENDANCE_PERIOD_FROZEN` | — | — |

### 7. 月报与冻结（14号 §11）

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 14.md:173 `P3-MONTH-001` | 月报按劳动关系＋自然月版本化，只聚合当前日报版本 | 已实现 | `extended_service.py:1310-1321`（`is_current=True` 过滤）；`:1326-1338` 版本化 | — | — |
| 14.md:174 `P3-MONTH-002` | 保存计划天数/出勤天数/请假天数/缺勤天数/迟到早退分钟/状态 | 部分实现 | 字段齐全 `attendance/models.py:289-317`；但 `extended_service.py:1322-1325`：`leave_days` 只统计 `status=="leave"`、`absent_days` 只统计 `status=="absent"`、`scheduled_days` 只统计 `scheduled_minutes>0` | 计算口径有实质缺口：①`leave_with_punch`（有打卡的请假，`:1171`）不计请假天数；②`exception`（迟到/早退/缺卡）不计缺勤；③未排班日不计入计划天数也不计缺勤 → 缺勤天数系统性偏低，直接影响月报可对账性 | P1 |
| 14.md:175 `P3-MONTH-003` | 月报字段/日转月折算/截止时间/复核期/生成时点 | 待企业输入 | `extended_service.py:1350` 状态硬编码 `"calculated"`；无复核状态/复核期/生成时点字段 | 正确等待，但落地时月报表需增状态机（草稿/已计算/待复核/已确认） | P2 |
| 14.md:176 `P3-FRZ-001` | 同时支持月结冻结和特殊业务冻结 | 已实现 | `attendance/models.py:324-327` 类型域；`extended_schemas.py:394` | — | — |
| 14.md:177 `P3-FRZ-002` | 月结冻结必须覆盖完整自然月；特殊冻结可任意日期段 | 已实现 | `extended_schemas.py:399-411`（`monthly` 必须首日为1号且末日为月末） | 校验基于请求日期，未绑定规则时区；因冻结区间为纯日期，现口径可接受 | P2 |
| 14.md:178 `P3-FRZ-003` | 冻结与解冻记录范围/类型/原因/操作者/时间；解冻不删除原记录 | 已实现 | `attendance/models.py:347-356`；`extended_service.py:81-106`（冻结）、`:149-182`（解冻写 `released_by/released_at/release_reason`） | — | — |
| 14.md:179 `P3-FRZ-004` | 解冻后更正源证据、重算并重新冻结，永久保留原结果版本 | 已实现 | 重算走 `extended_service.py:1205-1220` 新版本，旧版本保留；冻结记录 release 态保留 | — | — |
| 14.md:180 `P3-FRZ-005` | 月结发起人/复核人/冻结时点/特殊冻结触发/审批规则 | 待企业输入 | `attendance/models.py:347-353` 无复核人字段；`extended_service.py:86-91` 冻结直接置 `active`，无审批 | 正确等待 | P2 |

### 8. 权限与审计（14号 §12）

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 14.md:184 | 首批优先支持系统管理员和SSC | 与PRD冲突 | `modules/platform/dependencies.py:56-70` 权限来自 `permissions→role_permissions→roles→user_roles`；`alembic/versions/f2b000000001_seed_onboarding_initiator_role.py:31,51-54,65-79` 仅给 `SSC_ADMIN` 授 `ONBOARDING_INITIATE`；`alembic/versions/f1a000000001_phase_1a_organization_domain.py:404-410` 只种 5 个权限码；`f2a000000002_seed_governance_permissions.py:23-27` 种 2 个 | `ATTENDANCE_ADMIN`（以及 `LIFECYCLE_ADMIN`、`WORKFORCE_ADMIN`）在**全部 21 个 Alembic 迁移中都没有 Permission 行**（全仓检索 `ATTENDANCE_ADMIN` 仅命中 `business_router.py:42`、`attendance/api.py:22`、`attendance/extended_api.py:56` 与文档）。只有持 `*` 的主管理员能通过校验（`platform/service.py:31-32,48-66` + `dependencies.py:79,90`）→ **SSC 实际无法使用考勤、生命周期、人员档案模块**。注意 `docs/archive/2026-08-18-foundation-rebaseline/15-第三阶段PRD.md:269` 早已写明"`SSC_ADMIN`尚未获得考勤管理权限"，而现行 14.md:184 删除了该限定 | P0 |
| 14.md:185 | 规则发布/批量排班/打卡补录/余额调整/日报重算/月报重算/冻结解冻使用独立权限 | 与PRD冲突 | `attendance/api.py:22`、`attendance/extended_api.py:56`、`api/business_router.py:42` 全部为单一 `ATTENDANCE_ADMIN`；`extended_api.py:63-499` 共 30 余个路由无一例外 | 7 类高风险动作共用 1 个权限码，粒度不满足要求。建议按 `ATTENDANCE_RULE_PUBLISH / SCHEDULE_WRITE / PUNCH_BACKFILL / BALANCE_ADJUST / DAILY_RECALC / MONTHLY_RECALC / FREEZE_MANAGE` 拆分并落到 Permission 行 | P0 |
| 14.md:186 | 原始打卡/请假原因/位置设备证据按数据分级控制查看与导出 | 部分实现 | `modules/platform/models.py:33-38` Permission 只有 `code/name/module_code`，无字段级/数据级模型；`attendance/extended_schemas.py:147`（reason）、`:222`（raw_payload）原样返回给任何 `ATTENDANCE_ADMIN` | 文档 14.md:187 已自述未完成 UAT。落地需新增数据分级字段与导出白名单 | P1 |
| 14.md:188 | 高风险操作必须填原因，并审计操作者/时间/Trace ID/对象/前后状态/证据版本 | 部分实现 | `extended_service.py:56-79` AuditLog 记 actor/trace_id/action/object_type/object_id/before/after/reason；`core/middleware.py:14-16` Trace ID；`extended_service.py:1223-1229` 日报审计只记 `status`+`version` | "证据版本"未落审计（日报审计无 `rule_set_version`/`punch_ids` 引用）。另：`ingest_punch` 的审计不记 reason（`:429-434`），补卡无原因字段 | P1 |
| 14.md:189 | 普通角色数据范围支持本人/组织/全部下级/法人/自定义 | 未实现 | `modules/platform/models.py` 无数据范围实体；检索 `data_scope\|scope_type\|row_level` 在 `modules/platform/` 无命中 | 文档已声明"当前主管理员通配权限不代表该能力已验收"。落地需新增数据范围模型 | P1 |

### 9. 异常与补偿（14号 §13）

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 14.md:195 | 规则或班次在目标日无效 → 日报失败并返回业务错误 | 已实现 | `extended_service.py:1099-1103`（`SHIFT_NOT_FOUND` / `RULE_SET_NOT_FOUND`） | 无排班时返回 `status="unscheduled"`+`NO_SCHEDULE`（`:1095-1096`），不算错误——属另一种情形，需在企业口径中明确 | P2 |
| 14.md:196 | 打卡重复/乱序 → 幂等接收并按时间证据归属，不修改原时间 | 已实现 | `extended_service.py:415-423`、`:1111-1123` 按 `punched_at` 排序取用 | — | — |
| 14.md:197 | 余额不足 → `enforced` 模式阻止批准 | 已实现 | `extended_service.py:790` `enforce_nonnegative=balance_mode=="enforced"`；`:714-726` 409 `LEAVE_BALANCE_INSUFFICIENT` | — | — |
| 14.md:198 | 并发批准或余额调整 → 锁定账户版本，防透支或重复入账 | 已实现 | `extended_service.py:876-890` advisory lock；`:684-692` `with_for_update`；`:727` 版本自增 | — | — |
| 14.md:199 | 日报/月报计算中断 → 相同任务语义重试，旧当前版本在新版本成功前保持有效 | 部分实现 | `extended_service.py:1205-1220` 同事务内改 `is_current`＋插入新行，失败回滚则旧版本保持有效 | **无后台任务与任务语义**：全仓无调度器/队列（见 P3-BAL-004），"重试"只能人工再调一次 API，无任务 ID、无幂等任务键、无失败补偿记录 | P1 |
| 14.md:200 | 冻结期出现补传打卡 → 接收原始证据、标记待处理、不改已冻结结果 | 部分实现 | `extended_service.py:415-435` 接收且不触发重算 | **无"待处理"标记**：`attendance/models.py:84-108` `AttendancePunch` 无 pending/待处理状态列，补传打卡与正常打卡无法区分，冻结期无法筛出待处理集合 | P1 |
| 14.md:201 | 历史更正 → 解冻、产生新结果版本、复核、重新冻结 | 部分实现 | 解冻 `:149-182`、新版本 `:1205-1220`、重新冻结 `:81-106` 均已实现 | **复核步骤无实现**：月报无复核状态（`:1350` 硬编码 `calculated`）、冻结无复核人（`models.py:347-353`） | P1 |

### 10. 非功能需求（14号 §14）

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 14.md:205 | 时间统一保存明确时区或UTC，禁止无时区打卡时间 | 已实现 | `attendance/models.py:96-100` `DateTime(timezone=True)`；`extended_schemas.py:131-135` 拒绝 naive | — | — |
| 14.md:206 | 规则计算必须可复现，引用规则版本/班次/排班/打卡/假勤证据 | 部分实现 | `extended_service.py:1180-1192` evidence 含 `schedule_id/shift_id/rule_set_id/rule_set_version/timezone/punch_ids/punch_times/leave_request_id` | 缺班次侧版本与班次时间窗口（班次无版本概念，见 P3-SHIFT-001）；规则集发布新版本后旧日报无法证明当时所用班次口径 | P1 |
| 14.md:207 | 原始证据和余额流水不可物理删除 | 已实现 | `attendance/extended_api.py:63-499` 无 DELETE 路由；`extended_service.py:415-435,638-760` 只追加 | — | — |
| 14.md:208 | 接口和后台任务具备幂等、分页、Trace ID 和稳定错误码 | 部分实现 | 分页：`attendance/extended_api.py` 全部列表带 limit/offset；Trace ID：`core/middleware.py:14-16`、`core/errors.py:37,60`；错误码：全部 `ApiError(code=...)` | **后台任务完全缺失**（无调度器/队列/任务表），"后台任务具备幂等"无从谈起 | P1 |
| 14.md:209 | 计算器用合成场景建立回归测试 | 已实现 | `apps/api/tests/integration/test_attendance_calculation_api.py`、`test_attendance_period_freeze_api.py`、`test_leave_balance_api.py`；`apps/api/tests/integration/conftest.py:161-179` 合成角色/权限 | 测试通过是因为 conftest 在测试内建权限行，**不反映生产种子缺失** | P2 |
| 14.md:210 | 一万人同时打卡/查日报月报是容量目标，未压测不得宣称通过 | 待企业输入 | 全仓 `apps/api/tests/` 检索 `10000\|并发\|load_test\|performance` 无容量测试；无压测脚本 | 正确保持"未宣称通过"。缺口是缺流量模型与压测入口，属待企业输入第 7 项（14.md:234） | P2 |

### 11. 阶段级条款（14号 §15/§16/§17，整体判定）

| 文档条款（文件:行） | 要求摘要 | 判定 | 证据 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 14.md:214-222 | 第三阶段"企业业务验收通过"七项完成定义 | 待企业输入 | 逐项依赖企业口径；当前仅第 6/7 项有工程证据（解冻-重算-版本-重新冻结链路、集成测试） | 不得据此宣布企业验收通过；00.md:61 已列"企业考勤、假期、设备接入及月结冻结细则"待固化 | P2 |
| 14.md:226-234 | 企业输入顺序 7 步 | 待企业输入 | `docs/input-packs/07-attendance-rule-input.md`、`08-punch-interface-input.md` 已生成模板但企业未回填 | 顺序正确，无需改动 | P2 |
| 14.md:240-244 | AI 开发任务生成规则：`CONFIRMED` 可成任务；`IMPLEMENTED_GENERIC` 只能做缺陷加固；`PENDING_ENTERPRISE_INPUT` 禁止猜测数值；每个计算任务必须引用需求编号和输入—期望输出案例 | 未实现 | **考勤模块 0 条需求追踪注释**：全仓 `apps/api/src/hris/modules/` 共 136 条 `Requirement:` 注释，`modules/attendance/` 为 **0 条**（`apps/api/src/hris/modules/attendance/{service,extended_service,extended_schemas,models}.py` 无一条） | 违反 14.md:243"每个计算任务必须引用需求编号"与 `03`号 D-067。考勤计算器（迟到/早退/缺卡/缺勤/请假天数/余额扣减）目前无法从代码回溯到 P3-* 需求编号 | P0 |

---## 任务二：待确认问题与项目决策一致性

### 1. `99-待确认问题.md` 逐项核对

判定口径：代码是否已经绕过该问题实现了（→ 提前固化＝风险）；还是仍在正确等待输入。

| 文档条款（文件:行） | 条目摘要 | 判定 | 实现/文档证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 99.md:11 | §1 第一阶段业务规则已全部确认（Q-002、Q-004~Q-010） | 已实现 | `03-项目决策.md` 现存 D-001~D-087 无编号缺口，D-055~D-065 齐备（`03.md:118-133`）；`03.md:146` "当前业务规则问题已关闭" | 一致，无需修改 | — |
| 99.md:16-29 | Q-011 数据字典：待业务 Review 新枚举码值、法人/组织/职务/人员状态稳定业务键、历史编码冲突规则、脱敏小批量期望结果 | 部分实现 | 字典模型与 CRUD 已落地：`modules/platform/models.py:105-136`、`modules/platform/configuration_api.py:23-32`；组织类型已按 D-071 扩为 7 项并"支持配置"（`03.md:43`）；映射基线已写 `docs/input-packs/03-ehr-lookup-full-extraction-and-mapping.md`（4373 行枚举） | **部分提前固化**：字典/编码基础设施与 4373 行候选码已进代码与迁移，但"业务 Review"未做。若 Review 推翻码值，需返工字典与组织类型种子。建议在 99.md 标注"字典基础设施已建，码值待 Review" | P2 |
| 99.md:31-33 | Q-012 职务体系：首个企业组合已确认并进入有效日期职务模型，完整目录增量补充 | 已实现 | `alembic/versions/f1b000000001_effective_dated_job_architecture.py`；职位 API `/api/v1/workforce/jobs*`；`modules/workforce/extended_service.py` 职位与职级目录 | 与"增量补充"策略一致，正确等待 | P2 |
| 99.md:35-39 | Q-013 人事档案：当前推荐范围已实现并进入主管理员 UAT | 已实现 | `alembic/versions/f1c000000001_personnel_record_foundation.py`、`f1d000000001_personnel_sensitive_subrecords.py`；`docs/adr/ADR-0004-personnel-sensitive-field-protection.md`；`apps/api/tests/integration/test_personnel_record_api.py`、`test_personnel_security.py` | 一致 | — |
| 99.md:41-43 | Q-014 流程图：入职业务含义/发起角色/前置状态/并行互斥已确认；下一项仅确认入职生效日期来源、修改权限、审批晚于生效日的处理 | 部分实现 | 引擎能力已先行落地：节点类型 `start/approval/action/end`（`modules/workflow/schemas.py:61-70`）、`sign_mode all\|any`（`:62`、`:1216`）、条件算子 10 个（`modules/workflow/conditions.py:47-84`：exists/not_exists/eq/ne/in/not_in/gt/gte/lt/lte）、业务对象联动（`modules/workflow/extended_service.py:1085-1088`、`:1350-1363`）、批量异动联动（`modules/workforce/batch_change_service.py:224-241`） | **提前固化**：流程语义（会签/或签、条件路由、业务对象联动）在流程图确认前已定型。且新决策要求的"撤销/驳回/退回"三义在引擎层缺失（`modules/workflow/extended_schemas.py:490` 仅 `Literal["approve","reject"]`）。建议在 99.md Q-014 下追加"引擎已具备能力清单"与"待确认语义清单"，避免企业误以为流程图仍是空白 | P1 |
| 99.md:45-55 | Q-015 部署基线：待提供 8GB/32GB 服务器的 OS/CPU/网络/证书/数据库部署/备份恢复 SLA 监控 | 待企业输入 | `deploy/compose.yaml`、`deploy/compose.business.yaml:1-15` 仅覆盖 api 命令与密钥注入，**无监控/备份/SLA 定义**；`docs/implementation/business-runbook.md` 记录本地运行栈 | 正确等待。生产拓扑仍未定义（compose.business 仅 16 行 override） | P2 |
| 99.md:57-59 | Q-016 外部系统接口：待提供企业微信、自建 OA 接口清单、认证、字段映射、主从关系 | 待企业输入 | 全仓 `apps/` 检索 `notification\|notify\|webhook\|企业微信\|wecom` **零命中**；仅有来源追踪模型 `modules/platform/models.py:139-155`（`ExternalRecordLink`） | 正确等待，且无任何连接器代码，不存在提前固化 | P2 |
| 99.md:61-63 | Q-017 合同/协议：通用建档/变更/续签/解除/取消/到期提醒/回退已实现；待确认正式类型/字段/期限状态/真实审批图/**提醒对象与渠道**/附件存储安全/保留年限/电子签章 | 部分实现 | 合同表与生命周期已落地：`alembic/versions/f3a000000004_contract_lifecycle.py`；前端 `apps/web/src/business/features/lifecycle/ContractPanel.tsx:177-188`（`execution_mode:"direct"`）；到期提醒与提醒渠道**无任何实现**（无通知底座，见 Q-016） | **提前固化**：合同文档已把"到期提醒"写进"已实现"清单，但提醒链路依赖尚不存在的通知通道。建议在 99.md 中把"到期提醒"从已实现移出，改为待企业输入 + 待平台能力 | P1 |
| 99.md:65-67 | Q-018 考勤与假期企业规则：通用能力已实现，按 14 号＋输入包 07/08 依次确认 | 部分实现 | 通用链路已实现（见任务一）；但"待确认规则"已在 6 处被工程提前固化：①同日唯一排班（`attendance/models.py:64-66`）②请假重叠硬阻断（`attendance/extended_service.py:980-995`）③跨年请假强制拆分（`:770-775`）④余额模式值域 none/tracked/enforced（`:837-846`）⑤取卡 ±6 小时窗口（`:1117-1118`）⑥迟到/早退宽限取自开放 JSON（`:1109-1110`） | 建议在 14 号每条被提前固化的 `PENDING_ENTERPRISE_INPUT` 后加"当前工程临时口径"标注，并把这 6 条列入 99.md Q-018 的风险清单，避免企业以为这些规则尚未决定 | P1 |
| 99.md:69-77 | §3 后续阶段再讨论：员工自助与审批、多语言本地化、MCP 边界、一万人压测场景、多租户隔离、汇率与集团币种、MySQL/Oracle 兼容、Apusic 中间件 | 已实现 | 全仓 `apps/` 检索 `frappe\|tenant_id\|multi.?tenant\|mysql\|oracle\|exchange_rate\|currency_rate` **零命中**；`03.md:140` T-007 MCP `DEFERRED`；`00.md:64` 明确延期到第五阶段 | 与"未实现即延期"一致，无提前固化 | — |

### 2. `03-项目决策.md` — 有差异的条目

| 文档条款（文件:行） | 条目摘要 | 判定 | 实现/文档证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 03.md:15 `D-004` | 第一批用户为系统管理员和SSC | 与PRD冲突 | `modules/platform/dependencies.py:56-70`（权限来源）；`alembic/.../f2b000000001_seed_onboarding_initiator_role.py:51-54,65-79`（SSC_ADMIN 仅 `ONBOARDING_INITIATE`）；`alembic/.../f1a000000001_phase_1a_organization_domain.py:404-410`（仅 5 个权限码） | SSC 拿不到 `ATTENDANCE_ADMIN`/`LIFECYCLE_ADMIN`/`WORKFORCE_ADMIN`（这三个码在所有迁移中都没有 Permission 行），实际只有主管理员（`*`）可用这些模块。建议新增一条迁移种这三个权限码并授予 SSC_ADMIN | P0 |
| 03.md:131 `D-062` | 第一阶段不预置只读审计员，优先完成系统管理员权限；SSC仍作为首批业务管理角色 | 与PRD冲突 | 同上：`SSC_ADMIN` 角色实际只被授予 1 项权限 | "优先完成系统管理员权限"成立；"SSC仍是首批业务管理角色"未兑现。建议随 D-004 一并修复权限种子 | P0 |
| 03.md:21 `D-067` | 生产代码变化必须在实际规则落点附近写需求追踪注释，引用稳定需求/决策编号 | 与PRD冲突 | 全仓 `apps/api/src/hris/modules/` 共 136 条 `Requirement:` 注释；`modules/attendance/`（service/extended_service/extended_schemas/models）**0 条** | 考勤模块整体未落追踪注释，与 14.md:243 直接冲突。建议先给考勤计算链与余额链补 `Requirement: P3-xxx — 原因` | P0 |
| 03.md:99 `D-039` | 第二阶段存在人事流程时，以流程结果为准 | 已实现 | `modules/workflow/extended_service.py:1351-1380` `_finish_workflow_business_object` 现按 `business_object_type` 分派：`hr_event_batch` → `:1369` `batch_service.mark_approved(...)`、`:1371` `mark_rejected(...)`；`hr_event` → `:1375-1380` 置 `ready`/`rejected` 并执行到期事件 | **审计期间被并发修复**：初次取证时该回调只处理 `hr_event`（旧 `:1356-1357`），`mark_approved/mark_rejected` 无调用点，批量方案会卡在 `submitted`；当前工作区已补上分派（改动未提交）。建议补集成测试锁定"审批通过 → 整批明细转就绪"链路 | P2 |
| 03.md:129 `D-053` | 权限能力需支持可配置角色、动作、数据范围和字段权限 | 部分实现 | `modules/platform/models.py:23-74`（Role/Permission/UserRole/RolePermission）已实现角色与动作码；**无数据范围模型、无字段权限模型**（检索 `data_scope\|field_permission` 在 `modules/platform/` 无命中） | 动作级可配已达成，数据范围与字段权限完全缺失。14.md:186/189 同样悬空 | P1 |
| 03.md:22 `D-068` | 所有 Web 前端遵循 Ant Design 官方当前稳定版；仓库依赖版本继续锁定，升级必须单独立项并通过兼容、构建和关键旅程验证 | 部分实现 | 仓库锁定 `antd 6.5.2`（`apps/web/package.json`），与 `docs/design/antd-page-interaction-standard.md:19-20` 的"不得静默升级"一致；新决策 D-090（`03.md:155`）把口径明确为"统一遵循当前锁定版本 6.5.2"，此前的版本口径冲突已消解 | 仍有三处不达标：①`scripts/check-antd-usage.mjs` 是 **0 字节空文件**，D-090 要求的"废弃属性由守卫脚本阻断"当前不生效；②无 antd 6.5.2→6.6.1 的兼容/构建/关键旅程验证记录（升级未立项）；③`LeavePanel.tsx:110,124` 用 `window.prompt`，违反 antd 规范 §5（见 D-069 行） | P1 |
| 03.md:23 `D-069` | 宿主页发起的新增/编辑/详情/流程只能用 Modal/Drawer 或新标签页 | 部分实现 | 考勤页面合规：`apps/web/src/business/features/attendance/SchedulePunchPanel.tsx:128,135`、`RuleShiftPanel.tsx:189-205`、`ReportPanel.tsx:123-139`、`LeaveBalancePanel.tsx:158-208` 均用 Modal/Drawer | **违规点**：`apps/web/src/business/features/attendance/LeavePanel.tsx:110` 与 `:124` 用浏览器原生 `window.prompt` 采集批准意见与销假原因，既不是 Ant Design 组件也不属于三类载体，违反 `docs/design/antd-page-interaction-standard.md:48-56`（§5）与 D-069 | P1 |
| 03.md:64 `D-087` | 所有新增或变更的前端页面在编码前必须完成 Pencil 原型并经产品决策人确认 | 与PRD冲突 | `docs/design/prototypes/` 仅 `bmtzK.png`、`zhrPD.png` 与 `organization-management-framework-v0.1/zhrPD.png`（组织管理原型）；考勤六页签、职位、汇报关系、标签、批量异动、绩效均无原型登记；`docs/design/prototypes/README.md:7` 明确"权威 Review 状态记录在对应功能需求或产品输入稿的原型登记表中"，而这些登记表不存在 | 至少 20+ 新页面在无 Pencil 原型的情况下完成编码。违反 D-087 与 `17`号 §10.4、antd 规范 §10 | P1 |
| 03.md:14 `D-003` | 开发由 MinimaxCode 完成（状态 `SUPERSEDED_BY_D-066`） | 已实现 | `03.md:20` D-066 写明"由 Codex 直接完成"；`docs/delivery/` 已有 Codex 回执（如 `P1-JOB-ARCHITECTURE.md`、`P3-ATTENDANCE-PERIOD-FREEZE.md`）；`00.md:45` 同步说明 | 替代关系维护正确 | — |
| 03.md:31 `D-010` | 默认组织类型集团/BG/BU/部门（状态 `SUPERSEDED_BY_D-071`） | 已实现 | `03.md:43` D-071 扩展为 7 类；`alembic/.../f1a000000001_phase_1a_organization_domain.py:404-410` 种入权限与组织类型 | 替代关系维护正确 | — |
| 03.md:133 `D-065` | 首批组织类型冻结为 4 项（状态 `PARTIALLY_SUPERSEDED_BY_D-071`） | 已实现 | 同上，D-071 已标注 `PARTIALLY_SUPERSEDED_BY_D-071` | 替代关系维护正确 | — |
| 03.md:50 `D-073` | 职位/职务/职级/职等分类层级（状态 `PARTIALLY_SUPERSEDED_BY_D-081`） | 已实现 | `03.md:58` D-081 写明"职位类与职位族由分类层级向上推导"；`alembic/.../f1b000000001_effective_dated_job_architecture.py` 建职位目录与维度版本 | 替代关系维护正确 | — |
| 03.md:53 `D-076` | 基础资料禁用只检查当前有效引用（状态 `SUPERSEDED_BY_D-083`） | 已实现 | `03.md:60` D-083 写明"当前有效引用和未来生效引用均视为有效占用并阻止禁用" | 替代关系维护正确 | — |

### 3. `03-项目决策.md` — 逐条核对无差异（附录）

> 判定粒度为"决策在代码/文档中被遵守"；DEFERRED 项判定依据是"代码中确实没有提前实现"。

| 决策ID | 摘要 | 判定 | 证据（文件:行） |
|---|---|---|---|
| D-001 | 企业内部自用但按产品化标准建设 | 已实现 | `apps/api/src/hris/modules/*`（模块化单体）＋`docs/adr/ADR-0001-toolchain.md:47-59` 版本冻结 |
| D-002 | Frappe HRMS 仅作研究样本，不作开发底座 | 已实现 | 全仓 `apps/` 检索 `frappe` 零命中 |
| D-005 | 第一阶段先实现五国基础数据 | 已实现 | `modules/workforce/models.py` 法人主体四类＋国家码；`01-第一阶段需求规格.md` |
| D-006 | 第一阶段不做员工自助 | 已实现 | `apps/web/src/business/AppShell.tsx` 仅管理端工作台；全仓无 ESS 目录 |
| D-007 | 一万人同时在线为三四阶段容量目标 | 已实现 | `docs/review/phase-1-3-overall-review-2026-08-12.md`；`apps/api/tests/` 无容量测试（未宣称通过） |
| D-008 | 多租户推迟到第五阶段 | 已实现 | 全仓 `apps/` 检索 `tenant_id\|multi.?tenant` 零命中 |
| D-066 | 后续拆解/开发/测试/交付由 Codex 完成，用户负责规则与 UAT | 已实现 | `docs/delivery/*.md` 回执体系 |
| D-070 | 外部截图只用于提取业务目标，不复制代码/品牌/页面成品 | 已实现 | `docs/delivery/P1-JOB-ARCHITECTURE.md:27-28` 明确记录"只参考信息架构，未复制样式" |
| D-009 | 业务组织同一时间只能有一个直接上级 | 已实现 | `modules/workforce/organization_service.py:1610-1618,1804-1809`（每组织单一 parent，周期检测） |
| D-011 | 组织类型上下级组合不设限制 | 已实现 | `organization_service.py` 未见类型组合白名单校验 |
| D-012 | 新组织编码纯流水号，初始化导入保留历史编码 | 已实现 | `alembic/.../f1a000000001_phase_1a_organization_domain.py:375-402`（`ORG_NUMBER` 序列，width=6） |
| D-013 | 组织调整支持未来生效，只展示当前有效组织树 | 已实现 | `organization_service.py:1804-1809`（按 `effective_date` 取当时 parent） |
| D-014 | 每个组织最多三名负责人且均为主负责人 | 已实现 | `modules/workforce/organization_models.py` 负责人表 |
| D-015 | 后续审批需支持会签与或签 | 已实现 | `modules/workflow/schemas.py:62,67-70`；`workflow/extended_service.py:1216,1333-1336` |
| D-016 | 组织、法人与成本中心允许多对多 | 已实现 | `modules/workforce/models.py` 关系表 |
| D-017 | 法人主体独立于组织，一个 BU 可关联多个法人 | 已实现 | `modules/workforce/models.py` 法人/组织关系 |
| D-018 | 成本中心第一阶段只实现组织级分摊 | 已实现 | `modules/workforce/extended_service.py` 成本分摊服务 |
| D-019 | 同一组织同一有效期分摊比例合计 100% | 已实现 | `modules/workforce/organization_policy.py` |
| D-020 | 成本分摊关系带生效日期和历史版本 | 已实现 | `modules/workforce/models.py` 生效日期列 |
| D-059 | 不建独立待生效组织事件页，在组织详情按生效日期查看 | 已实现 | `apps/web/src/business/features/organization/OrganizationDetailWorkspace.tsx` |
| D-071 | 部门类型与组织类型同一基础资料，扩展为 7 类并支持配置 | 已实现 | `modules/platform/models.py:105-136` 字典；`configuration_api.py` |
| D-072 | 法人保持独立法律主体，不得按组织类型自动推导 | 已实现 | `modules/workforce/organization_service.py` 法人关系独立维护 |
| D-074 | 新职位分类与旧职务/职级/职等/职类/序列取超集，未确认前不得删旧概念 | 已实现 | `alembic/.../f1b000000001_effective_dated_job_architecture.py` 并存维度 |
| D-075 | 无引用基础资料可物理删除，有引用拒绝；非基础资料不删 | 已实现 | `modules/workforce/extended_service.py` 删除前置引用校验 |
| D-077 | 仅含生效日期的基础资料维护有效期历史版本 | 已实现 | `alembic/.../f1b000000001_effective_dated_job_architecture.py` |
| D-080 | 同一职务可被多个职位复用，每职位一个职务 | 已实现 | `modules/workforce/models.py` 职位↔职务多对一 |
| D-081 | 职级只关联一个类别，职位类与职位族向上推导 | 已实现 | `alembic/.../f1b000000001_effective_dated_job_architecture.py` |
| D-082 | 序列作为独立并行维度保留 | 已实现 | 同上迁移中的序列维度 |
| D-083 | 禁用时当前有效与未来生效引用均阻止禁用，仅历史引用不阻止 | 已实现 | `modules/workforce/extended_service.py` 引用占用检查 |
| D-084 | 职类与职位类同一概念，统一术语"职位类" | 已实现 | `modules/workforce/organization_schemas.py` 字段命名 |
| D-085 | 职位与部门为可选多对多 | 已实现 | `modules/workforce/models.py` 职位部门关系表 |
| D-086 | 职位多职等须构成连续区间 | 已实现 | `modules/workforce/organization_policy.py` 职等序校验 |
| D-021 | 实线组织为业务组织，虚线组织用于委员会/BP | 已实现 | `modules/workforce/organization_models.py` 组织类型维度 |
| D-022 | BP 类型为 HRBP/EBP/TBP/FBP | 已实现 | `modules/workforce/models.py` BP 关系表 |
| D-023 | 四种 BP 类型释义 | 已实现 | `modules/workforce/models.py` BP 类型枚举 |
| D-024 | 同一人同一期间只能兼一种 BP 类型，可服务多组织 | 已实现 | `modules/workforce/extended_service.py` BP 唯一性校验 |
| D-025 | 同一组织可由多个 BP 服务 | 已实现 | `modules/workforce/models.py` BP 服务关系表 |
| D-026 | 员工关系覆盖主组织/兼岗/借调/项目/虚拟组织/实线汇报/虚线汇报 | 已实现 | `modules/workforce/reporting_service.py:16-18,60-66`（`direct`/`dotted`）；`modules/workforce/models.py` 各关系表 |
| D-027 | 员工同一时间只有一个主组织，其他关系可并存 | 已实现 | `modules/workforce/extended_service.py` 主组织唯一性校验 |
| D-028 | 第一阶段只管理收入目标 | 已实现 | `modules/workforce/models.py` RevenueTarget |
| D-029 | 收入目标只使用一个业务字段 | 已实现 | `modules/workforce/models.py` 目标金额列 |
| D-030 | 叶子组织维护目标，上级自动汇总 | 已实现 | `modules/workforce/organization_service.py` 汇总逻辑 |
| D-031 | 目标选币种，不做汇率折算 | 已实现 | 全仓 `apps/` 检索 `exchange_rate\|currency_rate` 零命中 |
| D-032 | 收入目标调整保留历史版本与快照 | 已实现 | `modules/workforce/models.py` 版本/快照列 |
| D-063 | 年度目标拆解到 12 个月，月度合计与年度一致 | 已实现 | `modules/workforce/extended_service.py` 月度合计校验 |
| D-033 | Person 与 Employment 分层模型 | 已实现 | `modules/workforce/models.py` Person/Employment |
| D-034 | 工号六位纯数字，待入职分配，二次入职恢复原号 | 已实现 | `modules/workforce/extended_service.py` 工号生成与复用 |
| D-035 | 所有人员类型进入人员主数据 | 已实现 | `modules/workforce/models.py` `employee_type_code` |
| D-036 | 正式员工与校招生计入编制，规则可配置 | 已实现 | `modules/workforce/models.py` OccupancyRule |
| D-037 | 合同/发薪/社保/个税主体分别唯一，默认相同允许不同 | 已实现 | `modules/workforce/models.py` 主体外键列 |
| D-038 | SSC 可改授权信息并记录前后内容，界面引导更正事件 | 已实现 | `modules/workforce/extended_service.py` `EMPLOYMENT_CORRECTION` 事件（`workflow/extended_service.py:1381`） |
| D-040 | 人事事件允许受控回退，每次操作保留日志 | 已实现 | `modules/workflow/extended_api.py:548` `/hr-events/{id}/rollback`＋审计写入 |
| D-041 | 编制维度为组织/职务/年月 | 已实现 | `modules/workforce/models.py` HeadcountPlan |
| D-042 | 每月编制平铺，用户选年月维护 | 已实现 | `apps/web/src/business/features/workforce/HeadcountWorkspace.tsx` |
| D-043 | 编制只呈现结果，不阻断招聘 | 已实现 | `modules/workforce/extended_service.py` 编制仅统计 |
| D-044 | 招聘需求与编制弱关联，不预留空编 | 已实现 | `modules/workforce/extended_service.py` 招聘需求服务 |
| D-045 | 创建待入职档案并明确日期后进入人数统计 | 已实现 | `modules/workflow/extended_api.py` 入职转换；`f3a000000003_application_hire_conversion.py` |
| D-046 | 月均人数 =(月初+月末)/2 | 已实现 | `modules/workforce/extended_service.py` 月均计算 |
| D-047 | 年度页面展示当前值，不把 12 个月人数相加 | 已实现 | `apps/web/src/business/features/workforce/HeadcountWorkspace.tsx` |
| D-048 | 同时支持业务冻结与月结冻结 | 已实现 | `modules/workforce/models.py` HeadcountFreeze |
| D-049 | 月初月末保存完整数据快照 | 已实现 | `modules/workforce/models.py` HeadcountSnapshot |
| D-050 | 第一阶段招聘只实现招聘需求 | 已实现 | `modules/workforce/extended_service.py` 招聘需求，无候选人模块 |
| D-051 | 初始化导入整批校验、整批事务 | 已实现 | `modules/platform/import_service.py`（整批校验） |
| D-052 | 日常批量维护允许部分成功并返回失败明细 | 已实现 | `modules/platform/import_service.py` 行级错误返回 |
| D-054 | 当前结果/有效期历史/月度快照/操作审计分别保留 | 已实现 | `modules/workforce/models.py` AuditLog＋各模块版本表 |
| D-055 | 月初月末快照自动生成；月份边界按快照策略配置时区；修订不覆盖原版本 | 已实现 | `modules/workforce/extended_service.py:1374-1440`（`ZoneInfo(payload.timezone)`、`SnapshotBatch.version`、`parent_batch_id`） |
| D-056 | 业务冻结范围支持年月/组织/职务组合，限制普通角色修改 | 已实现 | `modules/workforce/models.py` HeadcountFreeze＋`modules/workforce/extended_service.py` 冻结范围校验 |
| D-057 | 月结后先更正源数据，再生成并重新冻结修订版本，原始永久保留 | 已实现 | `modules/workforce/extended_service.py:1421-1436`（父子版本链） |
| D-058 | 同一自然人同一期间只能有一条法人劳动关系 | 已实现 | `modules/workforce/extended_service.py` 劳动关系唯一性校验 |
| D-060 | 事件回退按场景采用补偿事件/历史版本恢复/组合，支持直接生效与审批生效 | 已实现 | `modules/workflow/extended_schemas.py:351-359` `execution_mode: Literal["direct","approval"]` |
| D-061 | 招聘需求完整预留状态机，第一阶段不执行审批 | 已实现 | `modules/workforce/extended_service.py` 招聘需求状态机 |
| D-078 | 职级关联员工与职位人数后续派生，不作人工维护字段 | 已实现（DEFERRED） | `modules/workforce/models.py` 无该人工字段 |
| D-079 | 参考截图中的部门层级等字段未来保留，字段定义另行确认 | 已实现（DEFERRED） | `docs/input-packs/10-organization-management-product-input.md` 记录为待确认输入 |
| D-064 | 第一至四阶段不引入 Apusic 等中间件 | 已实现（DEFERRED） | `deploy/compose.yaml` 无中间件服务；`03.md:132` 标注 DEFERRED |
| T-001 | 第一阶段采用模块化单体 | 已实现 | `apps/api/src/hris/modules/*` 单体多模块；`03.md:134` 状态标签仍为 `PARTIAL`（文档维护滞后） |
| T-002 | 后端采用 FastAPI | 已实现 | `apps/api/src/hris/business_main.py`、FastAPI 依赖；`03.md:135` 状态标签仍为 `PARTIAL` |
| T-003 | 前端采用 React/TypeScript/Ant Design，版本与交互按 D-068/D-069 执行 | 已实现 | `apps/web/package.json`（React 19.2.0、antd 6.5.2）＋antd 规范执行；但 `LeavePanel.tsx:110,124` 的 `window.prompt` 违反 D-069（见上表） |
| T-004 | PostgreSQL 采用统一业务 schema | 已实现 | `apps/api/src/hris/shared/db/base.py` 统一 Base；无多库配置 |
| T-005 | Redis 只用于明确的缓存/限流/任务协调场景 | 已实现 | `apps/api/src/hris/modules/system/api.py:31-36` 仅用于健康检查，未越界使用 |
| T-006 | 第一阶段使用本地账号密码，企业微信后接 | 已实现 | `modules/platform/security.py`＋`modules/platform/service.py:39-66`；企业微信未接（Q-016 待输入） |
| T-007 | MCP 以后通过受控业务 API 接入 | 已实现（DEFERRED） | `03.md:140` 标注 DEFERRED；全仓无 MCP server 实现 |

### 4. 本轮产品决策人拍板事项 → 文档落地情况（结论）

审计结束前，`docs/01-foundation/03-项目决策.md` 已由并发写入新增 **§8「2026-10 产品与工程决策」**（`03.md:144-181`），本轮拍板事项**已全部落文档**，编号 D-088~D-101。

| 本轮拍板事项 | 落文档编号 | 文档位置 |
|---|---|---|
| push 策略：等本机全绿或明确要求才 push | D-088 | `03.md:153` |
| push 身份用 GitHub 账号 `Millerprc`；提交身份 `Millerprc <Millerprc@users.noreply.github.com>` | D-089 | `03.md:154` |
| 所有页面统一 Ant Design 规范 + 组件复用 | D-090、D-091 | `03.md:155-156` |
| 当前只做管理端 PC 页面；员工端未来考虑 PC + 移动 | D-092 | `03.md:157` |
| 汇报关系做直属 + 虚线两种 | D-093 | `03.md:163` |
| 员工标签：基础资料定义标签库且允许扩展，从库里选择，支持多选 | D-094 | `03.md:164` |
| 审批动作语义：撤销 = 终止、驳回 = 终止、退回 = 回到上一节点 | D-095 | `03.md:170` |
| 流程引擎单独做底层 | D-096 | `03.md:171` |
| 批量异动：上限 1000 条、支持草稿、整批一个方案走审批 | D-097 | `03.md:172` |
| 绩效按 OKR 方式定义 | D-098 | `03.md:173` |
| 入职先做"按钮直接生效"版本 | D-099 | `03.md:174` |
| 「信息健康度」本次不做（从路线图移除） | D-101 | `03.md:181`（`DEFERRED`） |

另有两条本轮新增、旧清单未覆盖的决策：**D-100 消息引擎（站内信/短信/邮件）作为平台内核级基础服务统一建设**（`03.md:175`）、**D-091 共享组件复用约束**（`03.md:156`）。

> 口径提示：D-090 把"统一 Ant Design 最新版"落为"**统一遵循当前锁定版本 6.5.2**"，与 D-068「仓库依赖版本继续锁定」一致。若产品决策人本意是升级到官网当前 6.6.1，则 D-090 与 D-068 仍需一次显式取舍（升级须单独立项）。

### 5. `03`号 §8 新增决策 D-088~D-101 逐条核对

| 文档条款（文件:行） | 条目摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 03.md:153 `D-088` | 推送到远端必须等本机验证全部通过，或产品决策人明确要求 | 已实现 | `git log origin/main..main --oneline` → 7 个提交**尚未推送**；`git remote -v` → `https://github.com/Millerprc/HRIS.git` | 当前状态符合"未获明确要求即不推送" | — |
| 03.md:154 `D-089` | 推送使用 GitHub 账号 `Millerprc`；仓库提交身份为 `Millerprc <Millerprc@users.noreply.github.com>` | 部分实现 | `git config --local user.name` = `Millerprc`、`user.email` = `Millerprc@users.noreply.github.com`（本地配置已生效，覆盖全局 `MinimaxCode <mavis@local>`）；但 `git log --format='%an <%ae>' \| Sort-Object -Unique` → 历史提交署名为 `Codex <codex@local>`，另有早期 `Millerprc <millerlocke@foxmail.com>`（旧邮箱，非 noreply） | 配置已到位但**提交作者字段尚未生效**。需用一次真实提交验证作者字段，并考虑清理全局 `MinimaxCode <mavis@local>` 身份 | P1 |
| 03.md:155 `D-090` | 所有前端页面统一遵循 Ant Design 当前锁定版本 6.5.2；已废弃属性由守卫脚本阻断 | 部分实现 | `apps/web/package.json` 锁 `antd 6.5.2`；守卫脚本 `scripts/check-antd-usage.mjs` **文件长度 0 字节**（`Get-Item` → `Length 0`，2026-10-24 10:35 创建） | **守卫脚本是空文件，等于没有守卫**，"废弃属性阻断"当前完全不生效。建议先补脚本（至少覆盖 `Modal.visible`、`bodyStyle`、`dropdownClassName`、`Descriptions bordered` 等 v6 已废弃项）并接入 `scripts/check-business*.ps1` | P1 |
| 03.md:156 `D-091` | 新增与改造页面优先复用既有共享组件；同一能力域不得出现第二套结构写法 | 部分实现 | 考勤六页签共用 `workspace-section`/`panel-heading`/`payload-preview` 结构（`apps/web/src/business/features/attendance/AttendanceWorkspace.tsx:18`、`ReportPanel.tsx:138`）；但无共享组件台账，`apps/web/src/business/features/` 按业务域平铺，无公共组件层目录 | "不得出现第二套写法"无可验证依据，只能靠人工评审。建议先产出共享组件台账，并让 D-090 的守卫脚本一并检查 | P2 |
| 03.md:157 `D-092` | 当前只建设管理端 PC 页面，不在管理端实现移动端响应式适配；员工端后续立项，届时同时考虑 PC 与移动 | 已实现 | `apps/web/src/business/AppShell.tsx` 仅管理端工作台；`apps/web/src/business/features/` 无移动端/员工端入口；`00.md:55` "主管理员PC管理端" | 与 `00.md:64` 的"员工移动门户延期到第五阶段"一致。员工端 PC+移动形态已由 D-092 记录 | — |
| 03.md:163 `D-093` | 汇报关系同时支持实线与虚线；两者各自独立成环校验，虚线指向自己的实线上级合法 | 已实现 | `modules/workforce/reporting_service.py:16-18`（`direct`/`dotted`）；`:60-66` 类型白名单；`:239-266` 环路检测按 `relation_type` **独立成环**（`:247`），不会用实线环路拦截虚线 | 与 D-093 一致，含"矩阵汇报合法场景"这一细节 | — |
| 03.md:164 `D-094` | 员工标签由基础资料定义标签库并允许扩展；从标签库多选，不接受自由输入；单次批量赋予整批原子生效 | 已实现 | `modules/workforce/labels_api.py:151` `/label-library`、`:140` `/label-types`；`:109-125` `/persons/{id}/labels/batch`（`HR-LABEL-015`"从标签库多选的标签整批原子写入"）；`alembic/versions/f2c000000001_seed_person_label_library.py` 种子；前端 `apps/web/src/business/features/people/PersonLabelPanel.tsx` | 与 D-094 一致。前端目录在 `features/people/`、后端在 `modules/workforce/`，模块归属建议统一 | P2 |
| 03.md:170 `D-095` | 撤销＝终止、驳回＝终止、退回＝回到上一节点；三者在接口、状态、文案与审计上必须完全区分，不得共用同一操作入口 | 未实现 | `modules/workflow/extended_schemas.py:490` `decision: Literal["approve", "reject"]`（仅两值）；`workflow/extended_service.py:1324-1330` 驳回即 `instance.status="rejected"` 终止；**无撤销、无退回上一节点**（检索 `withdraw\|return_to\|rollback_node` 在 `modules/workflow/` 仅命中招聘状态机的 `withdrawn`，非审批动作）；请假侧同样两义：`attendance/extended_service.py:960-967`；前端 `LeavePanel.tsx:166` 只有"批准/拒绝"两个按钮，`:161` 把 `rejected` 与 `cancelled` 渲染成同一颜色 | **D-095 明确要求"不得共用同一个操作入口"，当前正是共用入口**。需扩展决策值域、任务/实例状态机、请假状态机与前端按钮与标签，并让审计区分三种动作 | P0 |
| 03.md:171 `D-096` | 审批流程引擎作为独立底层建设；对齐 Moka 的审批动作、批量催办与按流程分 Sheet 导出能力 | 部分实现 | 独立底层已成立：`apps/api/src/hris/modules/workflow/`（models/schemas/service/extended_*/conditions）；审批动作对齐部分未做（D-095）；**批量催办未实现**（检索 `urge\|remind\|催办` 在 `modules/` 无命中）；**按流程分 Sheet 导出未实现**（`modules/platform/master_data_export.py` 只做主数据导出） | 三项要求中只有"独立底层"达成。D-096 点名的 Moka 对标项（批量催办、按流程分 Sheet 导出）完全没有载体，建议纳入下一批流程引擎功能文档 | P1 |
| 03.md:172 `D-097` | 批量异动单方案上限 1000 条，支持草稿态增删改；整批只产生一个流程实例并统一审批，审批通过后整批执行 | 已实现 | 上限 `modules/workforce/batch_change_models.py:51-52` `BATCH_CHANGE_MAX_LINES = 1000`，`batch_change_service.py:148-163` 超限整批拒绝；草稿 `:29-49` 状态机与明细草稿态；单流程实例 `:224-241`；审批回调 `modules/workflow/extended_service.py:1359-1372`（**审计期间被并发补上**）→ `:1369` `mark_approved` 把整批明细转 `ready`，交既有 hr_event 执行器按生效日执行 | 四项要素全部落地（其中审批回调为审计期间并发修复，未提交） | P2 |
| 03.md:173 `D-098` | 绩效按 OKR 方式定义：周期、目标、关键结果，权重与评分在目标与关键结果两级维护；不实现 360 评估、强制分布与绩效面谈 | 已实现（开发中） | `modules/performance/models.py:1`（周期/目标/KR 表）、`:23-52`（周期类型与状态、OKR 状态、`MAX_OKR_WEIGHT=100`、`MIN/MAX_OKR_SCORE=0..100`）；`modules/performance/api.py:112-126` 目标与关键结果接口及计分卡；`alembic/versions/f2e000000001_performance_okr_schema.py`；`apps/api/tests/integration/test_performance_okr_api.py` | 范围与"不实现 360/强制分布/面谈"一致，无越界实现。属开发中；权限复用 `LIFECYCLE_ADMIN`（`performance/api.py:32-35`），该码同样无 Permission 行 | P2 |
| 03.md:174 `D-099` | 入职流程先做"按钮直接生效"的通用版本，等流程引擎底层定稿后再接入审批 | 与PRD冲突 | `modules/workflow/extended_schemas.py:357` `execution_mode: Literal["direct","approval"] = "approval"`；前端 `apps/web/src/business/features/lifecycle/HrEventPanel.tsx:253` 执行方式默认 **"审批后生效"**，另设"发起审批"弹窗（`:258`） | **默认值与决策相反**：入职走 `ONBOARDING` 时默认仍进审批流。建议把入职场景默认切为 `direct`、审批入口降为可选，并同步 99.md:41-43 Q-014 的下一项确认顺序 | P1 |
| 03.md:175 `D-100` | 消息引擎（站内信、短信、邮件）作为平台内核级基础服务统一建设，通过稳定端口适配各投递通道 | 未实现 | 全仓 `apps/` 检索 `notification\|notify\|webhook\|企业微信\|wecom` **零命中**；无消息模型、无投递端口抽象 | **D-100 是新增的平台级前置能力，当前完全缺失**。它同时是 99.md:63 Q-017（合同到期提醒）、Q-016（外部系统接口）与 D-096（批量催办）的共同底座。建议单独立项，不要在业务域各自实现 | P0 |
| 03.md:181 `D-101` | "信息健康度"能力本轮不建设，从补活路线图中移除 | 已实现（DEFERRED） | 全仓 `apps/` 与 `docs/` 检索 `信息健康\|健康度` 零命中；无对应代码或需求条目 | 与 DEFERRED 状态一致。若 `16` 号 PRD 或路线图仍列该能力，需同步移除 | P2 |

---## 任务三：文档规范遵守情况

### 3.1 `17-模块功能需求文档规范.md` 是否已落地：结论＝**定义了但一份都没落地**

| 检查项 | 检查方法与检索词 | 结果 | 证据 |
|---|---|---|---|
| 17号建议的正式需求目录 `docs/requirements/` | `Test-Path docs/requirements` ＋ `Get-ChildItem docs -Recurse -Directory` 全量列目录 | **不存在** | `docs/` 下只有 01-foundation/adr/architecture/archive/delivery/design/implementation/input-packs/migration/review/superpowers 共 13 个目录，无 requirements/ |
| 是否存在按 17 号 §4.2 编号的功能文档（`ATT-PUNCH-F001` 等） | 全树正则 `ATT-PUNCH\|ATT-[A-Z]{4}-F[0-9]{3}\|WFC-[A-Z]{4}-F[0-9]{3}\|FLW-[A-Z]{4}-F[0-9]{3}` | **仅命中规范本身** | `docs/01-foundation/17-模块功能需求文档规范.md`、`docs/01-foundation/10-代码结构与编码规范.md`（两处都是"引用规范"，不是功能文档实例） |
| 是否存在按 17 号 §3 命名规则的功能文档（`<功能ID>-<kebab-case>.md`） | glob `**/*-F0[0-9][0-9]-*.md` | **0 命中** | — |
| 是否存在按 17 号 §7 模板（§7 业务规则/§15 验收场景/§19 开发任务与追踪）写的文档 | 正则 `^## 15\. 验收场景\|^## 19\. 开发任务与追踪\|^## 7\. 业务规则` | **仅命中规范自身** | `docs/01-foundation/17-模块功能需求文档规范.md` |
| 是否存在 §10.4 的 Pencil 原型登记表 | 检索 `PROTOTYPE_APPROVED` 全树 | **仅 2 条**，且都在输入包而非功能文档 | `docs/input-packs/10-organization-management-product-input.md:266`（ORG-PROT-001 组织管理框架）、`:267`（ORG-PROT-002 组织详情新标签页）；`docs/design/prototypes/README.md:7` 明确"权威 Review 状态记录在对应功能需求或产品输入稿的原型登记表中" |
| 是否存在 §19「开发任务与追踪」表（任务ID/需求追踪注释/验收场景/交付证据） | 同上正则检索 | **0 份** | — |

**结论与影响链（这是本分片最重要的文档层发现）**

1. `17`号规范定义了"模块 → 能力域 → 功能 → 验收场景 → 最小任务"的完整拆解链路，但 `docs/` 全树**没有任何一份按它建立的功能文档**。规范处于"已定义、零实例"状态。
2. 由此产生的连锁失效：
   - `00.md:95` 自己规定"对应迁移输入中的已确认业务事实；**若尚未迁移到批准的功能文档，不得直接开工**"。按此规则，当前所有新增开发（职位管理、汇报关系、标签库、批量异动、绩效 OKR、审计日志前端、考勤六页签）都**缺少合法开工依据**。
   - `17.md:177-194`（进入开发前的 12 条准备门槛）、`:584-600`（工程实现完成定义）、`:643-663`（15 项 Review 检查表）**从未对任何功能走过一次**。
   - `14.md:244` 明确要求"收到用户确认后，先更新项目决策、本规格、对应输入包及按 `17`号规范建立的功能文档，再由 Codex 直接实施和验证"——该流程未执行。
   - `17.md:592` 要求"每项需求驱动的代码变化均能从规则落点的追踪注释回到稳定需求或决策ID"，`03.md:21` D-067 同义要求。考勤模块 **0 条** `Requirement:` 注释，恰好是"没有功能文档 ⇒ 没有规则编号 ⇒ 无处可引"的直接结果。
   - `17.md:597` 与 `docs/design/antd-page-interaction-standard.md:104`、`10-代码结构与编码规范.md:402` 要求"无 `PROTOTYPE_APPROVED` 不得进入前端开发"——除组织管理的 2 个画板外，考勤等 20+ 页面均无原型登记却已编码（D-087 违反）。

**修复建议（P1）**：先按 `17`号 §7 模板为 **Attendance（ATT）** 建立第一批功能文档，至少覆盖 `ATT-PUNCH`（原始打卡）、`ATT-LEAVE`（假期与余额）、`ATT-RESULT`（日报/月报）、`ATT-FREEZE`（冻结）四个能力域，每个功能带 §15 的最小验收场景集合（`17.md:497-516` 要求正常/边界/拒绝/越权/并发幂等/审计六类）与 §19 任务追踪表。这批文档也是本分片"考勤 0 条追踪注释"的补齐载体。

### 3.2 `00-正式文档目录.md` 权威清单 ↔ 实际文件一致性

| 检查项 | 结果 | 证据 | 判定 |
|---|---|---|---|
| §1.1 现行权威 6 项（16/17/03/10/antd 规范/99）对应文件是否存在 | 全部存在 | `docs/01-foundation/{16,17,03,10,99}.md`、`docs/design/antd-page-interaction-standard.md` | 一致 |
| §1.2 迁移输入 8 项（01/05/输入包10/06/07/08/12/14）是否存在 | 全部存在 | `docs/01-foundation/{01,05,06,07,08,12,14}.md`、`docs/input-packs/10-organization-management-product-input.md` | 一致 |
| `docs/01-foundation/` 实际文件是否都在清单内 | 实际 14 个文件，清单覆盖 12 个 | 目录内多出 `README.md`（索引，自指向 00）与 `00` 自身；编号空缺 02/04/09/11/13/15 已在 `docs/archive/2026-08-18-foundation-rebaseline/` 归档，与 `00.md:39` 一致 | 基本一致（README.md 未登记，P2） |
| §1.1 状态标签 | **16 与 17 都是 `BASELINE / REVIEW_PENDING`** | `00.md:15-16` | **不一致（P1）**：`00.md:88-97` 的冲突处理顺序把"16 总体 PRD"排第 2、"03 项目决策"排第 3，把一个**尚未被产品决策人批准**的文档排在已确认决策之前当裁判；`17` 号规范同样未批准，却是全部开发任务的依据来源。需产品决策人对 16 与 17 正式批准或明确降级顺序 |
| ADR 权威性 | `docs/adr/README.md:8-9` 中 ADR-0002/0004 状态 `Accepted`（"可以作为实现依据"，`:31`），ADR-0001 状态 `Proposed`（"不得作为正式实现依据"，`:30`） | 但 `00.md:9` 规定"未列入现行权威或迁移输入的资料，**不得作为新开发依据**"，而 `docs/adr/` 全目录**未在 00 号任何清单中登记** | **不一致（P1）**：ADR-0004（人员敏感字段应用层保护）已 Accepted 且代码已落地（`alembic/versions/f1d000000001_personnel_sensitive_subrecords.py`、`modules/workforce/personnel_service.py`、`apps/api/tests/integration/test_personnel_security.py`），却按 00 号规则"没有开发依据"；ADR-0001（工具链与版本冻结）仍是 Proposed 而 `03.md:134-140` T-001~T-007 的版本已实际落地 |
| 其他未登记的高影响文档 | `docs/architecture/product-architecture.md`、`docs/design/design-system-v1.md` 未在 00 号清单 | `design-system-v1.md:15`（被 antd 规范引用，且其方向 A/B "尚未批准"） | P2：`design-system-v1.md` 被 ACTIVE 规范引用却未登记，且自身未批准，属"引用了未批准文档" |
| §2 当前实现边界的时效 | `00.md:64` "当前真实完成度以一至三阶段整体Review报告（`docs/review/phase-1-3-overall-review-2026-08-12.md`）为准" | 该报告为 2026-08-12；工作区此后新增职位管理、汇报关系、员工标签+标签库、批量异动方案制、绩效 OKR、操作日志前端（`apps/web/src/business/features/platform/AuditLogWorkspace.tsx`） | **不一致（P2）**：完成度基准已过期，00 号 §2 的"已经实现"清单未随代码更新 |
| §5 第一阶段企业适配前条件 | `00.md:122` 要求"按实现符合性审查逐项关闭 PARTIAL"，该审查为 2026-08 之前 | `docs/review/phase-1-3-implementation-conformance-review.md` | P2 |

### 3.3 任务三小结

- `17`号规范**零落地**（P1，根因级）。它不是"写好了没人用"，而是"新功能全部绕过了它开工"，而 `00.md:95` 又明文禁止这样开工——两者互相打脸。
- `00`号清单的**文件层面**与实际一致；不一致集中在**状态与范围**层面：16/17 未批准却当权威、ADR 目录整体未登记却被代码依赖、完成度基准过期。
- 由此产生两条对本分片其他结论的放大效应：D-067（追踪注释）无载体、14.md:244 的"先建功能文档再实施"流程被整体跳过。

---

## 本分片 3 条最该先修的

1. **权限种子缺口（P0；14.md:184/185、03.md:15 D-004、03.md:131 D-062）**：`ATTENDANCE_ADMIN`、`LIFECYCLE_ADMIN`、`WORKFORCE_ADMIN` 三个权限码在全部 21 个 Alembic 迁移中都没有 Permission 行，`modules/platform/dependencies.py:56-70` 的权限判定因此只对持 `*` 的主管理员放行 → SSC 进不了考勤、生命周期、人员档案、批量异动、绩效任何模块，D-004（第一批用户含 SSC）与 14.md:184 同时落空，14.md:185 要求的"7 类高风险动作独立权限"也完全没落地粒度。修复成本最低（一条迁移种权限码并授予 `SSC_ADMIN`），收益覆盖考勤与生命周期两条主干。
2. **审批动作语义只有两义 + 消息引擎缺失（P0；03.md:170 D-095、03.md:175 D-100）**：`modules/workflow/extended_schemas.py:490` 的 `Literal["approve","reject"]` 让"撤销/驳回/退回"无法区分，而 D-095 恰恰要求"不得共用同一个操作入口"——`LeavePanel.tsx:166` 正是共用入口（`:161` 把 `rejected` 与 `cancelled` 渲染成同一颜色）；同时 D-100 把消息引擎定为平台内核级前置能力，当前全仓零实现，而合同到期提醒（Q-017）、外部系统接口（Q-016）、批量催办（D-096）全压在这块底座上。这两条一红一缺，决定第二轮企业 UAT 要不要返工。
3. **考勤计算链 0 条需求追踪注释 + 月报口径缺口（P0/P1；14.md:243、P3-MONTH-002）**：`modules/attendance/` 4 个文件里 `Requirement:` 注释数为 0（全仓 136 条），直接违反 `03.md:21` D-067 与 14.md:243，让 P3-* 需求编号无法从代码回溯；同时 `attendance/extended_service.py:1322-1325` 的月报口径漏算 `leave_with_punch`、`exception` 与未排班日，缺勤天数系统性偏低，企业验收对账阶段一定爆。两者都在考勤主干上，改动局部且可独立验证。

---
## 附：无法完全判定的条款及原因

| 条款 | 无法判定的原因 |
|---|---|
| `03`号 D-001、D-005、D-006、D-007、D-011~D-014、D-016~D-022、D-023~D-025、D-027~D-030、D-032~D-038、D-041~D-054、D-058、D-059、D-061、D-070~D-072、D-074~D-075、D-077、D-080~D-086（附录表中 60 余条） | **模块级判定**：已确认对应模块/迁移/测试存在且未见反向证据，但未逐条核对业务细节（如"每组织最多三名负责人且均为主负责人""成本分摊合计必须为 100%"这类取值级规则）。本分片预算优先给了考勤与待确认/决策主线，这些条目建议由对应模块的专项复核补齐 |
| 14.md:88-92（P3-RULE-004~007 的企业口径部分）、14.md:165-166（P3-DAY-004/005）、14.md:175（P3-MONTH-003）、14.md:180（P3-FRZ-005）、14.md:210（容量目标） | **缺企业输入**而非缺实现：这些条款本身声明 `PENDING_ENTERPRISE_INPUT`，"是否满足"取决于企业案例，不能由代码判定。本报告按"实现是否提前固化"这一可判定角度给出结论 |
| 99.md Q-011/Q-012/Q-013 的"业务 Review"与"增量字段"完成度 | 属企业侧动作，无技术侧可观测信号。代码侧只能证明基础设施与首个组合已落地 |
| 16 号总体 PRD 的条款 | 不在本分片范围（由另一 agent 审计）。本报告仅在需要判断"某决策是否已有落点"时做只读检索，不对其内容下结论 |
| `docs/input-packs/` 全部内容 | 按分片约定未纳入审计范围 |
| 03 号 D-014 等"每人/每组织上限类"规则 | 见上第一行，属取值级细节未逐条核对 |
| 03 号 D-090 的"守卫脚本"覆盖面 | `scripts/check-antd-usage.mjs` 为 0 字节，无法判断它原计划拦截哪些废弃属性；本报告只能确认"当前不拦截任何属性"，并对 `Descriptions bordered`（`ReportPanel.tsx:138`）是否属 antd 6.5.2 已废弃项保持**未判定**（`apps/web/node_modules` 未安装，无法核对类型声明） |
| 03 号 D-096 的 Moka 对标口径 | D-096 只写"对齐 Moka 的审批动作、批量催办与按流程分 Sheet 导出能力"，未给出可判定的验收口径；本报告只能判定这两项能力**当前无载体**，不能判定"是否已达到 Moka 水平" |