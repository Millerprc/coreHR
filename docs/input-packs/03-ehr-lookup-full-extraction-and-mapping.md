# 旧EHR完整字典处置与coreHR映射基线

> 状态：`READY_FOR_BUSINESS_REVIEW`
> 日期：2026-08-11
> 定位：旧系统是研究样本，新coreHR不承担原样兼容旧字典的目标

## 1. 最终建议

不把旧EHR的163个字典定义和4,373个字典项整体导入coreHR。旧数据只用于识别业务术语、发现边界和生成候选代码。

进入coreHR的数据必须满足三项条件：

1. 属于新系统已确认的领域对象或配置项。
2. 具有不依赖旧系统显示名和内部ID的稳定代码。
3. 已处理停用、删除、重复、测试和孤儿记录。

## 2. 本地提取边界

提取器顺序读取360GB原始dump，只识别以下三张表：

- `country`
- `ehr_dict`
- `ehr_dict_element`

提取器在第75张表 `ehr_dict_element` 结束后停止。输出仅保存在本机Git忽略目录；扫描过程没有向PostgreSQL、coreHR API或外部服务写入任何业务数据。

## 3. 全量分类结果

163个字典定义和4,373个字典项已经全部分流；另有20个无父字典的孤儿项单独隔离。

| 去向 | 字典数 | 字典项数 | 处理 |
|---|---:|---:|---|
| 第一阶段人员配置候选 | 16 | 141 | 清洗后转为coreHR字典或结构化字段 |
| 第一阶段主数据参考 | 8 | 427 | 仅作国家、法人、职务体系和组织标签参考 |
| 第二阶段招聘参考 | 75 | 555 | 等真实招聘流程和状态机确认，不直接导入 |
| 旧规则引擎参考 | 33 | 197 | 不复用旧表达式语义；coreHR流程引擎独立建模 |
| 外部渠道分类 | 27 | 3,022 | 归未来渠道连接器，不进入核心领域字典 |
| 测试字典 | 4 | 11 | 永久隔离 |
| 无父字典孤儿项 | — | 20 | 永久隔离，除非找到可证明的父项 |

### 3.1 第一阶段人员配置候选

`ACADEMIC_DEGREES`、`ACADEMIC_STATUS`、`CONTRACT_LIMIT`、`CONTRACT_TYPE`、`DOCUMENT_TYPE`、`DOMICILE_TYPE`、`EDUCATION_BACKGROUND`、`ETHNIC`、`FAMILY_RELATIONSHIP`、`HEALTH_STATUS`、`LEARNING_FORM`、`MARRIED`、`NATURE_POSITION`、`POLITICAL_LANDSAPE`、`PROBATION_MONTH`、`SEX`。

其中：

- 可转普通字典：性别、婚姻状况、学位、学历状态、学历、证件、户籍类别、民族、家庭关系、职位性质、政治面貌。
- 转结构化字段：合同期限、试用期月数。
- 转合同领域类型：合同/协议类型。
- 先清洗再决定：健康状态存在“健康/良好”语义重叠；学习形式存在代码与名称含义不一致。

### 3.2 第一阶段主数据参考

`COUNTRY`、`DEPTTYPE`、`JOB_CATEGORY`、`JOB_GRADE`、`JOB_LEVEL`、`JOB_RANK`、`STATUTORY_CORPORATION`、`ZHINENG`。

- 国家以独立 `country` 表为准，不使用只有中国内地/港澳台四项的 `COUNTRY` 字典。
- `DEPTTYPE` 只表达HR部门/非HR部门，不是组织层级。
- 法人公司列表可作样本，但不替代正式法人主数据和稳定法人代码。
- `JOB_*` 和 `ZHINENG` 存在测试项、停用项、重复层级和旧招聘语义，只用于帮助设计职务体系，不直接导入。

### 3.3 第二阶段招聘参考

75个字典覆盖候选人、筛选、邀约、面试、Offer、背调、淘汰、人才库和招聘优先级。它们可用于检查新流程是否漏场景，但不得直接生成coreHR状态机：真实审批节点、状态推进和撤回/回退规则仍以企业流程图为准。

### 3.4 外部渠道与旧规则引擎

- BOSS、猎聘、简历渠道、学校/专业分类等27个字典属于来源适配层。
- 运算符、强弱控制、自动流转、混合条件等33个字典属于旧厂商规则引擎。

两类数据均不进入coreHR核心数据字典。需要对接招聘渠道时，由连接器维护“渠道代码→coreHR标准代码”映射；需要企业规则时，由coreHR流程/规则模型重新表达。

## 4. 第一批候选代码

| 来源字典/值 | coreHR候选 | 处理 |
|---|---|---|
| `SEX.man / 男` | `GENDER.MALE` | 接受 |
| `SEX.female / 女` | `GENDER.FEMALE` | 接受 |
| `MARRIED.married / 已婚` | `MARITAL_STATUS.MARRIED` | 接受 |
| `MARRIED.spinsterhood / 未婚` | `MARITAL_STATUS.SINGLE` | 接受 |
| `MARRIED.divorced / 离异` | `MARITAL_STATUS.DIVORCED` | 接受 |
| `MARRIED.ww / www` | — | 测试项，拒绝 |
| `ACADEMIC_DEGREES.1 / 学士` | `ACADEMIC_DEGREE.BACHELOR` | 接受 |
| `ACADEMIC_DEGREES.2 / 硕士` | `ACADEMIC_DEGREE.MASTER` | 接受 |
| `ACADEMIC_DEGREES.3 / 博士` | `ACADEMIC_DEGREE.DOCTOR` | 接受 |
| `ACADEMIC_DEGREES.4 / 无学位` | `ACADEMIC_DEGREE.NONE` | 接受 |
| `ACADEMIC_STATUS.1 / 毕业` | `ACADEMIC_STATUS.GRADUATED` | 接受 |
| `ACADEMIC_STATUS.2 / 结业` | `ACADEMIC_STATUS.COURSE_COMPLETED` | 接受 |
| `ACADEMIC_STATUS.3 / 肆业` | `ACADEMIC_STATUS.ATTENDED_NOT_GRADUATED` | 先修正显示名为“肄业” |
| `ACADEMIC_STATUS.4 / 在读` | `ACADEMIC_STATUS.ENROLLED` | 接受 |
| `CONTRACT_TYPE.劳动合同` | `LABOR` | 关联唯一法人劳动关系 |
| `CONTRACT_TYPE.实习协议` | `INTERNSHIP` | 协议候选 |
| `CONTRACT_TYPE.派遣协议` | `DISPATCH` | 协议候选 |
| `CONTRACT_TYPE.兼职协议` | `PART_TIME` | 法律关系归类待合同输入包冻结 |
| `CONTRACT_TYPE.返聘协议` | `REHIRE` | 协议候选 |
| `CONTRACT_TYPE.培训协议` | `TRAINING` | 补充协议候选 |
| `CONTRACT_TYPE.保密协议` | `CONFIDENTIALITY` | 补充协议候选 |
| `CONTRACT_LIMIT` | `duration_months/open_ended` | 1/2/3/6/12/24/36/60个月或无固定期限 |
| `PROBATION_MONTH` | `probation_months` | 0至6的整数 |
| `DOCUMENT_TYPE.1` | `CN_NATIONAL_ID` | 接受 |
| `DOCUMENT_TYPE.2/3/4` | `HK_ID/MO_ID/TW_ID` | 接受 |
| `DOCUMENT_TYPE.5/6` | `HK_MO_TRAVEL_PERMIT/TW_TRAVEL_PERMIT` | 接受 |
| `DOCUMENT_TYPE.7` | `PASSPORT` | 接受 |
| `DOCUMENT_TYPE.8` | `OTHER_DOCUMENT` | 接受但禁止静默吞并未知证件 |

学历、民族、政治面貌等完整条目保留来源追踪，但目标码不机械沿用旧数字。正式导入时用受控CSV生成新的稳定码，并保留 `source_system/source_table/source_id`。

## 5. 数据质量闸门

导入工具必须在写入前拒绝或隔离：

- 20个无父字典项。
- 48个停用项和9个逻辑删除项；可以保留历史映射，但默认不得新选用。
- 218组同字典重复代码、365组同字典重复名称。
- 4个测试字典：`code`、`resf`、`sdfasdfasdfa`、`test`。
- 代码尾部空格 `PROFESSIONAL_CATEGORY `。
- 非大写稳定代码定义：`Portal_type`、`Invit_Fail_Archiv`、`InterviewRounds`及上述测试代码。
- 婚姻、职级、职能中的测试项和明显占位值。

## 6. 对开发的约束

1. 不新增“旧EHR兼容模式”。
2. 不把旧字典ID作为coreHR主键或稳定业务键。
3. 通用数据字典只接收经过确认的目标代码；源代码进入来源映射表。
4. 国家、法人、职务体系使用独立领域模型，不塞进普通字典规避建模。
5. 招聘渠道和旧规则引擎通过适配层转换，不污染核心状态机。

## 7. 业务Review时间

本文件建议预留30分钟：

| 检查 | 时间 |
|---|---:|
| 核对提取边界和行数 | 5分钟 |
| 核对六类数据去向 | 10分钟 |
| 核对第一批候选代码 | 10分钟 |
| 记录合同归类和正式职务体系缺口 | 5分钟 |

Review只需标记“接受/调整”。无需逐条检查3,022个渠道分类或旧规则引擎字典项，因为它们已明确不进入核心系统。
