import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it } from "vitest"

import BusinessApp from "./BusinessApp"


describe("BusinessApp login", () => {
  beforeEach(() => sessionStorage.clear())

  it("requires administrator credentials before business data is shown", () => {
    render(<BusinessApp />)

    expect(screen.getByText("coreHR 管理员工作台")).toBeInTheDocument()
    expect(screen.getByLabelText("账号")).toBeInTheDocument()
    expect(screen.getByLabelText("密码")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /登\s*录/ })).toBeInTheDocument()
  })
})
