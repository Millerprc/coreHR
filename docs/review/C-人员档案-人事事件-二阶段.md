# 分片 C：人员档案领域规范 + 人事数据与事件规范 + 第二阶段需求规格 ↔ 实现 对账

> 审计对象：`docs/01-foundation/07-人员档案领域规范.md`、`08-人事数据与事件规范.md`、`12-第二阶段需求规格.md`
> 审计时间：2026-10-24　｜　代码基线：**coreHR 工作区当前工作树**（`main` @ 8c5d207 + 未提交的在建改动：标签库/汇报关系/职位/审计日志/批量异动/绩效OKR）；本次审计**未做任何 git 写操作**，仅读取文件
> 判定口径：已实现 / 部分实现 / 未实现 / 与PRD冲突 / 待企业输入 / 待决策 / 开发中
> 判定说明：`待企业输入` 与 `待决策` 表示文档自身已声明依赖企业输入或明确未决，**不计为实现缺陷**。

## 汇总
| 判定 | 条数 |
|---|---|
| 已实现 | 83 |
| 部分实现 | 75 |
| 未实现 | 5 |
| 与PRD冲突 | 5 |
| 待企业输入 | 13 |
| 待决策 | 1 |
| 开发中 | 2 |
| **合计** | **184** |

优先级分布：

| 优先级 | 条数 |
|---|---|
| P0 | 1 |
| P1 | 68 |
| P2 | 28 |
| - | 86 |

## 明细

### 一、`07-人员档案领域规范.md`（人员档案领域规范）

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 07:11-20 | 第一阶段范围：自然人档案、待入职/在职/离职历史雇佣、六位工号、组织职务汇报与四类主体当前结果及有效期历史、证件联系方式、导入导出敏感保护审计 | 部分实现 | `apps/api/src/hris/modules/workforce/models.py:324`（Person）、`:604`（Employment）、`:691`（EmploymentAssignment）、`:645`（EmploymentLegalEntityRelation）、`:748`（ReportingRelation）、`apps/api/src/hris/modules/platform/import_api.py:96`、`:150`、`master_data_export.py:117`、`core/personnel_security.py:37` | 主体/雇佣/关系/敏感/导入导出均已落地；缺口在「四类主体的指定时点结果」没有统一读取入口（见明细表「07:324」行） | P2 |
| 07:22-27 | 本阶段不包含：员工自助、入职/转正/调动/离职/兼岗完整流程、合同协议全文管理、考勤薪酬社保税务核算 | 已实现 | 全仓无员工自助模块；`apps/api/src/hris/modules/workflow/models.py:189-242`（ContractRecord）只有结构化字段无原文；`apps/api/src/hris/modules/attendance/` 属第三阶段 | 边界未被越界，符合文档 | - |
| 07:46 | Person 表示不可因离职而删除的自然人身份，同一自然人可有多次历史雇佣 | 已实现 | `workforce/models.py:324-348`（Person 无 status=离职语义、无级联删除）；`apps/api/src/hris/modules/workforce/extended_api.py:271` 只有 PATCH，无 DELETE | 离职只改 `Employment.status`，Person 不删，符合 | - |
| 07:48 | 自然人匹配优先使用可信证件；无法可靠自动匹配时由 SSC 人工确认是否同一人 | 部分实现 | 证件唯一键含证件类型+签发国+digest：`workforce/models.py:384-391`；`personnel_service.py:139-150` 已具备按 digest 检索的密码学能力；检索词 `OrganizationPersonRelation`/`digest` 全仓检索后确认——对外检索仅 `extended_service.py:1114-1119`（`display_name`/`employee_number` ilike） | **缺按证件号/脱敏值检索自然人的接口**，也无「SSC 人工确认」环节（`hire_application` 直接吃 `existing_person_id`，`workflow/extended_service.py:598-608`）。建议：在 `list_persons` 增加 `document_digest` 检索参数，并把证件匹配候选做成待确认列表 | P1 |
| 07:52 | Employment 表示一次雇佣经历；二次入职创建新的 Employment，不覆盖历史雇佣 | 已实现 | `workforce/extended_service.py:764-835`（create_employment）；无 Employment 的 PUT/DELETE 接口 | 符合 | - |
| 07:54 | 同一自然人在任意重叠有效期间只能有一条有效 Employment；数据库和领域服务都必须阻止有效期重叠 | 部分实现 | 领域服务：`workforce/extended_service.py:805-817`（`EMPLOYMENT_PERIOD_OVERLAP`）；检索词 `EXCLUDE USING gist` / `daterange` 在 `apps/api/alembic/versions/` 只命中 `f1a000000001_phase_1a_organization_domain.py:316-372` 的六张组织表，`employments` 建表见 `6247e614f4a2_phase_1_3_core_schema.py:251-275` 无排他约束 | **只有领域服务拦截，数据库层无排他约束**，并发下可绕过（文档写明「数据库和领域服务都必须」）。建议：加 `EXCLUDE USING gist (person_id WITH =, daterange(planned_start_date, COALESCE(end_date+1,'infinity'), '[)') WITH &&)` | P1 |
| 07:58-64 | 非劳动关系不创建第二条 Employment，作为独立协议关系保存；至少保存关系类型、关联主体或合作方、生效日期、失效日期和来源 | 已实现 | `workforce/models.py:778-801`（AgreementRelationship 六个字段齐全）；`workforce/extended_service.py:1019-1046`；`extended_schemas.py:321-337`（法人/合作方至少一项） | 符合 | - |
| 07:68-71 | 工号为六位纯数字流水号；创建待入职档案时分配并占用；一经分配不因撤回入职或离职分配给其他自然人 | 已实现 | 格式：`workforce/models.py:327-330` CHECK `^[0-9]{6}$`；分配：`extended_service.py:681-690`（序列 + `EMPLOYEE_NUMBER_EXHAUSTED`）、`:721-734`（reserve_employee_number 占用）；Person.employee_number unique（`models.py:333-337`） | 序列只增不减，撤回/离职都不回收，符合 | - |
| 07:72-73 | 同一自然人原则上只有一个集团统一工号；初始化导入保留现有工号 | 已实现 | `workforce/models.py:333-337`；导入模型 `apps/api/src/hris/modules/platform/import_schemas.py:122-126`（PersonBasicImport 必填 employee_number）；落库 `platform/import_service.py:2533-2548` | 符合 | - |
| 07:74 | 自动编号避开已导入工号 | 已实现 | `workforce/extended_service.py:683-686`（`sequence.current_value = max(current_value, imported)`） | 符合 | - |
| 07:77 | 工号耗尽、历史重复或非法工号的处理方式在数据迁移设计中确定 | 部分实现 | 耗尽：`extended_service.py:687-688`；重复：`:694-698`；非法：`extended_schemas.py:177` 正则 | 「历史重复」的迁移期去重/留痕策略没有落成文档或脚本（工号耗尽与单条重复有码，批量历史重复无） | P2 |
| 07:92 | 人员类型使用可配置字典，不在代码中写死完整枚举 | 部分实现 | `workforce/models.py:619`（`employee_type_code` 为自由字符串，未硬编码枚举）；占编规则可配：`models.py:835-849`（OccupancyRule）；检索词 `EMPLOYEE_TYPE` / `PERSON_TYPE` 在 `apps/api/src` **无命中** | 代码未写死枚举 ✅，但**没有「人员类型」字典实体**，创建雇佣时不校验编码是否存在于字典，脏码可入库。建议：接入既有 `DataDictionary`（`platform/configuration_api.py:37-127`）并在使用点校验 | P1 |
| 07:95 | 正式员工和校招生计入编制结果，其他类型当前不计入；占编规则由配置控制 | 已实现 | `workforce/models.py:835-849`（`counts_for_headcount` + 有效期 + version）；`extended_service.py:1191-1231`（create_occupancy_rule）、`:1366-1372`（统计按 OccupancyRule 过滤） | 符合 | - |
| 07:99-109 | 雇佣状态至少容纳：待入职、试用、在职、停薪留职、离职中、已离职、入职撤回 | 部分实现 | 实际状态值仅 4 种：`extended_service.py:822`（`pending_start`）、`workflow/extended_service.py:1626,1628`（`active`）、`:1631`（`terminated`）、`:1636`（`withdrawn`）；检索词 `probation` / `notice_period` / `leave_without_pay` / `resigning` 在 `apps/api/src` 只命中 `probation_end_date` 字段 | **缺「试用」「停薪留职」「离职中」三个独立状态**；转正只写 `probation_end_date` 不改状态，无法表达「试用期在职」与「离职中待交接」。建议：扩状态字典 + `Employment.status` 取值域，并把 CONFIRMATION 拆成「试用→在职」两步 | P1 |
| 07:117-123 | 基础身份字段：姓名及历史姓名、性别、出生日期、国籍、国家或地区、证件姓名、照片 | 部分实现 | `workforce/models.py:338-348` 覆盖 legal_name/display_name/former_name/gender_code/birth_date/nationality_code/country_code；检索词 `photo` 在 `apps/api/src` **无命中** | 缺「照片」「证件姓名」字段。该节自述「最终字段以现有表结构为准」，按候选字段处理 | P2 |
| 07:127-132 | 联系方式：个人手机号、工作手机号、个人邮箱、工作邮箱、常住地址、通讯地址 | 已实现 | `workforce/models.py:425-455`（PersonContact.contact_type）、`:458-481`（PersonAddress.address_type）；前端选项 `apps/web/src/business/features/workforce/PersonnelSubrecordsPanel.tsx:397,403,467,473` | 四种联系方式 + 常住/通讯地址齐全，符合 | - |
| 07:136-145 | 证件一对多实体：证件类型、号码、签发国家或地区、签发日期、到期日期、是否主要证件、附件引用、校验状态 | 部分实现 | `workforce/models.py:382-422` 覆盖类型/号码/签发国/签发日/到期日/是否主要/校验状态；检索词 `attachment_ref` / `attachment_id` 在 `apps/api/src` **无命中** | 缺「附件引用」字段（证件扫描件无法挂接） | P2 |
| 07:147 | 证件类型和校验规则按国家或地区配置，不假设只有中国身份证 | 部分实现 | `workforce/models.py:408-409`（document_type_code / issuing_country_code 均为自由码）；校验仅日期顺序 `:392-395`；前端可选证件类型为自由文本 `PersonnelSubrecordsPanel.tsx:462-463` | 有国家维度字段 ✅，但**没有按国家/地区配置的证件类型与校验规则字典**（如身份证长度、护照正则）。建议：证件类型挂到 `DataDictionary` 并带国家维度 | P2 |
| 07:153-156 | 关联资料：紧急联系人、教育经历、工作经历、家庭成员 | 已实现 | `workforce/models.py:484-511`（EmergencyContact）、`:513-545`（EducationRecord）、`:547-577`（WorkExperience）、`:580-601`（FamilyMember）；接口 `apps/api/src/hris/modules/workforce/personnel_api.py:166-286` | 全部实现且带有效期，符合 | - |
| 07:157-158 | 候选关联实体：银行账户、附件 | 待企业输入 | 检索词 `bank_account` / `BankAccount` / `attachment_ref` / `attachment_id` 在 `apps/api/src` **无命中** | 文档自述「是否第一阶段全部上线，等待员工档案表头和数据样例后确认」，按企业输入待办处理，不计为实现缺陷 | P2 |
| 07:168-175 | 雇佣标识：工号、人员类型、雇佣状态、计划入职日期、实际入职日期、转正日期、离职日期、离职原因 | 已实现 | `workforce/models.py:619-625`（employee_type_code/status/planned_start_date/actual_start_date/probation_end_date/end_date/end_reason_code） | 字段齐，符合 | - |
| 07:179-185 | 职务信息：主职务、职级、职等、职类、序列 | 已实现 | `workforce/models.py:127-237`（JobCatalog + JobDimension + 版本表）；职级/职等/职类/序列落在 `JobCatalogVersion.level/grade/class/sequence_dimension_id`（`:231-234`）；主职务挂 `EmploymentAssignment.job_id`（`:712`） | 维度已建成可配置维度表，符合 | - |
| 07:189-196 | 同一生效日期分别保存劳动合同、发薪、社保、个税申报四类主体；四者默认相同，允许管理员分别调整；每类在同一时点只允许一个有效值 | 部分实现 | 默认相同：`extended_service.py:793-798,826-832`；可分别调整：`EmploymentLegalEntityRelation`（`models.py:645-688`）+ `extended_api.py:319-336`；唯一约束 `models.py:654-659` 为 `(employment_id, relation_kind, effective_from)` | 「同一时点唯一」仅靠**相同 effective_from 唯一**，未用排他区间约束——同 employment+kind 两个不同 effective_from 的**重叠**区间可同时存在，违反「同一时点只允许一个有效值」。建议：对该表加 `EXCLUDE USING gist (employment_id WITH =, relation_kind WITH =, daterange(...) WITH &&)` | P1 |
| 07:200-210 | 人员关系至少包括主组织、兼岗、借调、项目组织、虚拟组织、实线汇报、虚线汇报、BP 服务关系 | 部分实现 | 组织侧：`extended_schemas.py:294`（relation_type = primary/concurrent/secondment/project/virtual）+ `workforce/extended_service.py:961-1017`；汇报：`workforce/reporting_api.py:60-100` + `models.py:748-775`；BP：`workforce/organization_models.py:80-130`（PersonBpMembership/BpServiceScope）+ `organization_api.py:262-321` | 八类均有落点 ✅，但 Person 级组织关系表 `OrganizationPersonRelation`（`workforce/models.py:720-745`）**全仓无任何 service/API 写入路径**——检索词 `OrganizationPersonRelation` 仅命中 `models.py` 与 `shared/db/models.py`，属死模型。当前组织关系实际由 EmploymentAssignment 承载（挂在雇佣上），语义等价但与文档「人员关系」建模不一致 | P1 |
| 07:213 | 每条关系记录生效日期、失效日期、来源和历史版本 | 部分实现 | ReportingRelation：`workforce/models.py:748-775` 有 effective_from/to，**无 source、无 version**；EmploymentAssignment：`:691-717` 有 version，**无 source**；OrganizationPersonRelation：`:720-745` 有 note，**无 source、无 version** | 汇报关系缺「来源」与「历史版本」；组织关系缺「来源」。建议：统一补 `source` + `version` 并按有效区间保留多版本 | P1 |
| 07:214 | 员工同一时间只能有一个主组织 | 已实现 | `extended_service.py:978-999`（`PRIMARY_ASSIGNMENT_PERIOD_OVERLAP`） | 服务层已拦，符合 | - |
| 07:215-219 | 员工可同时存在多个其他类型组织关系；兼岗/借调/项目/虚拟组织默认不重复占编；实线和虚线汇报独立于组织负责人；BP 服务关系适用独立 BP 类型唯一性规则 | 已实现 | 仅 primary 做重叠校验：`extended_service.py:978`；统计只数 primary：`:1343-1372`；BP 排他唯一：`apps/api/alembic/versions/f1a000000001_phase_1a_organization_domain.py:335-342`（`ex_person_bp_memberships_person_period`）；BP 类型 CHECK `organization_models.py:84-87` | 符合 | P2 |
| 07:221 | 人员档案页面需要展示当前关系和历史关系 | 部分实现 | `apps/web/src/business/features/workforce/PeopleWorkspace.tsx:213-287`（Tab：基础信息 / 敏感与经历档案 / 员工标签 / 劳动关系 / 四类主体版本 / 组织职务 / 协议关系） | Drawer 内**没有「汇报关系」Tab、没有「事件历史」Tab、没有「敏感访问记录」Tab**，与文档要求的人员关系全貌不符 | P1 |
| 07:227-232 | 待入职：SSC 创建自然人或匹配已有自然人、创建待入职 Employment、填计划入职日期、分配六位工号、维护计划主组织职务人员类型和四类主体 | 已实现 | `extended_api.py:217-221`（建 Person）、`:284-289`（reserve-number）、`:292-298`（建 Employment）、`:339-352`（建组织职务关系）；`extended_service.py:790-791`（自动分配工号）、`:793-798`（四主体默认相同）、`:837+`（写主体版本） | 链路完整，符合 | - |
| 07:232 | 符合占编规则时按计划日期进入相关统计 | 已实现 | `extended_service.py:1343-1372`（`_count_people` 用 `planned_start_date <= as_of` 且按 OccupancyRule 过滤） | 符合 | - |
| 07:238-243 | 二次入职：用证件等可靠标识检索历史自然人、SSC 确认是否同一人、创建新的 Employment、恢复原工号、历史 Employment 保持只读可查 | 部分实现 | 复用原 Person/工号：`workflow/extended_service.py:598-635,790-791`；历史只读：Employment 无 PUT/DELETE 接口 | **缺「证件检索 + SSC 人工确认」前置步骤**（直接传 `existing_person_id`），与文档「检索历史自然人 → SSC 确认」的必经流程不符 | P1 |
| 07:247 | SSC 可直接修改被授权的基础信息 | 已实现 | `extended_api.py:271-281`（PATCH /persons/{id}，需 PERSON_EDIT_BASIC） | 符合 | - |
| 07:248 | 每次修改记录修改前值、修改后值、操作者、时间、来源和原因 | 部分实现 | `extended_service.py:736-755`：`update_person` 的审计只写 `{"changed_fields": sorted(changes)}`（**字段名，不含值**）；对比 `personnel_service.py:98-126`（敏感档案审计也只存 masked_values） | **人员基础信息修改的审计缺「修改前值/修改后值」**，无法还原改了什么。建议：`update_person` 落 before/after 实际值（非敏感字段可明文，敏感字段走脱敏） | P1 |
| 07:249 | 核心雇佣、组织、职务和主体关系在界面上引导使用更正事件 | 与PRD冲突 | `apps/web/src/business/features/workforce/PeopleWorkspace.tsx:119-132`：「新建劳动关系 / 新增关系 / 新增主体版本」按钮直接调 `createEmployment` / `createAssignment` / `createLegalEntityRelation` 写当前结果 | 文档要求「界面引导使用更正事件」，实现是界面直接改当前结果且无引导文案——语义相反。建议：核心关系的变更入口改为「发起更正事件」，直接编辑入口收敛到有权限的 SSC 后台并加确认提示 | P1 |
| 07:250 | 第二阶段上线人事流程后，有流程的数据以流程结果为准 | 已实现 | `workflow/extended_service.py:1350-1363`（流程通过 → 置事件 ready → 执行写结果）、`:1592-1764`（写 Employment/EmploymentAssignment） | 符合 | - |
| 07:251 | 已生效记录允许按授权回退，但必须完整记录回退操作 | 部分实现 | 回退能力：`workflow/extended_service.py:2131-2234`（rollback_hr_event）、`:1824-1872`（合同回退）；检索词 `PERSON_.*ROLLBACK` 在 `apps/api/alembic/versions` **无命中**（权限仅 `PERSON_VIEW/EDIT_BASIC/SENSITIVE_VIEW/SENSITIVE_REVEAL/IMPORT/EXPORT`，见 `f1c000000001_personnel_record_foundation.py:144-149`） | 只有 hr_event/contract 走 HrEvent 回退；**被直接修改的雇佣/组织/主体关系没有回退通道**，且回退复用 `LIFECYCLE_ADMIN` 无独立权限 | P1 |
| 07:252 | 未来生效变更使用正式事件和有效期，不使用普通标签替代 | 已实现 | `workforce/models.py:950-989`（HrEvent + effective_date）；标签是独立实体 `models.py:351-379`（PersonLabel） | 符合 | - |
| 07:269 | 证件号码、银行账户等敏感字段加密存储 | 已实现 | `core/personnel_security.py:83-137`（AESGCM + key_version/nonce/ciphertext + AAD 绑定 field_code+record_id）；`workforce/models.py:418-422`（证件号四列）、`:451-455`（联系方式）、`:478-481`（地址）、`:502-510`（紧急联系人）、`:537-544`（教育）、`:570-577`（工作经历） | 符合 | - |
| 07:270 | 页面默认脱敏 | 已实现 | 每张敏感表都有 `masked_*` 列（`workforce/models.py:421,454,481,505,509,540,544,573,577,601`）；前端只渲染 masked 值 `PersonnelSubrecordsPanel.tsx:233,264,285,302,304,323,325,346,347,367` | 符合 | - |
| 07:271 | 明文查看、导出和打印独立授权 | 部分实现 | 明文：`apps/api/src/hris/modules/workforce/personnel_api.py:56-65`（需 PERSON_SENSITIVE_REVEAL）；导出权限码 PERSON_EXPORT（`f1c000000001_personnel_record_foundation.py:149`）；检索词「打印」在人员模块**无命中** | 无「打印」通道及其独立授权 | P2 |
| 07:272 | 每次明文访问记录人员、字段、操作者、时间和目的 | 已实现 | `personnel_service.py:904-911`（`_audit(action="reveal", person_id=..., fields=[field_code], reason=reason)`）+ `AuditLog`（`workforce/models.py:992-1009`，含 actor_id/occurred_at/reason/trace_id） | 符合 | - |
| 07:273 | 搜索、日志、缓存、错误信息和导出临时文件不得泄露明文 | 已实现 | 日志只存 masked：`personnel_service.py:98-126`；导出只含非敏感字段：`platform/master_data_export.py:117-135`（employee_number/legal_name/display_name/former_name）；错误信息不带明文：`core/personnel_security.py:24-26,123-137`（fail-closed 文案） | 符合 | - |
| 07:274 | 非生产环境使用脱敏数据 | 未实现 | `apps/api/src/hris/core/config.py:16` 有 `app_env: str = "development"`，但**没有任何按 app_env 分支的脱敏/合成数据逻辑**；检索词 `masking`/`synthetic`/`fake_data`/`seed` 在 `apps/api/src` 无命中 | 有环境标识但无脱敏数据机制，非生产环境可写真实证件/薪资。建议：加 `app_env != production` 时的写入拦截或种子数据策略 | P2 |
| 07:280-288 | 权限至少区分：查看基础信息、查看敏感信息、明文查看、修改基础信息、修改雇佣和组织结果、导入、导出、回退或更正、查看历史和审计 | 部分实现 | 已有：`PERSON_VIEW`/`PERSON_EDIT_BASIC`/`PERSON_SENSITIVE_VIEW`/`PERSON_SENSITIVE_REVEAL`/`PERSON_IMPORT`/`PERSON_EXPORT`（`f1c000000001_personnel_record_foundation.py:144-149`）+ `WORKFORCE_ADMIN`/`LIFECYCLE_ADMIN`/`ONBOARDING_INITIATE`（`f2b000000001_seed_onboarding_initiator_role.py:32`）；审计用 `DATA_GOVERNANCE_ADMIN`（`platform/audit_api.py:24-26`） | 九项里只独立了 6 项；「修改雇佣和组织结果」「回退或更正」「查看历史和审计」都并入通用管理码，无法按岗分权 | P1 |
| 07:290 | 数据范围需支持组织及全部下级、法人和未来 BP 服务范围；字段权限和数据范围必须同时通过才可访问 | 未实现 | 检索词 `data_scope` / `scope_filter` / `organization_scope` 在 `apps/api/src` 仅命中 `workforce/extended_service.py:1281`（`_organization_in_scope`，只服务编制统计内部）；人员读取 `extended_service.py:1106-1132`（list_persons）、`:1048-1104`（person_archive）**无任何范围过滤**；`platform/dependencies.py:56-98` 只有扁平权限码 + `*` 通配 | **人员列表与详情完全没有数据范围过滤**——任何持 PERSON_VIEW 者可见全量人员，这是本文档最严重的红线缺口。建议：引入 `DataScope`（组织子树/法人/BP 服务范围）并在人员查询统一套用 | P1 |
| 07:294-302 | 初始化导入顺序：字典与国家地区 → 法人/组织/成本中心/职务 → Person → Employment → 组织/汇报/主体关系 → 关联档案 | 部分实现 | 导入实体枚举：`platform/import_schemas.py:9-21`（dictionary / dictionary_item / organization_type / legal_entity / job_dimension(_version) / job(_version) / organization(_version) / person_basic）；person_basic 落库 `platform/import_service.py:2533-2548` | 导入框架完整（校验/幂等/逐行明细），但**只覆盖到 Person 基础层**：缺 Employment、组织/汇报/主体关系、关联档案四类导入，文档六步只走通前三步 | P1 |
| 07:305-313 | 导入校验至少包括：工号格式和唯一性、自然人重复候选、证件格式和重复、日期先后关系、主组织/职务和主体有效性、同类有效关系重叠、主组织唯一、四类主体各自唯一、枚举代码有效 | 部分实现 | 工号格式：`import_schemas.py:123` + `extended_service.py:694-698`；证件重复：`personnel_service.py:643-653`；主组织唯一：`extended_service.py:978-999`；日期先后：`import_schemas.py:115-119` 等 | 导入侧缺「自然人重复候选」「四类主体各自唯一」「同类有效关系重叠」「枚举代码有效」（person_basic 只有 4 个字段，天然无这些校验） | P1 |
| 07:315 | 系统不能在重复自然人无法可靠判断时自动合并 | 已实现 | 无任何 merge 合并接口（检索词 `merge` 在 `apps/api/src` 无命中）；`workflow/extended_service.py:546-556` 对已转换应聘直接 409 | 符合 | - |
| 07:321 | 按工号、姓名、证件脱敏值和联系方式搜索 | 部分实现 | `extended_service.py:1114-1119`：只对 `Person.display_name` 与 `Person.employee_number` 做 ilike | **不支持按证件脱敏值、联系方式检索**——而 `core/personnel_security.py:139-150` 的 HMAC digest 已具备精确检索能力，缺一个把它接到查询层的入口 | P1 |
| 07:322 | 按组织及全部下级、法人、人员类型和状态筛选 | 部分实现 | `extended_service.py:1120-1121`：只支持 `Person.status` 过滤 | 缺组织及下级、法人、人员类型三个筛选维度 | P1 |
| 07:323 | 查看自然人全部历史雇佣 | 已实现 | `extended_service.py:1048-1104`（person_archive 返回全部 employments，按 planned_start_date 倒序） | 符合 | - |
| 07:324 | 查看指定时点的组织、职务、主体和汇报结果 | 部分实现 | 主体时点：`extended_api.py:301-317`（`effective_at`）；职务时点：`:139-158`；汇报时点：`reporting_api.py:81-100`（`effective_at`）；组织时点：`organization_api.py:142-158`（`get_as_of`） | 各表分别支持时点，但**没有「某人某时点全量结果」的统一入口**，且 Person 级组织关系表无任何接口（见明细表「07:200-210」行），人员页拿不到时点组织 | P1 |
| 07:325 | 查看字段修改、事件和敏感访问记录 | 部分实现 | 审计 API：`apps/api/src/hris/modules/platform/audit_api.py:59-160`（列表/动作枚举/导出/详情）；敏感访问落 `action="reveal"`（`personnel_service.py:904-911`） | 有独立审计工作台 ✅，但**人员档案页没有入口串联**，审计对象维度靠 `object_type` 字符串区分，人员视角需自己拼参数 | P2 |
| 07:326 | 按权限导出人员档案 | 部分实现 | `platform/import_api.py:54-67` → `master_data_export.py:48-60,117-135`；仅 employee_number / legal_name / display_name / former_name | 导出**不含证件、联系方式、雇佣、组织关系**，也不按数据范围过滤（见明细表「07:328」行）。文档说「按权限导出人员档案」，当前只能导出基础四字段 | P1 |
| 07:328 | 所有列表和导出必须使用相同的数据范围与字段权限 | 未实现 | 列表：`extended_service.py:1106-1132`（无范围参数）；导出：`master_data_export.py:48-60`（`export(entity_type, as_of)` 无用户/范围入参，只按导出者是否有导出权限判定） | 列表与导出**两套口径**，都无法收窄到组织/法人范围。与明细表「07:290」行同源 | P1 |
| 07:332 | 验收点1：所有人员类型可以进入统一人员主数据 | 已实现 | `workforce/models.py:619`（employee_type_code 自由码）+ `extended_service.py:764-835` | 符合 | - |
| 07:333-334 | 验收点2-3：Person 和多次 Employment 可正确区分；待入职分配六位工号，二次入职恢复原号 | 已实现 | `extended_service.py:764`（新 Employment）、`:721-734`（分配）、`workflow/extended_service.py:598-635`（复用 Person 与工号） | 符合 | - |
| 07:335-337 | 验收点4-6：主组织唯一、其他组织关系可同时存在；四类主体分别保存、默认相同且允许不同；当前结果、有效期历史、快照和审计可以相互复核 | 部分实现 | 主组织唯一 `extended_service.py:978-999`；四主体 `models.py:626-641` + `EmploymentLegalEntityRelation`；快照 `extended_service.py:1440-1477`（只含组织×职务×人数 + evidence）；审计 `workforce/models.py:992-1009` | 快照**只固化了编制人数**，不含组织层级、四类主体、汇报关系、Person/Employment 状态，因此「快照↔当前结果↔审计」三方无法相互复核 | P1 |
| 07:338 | 验收点7：敏感字段默认脱敏，明文访问和导出受到独立控制 | 已实现 | 见明细表「07:269」「07:270」「07:271」「07:272」行；导出权限码 PERSON_EXPORT 独立于 PERSON_VIEW | 符合 | - |
| 07:339 | 验收点8：初始化导入发现重复或关系冲突时整批拒绝并返回明细 | 与PRD冲突 | `platform/import_service.py:481-645`：`execute_batch` 只执行 `row.status == "valid"` 的行，失败行单独置 `rejected`，最终 `batch.status = "completed_with_errors"`（`:643-645`） | **实现是「逐行部分成功」，文档要求「整批拒绝」**。这是语义冲突不是缺陷细节。建议：要么改文档为「按行隔离、整批可重试」，要么给初始化导入加 `atomic=true` 模式在有错误行时整体不落库 | P1 |

### 二、`08-人事数据与事件规范.md`（人事数据与事件规范）

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 08:13-20 | 目标：日常页面可快速读取当前有效结果；未来生效变更不提前污染当前数据；任一重要变化可解释；可查询指定时点状态；错误操作可按权限回退且留痕；第二阶段流程引擎驱动同一套人员结果 | 部分实现 | 当前结果 ✅ `workforce/extended_service.py:1048-1104`；未来生效不污染 ✅ `workflow/extended_service.py:1971-1973`（scheduled）；可解释 ✅ `workforce/models.py:966-980`（before/planned/actual）；回退 ✅ `workflow/extended_service.py:2131-2234`；流程驱动 ✅ `:1350-1363` | 五项达标；「可查询指定时点状态」只做到分表时点查询，无人员级统一时点视图（见明细表「08:154-163」行） | P1 |
| 08:40-48 | 分层模型与职责：当前结果 / 有效期历史 / 业务事件 / 快照 / 审计；审计日志不能替代业务历史，快照也不能替代事件 | 已实现 | 当前结果（Employment/EmploymentAssignment 主表列）、有效期历史（`EmploymentLegalEntityRelation` `workforce/models.py:645-688`）、事件（`HrEvent` `:950-989`）、快照（`SnapshotBatch`/`HeadcountSnapshot` `:868-918`）、审计（`AuditLog` `:992-1009`）五层各有独立模型与表 | 五层未互相覆盖，符合 | - |
| 08:54-61 | 第一阶段事件范围：组织新建/改名/换上级/合并/拆分/撤销、组织负责人和 BP 关系变化、成本中心分摊版本变化、收入目标调整、人员基础档案更正、雇佣当前结果更正、员工组织/职务/汇报/四类主体的未来生效变更、事件取消和回退 | 部分实现 | 组织类事件独立为 `OrganizationEvent`（`workforce/organization_models.py:23-44`），event_type 实测：CREATE、VERSION_CHANGE、LEGAL_ENTITY_SET、LEADER_SET、BP_MEMBERSHIP_CREATE、BP_SCOPE_SET、COST_ALLOCATION_SET、REVENUE_TARGET_SET（`organization_service.py:242,369,749,858,976,1087,1370,1550`）；取消 `organization_api.py:198-210` | **组织类事件未并入统一 HrEvent 模型**，且**「合并/拆分」事件类型不存在**（检索词 `"merge"` / `"split"` 在 `apps/api/src` 无命中），文档第一阶段事件范围未走完 | P1 |
| 08:63 | 第一阶段不要求为以上所有事件建设审批流，但数据模型必须保留发起、审批和来源标识 | 部分实现 | HrEvent 有 `source` 与 `workflow_instance_id`（`workforce/models.py:964,981`）；OrganizationEvent **无发起人、无审批挂载、无 source**（`organization_models.py:23-44`） | 组织类事件不满足该红线。建议：OrganizationEvent 补 `initiator_id`/`source`/`workflow_instance_id`，或直接收敛到 HrEvent 统一模型 | P1 |
| 08:67-76 | 第二阶段扩展：入职、转正、调动、兼岗、借调、离职、合同与协议变化、流程撤回、驳回和重新提交 | 部分实现 | 9 类人事事件 ✅ `workflow/extended_service.py:1370-1380`；4 类合同动作 ✅ `:1381-1386`；驳回 ✅ `:1324-1330` | **「流程撤回」与「重新提交」未实现**——检索词 `resubmit` / `send_back` / `withdraw_workflow` 在 `apps` 目录**全仓无命中**；前端也无相应入口（`apps/web/src/business/features/lifecycle/WorkflowPanel.tsx:136-139` 只有通过/驳回） | P1 |
| 08:80-96 | 通用事件字段至少包含：事件编号、事件类型、业务对象类型和标识、发起人、发起时间和来源、生效日期、当前状态、变更原因、变更前结果、计划变更后结果、实际执行结果、字段差异、关联流程编号、关联原事件或回退事件、执行次数、最后错误和执行时间、并发版本 | 部分实现 | HrEvent 字段对照 `workforce/models.py:950-989`：event_number ✅、event_type ✅、object_type/object_id ✅、effective_date ✅、status ✅、reason ✅、before/planned/actual_payload ✅、workflow_instance_id ✅、related_event_id ✅、attempts/last_error/executed_at ✅、version ✅ | **缺「发起人」**：HrEvent 无 initiator 字段，source 被写死为 `"api"`（`workflow/extended_service.py:2103`）或 `"rollback"`（`:2215`），无法回答「谁发起」；**缺「字段差异」**：只有三份 payload，无 diff 结构/接口；**「并发版本」只是行 version**，不是乐观锁令牌 | P1 |
| 08:98 | 快照结构可以按领域实现，但必须能够明确还原关键字段差异 | 部分实现 | `workforce/models.py:918`（HeadcountSnapshot.evidence）与 `extended_service.py:1470-1473`（只写 `{as_of, rule_version}`） | 快照无法还原任何关键字段差异 | P1 |
| 08:104-111 | 第一阶段基础事件状态机：草稿 → 待生效 → 已生效 →（已取消 / 执行失败）；已生效 → 回退处理中 → 已回退 →（回退失败） | 部分实现 | HrEvent.status 实际取值：`pending_approval`（`workflow/extended_service.py:2102`）、`ready`、`scheduled`（`:1972`）、`completed`（`:1990`）、`failed`（`:2065`）、`rejected`（`:1361`） | **缺「草稿」「已取消」「回退处理中」「已回退」「回退失败」五个状态**。回退复用 `completed`/`failed`，无法区分「回退成功」与「原事件成功」，也没有事件取消接口 | P1 |
| 08:113-119 | 若事件需要审批，可在第二阶段扩展：草稿 → 审批中 → 已通过待生效 → 已生效 →（已驳回 / 已撤回） | 部分实现 | `pending_approval`（审批中）✅、`ready`（已通过待生效）✅、`completed`（已生效）✅、`rejected`（已驳回）✅ | 缺「已撤回」状态（无撤回接口） | P1 |
| 08:121 | 具体事件可裁剪不适用状态，但状态代码、转换条件和权限必须明确 | 部分实现 | 状态在 UI 直接显示英文码（`apps/web/src/business/features/lifecycle/HrEventPanel.tsx:204`、`:22` 仅按 failed/rejected 上色）；转换条件写在代码里没有成文表 | 无状态码字典与前端中文映射，转换条件/权限未成文 | P2 |
| 08:125 | 事件必须有明确生效日期 | 已实现 | `workforce/models.py:962`（`effective_date` NOT NULL）；`workflow/extended_schemas.py:356` | 符合 | - |
| 08:126 | 即时事件通过同一事务提交事件和当前结果 | 已实现 | `workflow/extended_service.py:2112-2115`（同一 session 内 add + flush + `_execute_hr_event_if_due`） | 符合 | - |
| 08:127 | 未来事件在生效日前只显示为待生效 | 已实现 | `workflow/extended_service.py:1971-1973`（effective_date > today → status=scheduled 不执行）；`:2114`（approval 模式不立即执行） | 符合 | - |
| 08:128 | 生效时重新校验业务规则，不能只相信发起时校验 | 已实现 | 发起时 `_validate_hr_event`（`:1369-1560`）；执行时二次校验：ONBOARDING 状态 `:1620-1625`、职务生效性 `:1710`、合同状态与日期 `:1478-1489` | 符合 | - |
| 08:129 | 生效任务必须支持幂等和安全重试 | 已实现 | 状态机保证 completed 不被重复捞起（`:1974`、`:2048`）；failed 可重试并累加 attempts（`:2056-2068`）；幂等键 + 请求校验和 `workforce/models.py:957-958` | 符合 | - |
| 08:130 | 事件失败不得留下部分更新结果 | 已实现 | `workflow/extended_service.py:2058-2061`（`begin_nested()` 保存点，异常回滚子事务） | 符合 | - |
| 08:131 | 同一对象多个未来事件发生冲突时，不允许静默覆盖 | 部分实现 | 仅 ONBOARDING 有并发检查：`workflow/extended_service.py:1412-1425`（`ONBOARDING_EVENT_ALREADY_OPEN`，状态集合 pending_approval/ready/scheduled/failed） | **TRANSFER / CONCURRENT_ASSIGNMENT / SECONDMENT / TERMINATION 无冲突检测**，同一雇佣可挂多个未来调动并先后生效，后一条会覆盖前一条。建议：为 employment 维度的未来事件加唯一开放事件校验 | P1 |
| 08:132 | 对当前结果的更新需要并发控制 | 部分实现 | `Employment.version` / `EmploymentAssignment.version` 会递增（`workflow/extended_service.py:1658`、`:1737-1744`）；只有**合同回退**比对版本（`:2173-2179` `CONTRACT_ROLLBACK_NOT_LATEST`） | **事件不带 expected_version，执行时不比较并发变更**——发起后若他人改了同一雇佣，执行时直接覆盖。建议：HrEvent 增 `expected_version`（发起时读当前版本），执行时不匹配即报并发冲突 | P1 |
| 08:133 | 生效后记录实际差异、执行时间和执行版本 | 已实现 | `workflow/extended_service.py:1989-1993`（actual_payload、status=completed、attempts+1、last_error=None、executed_at）；版本随 payload 返回 `:1666` | 符合 | - |
| 08:135 | 界面只展示当前有效组织树和人员结果；组织未来事件在对应组织详情中按生效日期查看，不建设独立的待生效组织事件页面 | 已实现 | `workforce/organization_api.py:128-140`（当前树）、`:160-178`（变更事件列表）；`apps/web/src/business/features/organization/OrganizationDetailWorkspace.tsx` 按生效日期展示 | 符合 | P2 |
| 08:141-150 | 当前结果包括：当前雇佣状态、当前主组织和主职务、当前其他组织关系、当前实线和虚线汇报、当前四类主体、当前组织负责人和 BP 关系 | 部分实现 | 对应表全部存在（Employment/EmploymentAssignment/ReportingRelation/EmploymentLegalEntityRelation/OrganizationLeader/PersonBpMembership） | 各表都有当前值，但**没有「当前结果统一读取投影」**——`person_archive`（`workforce/extended_service.py:1048-1104`）返回全部历史而非当前投影，前端需自行判断哪条是当前 | P2 |
| 08:154-163 | 时点查询：查询当前状态；查询全部历史事件；查询字段变更时间线；查询指定日期的组织、职务、主体和状态；对比两个时间点的差异；从月度快照进入明细复核 | 部分实现 | 当前状态 ✅；历史事件 ✅ `workflow/extended_service.py:2005-2031`；指定日期的主体/职务/汇报 ✅（`workforce/extended_api.py:301-317,139-158`、`reporting_api.py:81-100`） | **缺「字段变更时间线」「对比两个时间点的差异」「从月度快照进入明细复核」**——检索词 `timeline` / `/diff` 在 `apps/api/src` **无命中** | P1 |
| 08:163 | 时点查询结果必须标明数据来源和有效期，避免把快照、实时重建和当前结果混为一谈 | 部分实现 | 返回体带 `effective_from`/`effective_to`（`workforce/extended_schemas.py:276-287`）与 `evidence.as_of`（`workforce/extended_service.py:1471`） | **没有统一的「来源类型」标记**（快照 / 实时重建 / 当前结果），调用方无法区分 | P2 |
| 08:167-169 | 基础档案可以由授权 SSC 按生效日期维护结果；每次修改均记录前后内容；系统界面引导核心人事关系使用更正事件 | 部分实现 | PATCH `/persons/{id}` ✅（`workforce/extended_api.py:271-281`）；审计前后值 ✗（见明细表「07:248」行）；界面引导 ✗（见明细表「08:169」行） | 「按生效日期维护结果」未实现——`Person` 更新没有 effective_from/effective_to，直接覆盖当前行 | P1 |
| 08:169 | 系统界面引导核心人事关系使用更正事件 | 与PRD冲突 | `apps/web/src/business/features/workforce/PeopleWorkspace.tsx:119-132,334-345`（「建立劳动关系」「新增关系」「新增主体版本」直接写当前结果） | 同明细表「07:249」行：界面行为与文档要求相反 | P1 |
| 08:170-171 | 第一阶段不强制所有信息修改都经过流程；第二阶段存在人事流程时，以已完成流程生成的事件为准 | 已实现 | `workflow/extended_service.py:1350-1363`（流程完成才执行事件写当前结果） | 符合 | - |
| 08:172 | 流程处理中不得通过普通编辑无痕改变同一字段 | 部分实现 | 只有 ONBOARDING 有开放事件检查（`workflow/extended_service.py:1412-1425`）；普通接口 `workforce/extended_api.py:271-281`（PATCH Person）、`:292-298`（建 Employment）、`:339-352`（建关系）**都不检查该雇佣是否处于流程中** | 流程审批期间仍可绕过事件直接改同一雇佣/关系，改动无痕。建议：写路径统一检查目标对象的开放事件 | P1 |
| 08:173 | 紧急更正需要独立权限、原因和审计 | 部分实现 | 原因必填 ✅（`workforce/extended_schemas.py:219` change_reason；`personnel_schemas.py` 各 Update 均带 change_reason）；审计 ✅；独立权限 ✗（检索词 `EMERGENCY` / `CORRECTION` 权限码在 `apps/api/alembic/versions` **无命中**） | 「紧急更正」与普通编辑共用 PERSON_EDIT_BASIC / WORKFORCE_ADMIN，无法单独授权与单独审计 | P1 |
| 08:177-187 | 回退要求：回退前校验当前结果是否仍由目标事件产生；已被后续事件覆盖时不能强行覆盖；回退必须记录目标事件、原因、操作者和影响范围；回退失败不能产生部分状态；回退后仍保留原事件和原审计；已同步下游时回退生成新的业务记录和出站同步记录并关联原记录再同步、不修改原同步历史；回退属于高风险独立权限 | 部分实现 | 新事件 + related_event_id 保留原事件 ✅ `workflow/extended_service.py:2206-2223`；合同版本冲突拒绝 ✅ `:2173-2179`；失败不部分状态 ✅ `:2058-2061`；操作日志 ✅ `:2228-2233` | **无出站同步记录机制**（检索词 `outbound` / `webhook` / `sync` 在 `apps/api/src/hris` 无命中），「已同步下游」的分支逻辑无处落地；**回退无独立权限码**（并入 LIFECYCLE_ADMIN）；**「影响范围」未建模**（rollback payload 只有 reason + effective_date） | P1 |
| 08:191-194 | 回退执行方式：直接生效（立即执行）；审批生效（通过回退审批后执行，驳回或撤回不改变当前结果）；回退审批是受控领域动作，第二阶段可由通用流程引擎接管；未注册回退策略或影响范围无法确定时默认拒绝自动回退 | 部分实现 | `execution_mode: direct/approval` ✅（`workflow/extended_schemas.py:374`）；走 hr_event 审批链路 ✅（`:2102`、`:2214` + `:1085-1091` 挂 workflow_instance） | **没有「回退策略注册表」**，所有事件类型共用一条 rollback 路径；**没有「影响范围无法确定时拒绝自动回退」的显式判定**——文档第 194 行的兜底拒绝语义缺实现 | P1 |
| 08:196-202 | 回退策略支持三种方式并按事件类型组合：从历史版本或快照生成新的恢复结果、创建补偿事件并生成新的结果版本、组合使用；无论采用哪种方式都必须生成新记录，满足可追溯、可重试且不破坏后续历史；存在后续事件时必须先校验事件链，不能直接覆盖 | 部分实现 | 统一生成新 HrEvent + related_event_id ✅（`workflow/extended_service.py:2206-2223`）；合同侧快照恢复 + 取消后继 ✅ `:1824-1872`；事件链校验 ✅（合同 version 比对 `:1817-1823`） | **策略只有一种实现**（恢复前值 + 补偿），没有按事件类型的策略选择与组合；雇佣/组织关系类回退只写 `planned_payload` 原样回填（`:1617-1618`），不等于「从快照恢复」 | P1 |
| 08:208-211 | 系统自动生成月初快照和月末快照；月份边界按快照策略配置的时区计算，不使用服务器本地时区隐式判断；每个快照批次保存所用时区、边界时刻和规则版本；授权管理员可以补跑或生成修订版本 | 部分实现 | SnapshotBatch 存 timezone/boundary_at/rule_version/parent_batch_id/version/status ✅（`workforce/models.py:868-888`）；边界一致性校验 ✅ `extended_service.py:1378-1397`；修订需关联父批次 ✅ `:1416-1430`；幂等 ✅ `:1407-1415` | **无自动生成调度**——检索词 `APScheduler` / `BackgroundScheduler` / `cron` / `scheduler` / `startup` 在 `apps/api/src` **无命中**；只能人工调 `POST /api/v1/workforce/headcount-snapshots`（`extended_api.py:480-493`）。「自动生成」这条红线未满足 | P1 |
| 08:217-223 | 快照内容至少包含：组织和层级、组织与法人和成本中心关系、收入目标、月度编制和人数结果、Person 与 Employment 关键状态、员工组织职务主体和汇报关系、使用的规则版本 | 部分实现 | 只生成 `HeadcountSnapshot`（组织×职务×人数 + evidence{as_of, rule_version}）：`workforce/extended_service.py:1458-1477`；`models.py:891-918` | **七项里只有「月度编制和人数结果」与「规则版本」两项**，缺组织层级、法人/成本中心关系、收入目标、Person/Employment 状态、组织职务主体汇报关系 | P1 |
| 08:227-231 | 快照不可由普通用户直接修改；错误数据先更正业务数据再创建快照修订版本；修订不覆盖原快照；每个版本记录原因、生成批次、操作者和统计范围；快照任务可重试且幂等 | 已实现 | 无快照更新/删除接口；version 递增 + parent_batch_id 关联不覆盖原批次（`extended_service.py:1416-1445`）；幂等返回同一批次（`:1407-1415`）；reason 落库（`models.py:888`） | 「统计范围」未单独记录（隐含在快照行的 organization/job 上） | P2 |
| 08:233-239 | 月结后修订流程：保留原始月初月末快照并保持只读 → 更正源业务数据 → 授权用户生成与原快照关联的修订版本 → 记录原因、操作者、差异和版本关系 → 复核后重新冻结修订版本 | 部分实现 | 修订版本 + parent_batch_id + reason ✅（`extended_service.py:1416-1445`） | **缺「差异」记录**（新版本与父版本的字段差异未落库），「复核后重新冻结」无冻结状态（快照 status 只有 running/completed） | P2 |
| 08:245-252 | 领域联动六项：待入职日期或人员类型变化→更新适用月份人员统计；主组织或职务生效→更新当前归属和后续统计；离职或入职撤回生效→按生效日期释放相关人数；法人主体变化→更新人员主体结果；组织换上级生效→更新当前组织树不改写历史快照；占编规则变化→记录规则版本，影响生效日期后的统计 | 部分实现 | 人数按 as_of 重算 ✅ `extended_service.py:1343-1372`；组织换上级走 OrganizationEvent → OrganizationVersion ✅ `organization_service.py:367-371`；占编规则生效期 ✅ `models.py:835-849` | 联动**没有显式的「领域变更通知」记录**（文档第 254 行要求「通过明确应用服务或可靠消息记录实现」）；「占编规则变化记录规则版本」目前只是快照批次上的一个自由字符串 `rule_version`，没有规则版本实体 | P2 |
| 08:254 | 系统内部联动应通过明确应用服务或可靠消息记录实现；第一阶段不建设通用事件总线平台 | 已实现 | 全部走 service 层直接调用，无事件总线（检索词 `bus` / `message_queue` 在 `apps/api/src` 无命中） | 符合 | - |
| 08:262-267 | 第一阶段需要预留：稳定业务对象标识、版本化API、变更事件编号、幂等键、同步状态和错误记录、可重试的出站消息表或等效机制 | 部分实现 | 业务对象标识 ✅；版本化 API ✅（`/api/v1`，`core/config.py:17`）；变更事件编号 ✅ `event_number`；幂等键 ✅ `idempotency_key` | **缺「同步状态和错误记录」与「可重试的出站消息表或等效机制」**——全仓无 outbound 表/模型/服务 | P1 |
| 08:269 | 在接口资料确认前，不实现猜测性的字段映射和自动同步 | 已实现 | 无任何下游映射/同步代码 | 符合 | - |
| 08:273-281 | 独立权限至少包括：创建和修改草稿事件、取消待生效事件、紧急更正、回退已生效事件、补跑或修订快照、查看事件前后值、查看敏感字段差异 | 部分实现 | 只有 `LIFECYCLE_ADMIN` + `ONBOARDING_INITIATE`（`workflow/extended_api.py:59-61`）+ `PERSON_SENSITIVE_REVEAL`；快照接口走 WORKFORCE_ADMIN（`workforce/extended_api.py:485-493`） | **七项里没有一项有独立权限码**；「取消待生效事件」连接口都没有 | P1 |
| 08:285-289 | 审计至少记录：事件创建、提交、审批、执行、取消和回退；自动任务及重试；当前结果的直接更正；快照生成和修订；下游初始同步、回退新记录的再次同步及失败补偿 | 部分实现 | 创建 ✅ `workflow/extended_service.py:2116-2128`；执行 ✅ `:1995-2002`；回退 ✅ `:2228-2233`；审批决定 ✅ `:1342-1347`；发布 ✅ `:1040-1045`；快照生成 ✅ `workforce/extended_service.py:1480-1492` | **缺「事件提交」「事件取消」审计**（HrEvent 无提交/取消接口，审计动作只有 create/execute/rollback_requested）；**缺下游同步相关审计** | P1 |
| 08:293-299 | 异常与补偿：生效时引用对象无效→事件失败并给出业务错误不部分执行；当前版本已变化→标记并发冲突要求重新确认；多事件有效期冲突→阻止后一个事件生效；自动任务中断→使用幂等键重试；下游同步失败→本地事务不回滚按新记录幂等键重试仍失败转人工补偿；快照部分失败→整批不发布为成功版本；回退影响范围无法确定→禁止自动回退转人工 | 部分实现 | 引用对象无效 ✅（`workflow/extended_service.py:1394-1404,1471-1477,1703-1704`）；幂等重试 ✅（`:2056-2068`）；快照整批事务 ✅（`workforce/extended_service.py:1440-1479` 同一事务） | **缺「当前版本已变化→并发冲突」**（无 expected_version）；**缺「多事件有效期冲突→阻止后一个生效」**（仅 ONBOARDING 有）；**缺「回退影响范围无法确定→禁止自动回退」**；下游同步失败分支因无出站机制而无实现 | P1 |
| 08:303-309 | 第一阶段验收要点七条：未来事件生效前不改变当前结果；到达生效日期后结果只应用一次、失败可安全重试；可查看事件前后值、字段差异和完整操作记录；可查询指定时点关键人员关系；已生效事件具备受控回退能力且原历史不被删除；月初月末快照可复核、补跑和修订；事件、当前结果、快照和审计之间可以相互关联 | 部分实现 | 验收1 ✅（`:1971-1973`）；验收2 ✅（`:1974,2048,2056-2068`）；验收3 部分（前后值 ✅、**字段差异 ✗**）；验收4 部分（分表时点 ✅、**统一时点/差异对比 ✗**）；验收5 ✅（`:2159-2160` 要求 completed 才可回退，原事件保留 `:2220`）；验收6 部分（补跑/修订 ✅、**自动生成 ✗**、快照内容不足）；验收7 部分（事件↔审计 ✅、**事件↔快照 ✗**） | 七条里 2 条全通、5 条部分通；核心短板是「字段差异」与「快照覆盖面」 | P1 |

### 三、`12-第二阶段需求规格.md`（第二阶段需求规格）

| 文档条款（文件:行） | 要求摘要 | 判定 | 实现证据（文件:行）/ 检索词 | 差异与修复建议 | 优先级 |
|---|---|---|---|---|---|
| 12:3（状态） | 文件状态为 `MIGRATION_INPUT / PARTIAL / ENTERPRISE_INPUT_PENDING`；通用工程能力已实现，未确认的企业流程不得被本文件或当前代码推定为正式规则 | 待企业输入 | 文档头部 `12-第二阶段需求规格.md:3`；`docs/01-foundation/00-正式文档目录.md` 已把 07/08/12 标为迁移输入 | 文档自身声明「不再单独构成开发批准」「不得绕过 17 号规范」。**本分片所有「实现」结论只描述代码现状，不代表企业规则已确认**；建议按 `17` 号规范为 07/08/12 建立正式功能文档后再做验收级对账 | P1 |
| 12:17-25 | 第二阶段目标：管理候选人/应聘/Offer/转待入职；配置并发布人事流程并处理会签、或签、条件分支；通过人事事件执行入职转正调动兼岗借调离职撤回更正；按场景选择直接生效、审批生效和未来生效；对已生效业务执行受控回退；管理劳动合同和其他协议的建档变更续签解除取消与到期提醒；保留流程实例、审批任务、业务结果、同步记录和审计之间的完整链路 | 部分实现 | 候选人/应聘/Offer ✅ `workflow/extended_service.py:102-472`；会签或签条件分支 ✅ `workflow/schemas.py:62,11-45` + `workflow/extended_service.py:1245-1276`；9 类人事事件 ✅ `:1370-1380`；三种生效方式 ✅ `workflow/extended_schemas.py:357`（direct/approval）+ `effective_date`；回退 ✅ `:2131-2234`；合同四动作 ✅ `:916-947` | **「流程撤回」「同步记录」两项未达成**：撤回无接口无状态（检索词 `withdraw_workflow` 在 `apps` 无命中）；同步记录无任何模型（见明细表「08:262-267」行） | P1 |
| 12:31-36 | 状态口径四值：CONFIRMED / IMPLEMENTED_GENERIC / PENDING_ENTERPRISE_INPUT / DEFERRED | 已实现 | 文档自身定义，代码侧对应关系已在下表逐条标注 | 口径本身无实现要求 | - |
| 12:42-51 | 纳入范围八域：流程定义、流程运行、应聘管理、人事事件、生效机制、回退、合同/协议、流程数据 | 部分实现 | 流程定义 ✅ `workflow/service.py:42-171`；流程运行 ✅ `workflow/extended_service.py:1048-1348`；应聘 ✅ `:360-472`；人事事件 ✅ `:1370-1380`；生效机制 ✅ `:1969-2069`；回退 ✅ `:2131-2234`；合同 ✅ `:755-1019` | 「流程数据」域里的「下游同步链路」缺失 | P1 |
| 12:55-61 | 不纳入范围：招聘门户与外部候选人自助、员工自助发起人事流程、薪酬社保个税费用计算、电子签章与附件对象存储最终实现、下游连接器正式接入、任意脚本节点/SQL条件/无代码表单引擎、多租户多语言多数据库兼容 | 已实现 | 无招聘门户模块；无员工自助入口（`apps/web/src/business/features/` 无 employee 自助目录）；无签章/附件存储；无脚本节点（`workflow/schemas.py:11-45` 条件为结构化 path+operator+value）；无多租户 | 符合 | - |
| 12:77 | 组织、职务、法人和 Person 以第一阶段稳定 ID 为准 | 已实现 | `workforce/models.py` 全表外键指向 organizations/job_catalog/legal_entities/persons；`workflow/extended_service.py:1701-1710` 校验目标组织与职务存在且生效 | 符合 | - |
| 12:78 | Offer 确认不是入职生效；它只创建或复用待入职档案 | 已实现 | `workflow/extended_service.py:658-670`（建 pending_start Employment，status 在 `workforce/extended_service.py:822` 固定为 pending_start）；入职要另发 ONBOARDING 事件 | 符合 | - |
| 12:79 | 人事流程改变第一阶段当前结果时，必须通过领域事件服务写入，不得由流程引擎直接更新任意表 | 已实现 | 流程结束只改 HrEvent.status：`workflow/extended_service.py:1350-1363`；真正写结果由 `_execute_hr_event_if_due`（`:1969-2003`）→ `_execute_employment_event` / `_execute_assignment_event` / `_execute_contract_event` | 引擎不直接写业务表，符合 | - |
| 12:80 | 第三阶段考勤只读取已生效的劳动关系、任职和人事事件结果 | 已实现 | `apps/api/src/hris/modules/attendance/` 不写 Employment/Assignment，只读 | 符合 | - |
| 12:86 `P2-FLOW-001` | 流程定义使用稳定代码，包含名称、业务类别、状态和当前发布版本 | 已实现 | `workflow/models.py:22-30`（code/name/category/status/active_version，code unique） | 符合 | - |
| 12:87 `P2-FLOW-002` | 修改已发布流程时创建新版本，不原地覆盖运行中实例引用的版本 | 未实现 | 检索词 `WorkflowVersion(` 在 `apps/api/src` **仅命中 `workflow/service.py:154`**，且固定 `version=1`；`workflow/api.py` 只暴露 `POST /workflows/definitions`（创建）与两个 GET，**无创建新版本接口**；`workflow/extended_service.py:1021-1046`（publish）直接把当前最高版本置 active | **已发布流程无法演进**，active_version 永远只能是 1。这是流程引擎的结构性缺口：条件分支、审批节点变更全部无从落地。建议：新增 `POST /workflows/{id}/versions`（复用 create_definition 的图校验）+ publish 切版本 | P1 |
| 12:88 `P2-FLOW-003` | 节点类型限制为开始、审批、受控动作和结束；当前一个版本恰有一个开始节点和一个结束节点 | 已实现 | `workflow/schemas.py:61`（`Literal["start","approval","action","end"]`）；`workflow/service.py:78-85`（`WORKFLOW_BOUNDARY_COUNT_INVALID` 要求恰好 1 start + 1 end） | 类型限制与边界校验均已落地 | - |
| 12:88 `P2-FLOW-003`（受控动作语义） | 「受控动作」节点应有受控的执行语义 | 部分实现 | `workflow/extended_service.py:1204-1226`：`_advance_workflow` 只识别 `end` 与 `approval`，`action` 节点被**直接穿过**（`current_code = next_code`），不执行任何动作、不产生任务 | 节点类型允许 `action`，但引擎对它没有任何受控执行语义——配了 action 节点等于静默跳过。建议：要么实现受控动作（白名单动作类型 + 幂等执行 + 审计），要么先从 `Literal` 里去掉 action | P2 |
| 12:89 `P2-FLOW-004` | 发布前校验缺失节点、断线、歧义条件、无默认线及其他无效图结构 | 部分实现 | 校验**全在创建时**做（`workflow/service.py:58-141`：节点码重复、悬空边、起止计数、重复边、起点入线、终点出线、重复默认线、重复条件、环路、不可达节点）；`workflow/extended_service.py:1021-1036`（publish）**只检查 start/end 是否存在** | 校验时点错位（文档要求「发布前」）+ publish 不复用校验。后果是 P2-FLOW-002 一旦实现（新增版本）就会绕过全部图校验。建议：把 `service.py:58-141` 抽成 `_validate_graph()`，创建与发布各调一次 | P1 |
| 12:90 `P2-FLOW-005` | 审批节点同时支持会签 `all` 和或签 `any` | 已实现 | `workflow/schemas.py:62`（`sign_mode: Literal["all","any"]`）、`:65-71`（非审批节点不得配 sign_mode/assignees）；`workflow/extended_service.py:1216`（落任务）、`:1333-1336`（any 时取消兄弟任务）；前端 `apps/web/src/business/features/lifecycle/WorkflowPanel.tsx:199` | 会签=全部 pending 完才推进、或签=一人通过即取消其余，符合 | - |
| 12:91 `P2-FLOW-006` | 条件使用结构化字段路径、运算符和值，不执行 SQL、脚本或函数 | 已实现 | `workflow/schemas.py:11-45`（path 正则 `^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*){0,7}$`、operator 枚举 10 个、value 标量/列表）；`workflow/conditions.py:40-101`（纯结构化求值，无 eval） | 符合。补充：实测算子为 **10 个**（eq/ne/gt/gte/lt/lte/in/not_in/exists/not_exists），比任务简报里的「9 算子」多一个 not_exists | - |
| 12:92 `P2-FLOW-007` | 条件分支最多命中一条；无命中时走唯一默认线；多条命中时失败关闭 | 已实现 | `workflow/extended_service.py:1245-1276`：`WORKFLOW_ROUTE_AMBIGUOUS`（多条命中→422 失败关闭）、`WORKFLOW_ROUTE_NOT_MATCHED`（无命中且无唯一默认线→422）；默认线唯一性在创建时校验 `workflow/service.py:104-110` | 符合 | - |
| 12:93 `P2-FLOW-008` | 流程实例固定引用启动时的发布版本，并保留选路历史 | 已实现 | `workflow/extended_service.py:1052-1060`（按 active_version 取 active 版本）→ `:1072-1074` 固定 `workflow_version_id`；选路历史写入 `context._workflow_route_history`（`:1229-1237`），且 `workflow/extended_schemas.py:431-435` 保护用户不能伪造 `_workflow_` 前缀键 | 符合（选路历史存在 context JSON 里，无独立查询接口） | P2 |
| 12:94 `P2-FLOW-009` | 审批任务记录节点、办理人引用、决定、意见、实际办理人和时间 | 已实现 | `workflow/models.py:77-94`（node_code/assignee_type/assignee_ref/status/decision/comment/decided_by/decided_at）；`workflow/extended_service.py:1308-1312` 落 decided_by=self._actor_id、decided_at | 符合 | - |
| 12:95 `P2-FLOW-010` | 动态办理人必须从已确认的组织、负责人、BP 或角色关系解析，并定义缺失时的兜底角色 | 待企业输入 | `workflow/schemas.py:54` 允许 `assignee_type: "expression"`，但检索词 `expression` 在 `apps/api/src` **只命中 schemas.py:54 这一处**——引擎从不做解析（`workflow/extended_service.py:1204-1223` 原样落库 assignee_ref） | 文档已标 PENDING_ENTERPRISE_INPUT ✅。**但当前实现有隐患**：允许提交 `expression` 类型的办理人却从不解析，会生成永远无人可办的任务且不报错。建议：在企业输入到位前，先把 `expression` 从 schema 枚举中移除或直接拒绝（fail-closed），符合 `12:179`「未知办理人表达式默认拒绝」 | P1 |
| 12:96 `P2-FLOW-011` | 任务只能由实际办理人、有效代理人或授权管理员处理；当前主管理员通用操作不代表最终权限模型 | 待企业输入 | `workflow/extended_service.py:1289-1348`（decide_workflow_task）：**完全不校验 actor 与 task.assignee_ref 的关系**，任何持 LIFECYCLE_ADMIN 者可办理任意任务；前端 `WorkflowPanel.tsx:136` 也只按 `canAdmin` 显示按钮 | 文档已标 PENDING_ENTERPRISE_INPUT ✅，且已自陈「当前主管理员通用操作不代表最终权限模型」。**但这正是 `12:214`（完成定义第 5 条）不满足的根因**。建议：企业输入到位前，至少加一条「assignee_ref 匹配 actor 或该 actor 持有对应角色」的最小校验 | P1 |
| 12:97 `P2-FLOW-012` | 撤回、重新提交、转办、加签、减签、超时、催办和升级按流程逐项确认 | 待企业输入 | 检索词 `resubmit` / `send_back` / `withdraw_workflow` / `timeout` / `escalate` 在 `apps` 目录**全仓无命中**；`workflow/extended_schemas.py:489-491`（`decision: Literal["approve","reject"]`）是唯一的任务动作 | 文档已标 PENDING_ENTERPRISE_INPUT ✅。**产品已明确审批动作三义语义**（撤销=终止、驳回=终止、退回=回到上一节点），三者互不等价，因此「撤销」「退回」不应与「转办/加签/超时」一起等到企业输入再定。建议：先落「撤销（终止）」与「退回（回到上一节点）」两个动作并补状态机 | P1 |
| 12:99 | 当前流程不支持两条独立业务支线并行后汇合；节点内多人会签不等于并行流程 | 已实现 | `workflow/service.py:124-141`（环路检测 + 不可达检测）；`workflow/extended_service.py:1172-1226`（单链推进，`while` 循环一次只走一条线）；会签只产生同节点多个任务（`:1211-1223`） | 符合 | - |
| 12:105 `P2-REC-001` | 候选人具有独立编号、展示名称、通用联系方式载荷、状态和可选 Person 关联；当前载荷未形成企业敏感字段合同 | 已实现 | `workflow/models.py:97-115`（candidate_number unique、display_name、contact_payload JSON、status、linked_person_id）；编号生成 `workflow/extended_service.py:102-129` | 符合 | - |
| 12:106 `P2-REC-002` | 一个候选人可以对不同招聘需求产生应聘记录；同一候选人和同一需求不得重复建档 | 已实现 | `workflow/models.py:120-122`（`UniqueConstraint("candidate_id","recruitment_request_id")`） | 符合 | - |
| 12:107 `P2-REC-003` | 应聘记录保存当前阶段、状态和 Offer 结构化信息 | 已实现 | `workflow/models.py:118-142`（status/current_stage/offer_payload JSON） | 符合 | - |
| 12:108 `P2-REC-004` | 招聘需求与编制保持弱关联，录用转换不因无空编被阻断 | 已实现 | `workflow/extended_service.py:514-753`（hire_application）全程不查 HeadcountPlan；只校验 recruitment.status != cancelled（`:591-596`） | 符合 | - |
| 12:109 `P2-REC-005` | 普通状态修改不得直接把应聘标记为已录用；必须执行显式 Offer 确认/录用转换命令 | 已实现 | `workflow/extended_service.py:445-453`（`APPLICATION_HIRE_COMMAND_REQUIRED`） | 符合 | - |
| 12:110 `P2-REC-006` | 录用转换在同一事务中创建或复用 Person、六位工号、待入职 Employment 和目标组织/职务主任职 | 已实现 | `workflow/extended_service.py:615-680`（create_person → create_document → create_employment → create_assignment，全在同一 session 事务内） | 符合 | - |
| 12:111 `P2-REC-007` | 二次入职复用原 Person 和原工号 | 已实现 | `workflow/extended_service.py:598-608`（复用 existing_person_id / candidate.linked_person_id）；`:790-791`（已有工号不再分配） | 符合 | - |
| 12:112 `P2-REC-008` | 新人录用必须提供计划入职日有效的已核验主要证件；复聘可以复用有效证件 | 已实现 | `workforce/extended_service.py:768-789`（`VERIFIED_PRIMARY_DOCUMENT_REQUIRED`：要求计划入职日当天有一张 is_primary + verification_status=verified + 未过期的证件）；`workflow/extended_service.py:637-656`（录用时建 verified 主要证件）；复聘沿用已有证件 | 符合 | - |
| 12:113 `P2-REC-009` | 录用转换使用幂等键和唯一转换链路；重试不得重复建人、劳动关系或任职 | 已实现 | `workflow/extended_service.py:519-533`（idempotency_key + request_checksum 冲突报 409）、`:546-556`（application_id 唯一转换链路，`models.py:148-151` 唯一约束） | 符合 | - |
| 12:114 `P2-REC-010` | 招聘阶段、Offer 正式字段、拒绝/撤回原因和可见范围等待企业招聘规则 | 待企业输入 | 文档已标 PENDING_ENTERPRISE_INPUT；当前阶段/原因均为自由字符串（`workflow/extended_schemas.py:110-128`） | 依赖企业输入，不计为缺陷 | - |
| 12:115 `P2-REC-011` | 候选人联系方式和 Offer 字段完成结构化、加密、脱敏、权限和保留规则前，只能使用合成数据 | 待企业输入 | `workflow/models.py:106-110`（`contact_payload` 明文 JSON）、`:138-142`（`offer_payload` 明文 JSON）；无加密、无脱敏、无保留策略 | 文档已标 PENDING_ENTERPRISE_INPUT ✅。**但代码层没有任何「合成数据」守卫**——真实手机号/薪资可以直接写入这两个 JSON 字段（另见明细表「12:183」行） | P2 |
| 12:123-132 | 事件类型稳定代码表：ONBOARDING / CONFIRMATION / TRANSFER / CONCURRENT_ASSIGNMENT / SECONDMENT / END_ASSIGNMENT / TERMINATION / WITHDRAWAL / EMPLOYMENT_CORRECTION / ROLLBACK_* | 已实现 | `workflow/extended_service.py:1370-1386`（9 类 employment + 4 类 contract 事件白名单）；ROLLBACK_* 由 `:2210` 生成（`f"ROLLBACK_{original.event_type}"`）；前端 `apps/web/src/business/features/lifecycle/HrEventPanel.tsx:225-235` 全部按稳定 code 提交 | 9 类人事事件全部落地，符合 | - |
| 12:134 | 事件类型是稳定业务代码，企业流程名称变化不得改变代码含义 | 已实现 | 事件类型枚举集中在 `_validate_hr_event`（`workflow/extended_service.py:1370-1386`），前端只传 code 不传中文名 | 符合 | - |
| 12:140 `P2-EVT-001` | 同一事件可按场景直接生效或审批生效 | 已实现 | `workflow/extended_schemas.py:357`（`execution_mode: Literal["direct","approval"]`）；`workflow/extended_service.py:2102`（direct→ready，approval→pending_approval） | 符合 | - |
| 12:141 `P2-EVT-002` | 审批通过的未来事件等待生效日期；到期处理不得重复执行 | 已实现 | `workflow/extended_service.py:1361-1363`（审批通过→ready→按日期执行）、`:1971-1973`（未到期→scheduled）、`:1974`（completed 不再执行） | 符合 | - |
| 12:142 `P2-EVT-003` | 事件保存目标对象、事件类型、计划变更、执行方式、生效日期、原因、状态和幂等信息 | 部分实现 | `workforce/models.py:950-989` 逐字段可对上：object_type/object_id ✅、event_type ✅、planned_payload ✅、effective_date ✅、reason ✅、status ✅、idempotency_key/request_checksum ✅ | **「执行方式」未落库**——direct/approval 只体现在初始 status 上（`workflow/extended_service.py:2102`），事件行里查不到它是直接生效还是审批生效，事后无法按执行方式审计与统计；**idempotency_key 可空**（`HrEventCreate.idempotency_key: UUID \| None`，`workflow/extended_schemas.py:352`），非幂等请求无法与幂等请求区分 | P1 |
| 12:143 `P2-EVT-004` | 执行前重新校验目标状态、有效日期、引用主数据和并发版本；失败不得部分写入 | 部分实现 | 目标状态 ✅（`workflow/extended_service.py:1620-1625`）；引用主数据 ✅（`:1703-1710` 组织/职务有效性）；失败不部分写入 ✅（`:2058-2061`） | **缺「并发版本」校验**——事件不携带发起时的 expected_version，执行时不比较当前结果的版本，审批期间目标被改过仍会照单执行（另见明细表「08:132」「08:293-299」行） | P1 |
| 12:144 `P2-EVT-005` | 允许受控回退；回退保留原事件和审计，根据场景使用补偿事件、版本恢复或组合策略 | 部分实现 | `workflow/extended_service.py:2131-2234`（生成新 ROLLBACK_* 事件，related_event_id 指回原事件，原事件与原审计保留）；合同侧快照恢复 `:1824-1872` | **策略只有一种**（回填原 before_payload + 版本恢复），没有按场景选择「补偿事件 / 版本恢复 / 组合」的注册与分发 | P1 |
| 12:145 `P2-EVT-006` | 回退支持直接生效和审批生效 | 已实现 | `workflow/extended_schemas.py:374`（`HrEventRollbackCreate.execution_mode`）；`workflow/extended_service.py:2214` | 符合 | - |
| 12:146 `P2-EVT-007` | 下游已经同步时，回退或更正形成新记录，并以新记录重新同步 | 未实现 | 回退已形成新记录 ✅（`workflow/extended_service.py:2206-2223`）；但检索词 `outbound` / `webhook` / `sync` 在 `apps/api/src/hris` **无命中** | **无「以新记录重新同步」的实现**：没有出站消息表、没有同步状态与错误记录，全链路止于本地。建议：随下游接口资料到位一并落地出站表 + 幂等重试 | P2 |
| 12:147 `P2-EVT-008` | 自动执行失败可使用同一幂等语义重试，不重复改变结果 | 已实现 | `workflow/extended_service.py:1974`（completed 不再捞起）、`:2048`（只捞 ready/scheduled/failed）、`:2056-2068`（失败置 failed + attempts+1，可重试且不改结果） | 符合 | - |
| 12:148 `P2-EVT-009` | 每种事件的输入字段、前置状态、审批节点、结果字段、释放规则和回退策略逐流程确认 | 待企业输入 | 文档已标 PENDING_ENTERPRISE_INPUT；当前 `_validate_hr_event`（`workflow/extended_service.py:1369-1560`）写死了一套通用校验 | 依赖企业输入。但注意：这套通用校验本身有语义风险（例如 `END_ASSIGNMENT` 只校验 assignment_id 存在，不校验目标任职是否属于该雇佣、是否已结束），企业输入到位后应逐事件重写 | P2 |
| 12:152 | `ONBOARDING` 只表示待入职劳动关系转为在职，不包含 Offer 确认和待入职建档 | 已实现 | `workflow/extended_service.py:1619-1626`（ONBOARDING 只改 status=active 与 actual_start_date） | 符合 | - |
| 12:153 | SSC 可以发起；系统管理员可以代发起或补录，必须填写原因 | 部分实现 | ONBOARDING_INITIATE 独立权限 ✅（`workflow/extended_api.py:60,490-491`；权限码 `apps/api/alembic/versions/f2b000000001_seed_onboarding_initiator_role.py:32`）；原因必填 ✅（`workflow/extended_schemas.py:358-369`，空白拒绝） | **「代发起」无任何标记**：HrEvent 无 initiator 字段，管理员代 SSC 发起与 SSC 本人发起在事件与审计上不可区分 | P2 |
| 12:154 | HRBP、招聘人员、业务主管和员工本人本期不能发起 | 部分实现 | 只有 LIFECYCLE_ADMIN / ONBOARDING_INITIATE 两个权限码（`workflow/extended_api.py:59-61`），靠角色授权间接约束 | **无代码级的发起人角色黑名单**，误配角色即放开 | P2 |
| 12:155 | 只有 `pending_start` 劳动关系可以创建或执行入职事件 | 已实现 | 发起时 `workflow/extended_service.py:1405-1411`；执行时二次校验 `:1620-1625` | 符合 | - |
| 12:156 | 同一劳动关系不能并行存在多个未结束的入职事件 | 已实现 | `workflow/extended_service.py:1412-1425`（`ONBOARDING_EVENT_ALREADY_OPEN`，覆盖 pending_approval/ready/scheduled/failed） | 符合 | - |
| 12:157 | 生效日期口径、审批节点、动态办理人和分支仍待确认 | 待企业输入 | 文档已标；对应 `12:222-226` 的 P2-Q001~P2-Q003 | 依赖企业输入 | - |
| 12:163 `P2-CON-001` | 合同记录关联 Person，并且最多关联一种劳动关系或协议关系 | 已实现 | `workflow/models.py:196-199`（CheckConstraint `employment_id IS NULL OR agreement_relationship_id IS NULL`）；`workflow/extended_schemas.py:230-233`；`workflow/extended_service.py:759-790`（校验关系属于该 person） | 符合 | - |
| 12:164 `P2-CON-002` | 保存合同类型、编号、主体、签署日、生效区间、提醒天数、版本和状态 | 已实现 | `workflow/models.py:189-242`（contract_type_code/contract_number unique/legal_entity_id/signed_on/effective_from/effective_to/expiry_notice_days/version/status） | 符合 | - |
| 12:165 `P2-CON-003` | 合同变更、续签、解除和取消使用显式动作，支持直接、审批和未来生效 | 已实现 | `workflow/extended_schemas.py:296-316`（`ContractActionCreate.action_type: amendment/renewal/termination/cancellation` + execution_mode + effective_date）；`workflow/extended_service.py:916-947`（转成 hr_event）；`:1789-1967`（执行） | 符合 | - |
| 12:166 `P2-CON-004` | 续签建立前后合同链；变更形成版本；动作具备幂等和回退 | 已实现 | 合同链：`workflow/models.py:218-222`（`predecessor_contract_id`）+ `workflow/extended_service.py:1921`；版本递增 `:1896,1903,1938`；幂等 `:519-533`；回退取消后继 `:1824-1872` | 符合 | - |
| 12:167 `P2-CON-005` | 到期提醒和状态刷新按查询/处理日期计算，不改写历史动作 | 已实现 | `workflow/extended_service.py:949-987`（list_contract_expiry_alerts 按 as_of + days_ahead 与 expiry_notice_days 计算）、`:989-1019`（process_contract_statuses 按处理日置 expired 并留审计） | 符合 | - |
| 12:168 `P2-CON-006` | 合同/协议正式类型、字段、期限状态、编号规则和必填条件等待企业表头 | 待企业输入 | 文档已标 PENDING_ENTERPRISE_INPUT；当前 contract_type_code 为自由码（`workflow/extended_schemas.py:216-220`） | 依赖企业输入 | - |
| 12:169 `P2-CON-007` | 附件格式、大小、存储、病毒扫描、保留、下载和明文访问权限待确认 | 待企业输入 | 文档已标；`ContractRecord` 无附件字段（`workflow/models.py:189-242`） | 依赖企业输入 | - |
| 12:170 `P2-CON-008` | 电子签章、提醒渠道/对象、审批图和失败补偿待确认 | 待企业输入 | 文档已标；到期提醒只有 API 列表（`workflow/extended_api.py:302-319`），无通知渠道 | 依赖企业输入 | - |
| 12:172 | 开放的 `metadata_payload` 只用于通用工程验证，不允许把未建模的敏感字段或合同原文长期塞入 JSON 来规避字段评审 | 部分实现 | `workflow/models.py:239-242`（metadata_payload JSON）；`workflow/extended_service.py:1501-1508`（CONTRACT_AMENDMENT 允许改 metadata_payload） | **没有任何校验或告警阻止把合同原文/薪资写进 metadata_payload**，约束只存在于文档文字 | P2 |
| 12:176-177 | 首批操作角色为系统管理员和 SSC；账号、角色和启停由主管理员维护；停用账号永久撤销既有会话 | 已实现 | `apps/api/src/hris/modules/platform/account_admin_api.py:39-90`；停用即撤销会话 `account_admin_service.py:152-161`（`update(UserSession).values(revoked_at=now)`）；会话校验 `platform/dependencies.py:34-50` | 符合 | - |
| 12:178 | 流程配置、流程办理、事件发起、事件执行、回退、合同操作和明文访问必须使用独立权限代码 | 部分实现 | 实际权限码只有 `LIFECYCLE_ADMIN`（覆盖流程配置/办理/事件/回退/合同全部接口，`workflow/extended_api.py:59`）+ `ONBOARDING_INITIATE`（仅入职发起，`:60,490-491`）+ `PERSON_SENSITIVE_REVEAL`（明文，`workforce/personnel_api.py:56-65`）；检索词 `LIFECYCLE_[A-Z]+` 在 `apps/api/alembic/versions` 只命中 LIFECYCLE_ADMIN 与 LIFECYCLE 分类 | **七项要求里只有 2 项有独立码**（入职发起、明文访问）。回退、事件执行、合同操作全部共用 LIFECYCLE_ADMIN，无法按岗分权。建议：拆成 LIFECYCLE_WORKFLOW_CONFIG / LIFECYCLE_TASK_APPROVE / HR_EVENT_RAISE / HR_EVENT_EXECUTE / HR_EVENT_ROLLBACK / CONTRACT_OPERATE 六个码 | P1 |
| 12:179 | 未知权限、未知办理人表达式和缺失兜底关系均默认拒绝 | 部分实现 | 未知权限 ✅ `platform/dependencies.py:79-80,90-91`（无 `*` 通配时按码集合判定） | **未知办理人表达式不拒绝**：`assignee_type="expression"` 被原样落库（`workflow/extended_service.py:1205-1223`），且缺兜底时硬编码 `SYSTEM_ADMIN`（`:1208-1210`）而非拒绝 | P1 |
| 12:180 | 审计至少记录操作者、代理/代办关系、时间、Trace ID、原因、业务对象、前后值摘要和来源 | 部分实现 | `workforce/models.py:992-1009`（actor_id/occurred_at/trace_id/action/object_type/object_id/reason/before_payload/after_payload/source）；TraceId 中间件 `core/middleware.py:8-17` | **缺「代理/代办关系」字段**（AuditLog 无 actor_on_behalf_of 之类）；事件链路的 before/after 摘要可取，但普通编辑类审计的 before 只有字段名（见明细表「07:248」行） | P2 |
| 12:181 | 密码、证件明文、合同原文及其他秘密不得进入审计日志 | 已实现 | `workforce/personnel_service.py:98-126`（审计只写 masked_values）；`platform/audit_service.py` 同样只落库脱敏 payload | 符合 | - |
| 12:182 | 候选人联系方式、人员证件和合同附件按敏感数据规则保护 | 部分实现 | 人员证件 ✅（`core/personnel_security.py` 全套）；合同附件 ✗（不存在）；候选人联系方式 ✗（`workflow/models.py:106-110` 明文 JSON） | **候选人联系方式未加密未脱敏**，与 12:183 的合成数据限制叠加后是真实泄露面 | P1 |
| 12:183 | 当前候选人 `contact_payload`、应聘 `offer_payload` 和合同 `metadata_payload` 是通用 JSON 载荷，不具备企业敏感字段合同；不得写入真实联系方式、Offer 薪资、证件、合同原文或秘密 | 与PRD冲突 | `workflow/models.py:106-110`（contact_payload）、`:138-142`（offer_payload）、`:239-242`（metadata_payload）三处均为无约束 JSON；`workflow/extended_api.py:67-122`（候选人建档）、`:192-249`（应聘建档）无任何内容过滤 | **文档写的是「不得写入」，代码层没有任何校验阻止写入**。这是文档明文红线与实现的直接冲突。建议：加 schema 层的敏感键名黑名单（phone/email/id_card/salary/passport 等）拒绝或强制脱敏，并把 contact_payload 迁到 personnel_security 的加密字段 | P1 |
| 12:189-195 | 异常与补偿六条：流程图无效或条件歧义→禁止发布或推进并返回可定位错误；动态办理人无法解析→不跳过审批进入失败/人工补偿；审批期间业务对象已变化→执行时报告并发冲突重新确认；生效日引用的组织/职务已失效→事件失败且不部分执行；自动任务中断→使用原幂等键安全重试；下游同步失败→本地不回滚按事件重试；自动回退影响不明确→禁止自动处理转人工评审 | 部分实现 | 图歧义 ✅（`workflow/extended_service.py:1259-1264` `WORKFLOW_ROUTE_AMBIGUOUS`、`:1272-1276` `WORKFLOW_ROUTE_NOT_MATCHED`）；引用失效 ✅（`:1703-1710`、`:1394-1404`）；幂等重试 ✅（`:2056-2068`） | **「审批期间业务对象已变化→并发冲突」无实现**（无 expected_version）；**「动态办理人无法解析→进入失败/人工补偿」无实现**（expression 从不解析，也不报错）；**「下游同步失败」「自动回退影响不明确」无实现** | P1 |
| 12:199 | 所有业务写入使用数据库事务和迁移管理 | 已实现 | Alembic 21 个版本迁移（`apps/api/alembic/versions/`）；所有 service 用 AsyncSession 事务，跨表写入在同 session 内 | 符合 | - |
| 12:200 | 运行中流程和已生效事件不得物理删除 | 已实现 | 检索词 `delete` 在 `apps/api/src` 仅命中 `performance/service.py`（OKR 目标）与 `workforce/batch_change_service.py`（草稿明细行）；**workflow / hr_events / contract_records 无任何 DELETE 接口** | 符合 | - |
| 12:201 | API 必须提供稳定错误码、Trace ID 和分页 | 已实现 | `core/errors.py`（ApiError + code + trace）；`core/middleware.py:14-17`（X-Trace-ID 透传）；所有列表接口带 limit/offset（如 `workflow/extended_api.py:409-412`） | 符合 | - |
| 12:202 | 核心规则覆盖正常、边界、失败、并发、权限、幂等和回退测试 | 部分实现 | 集成测试 27 个文件，含 `apps/api/tests/integration/test_workflow_execution_api.py`、`test_hr_event_execution_api.py`、`test_contract_lifecycle_api.py`、`test_person_archive_api.py`、`test_personnel_record_api.py`、`test_reporting_relations_api.py`；单元测试 `apps/api/tests/test_workflow_conditions.py`、`test_personnel_security.py` | **无「并发」测试**（因为没有 expected_version 机制可测）；回退测试集中在合同侧，雇佣/组织关系回退未覆盖；权限测试未覆盖「任务办理人校验」 | P1 |
| 12:203 | 后台到期任务可重复启动，且同一业务结果只应用一次 | 部分实现 | 幂等 ✅ `workflow/extended_service.py:2039-2069`（process_due_hr_events：只捞 ready/scheduled/failed，completed 不重复执行，逐条 begin_nested） | **没有后台任务**：检索词 `APScheduler` / `BackgroundScheduler` / `cron` / `scheduler` / `lifespan` / `startup` 在 `apps/api/src` **无命中**，全靠人工调 `POST /api/v1/lifecycle/hr-events/process`（`workflow/extended_api.py:537-545`）与 `POST /contracts/process-statuses`（`:322-333`）。同一条「同一业务结果只应用一次」成立，但「后台任务可重复启动」不成立 | P1 |
| 12:204 | 第二阶段不以一万人同时提交流程作为完成条件；容量场景在非功能输入包中单独冻结 | 待决策 | 无容量测试、无非功能输入包；`apps/api/tests/` 无压测目录 | 文档明确「单独冻结」，属待决事项 | - |
| 12:210-216 | 第二阶段完成定义七条（逐项确认发布、流程要素版本明确、合成数据 UAT、合同字段确认、普通办理人权限校验、链路对账、自动化测试与 Review 通过） | 部分实现 | 第 3 条部分达成（合成数据链路已有测试）；第 6 条部分达成（事件/任务/结果/审计可对账，**同步链路缺**）；第 7 条部分达成（测试与 Docker 复跑有基础）；第 1、2、4 条依赖企业输入；第 5 条不满足（任务办理不校验办理人，见明细表「12:96 `P2-FLOW-011`」行） | **当前不可从「通用工程 MVP」升级为「企业业务验收通过」**，7 条里第 5 条是纯工程缺口（可立即修），第 1/2/4 条是企业输入 | P1 |
| 12:222-226 | 企业输入顺序 P2-Q001~P2-Q005（入职生效日期来源/修改权限/审批晚于生效日；入职审批节点与会签或签与动态办理人；入职条件分支/驳回/撤回/超时/回退；依次转正调动兼岗借调离职撤回更正；合同正式字段与附件规则） | 待企业输入 | 文档已标；输入包 `docs/input-packs/06-hr-workflow-input.md` 尚未提供（本分片按分工不查阅该目录） | 依赖企业输入，不计为缺陷 | - |
| 12:45（流程运行） | 流程运行域：实例、审批任务、会签/或签、选路、通过、驳回和审计 | 部分实现 | 实例 ✅ `workflow/models.py:51-74`；任务 ✅ `:77-94`；会签或签 ✅ `workflow/extended_service.py:1333-1336`；选路 ✅ `:1240-1287`；通过/驳回 ✅ `:1324-1341`；审计 ✅ `:1342-1347` | 通过与驳回已实现；**「撤销」与「退回」两个动作缺失**（见下条专项） | P1 |
| 12:45 / 12:51 / 08:67-76（业务对象联动） | 流程实例应能驱动业务对象；流程数据域应覆盖业务对象、实例、任务、事件、审计和下游同步链路 | 部分实现 | `workflow/extended_service.py:1356-1357`：`_finish_workflow_business_object` 对 `business_object_type != "hr_event"` **直接 return**；`:1085-1091` 也只对 hr_event 做挂接 | **业务对象联动只支持 hr_event**。合同事件通过 `object_type="contract"` 的 hr_event 间接覆盖 ✅，但 `leave_requests`（`apps/api/src/hris/modules/attendance/models.py:121`）等其他业务对象**无法被流程驱动**，且 `start_workflow` 接口对任意 business_object_type 都接受（`workflow/extended_schemas.py:427`）→ 会静默生成一个跑完却什么都不做的实例（no-op）。建议：启动时校验业务对象类型白名单，未注册类型直接 422 | P1 |
| 12:97 / 12:148 / 08:67-76（审批动作三义专项） | 产品已明确审批动作语义：**撤销 = 终止、驳回 = 终止、退回 = 回到上一节点**，三者语义互不相同 | 与PRD冲突 | `workflow/extended_schemas.py:489-491`（`decision: Literal["approve","reject"]`）；`workflow/extended_service.py:1324-1330`（reject → instance.status="rejected" + 结束流程）；检索词 `send_back` / `withdraw` 在 `apps` **无命中**；前端 `apps/web/src/business/features/lifecycle/WorkflowPanel.tsx:136-139` 只有「通过」「驳回」两个按钮 | **当前只有「通过」与「驳回」两个动作**：驳回=终止 ✅ 符合口径；**「撤销」（发起方主动终止）与「退回」（回到上一节点继续走）两个动作完全没有**，而这两者与「驳回=终止」在产品口径下语义不同，不能用同一个 reject 顶替。注意：文档 12:97 把这些整体标为 PENDING_ENTERPRISE_INPUT，但「撤销/退回」的产品语义已确定，建议按产品口径先行落地 | P0 |
| 08:3.1 / 12:47（批量异动方案，开发中） | 整批异动方案制：整批一个方案走审批、1000 条上限、草稿态 | 开发中 | `apps/api/src/hris/modules/workforce/batch_change_models.py:28-98`（HrEventBatch 状态机 draft/submitted/approved/rejected/cancelled、1000 条上限、复用 hr_events 行 + batch_id 列）；`batch_change_api.py:44-142`；迁移 `apps/api/alembic/versions/f2d000000001_batch_change_plans.py` | 模块与迁移文件已存在，但处于并行开发中（模型文件注释自述「workforce/models.py 由主 agent 独占」）。本分片不将其判为缺陷，**待开发完成后重跑本分片对账** | P2 |
| 附：绩效 OKR 模块（开发中） | 绩效 OKR（`modules/performance/*`） | 开发中 | `apps/api/src/hris/modules/performance/{api.py,models.py,schemas.py,service.py}`；迁移 `apps/api/alembic/versions/f2e000000001_performance_okr_schema.py` | **不属于本分片三份文档的条款范围**（属 06/14 域），仅作现状备注，不计入本表判定统计 | P2 |

---

## 本分片 3 条最该先修的

1. **P0｜审批动作三义缺失（明细表「12:97 / 12:148 / 08:67-76（审批动作三义专项）」行）** —— 现在 `decision` 只有 `approve`/`reject` 两种（`workflow/extended_schemas.py:489-491`），而产品口径里「撤销=终止、驳回=终止、退回=回到上一节点」是三个互不相同的动作；缺「撤销」和「退回」会让 SSC 无法撤回误提交、无法把单节点退回到上一节点补材料，这是第二阶段流程可用性的地基，且不依赖任何企业输入即可先做。

2. **P1｜人员数据范围缺失（明细表「07:290」行）** —— `list_persons` 与 `person_archive` 全无组织/法人/BP 范围过滤（`workforce/extended_service.py:1106-1132, 1048-1104`），`dependencies.py` 只有扁平权限码；任何持 `PERSON_VIEW` 的账号可见全量人员，导出也同样不受限（`master_data_export.py:48-60`），直接违反文档写明的数据范围与字段权限双通过红线。

3. **P1｜流程定义无法演进 + 图校验不在发布时（明细表「12:87 `P2-FLOW-002`」「12:89 `P2-FLOW-004`」两行）** —— `WorkflowVersion(` 全仓只在创建时出现一次且固定 version=1（`workflow/service.py:154`），没有创建新版本的接口，已发布流程的审批节点与条件分支永远改不了；而全部图校验（断线/歧义/环路/不可达）都挂在创建时（`service.py:58-141`），`publish_workflow` 只查 start/end 存在（`workflow/extended_service.py:1021-1036`），一旦补上版本能力就会绕过校验。

---

## 附录 A：本次审计实际执行的检索（未找到即判定的条款可复核）

| 判定为「未实现/部分实现」的要点 | 实际检索词与范围 |
|---|---|
| Employment 有效期重叠的数据库层约束 | `EXCLUDE` / `exclusion` / `btree_gist` / `daterange` @ `apps/api`（命中仅 `f1a000000001_phase_1a_organization_domain.py:316-372` 六张组织表） |
| 银行账户 / 附件 / 照片字段 | `bank_account` / `BankAccount` / `attachment_ref` / `attachment_id` / `photo` @ `apps/api/src`（无命中） |
| 人员类型字典 | `EMPLOYEE_TYPE` / `PERSON_TYPE` / `employment_type` / `dictionary` @ `apps/api/src`（无人员类型字典） |
| 雇佣状态枚举 | `pending_start` / `probation` / `notice_period` / `leave_without_pay` / `resigning` / `terminated` / `withdrawn` @ `apps/api/src` |
| Person 级组织关系写入路径 | `OrganizationPersonRelation` @ `apps/api/src`（仅 `workforce/models.py:720-745` 与 `shared/db/models.py`，无 service/API） |
| 字段变更时间线 / 两时点差异对比 | `timeline` / `/diff` / `as_of` / `effective_at` @ `apps/api/src`（无 timeline/diff 端点） |
| 下游出站同步机制 | `出口` / `出站` / `outbound` / `Outbound` / `sync` / `webhook` / `企业微信` / `wechat` / `wecom` @ `apps/api/src/hris` |
| 后台到期任务调度器 | `APScheduler` / `BackgroundScheduler` / `cron` / `scheduler` / `lifespan` / `startup` @ `apps/api/src`（无命中） |
| 流程版本创建 | `WorkflowVersion(` @ `apps/api/src`（仅 `workflow/service.py:154`，固定 version=1） |
| 撤销 / 退回 / 重新提交 / 转办 / 加签 / 超时 / 升级 | `resubmit` / `re_submit` / `withdraw_workflow` / `cancel_workflow` / `send_back` / `return_to` / `roll_back_node` @ `apps`（无命中）；`expression` / `assignee_type` @ `apps`（仅 schema 枚举与落库，无解析） |
| 组织事件类型覆盖 | `event_type=` / `event_type ==` @ `workforce/organization_service.py`（CREATE / VERSION_CHANGE / LEGAL_ENTITY_SET / LEADER_SET / BP_MEMBERSHIP_CREATE / BP_SCOPE_SET / COST_ALLOCATION_SET / REVENUE_TARGET_SET；无 merge/split） |
| 独立权限码清单 | `PERSON_[A-Z_]+` / `LIFECYCLE_[A-Z_]+` / `WORKFORCE_[A-Z_]+` / `ONBOARDING_[A-Z_]+` @ `apps/api/alembic/versions` |
| 事件状态取值 | `pending_start` / `probation` / `terminated` / `withdrawn` @ `apps/api/src`（HrEvent 实际 status：pending_approval / ready / scheduled / completed / failed / rejected） |
| 流程业务对象联动范围 | `business_object_type` / `startWorkflow` / `workflow-instances` @ `apps/web` + `workflow/extended_service.py:1356-1357, 1085-1091` |

## 附录 B：已知现状复核结论（任务简报所列，均已自行复核）

| 简报说法 | 复核结论 |
|---|---|
| 员工标签 + 标签库刚做完 | ✅ 成立。`workforce/labels_api.py`、`labels_service.py`、`label_library.py`；字典码 `PERSON_LABEL_LIBRARY`（`label_library.py:13`）；标签库项未命中报 `PERSON_LABEL_LIBRARY_ITEM_NOT_FOUND`（`label_library.py:105,118`） |
| 汇报关系刚做完 | ✅ 成立。`workforce/reporting_api.py`、`reporting_service.py`，支持 effective_at 时点查询 |
| 职位管理刚做完 | ✅ 成立。`workforce/extended_api.py:117-214`（jobs / job-dimensions / versions），含 `ensure_job_effective`（`extended_service.py:474-480`） |
| 操作日志刚做完 | ✅ 成立。`platform/audit_api.py`、`audit_service.py`，权限 DATA_GOVERNANCE_ADMIN |
| 批量异动方案制开发中 | ✅ 成立，判为「开发中」 |
| 绩效 OKR 开发中 | ✅ 成立，但不属本分片文档范围，仅备注 |
| 决策枚举只有 approve/reject | ✅ 成立（`workflow/extended_schemas.py:490`） |
| 节点类型只有 start/approval/action/end | ✅ 成立（`workflow/schemas.py:61`），但 `action` 节点无执行语义（见明细表「12:88 `P2-FLOW-003`（受控动作语义）」行） |
| 会签/或签 sign_mode: all/any | ✅ 成立（`workflow/schemas.py:62`） |
| 条件 9 算子 | ⚠️ 实际为 **10 个**：eq/ne/gt/gte/lt/lte/in/not_in/exists/not_exists（`workflow/schemas.py:17-28`） |
| 业务对象联动只支持 hr_event | ✅ 成立（`workflow/extended_service.py:1356-1357`） |
| 驳回即终止 | ✅ 成立（`workflow/extended_service.py:1324-1330`，instance.status="rejected"） |

## 附录 C：本分片无法判定的条款及原因

| 条款 | 无法判定原因 |
|---|---|
| 07:77 工号耗尽/历史重复/非法工号的迁移期处理 | 文档明确「在数据迁移设计中确定」，但仓内未见对应迁移设计文档；无法判断是遗漏还是另存他处 |
| 07:113-160 候选字段的最终必填性与校验规则 | 文档自述「最终字段、必填性和校验规则以现有表结构为准」，但企业表头与数据样例尚未提供，无法判定缺字段是遗漏还是候选 |
| 08:26 界面「不建设独立的待生效组织事件页面」 | 组织未来事件已在组织详情内按生效日期展示，但「独立页面」的边界取决于导航信息架构（属 16 号总体 PRD 分片），本分片无法裁定 |
| 12:86-98 的 `IMPLEMENTED_GENERIC` 升级 | 文档定义该状态为「当前系统已有通用实现，但仍需企业输入才能验收为正式流程」；企业输入未到位，无法判定是否可升级 |
| 12:233 `P2-EVT-009` 每种事件的输入字段/前置状态/审批节点/结果字段/释放规则/回退策略 | 文档明确「逐流程确认」，企业输入未到位 |
| 12:168-170 合同正式类型、字段、编号规则、附件与电子签章 | 依赖企业合同表头（`P2-CON-006/007/008`），输入包未到位 |
| 12:222-226 `P2-Q001`~`P2-Q005` | 依赖企业输入包 06，本分片按分工未查阅 `docs/input-packs/` |
| 12:204 容量场景 | 文档明确「在非功能输入包中单独冻结」，无冻结输入即无法判定 |
| 批量异动方案（开发中） | 并行开发中，功能未完成，判定会失真；待开发完成后重跑本分片对账 |
