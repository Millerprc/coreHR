# 企业输入包01：非敏感枚举提取结果

> 执行日期：2026-08-11
> 数据位置：本机只读 `ehr_data.sql`、本机 Docker `mysql/ehr_lookup`
> 数据范围：`country`、`ehr_dict`、`ehr_dict_element` 三张白名单表
> 结论：完整非敏感字典已经取得；旧系统仅作研究样本，不原样导入 coreHR

## 1. 执行证据

- 原始文件大小：`360,751,808,513` bytes。
- 流式扫描在 `ehr_dict_element` 表结束后停止，逻辑处理 `324,407,379,443` bytes，未继续读取文件尾部。
- 提取文件大小：`1,206,513` bytes。
- 提取文件 SHA-256：`A158E07BECC4EBAD853998A6C6B308DC06B25CF93588D2BA1AE5B1662CC4EE7B`。
- 输出结构复核只包含 `country`、`ehr_dict`、`ehr_dict_element`，没有员工表、人员行或其他业务表。
- 提取结果位于 Git 忽略的本机 `tmp/` 目录，不进入代码仓库。

完整行数：

| 源表 | 行数 | 结果 |
|---|---:|---|
| `country` | 240 | 240 个唯一、非空、三位大写代码 |
| `ehr_dict` | 163 | 完整字典定义 |
| `ehr_dict_element` | 4,373 | 完整字典项；其中20项缺少父字典 |

可复现工具为 `scripts/extract_ehr_lookup_tables.py`。工具只复制三张固定白名单表；缺少任一目标表、目标语句超过安全上限或表名不匹配时会失败且不保留半成品。

## 2. 已冻结的转换方向

| 业务维度 | 来源 | coreHR处理 | 结论 |
|---|---|---|---|
| 国家/地区 | `country` | 保留三位代码和中文名，`leaf`不迁移 | 可作为ISO三位码候选参考表 |
| 性别 | `SEX` | `man→MALE`、`female→FEMALE` | 可自动映射 |
| 婚姻状况 | `MARRIED` | `married→MARRIED`、`spinsterhood→SINGLE`、`divorced→DIVORCED` | 三项可映射；`ww/www`隔离 |
| 学位 | `ACADEMIC_DEGREES` | `BACHELOR/MASTER/DOCTOR/NONE` | 可自动映射 |
| 学历状态 | `ACADEMIC_STATUS` | `GRADUATED/COURSE_COMPLETED/ATTENDED_NOT_GRADUATED/ENROLLED` | 修正“肆业”为“肄业”后映射 |
| 合同期限 | `CONTRACT_LIMIT` | 转为期限月数或无固定期限标志 | 不作为普通字典导入 |
| 试用期 | `PROBATION_MONTH` | 转为0至6的月数 | 不作为普通字典导入 |
| 合同/协议类型 | `CONTRACT_TYPE` | 候选代码见完整处置基线；劳动合同与其他协议分流 | 类型可映射，法律关系归类仍以企业规则为准 |
| 证件类型 | `DOCUMENT_TYPE` | 转为身份证、港澳台证件、通行证、护照和其他证件稳定码 | 可自动映射 |
| 民族 | `ETHNIC` | 作为扩展字典，不写入 `nationality_code` | 56项完整，但目标稳定码不沿用旧序号 |
| 部门类型 | `DEPTTYPE` | 作为HR/非HR组织标签 | 不得映射为集团/BG/BU/部门 |
| 法人、职级和职能 | `STATUTORY_CORPORATION`、`JOB_*`、`ZHINENG` | 只作研究参考 | 不覆盖企业正式法人和职务体系 |

完整分流、质量问题和候选代码见[旧EHR完整字典处置与coreHR映射基线](./03-ehr-lookup-full-extraction-and-mapping.md)。

## 3. 仍然成立的禁止项

1. 不得把 `nationality_id/nationality=1/汉族` 写入 `persons.nationality_code`。
2. 不得根据 `department_level` 或 `DEPTTYPE` 猜测集团/BG/BU/部门。
3. 不得把兼岗记录状态当作兼岗、借调或虚线关系类型。
4. 不得把163个旧字典整体灌入coreHR；旧招聘渠道、规则表达式和测试数据不属于新系统领域基线。
5. 不得从本次白名单结果推断人员档案字段中的完整员工类型和劳动关系状态。

## 4. 下一项最小输入

不再要求恢复完整旧系统数据库，也不再要求重新导出三张字典表。

后续只需补充新系统本身的企业规则：

1. 正式职务、职级、职等、职类、序列编码表。
2. 人员档案字段验收表。
3. 合同/协议字段和法律关系归类。
4. 入转调离兼真实流程图。

这些输入按模块分别阻塞，不阻塞已经完成的一至三阶段通用工程MVP。
