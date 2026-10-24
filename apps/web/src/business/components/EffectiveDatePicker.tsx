// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { Input, Space, Typography } from "antd"


interface EffectiveDatePickerProps {
  readonly value: string
  readonly onChange: (value: string) => void
  readonly label?: string
}


export function EffectiveDatePicker({
  value,
  onChange,
  label = "查看日期",
}: EffectiveDatePickerProps) {
  return (
    <Space orientation="vertical" size={4} className="effective-date-picker">
      <Typography.Text strong>{label}</Typography.Text>
      <Input
        aria-label={label}
        type="date"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </Space>
  )
}
