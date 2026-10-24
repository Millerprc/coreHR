// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { Alert, Typography } from "antd"
import type { CSSProperties, JSX, ReactNode } from "react"


// Requirement: D-091 — 同一能力域不得出现第二套结构写法：
// 错误条、页头（标题 + 副标题 + 右侧操作区）与页面外框统一由公共组件层承载，
// 各工作区不再各自实现一套页面骨架。

const NOOP = (): void => undefined


export interface WorkspaceErrorProps {
  readonly message: string | null
  readonly onClose: () => void
  readonly style?: CSSProperties
}


export function WorkspaceError({ message, onClose, style }: WorkspaceErrorProps): JSX.Element | null {
  if (!message) return null
  return <Alert closable={{ onClose }} type="error" showIcon title={message} style={style} />
}


export interface WorkspaceShellProps {
  readonly titleId: string
  readonly title: string
  readonly subtitle?: ReactNode
  readonly actions?: ReactNode
  readonly error?: string | null
  readonly onErrorClose?: () => void
  readonly children: ReactNode
}


export function WorkspaceShell({
  titleId,
  title,
  subtitle,
  actions,
  error = null,
  onErrorClose,
  children,
}: WorkspaceShellProps): JSX.Element {
  return (
    <section aria-labelledby={titleId} className="workspace-section">
      <div className="workspace-heading">
        <div>
          <Typography.Title id={titleId} level={2}>{title}</Typography.Title>
          {subtitle ? <Typography.Paragraph type="secondary">{subtitle}</Typography.Paragraph> : null}
        </div>
        {actions}
      </div>
      <WorkspaceError message={error} onClose={onErrorClose ?? NOOP} />
      {children}
    </section>
  )
}


export interface WorkspaceDeniedProps {
  readonly titleId: string
  readonly title: string
  readonly message: string
  readonly description: string
}


export function WorkspaceDenied({
  titleId,
  title,
  message,
  description,
}: WorkspaceDeniedProps): JSX.Element {
  return (
    <section aria-labelledby={titleId}>
      <Typography.Title id={titleId} level={2}>{title}</Typography.Title>
      <Alert type="error" showIcon title={message} description={description} />
    </section>
  )
}
