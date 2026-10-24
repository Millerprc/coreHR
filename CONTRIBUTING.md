# 贡献指南

感谢你愿意为 coreHR 出力。本文件说明如何提交改动，以及哪些事**必须**先做。

> ⚠️ **先读这一条**：coreHR 采用 **coreHR Sustainable Use License v1.0**（源码可见，非 OSI 开源）。
> 贡献即表示你同意你的贡献按 LICENSE 第 6 节授权。**不要**提交任何你无权授权的第三方内容。

---

## 1. 五条硬规矩

1. **不要猜业务规则。** 企业侧的取值（假期计提频率、工龄折算、封顶、结转、清零、
   离职处理、轮班周期、审批链等）一律留空或标记 `PENDING`，由产品决策人给出。
   把不确定的取值猜出来写死，是本项目最严重的错误类型。
2. **原型先行。** 涉及界面的改动，**先改 `.pen` 画板**并登记到
   `docs/review/pen-artboard-registry.json`，画板达到 `PROTOTYPE_APPROVED`
   之后才允许写前端代码（规范 §10.2、D-087）。
3. **决策先落文档。** 任何架构性取舍先写进 `docs/01-foundation/03-项目决策.md`
   的决策编号（D-xxx），再在代码里用 `# Requirement: D-xxx — 原因` 指向它。
4. **不削弱既有测试。** 改实现就得改断言，而不是把断言改松。修测试必须是
   "实现语义确实变了"，且要在提交说明里写明变了什么、为什么。
5. **不碰别人的文件。** 并行开发时每个任务有明确的文件所有权；需要改别人
   拥有的文件时，先在任务里说明，由协调者合并。

---

## 2. 开发环境

```bash
git clone <repo-url>
cd coreHR

# 后端
cd apps/api
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[test]"

# 前端
cd apps/web
npm install
```

数据库与 Redis 用 Docker Compose 起，详见
[业务切片运行手册](./docs/implementation/business-runbook.md)。

---

## 3. 提交前必须全绿的检查

```powershell
# 许可证声明（公开仓逐文件版权头；从仓库根目录执行）
node scripts/check-license-header.mjs

# 前端
cd apps/web
node scripts/check-antd-usage.mjs     # AntD 6.5.2 废弃用法守卫
npx tsc -b                           # 类型检查
npm run test:run                     # vitest
cd ../..                             # 回到仓库根目录

# 后端
cd apps/api
alembic -c alembic-business.ini upgrade head
alembic -c alembic-business.ini check     # 必须零漂移
python -m compileall -q src
python -m pytest tests/integration -q
```

> **测试库命名**：临时库名**必须**含 `test`（如 `corehr_regression_test_<pid>`），
> 否则测试用例会因环境契约直接报 error 而不是 fail，看起来像"测试挂了"。
>
> **迁移链**：新迁移的 `down_revision` 必须取自 `alembic heads` 的真实输出，
> **不可按文件名排序推断**——本项目历史上出现过文件名顺序与链顺序不一致。
> 提交前跑一次 `alembic heads`，确认仍然**单根、单头、无分支**。

---

## 4. 代码风格

- **Python**：类型注解齐全；服务层抛 `ApiError` 并带稳定错误码；日志与错误
  信息**不得包含姓名、工号、手机号、证件号等 PII**（只记 ID 与字段名）。
- **TypeScript / React**：统一 Ant Design 6.5.2 原生交互；**组件复用优先**
  ——同一能力域不得出现第二套写法（自建表格、自建日期选择器、自建按钮样式
  都是违规）；管理端只做 PC。
- **注释**：解释"为什么"，不复述"做了什么"。禁止 TODO / FIXME / NotImplemented /
  裸 `pass` 占位。
- **提交信息**：Conventional Commits（`feat:` / `fix:` / `docs:` / `refactor:` /
  `test:` / `chore:`），一行摘要 + 空行 + 正文说明动机与影响面。

---

## 5. 数据库迁移

- 一个迁移只做一件事；`down_revision` 接当前 head。
- 迁移必须**真实建表/改列**，不能靠 `alembic check` 通过就了事。
- 迁移链的编号段由协调者分配，**不要自己猜下一个编号**——并行开发时多人
  容易撞号。
- 只追加触发器、只读视图这类数据库对象，迁移要保证重复执行不报错。

---

## 6. 文档

| 你改了什么 | 要同步改哪份文档 |
|---|---|
| 新增/修改界面 | `.pen` 画板 + `docs/review/pen-artboard-registry.json` + 对应功能需求文档 §10.4 |
| 新增业务规则 | `docs/01-foundation/03-项目决策.md` 加决策编号 |
| 改变架构取舍 | `docs/adr/` 新建或更新 ADR（6 段式） |
| 新增/修改模块功能 | `docs/requirements/` 下对应功能文档（17 号规范的 20 章模板） |

文档是**权威来源**，代码是文档的落地。两边不一致时，以文档为准，且必须把
代码改到与文档一致——不要反过来改文档去迁就代码。

---

## 7. 保密与个人信息

- **绝不提交**：真实人员数据、`.env`、`*.pem`、`*.key`、`*.lic`、`*.license.json`、
  `signing/` 目录、License 明文 token、签发私钥、生产连接串。
- 测试数据必须**可识别为合成数据**（如 `Synthetic Licensee`、明显的测试邮箱），
  不得用看起来像真实员工的信息。
- 截图与日志贴进 issue / PR 前，先确认没有 PII。

---

## 8. 报告问题

提交 issue 时请包含：复现步骤、期望行为、实际行为、版本或 commit、
最小复现片段（不要贴整段业务数据）。能提供 `.pen` 画板 ID 或
`docs/review/` 下相关文档编号的，一起给出，能显著加快定位。

---

## 9. 许可与归属

你的贡献按 LICENSE 第 6 节授权给项目；你保留自己贡献的著作权。
项目不会因为你贡献了代码就要求你放弃任何权利。

署名与商标：coreHR 名称与标识归项目维护者所有。贡献不会让你获得使用
coreHR 商标的权利；商业分发场景下的归属标记要求见 LICENSE 第 4 节。
