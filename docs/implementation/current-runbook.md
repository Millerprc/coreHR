# 当前运行手册

本文件是业务一至三阶段首批切片的当前权威入口。

## 启动

```powershell
$env:COREHR_DB_PASSWORD = "本地随机数据库密码"
$env:COREHR_BOOTSTRAP_TOKEN = "一次性随机初始化凭证"
./scripts/dev-business-up.ps1
```

## 访问

- 主管理员工作台：`http://127.0.0.1:5173/business.html`
- API文档：`http://127.0.0.1:8000/docs`

## 完整检查

使用会继承Compose数据库密码的可移植检查脚本：

```powershell
./scripts/check-business-portable.ps1
```

不要把初始化凭证、管理员密码或数据库密码提交到仓库。

当前仍是首批切片：企业导入映射、真实审批链、考勤核算规则和完整管理表单尚未完成。
