// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

// Requirement: D-103 / D-091 — 组织架构页与组织详情页共用同一套「查看时点」口径：
// 当天即当前时点（请求不带 as_of，后端返回当前组织树），历史日期即历史时点（请求带 as_of）。
// Requirement: D-013 — 只允许查看当前与历史时点，未来时点由后端拒绝。


export function localDate(): string {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}


/** 当前时点返回 undefined：请求不带 as_of，由后端返回当前组织树。 */
export function treeAsOf(viewDate: string): string | undefined {
  return viewDate === localDate() ? undefined : viewDate
}


/** 界面上显示的查看时点文案：当前或截至某日。 */
export function viewDateText(viewDate: string): string {
  return viewDate === localDate() ? "当前" : `截至 ${viewDate}`
}
