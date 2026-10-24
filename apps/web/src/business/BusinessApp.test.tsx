import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it } from "vitest"

import BusinessApp from "./BusinessApp"


describe("BusinessApp", () => {
  beforeEach(() => sessionStorage.clear())

  it("requires an administrator login before showing business data", () => {
    render(<BusinessApp />)

    expect(screen.getByText("coreHR 管理员工作台")).toBeInTheDocument()
    expect(screen.getByLabelText("账号")).toBeInTheDocument()
    expect(screen.getByLabelText("密码")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "登录" })).toBeInTheDocument()
  })
})
