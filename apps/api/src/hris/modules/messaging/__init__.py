# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Platform messaging kernel: inbox messages, transactional delivery outbox and SSE push.

Requirement: D-100 — 消息引擎是平台内核级基础服务，业务模块只依赖本模块的稳定接口，
不直接依赖队列实现；一期只交付站内信通道，短信与邮件只保留通道端口。
"""
