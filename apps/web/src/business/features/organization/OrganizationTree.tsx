import { Empty, Tag, Tree, Typography } from "antd"
import { useMemo } from "react"
import type { DataNode } from "antd/es/tree"

import type { OrganizationTreeNode } from "./types"


interface OrganizationTreeProps {
  readonly nodes: readonly OrganizationTreeNode[]
  readonly selectedId: string | null
  readonly onSelect: (organizationId: string) => void
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


export function OrganizationTree({ nodes, selectedId, onSelect }: OrganizationTreeProps) {
  const data = useMemo(() => toTreeData(nodes), [nodes])
  if (!data.length) return <Empty description="尚未建立有效组织树" />
  return (
    <Tree
      aria-label="当前有效组织树"
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
