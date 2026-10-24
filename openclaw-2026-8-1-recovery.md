# OpenClaw 2026.8.1 升级后启动失败 — 修复复盘

> 记录一次本地 OpenClaw 升级导致 gateway 起不来的完整修复过程，给后续接手 / 其他 agent 参考。
> 修复时间：2026-08-31 晚
> 操作系统：Windows 11，PowerShell

---

## 一、结论

OpenClaw 2026.8.1 启动失败原因是 **session store 格式不兼容**（老 `sessions.json` → 新 sqlite）。
核心修复由 `openclaw doctor --fix` 完成，把 sessions 迁到 `state/openclaw.sqlite` 和 `agents/main/agent/openclaw-agent.sqlite`。
之后遇到 **plugin SDK 不兼容** 和 **`openclaw plugins enable/disable` 卡死** 两个新坑，靠 `config set/unset` + `schtasks` 绕过。

最终 gateway 在 `ws://127.0.0.1:18789` 正常监听，dashboard `http://127.0.0.1:18789/` 可访问。
代价：**4 个 plugin（feishu / deepseek / searxng / tavily）临时 disabled**，yuanbao 整体移除。

---

## 二、环境

- OpenClaw 2026.8.1 (ea80657)
- 状态目录：`C:\Users\83289\.openclaw\`
- CLI 入口：`C:\Users\83289\AppData\Roaming\npm\openclaw.ps1` → `node_modules\openclaw/openclaw.mjs`
- Gateway 端口：18789（仅 loopback）
- 主 agent：`main`，model `minimax-portal/MiniMax-M3`
- Dashboard：`http://127.0.0.1:18789/`
- Gateway 启动方式：Windows Scheduled Task `OpenClaw Gateway`

---

## 三、根因

```
Legacy session store requires migration:
C:\Users\83289\.openclaw\agents\main\sessions\sessions.json.
Run "openclaw doctor --fix" against the same state/config before starting OpenClaw.
```

- OpenClaw 2026.8.1 不再支持老的 `sessions.json`，要求迁到 sqlite。
- 此外 `exec-approvals.json` 也是 legacy v1 格式，doctor 一起要清。

---

## 四、修复时间线（7 步）

### 1. 备份（不改先备份）

```powershell
Copy-Item $env:USERPROFILE\.openclaw\agents\main\sessions\sessions.json `
         $env:USERPROFILE\.openclaw\agents\main\sessions\sessions.json.bak-20260831-204133
Rename-Item $env:USERPROFILE\.openclaw\exec-approvals.json `
           $env:USERPROFILE\.openclaw\exec-approvals.json.legacy-v1
```

### 2. 跑 doctor 迁移

```powershell
openclaw doctor --fix --non-interactive --yes
```

- 180s 被超时杀但**核心工作已完成**。
- sessions.json → `state/openclaw.sqlite`（3.7MB，state-db v1 → v15）
- agent-db v1 → v19，6 条 session 全部迁到 `agents/main/agent/openclaw-agent.sqlite`

### 3. 升级所有 plugin

```powershell
openclaw plugins update --all --accept-capabilities --acknowledge-install-policy-warning
```

- clickclack / deepseek / feishu / **yuanbao 2.15.0 → 2.18.2** / searxng / tavily 全部到 2026.8.1

### 4. 移除 yuanbao（SDK 不兼容）

yuanbao 2.18.2 找不到 `openclaw/plugin-sdk/command-gating`，整体移除：

```powershell
openclaw plugins disable openclaw-plugin-yuanbao
openclaw config unset channels.yuanbao
```

### 5. 绕开 `plugins enable` 卡死

**`openclaw plugins enable feishu` 在 clickclack 之后卡住不返回**，连续 2 次都被迫 timeout 杀掉。
卡死后还会导致后续 CLI 跟 gateway 通讯失败。

绕开方案：直接改配置文件。

```powershell
openclaw config set plugins.entries.searxng.enabled false
openclaw config set plugins.entries.tavily.enabled  false
openclaw config set plugins.entries.deepseek.enabled false
openclaw config set plugins.entries.feishu.enabled false
```

### 6. 启动 gateway（绕开 `gateway restart`）

`openclaw gateway restart` 60s 超时也卡，改用 schtasks 拉起：

```powershell
schtasks /Run /TN "OpenClaw Gateway"
Start-Sleep -Seconds 80
Get-NetTCPConnection -LocalPort 18789 -State Listen
```

### 7. 验证

```powershell
openclaw health                      # ok
openclaw gateway status --deep      # bind=loopback / port=18789 / Service=Scheduled Task (running)
```

---

## 五、关键变通方案

| 现象 | 官方命令 | 变通 |
|------|---------|------|
| `plugins enable <id>` 卡死 | `openclaw plugins enable <id> --accept-capabilities` | `openclaw config set plugins.entries.<id>.enabled false` |
| `gateway restart` 60s 超时 | `openclaw gateway restart` | `schtasks /Run /TN "OpenClaw Gateway"` + 手动 sleep 80s |
| doctor 之前 legacy 格式阻塞 | 无 | 把 `exec-approvals.json` 改名 `.legacy-v1`（保留回滚） |
| yuanbao SDK 不兼容 | 等新版 | 整体 disable + `config unset channels.yuanbao` |

---

## 六、当前状态快照

### 进程 / 端口
- Gateway：✅ running，ws://127.0.0.1:18789，dashboard http://127.0.0.1:18789/
- Health 警告：`event_loop degraded 31s`（启动后抖动，可忽略）

### Plugin 状态
| Plugin | 状态 |
|--------|------|
| minimax | ✅ enabled |
| clickclack | ✅ enabled（not configured） |
| feishu | ⚠️ disabled（plugin enable 卡死） |
| deepseek | ⚠️ disabled（同上） |
| searxng | ⚠️ disabled（同上） |
| tavily | ⚠️ disabled（同上） |
| yuanbao | ❌ 整体移除（SDK 不兼容，等新版） |

### Session store
- `state/openclaw.sqlite` v15
- `agents/main/agent/openclaw-agent.sqlite`，6 entries
- 老 `sessions.json` 已备份未删

### 备份文件
- `~/.openclaw/agents/main/sessions/sessions.json.bak-20260831-204133`（197943 bytes）
- `~/.openclaw/exec-approvals.json.legacy-v1`（182 bytes）

### doctor 警告（非阻塞）
- searxng / tavily disabled-in-config
- gateway loopback bind
- `openclaw.json` 含明文 API key（tavily / minimax）— **建议未来迁 secrets，但 doctor 不阻塞**
- feishu `groupPolicy=open`（业务策略，非技术问题）

---

## 七、未解决 / 待跟进

1. **`plugins enable` 卡死根因未定位**
   猜测：enable 触发立即注册 / 网络 IO，跟 clickclack 抢资源。
   建议下次先 disable clickclack 再单独 enable feishu，观察。

2. **yuanbao 2.18.2 SDK 不兼容**
   等 yuanbao 发新版对齐 OpenClaw 2026.8.1 SDK 重新引入。

3. **19/65 stock plugins 未成功 index**
   doctor 输出 `Plugin registry refreshed: 46/65 enabled plugins indexed`。
   19 个未 index 的不阻塞 gateway，但建议下次升级后查 `~/.openclaw/logs/`。

4. **明文 secrets 迁移**
   `tavily.webSearch.apiKey` 和 minimax API key 在 `openclaw.json` 明文。
   OpenClaw 有 secrets subsystem，建议未来用 `openclaw secrets set` 迁。

---

## 八、给其他 agent 的注意事项

1. **升级前先备份 `~/.openclaw/`**（至少 `openclaw.json` + `agents/main/sessions/` + `exec-approvals.json`）
2. **`openclaw doctor --fix` 跑前确认能等 3 分钟**，必要时后台跑 + 写日志
3. **`openclaw plugins enable/disable` 在 clickclack 之后可能卡死**，卡死后 CLI 跟 gateway 通讯也会断；
   卡死时直接 `schtasks /Run` 重拉 gateway 即可恢复 CLI
4. **不要用 `openclaw gateway restart`**——用 schtasks
5. **新版本 plugin 升级后先看 SDK import 路径**，对不上就 disable + 移除 channel config
6. **飞书 channel 在 `openclaw.json` 用的是新 schema**（`streaming.mode` / `streaming.block.enabled`），
   旧 schema 文档别用
7. 升级完成立刻跑 `openclaw health` + `openclaw gateway status --deep` 双确认
