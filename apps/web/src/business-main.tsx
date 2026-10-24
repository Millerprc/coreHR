import { ConfigProvider } from "antd"
import zhCN from "antd/locale/zh_CN"
import React from "react"
import ReactDOM from "react-dom/client"

import BusinessApp from "./business/BusinessApp"

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          // Requirement: ORG-PROT-001 — 已批准框架页使用Ant Design主蓝与紧凑圆角Token。
          colorPrimary: "#1677ff",
          borderRadius: 6,
          colorBgLayout: "#f5f7fa",
          fontFamily: '"Noto Sans SC", "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
        },
      }}
    >
      <BusinessApp />
    </ConfigProvider>
  </React.StrictMode>,
)
