-- coreHR 企业输入包 01：非敏感枚举只读提取
--
-- 目标库：本机 ehr_source
-- 安全边界：
--   1. 只输出代码、ID、名称、层级和启停状态。
--   2. 不输出姓名、工号、证件、电话、邮箱、地址、薪酬或银行信息。
--   3. 不执行 INSERT、UPDATE、DELETE、DDL 或存储过程。
--   4. ehr_employee_info 只做枚举去重，不输出任何人员行标识。

USE ehr_source;

-- A. 旧系统字典定义。create_by/update_by 等操作人字段不导出。
SELECT
    id AS source_dictionary_id,
    name AS source_dictionary_name,
    code AS source_dictionary_code,
    number AS source_dictionary_number,
    en_name AS source_dictionary_en_name,
    enable AS is_enabled,
    type AS source_dictionary_type
FROM ehr_dict
WHERE is_delete = 0
ORDER BY id;

-- B. 旧系统字典项。只保留稳定来源键、层级、代码和显示名。
SELECT
    id AS source_item_id,
    dict_id AS source_dictionary_id,
    out_id AS source_external_id,
    old_id AS source_legacy_id,
    parent_id AS source_parent_item_id,
    name AS source_item_name,
    code AS source_item_code,
    en_name AS source_item_en_name,
    sort AS sort_order,
    level AS hierarchy_level,
    enable AS is_enabled
FROM ehr_dict_element
WHERE is_delete = 0
ORDER BY dict_id, sort, id;

-- C. 员工类型。结果不包含人员标识或人数。
SELECT DISTINCT
    employee_type_id AS source_id,
    employee_type AS source_name
FROM ehr_employee_info
WHERE employee_type_id IS NOT NULL
  AND employee_type IS NOT NULL
  AND TRIM(employee_type) <> ''
ORDER BY source_id, source_name;

-- D. 员工状态。结果不包含人员标识或人数。
SELECT DISTINCT
    employee_status_id AS source_id,
    employee_status AS source_name
FROM ehr_employee_info
WHERE employee_status_id IS NOT NULL
  AND employee_status IS NOT NULL
  AND TRIM(employee_status) <> ''
ORDER BY source_id, source_name;

-- E. 性别枚举。结果不包含人员标识或人数。
SELECT DISTINCT
    gender_id AS source_id,
    gender AS source_name
FROM ehr_employee_info
WHERE gender_id IS NOT NULL
  AND gender IS NOT NULL
  AND TRIM(gender) <> ''
ORDER BY source_id, source_name;

-- F. 民族枚举。源字段名 nationality 不准确，首行样例已证明其值为“汉族”；
--    本结果不得直接映射到 coreHR nationality_code。
SELECT DISTINCT
    nationality_id AS source_id,
    nationality AS source_name
FROM ehr_employee_info
WHERE nationality_id IS NOT NULL
  AND nationality IS NOT NULL
  AND TRIM(nationality) <> ''
ORDER BY source_id, source_name;

-- G. 国家字典。是否代表员工国籍、所在国家或其他地区语义仍需业务确认。
SELECT
    code AS source_country_code,
    name AS source_country_name,
    leaf AS is_leaf
FROM country
ORDER BY code;

-- H. 组织层级候选。只输出层级编号，不输出组织名称或人员结果。
SELECT DISTINCT
    department_level AS source_department_level
FROM ehr_department_snap
WHERE department_level IS NOT NULL
ORDER BY source_department_level;

-- I. 兼岗/兼职关系状态候选。只输出状态ID和状态名。
SELECT DISTINCT
    status_id AS source_status_id,
    status AS source_status_name
FROM ehr_employee_part_dept
WHERE status_id IS NOT NULL
   OR (status IS NOT NULL AND TRIM(status) <> '')
ORDER BY source_status_id, source_status_name;
