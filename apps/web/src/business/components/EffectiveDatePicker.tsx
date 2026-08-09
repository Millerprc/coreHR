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
