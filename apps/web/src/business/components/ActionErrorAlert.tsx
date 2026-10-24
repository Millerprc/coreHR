// Copyright (c) 2026 coreHR 项目贡献者
// 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import { Alert } from "antd"

import { ApiClientError } from "../client"


/**
 * 弹窗内操作失败的统一展示。
 *
 * 为什么单独抽出来（Requirement: D-113）：
 * 面板级错误提示放在**弹窗外面**，而弹窗带遮罩 —— 提交失败时用户看不到任何反馈，
 * 只能关掉弹窗才发现被拒。对「冻结期间禁止补卡」这类**业务规则拒绝**尤其致命：
 * 用户会以为系统坏了，而不是以为自己踩了业务规则。
 *
 * 所以约定：会触发弹窗的操作，错误必须渲染在**弹窗内部**。
 */

/** 考勤期间冻结的错误码（后端 `ATTENDANCE_PERIOD_FROZEN`）。 */
export const FROZEN_PERIOD_CODE = "ATTENDANCE_PERIOD_FROZEN"

/** 请求体校验失败（后端 `REQUEST_VALIDATION_FAILED`，422）。 */
export const VALIDATION_FAILED_CODE = "REQUEST_VALIDATION_FAILED"


export interface ActionErrorInfo {
  /** warning = 业务规则拒绝（系统正常，是这个操作不被允许）；error = 系统/校验失败。 */
  readonly tone: "warning" | "error"
  readonly title: string
  readonly description?: string
}


/** 从 422 的 `details` 里取出逐字段的校验说明。 */
function validationDetailText(error: ApiClientError): string | null {
  const messages = error.details
    .map((item) => {
      if (typeof item !== "object" || item === null || !("message" in item)) return ""
      return String((item as { message: unknown }).message)
    })
    .filter((text) => text.length > 0)
  return messages.length > 0 ? messages.join("；") : null
}


/** 把捕获到的异常翻译成可展示的错误信息。 */
export function describeActionError(caught: unknown, fallback: string): ActionErrorInfo {
  if (caught instanceof ApiClientError) {
    if (caught.code === FROZEN_PERIOD_CODE) {
      return {
        tone: "warning",
        title: caught.message,
        description:
          "该账期已冻结：补录打卡与结果重算都会被拦截。请先在「考勤期间冻结」填写原因解冻，再补录并重算。",
      }
    }
    if (caught.code === VALIDATION_FAILED_CODE) {
      // 422 的顶层 message 只是「请求参数校验失败」，真正的原因在 details 里。
      return { tone: "error", title: validationDetailText(caught) ?? caught.message }
    }
    return { tone: "error", title: caught.message }
  }
  return { tone: "error", title: caught instanceof Error ? caught.message : fallback }
}


interface ActionErrorAlertProps {
  readonly info: ActionErrorInfo | null
  readonly onClose?: () => void
}


export function ActionErrorAlert({ info, onClose }: ActionErrorAlertProps) {
  if (!info) return null
  return (
    <Alert
      closable={onClose ? { onClose } : false}
      type={info.tone}
      showIcon
      title={info.title}
      description={info.description}
      style={{ marginBottom: 16 }}
    />
  )
}
