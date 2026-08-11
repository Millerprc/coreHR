# Architecture Decision Records

ADR用于记录影响工程结构、技术选型、安全或运行方式的重要技术决策，不用于决定产品业务规则。

| ADR | 标题 | 状态 | 日期 |
|---|---|---|---|
| [ADR-0001](ADR-0001-toolchain.md) | 第零阶段工具链与版本冻结 | Proposed | 2026-07-31 |
| [ADR-0002](ADR-0002-ehr-source-migration-boundary.md) | EHR 源库镜像与 coreHR 归一化迁移边界 | Accepted | 2026-08-08 |
| [ADR-0004](ADR-0004-personnel-sensitive-field-protection.md) | 人员敏感字段应用层保护 | Accepted | 2026-08-12 |

## 命名

```text
ADR-NNNN-short-title.md
```

示例：

```text
ADR-0001-toolchain.md
ADR-0002-auth-session.md
```

编号一经使用不得复用。

## 状态

| 状态 | 含义 |
|---|---|
| `Proposed` | 正在评审，不得作为正式实现依据 |
| `Accepted` | 已接受，可以作为实现依据 |
| `Superseded` | 已由另一份ADR替代 |
| `Rejected` | 已拒绝，仅保留决策历史 |

状态变化直接修改ADR头部。`Superseded`必须链接替代它的新ADR；新ADR也必须链接被替代ADR。

## 必填结构

```markdown
# ADR-NNNN 标题

> 状态：Proposed
> 日期：YYYY-MM-DD
> 决策人：
> 关联任务：

## 背景

说明需要解决的问题、约束和触发原因。

## 决策

清楚写明选择了什么。

## 备选方案

列出评估过的方案以及未选择原因。

## 影响

说明收益、代价、迁移影响、安全影响和后续约束。

## 验证证据

记录安装、构建、测试、性能或兼容性验证的命令和真实结果。

## 复审条件

说明什么变化出现时需要重新评估。
```

## 规则

- ADR必须描述“为什么”，不能只抄实现步骤。
- 只有`Accepted` ADR可被任务依赖。
- 精确版本选择必须包含当前环境验证证据。
- 不得把未经用户确认的HR业务规则包装成技术决策。
- 不得删除已接受、替代或拒绝的ADR。
- ADR修改必须与相关实现处于同一任务或明确的前置任务中。
