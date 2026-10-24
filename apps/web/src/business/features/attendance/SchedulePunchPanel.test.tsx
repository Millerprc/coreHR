// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { SchedulePunchPanel } from "./SchedulePunchPanel"


const page = (items: readonly unknown[]) => ({ items, total: items.length, limit: 200, offset: 0 })

const FROZEN_MESSAGE = "打卡业务日 2026-08-10 处于考勤冻结期间（2026-08-01 至 2026-08-31），不允许补录打卡，需先填写原因并解冻"


/** 打开 AntD Select 的下拉并选中一项。

 * AntD 6 的 Select 结构是 `.ant-select > .ant-select-content > input.ant-select-input`，
 * 下拉的 mouseDown 触发器挂在 `.ant-select-content` 上；直接对 input 派发不展开。
 */
async function selectOption(inputId: string, optionText: string): Promise<void> {
  const input = document.getElementById(inputId) as HTMLElement
  const trigger = input.closest(".ant-select-content") ?? input
  fireEvent.mouseDown(trigger)
  fireEvent.click(await screen.findByText(optionText))
}


describe("SchedulePunchPanel", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("shows the frozen-period rejection inside the punch dialog", async () => {
    // Requirement: D-113 —— 冻结账期内的补录被后端拒绝（409 ATTENDANCE_PERIOD_FROZEN），
    // 前端必须把拒绝原因**渲染在弹窗内部**：弹窗带遮罩，弹窗外的提示用户看不到。
    const punches: unknown[] = []
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (init?.method === "POST" && path.includes("/attendance/punches")) {
        punches.push(path)
        return Response.json(
          {
            code: "ATTENDANCE_PERIOD_FROZEN",
            message: FROZEN_MESSAGE,
            details: [{ freeze_id: "freeze-1", freeze_type: "monthly", date_from: "2026-08-01", date_to: "2026-08-31" }],
            trace_id: "trace-freeze",
          },
          { status: 409 },
        )
      }
      if (path.includes("/employment-options")) return Response.json(page([{
        id: "employment-1",
        person_id: "person-1",
        employee_number: "993201",
        display_name: "合成打卡员工甲",
        employee_type_code: "REGULAR",
        status: "active",
      }]))
      if (path.includes("/shifts?")) return Response.json(page([{
        id: "shift-1",
        code: "DAY",
        name: "白班",
        start_time: "09:00:00",
        end_time: "18:00:00",
        crosses_midnight: false,
        rule_set_id: "rule-1",
        rule_set_version: 1,
        rule_snapshot: {},
        status: "active",
      }]))
      return Response.json(page([]))
    }))

    render(<SchedulePunchPanel token="synthetic-token" canAdmin />)

    fireEvent.click(await screen.findByRole("button", { name: "手工补录" }))

    // 员工劳动关系（AntD Select；选项文案是「姓名 (工号) · 员工类型」）
    await selectOption("employment_id", "合成打卡员工甲 (993201) · REGULAR")

    // 本地时间（datetime-local）
    fireEvent.change(document.getElementById("punched_at") as HTMLElement, {
      target: { value: "2026-08-10T09:00" },
    })

    // 打卡类型（AntD Select）
    await selectOption("punch_type", "上班")

    // AntD 会在两个汉字的按钮文案中间自动插空格，所以用正则匹配。
    fireEvent.click(screen.getByRole("button", { name: /保\s*存/ }))

    await waitFor(() => expect(punches).toHaveLength(1))

    // 拒绝原因必须出现在弹窗里（不是只在面板底部）
    const dialog = await screen.findByRole("dialog")
    expect(dialog).toHaveTextContent(FROZEN_MESSAGE)
    expect(dialog).toHaveTextContent("该账期已冻结")
    // 弹窗不能被关掉 —— 用户要看到原因才能决定下一步
    expect(screen.getByRole("dialog")).toBeInTheDocument()
  }, 15_000)
})
