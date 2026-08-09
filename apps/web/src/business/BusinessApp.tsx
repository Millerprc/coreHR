import { Alert, Button, Card, Form, Input, Skeleton, Typography } from "antd"
import { useCallback, useEffect, useState } from "react"

import { AppShell } from "./AppShell"
import {
  clearToken,
  getProfile,
  login,
  storedToken,
  storeToken,
} from "./client"
import type { UserProfile } from "./types"
import "./business.css"


function LoginPanel({ onLoggedIn }: { readonly onLoggedIn: (token: string) => void }) {
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(values: { username: string; password: string }): Promise<void> {
    setSubmitting(true)
    setError(null)
    try {
      const result = await login(values.username, values.password)
      storeToken(result.access_token)
      onLoggedIn(result.access_token)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "登录失败")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <Card className="login-card" variant="borderless">
        <div className="login-brand">C</div>
        <Typography.Title level={2}>coreHR 管理员工作台</Typography.Title>
        <Typography.Paragraph type="secondary">第一批仅向 HR 系统主管理员开放</Typography.Paragraph>
        {error && <Alert type="error" showIcon message={error} />}
        <Form layout="vertical" onFinish={(values) => void submit(values)} requiredMark={false}>
          <Form.Item label="账号" name="username" rules={[{ required: true, message: "请输入账号" }]}>
            <Input autoComplete="username" size="large" />
          </Form.Item>
          <Form.Item label="密码" name="password" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password autoComplete="current-password" size="large" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={submitting} block size="large" autoInsertSpace={false}>登录</Button>
        </Form>
      </Card>
    </main>
  )
}


function AuthenticatedApp({
  token,
  onSignedOut,
}: {
  readonly token: string
  readonly onSignedOut: () => void
}) {
  const [user, setUser] = useState<UserProfile | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      setUser(await getProfile(token))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "账号信息加载失败")
    }
  }, [token])

  useEffect(() => {
    void load()
  }, [load])

  if (error) {
    return (
      <main className="session-error-page">
        <Alert type="error" showIcon message="无法进入管理员工作台" description={error} />
        <Button onClick={() => void load()}>重试</Button>
        <Button onClick={onSignedOut}>重新登录</Button>
      </main>
    )
  }
  if (!user) return <main className="session-loading"><Skeleton active paragraph={{ rows: 10 }} /></main>
  return <AppShell token={token} user={user} onSignedOut={onSignedOut} />
}


export default function BusinessApp() {
  const [token, setToken] = useState<string | null>(() => storedToken())

  function signedOut(): void {
    clearToken()
    setToken(null)
  }

  return token
    ? <AuthenticatedApp token={token} onSignedOut={signedOut} />
    : <LoginPanel onLoggedIn={setToken} />
}
