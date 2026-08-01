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
          colorPrimary: "#1769aa",
          borderRadius: 10,
          colorBgLayout: "#f3f6fa",
        },
      }}
    >
      <BusinessApp />
    </ConfigProvider>
  </React.StrictMode>,
)
