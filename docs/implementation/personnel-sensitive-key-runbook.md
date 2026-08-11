# 人员敏感字段密钥运行手册

> 依据：[ADR-0004](../adr/ADR-0004-personnel-sensitive-field-protection.md)
> 范围：本机、测试及后续生产环境的人员敏感字段密钥生成、注入、轮换与恢复

## 1. 约束

- 加密密钥和检索密钥必须分别随机生成32字节，不得复用。
- 真实密钥不得写入仓库、数据库、镜像、日志、截图、工单或聊天。
- `COREHR_PERSONNEL_ENCRYPTION_KEYS`是JSON密钥环；`COREHR_PERSONNEL_ACTIVE_KEY_VERSION`指定新写入版本；`COREHR_PERSONNEL_SEARCH_KEY`用于HMAC精确检索。
- 密钥缺失或无效时，非敏感功能仍可运行，但所有敏感写入和明文Reveal失败关闭。

## 2. 本机生成与注入

PowerShell仅在当前进程生成并注入，不要回显变量值：

```powershell
$personDataKey = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
$personSearchKey = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
$env:COREHR_PERSONNEL_ENCRYPTION_KEYS = (@{v1 = $personDataKey} | ConvertTo-Json -Compress)
$env:COREHR_PERSONNEL_ACTIVE_KEY_VERSION = "v1"
$env:COREHR_PERSONNEL_SEARCH_KEY = $personSearchKey
./scripts/dev-business-up.ps1
```

Linux或macOS：

```bash
person_data_key="$(openssl rand -base64 32 | tr -d '\n')"
person_search_key="$(openssl rand -base64 32 | tr -d '\n')"
export COREHR_PERSONNEL_ENCRYPTION_KEYS="{\"v1\":\"${person_data_key}\"}"
export COREHR_PERSONNEL_ACTIVE_KEY_VERSION="v1"
export COREHR_PERSONNEL_SEARCH_KEY="${person_search_key}"
./scripts/dev-business-up.sh
```

本机重启前必须从受控密码库重新注入同一组密钥；重新随机生成会使已有密文无法读取。变量退出当前会话后应清除。

## 3. 轮换

1. 在受控密钥库生成新32字节加密密钥，旧密钥保持不变。
2. 将新版本加入密钥环，例如同时保留`v1`和`v2`。
3. 把当前写入版本切换为`v2`并重启服务，先验证新记录使用`v2`且旧记录仍可读取。
4. 使用专用批次逐页锁定并重加密旧记录；每条成功后才提交，失败记录保留旧版本并进入报告。
5. 数据库扫描确认没有旧版本引用、完成备份恢复演练后，才从运行密钥环移除旧版本。

检索密钥轮换会改变所有HMAC摘要，不与加密密钥轮换合并执行。它需要停写或双摘要迁移、完整重建唯一约束及重复冲突报告，首版不提供在线自动轮换。

## 4. 备份与恢复

- 密钥备份必须与数据库备份分离，分别限制访问，并至少保留两个受控副本。
- 恢复演练使用隔离环境：先恢复数据库，再注入对应版本密钥，验证抽样密文、摘要查询和审计。
- 密钥丢失不可通过生成新密钥、置空字段或关闭认证来恢复。必须停止敏感访问并按安全事件处理。

## 5. 只读健康核对

健康核对只能返回以下非秘密信息：是否完整配置、当前写入版本、可用版本数量及数据库各版本记录数。不得返回Base64密钥、密文、nonce、摘要样本或解密测试值。
