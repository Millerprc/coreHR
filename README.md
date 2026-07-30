# coreHR

企业内部产品化HRIS项目。

当前处于“第一阶段需求澄清 + 第零阶段工程底座开发”状态。

## 文档入口

- [第一阶段正式文档目录](./docs/01-foundation/00-正式文档目录.md)
- [MinimaxCode第零阶段开发基线](./docs/01-foundation/09-MinimaxCode第零阶段开发基线.md)
- [待确认问题](./docs/01-foundation/99-待确认问题.md)
- [ADR规则](./docs/adr/README.md)

## 当前可执行任务

MinimaxCode首先执行`Z0-001 技术版本与依赖冻结`。其余任务只有在任务卡依赖全部完成后才能开工。

第一阶段HR业务模块尚未批准开发，不得自行推断业务字段、状态机或审批规则。

## Git工作方式

- 默认分支：`main`。
- 每个原子任务使用独立分支，例如`feature/z0-001-toolchain`。
- 一个任务对应一个独立提交或可独立审查的变更集。
- 提交信息使用Conventional Commits，例如`docs(adr): freeze toolchain versions`。
- 不向仓库提交密钥、`.env`、真实人员数据、构建产物或本地数据库。
