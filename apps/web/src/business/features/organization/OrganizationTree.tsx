// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { Empty, Tag, Tree, Typography } from "antd"
import { useMemo } from "react"
import type { DataNode } from "antd/es/tree"

import type { OrganizationTreeNode } from "./types"


interface OrganizationTreeProps {
  readonly nodes: readonly OrganizationTreeNode[]
  readonly selectedId: string | null
  readonly onSelect: (organizationId: string) => void
  readonly label?: string
}


function collectIds(nodes: readonly OrganizationTreeNode[]): string[] {
  return nodes.flatMap((node) => [node.id, ...collectIds(node.children)])
}


function toTreeData(nodes: readonly OrganizationTreeNode[]): DataNode[] {
  return nodes.map((node) => ({
    key: node.id,
    title: (
      <span className="organization-tree-title">
        <span>{node.name}</span>
        <Typography.Text code>{node.code}</Typography.Text>
        <Tag>{node.organization_type_code}</Tag>
      </span>
    ),
    children: toTreeData(node.children),
  }))
}


export function OrganizationTree({
  nodes,
  selectedId,
  onSelect,
  label = "当前有效组织树",
}: OrganizationTreeProps) {
  const data = useMemo(() => toTreeData(nodes), [nodes])
  // Requirement: D-103 — 切换查看时点后组织结构会变化，
  // 用结构键重建树，保证新时点的节点按默认全部展开。
  const structureKey = useMemo(() => collectIds(nodes).join("|"), [nodes])
  if (!data.length) return <Empty description="尚未建立有效组织树" />
  return (
    <Tree
      key={structureKey}
      aria-label={label}
      blockNode
      defaultExpandAll
      selectedKeys={selectedId ? [selectedId] : []}
      treeData={data}
      onSelect={(keys) => {
        const key = String(keys[0] ?? "")
        if (key) onSelect(key)
      }}
    />
  )
}
