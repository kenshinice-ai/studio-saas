# 2026-08-17 Xero X2 轮（开轮）

> 状态：开轮。前一轮 v10.8.0 已上线并完成生产实点验收（时间线/月结单/记录提醒三项，
> 证据见 2026-08-16-v10.8.0-round.md 与本文件下方）。

## 生产实点验收（2026-08-17，showcase 演示租户）

- 学员时间线：Ana Bianchi 倒序 4 条扣课 + 1 条充值（+16 课时 $585），与余额 12 自洽。✔
- 月结单：Chen 一家 2026-08：期初 $605 → INV-0006 +$40 → cash −$15 → bank −$25 → 期末 $605，
  守恒成立且期末 == 该户当前未结。✔
- 记录提醒：INV-0003 记录备注「v10.8.0 验收测试：演示数据…」，toast 确认，
  事件即时出现在「这张单发生过什么」。✔（演示租户数据，允许写入）

## X2 范围（沿 Full_System_Audit_Plan Batch F）

OAuth2（auth code + PKCE）连接流：集成页「连接 Xero」→ Xero 授权 → 回调 →
per-tenant token 加密存储 + 自动 refresh；先只接 Xero Demo Company；连接/断开/过期自愈
三条验收。不做推送（X3）、不做双向。

## 等 Lee 的硬前置（代码可先行，联调必须有它们）

1. 在 developer.xero.com 用自己的 Xero 账号建一个 **Web app**（OAuth 2.0 auth code）：
   - redirect URI 填 `https://pwestudio.online/xero/callback`（本地联调另加 `http://localhost:8100/xero/callback`）。
   - scopes：`openid profile email accounting.transactions accounting.contacts offline_access`。
2. 把 Client ID / Client Secret 放进生产 env（`XERO_CLIENT_ID` / `XERO_CLIENT_SECRET`，
   路径照 `deploy/aws` 现有 env 惯例）——**由 Lee 自己放，不要把 secret 发进对话**。
3. Xero 账号里启用 Demo Company（AU）作为测试组织。

代码侧下一步：token 存储表迁移（加密 at rest）、/xero/connect 与 /xero/callback 路由、
集成页按钮与状态、refresh 自愈；无真实凭据时以测试桩过合同测试。

## 实现闭环（v10.9.0，待发布证据）

- 迁移 `0045_xero_oauth_state.sql`（PKCE verifier 服务器侧暂存，state 存哈希、单次消费、10 分钟过期；tenant_archive 已登记豁免）。
- `services/xero_oauth.py`：begin/finish/ensure_access_token/disconnect/connection_status；Fernet 加密落库；stdlib urllib；配置缺失是命名状态不是空白。
- 路由：`/integrations/xero/connect-url|disconnect|refresh-check`（integrations:manage）+ 根级 `/xero/callback`（state 即租户解析，取消/失败都回集成页带原因）。
- UI：集成页连接卡（未配置/未连接/已连接/过期四态、两击确认断开、令牌自愈测试按钮）；Step 2 接真连接。
- `deploy/aws/set_xero_env.sh`：凭据只走一条 SSH 的 stdin（不进 argv/history/仓库），token key 服务器生成，改完走 lightsail_ctl up。
- 依赖：backend/requirements.txt + cryptography>=42,<46。
- 测试：`test_xero_oauth.py` 7 项全过；全量 pytest 2758 passed / 7 skipped。

## 发布证据（2026-08-17 闭环）

- 第一次部署失败并自动回滚（10.8.0 全程健康）：requirements.lock 缺 cryptography，容器 import 崩、深健康 90s 超时。修复 + 新增 lock 漂移台账测试后二次部署成功。
- Source：release commit `9c9c851` 后接 lock 修复 commit `85b13b498`；main == origin/main。
- Package/SaaS：SHA-256 `b445de62cf9cd555eb9b53a8a1f2b677b678311babe3fb1a85e1242eb33f06fb`；Package/Edition：SHA-256 `442c941580c76ecd0ce82993dd3a6e38bb5276932574c16ca83eb45519cd01e8`（重建于 lock 修复后，guard 三方一致）。
- Production：`Deployed: PWE-StudioSaaS-aws-10.9.0`，deep health `appVersion=10.9.0`、`db=ok`；迁移 0045 已应用。
- 浏览器验收（生产）：集成页如实显示「服务器未配置，缺 XERO_CLIENT_ID / XERO_CLIENT_SECRET / STUDIOSAAS_XERO_TOKEN_KEY」并指向 set_xero_env.sh。
- 待 Lee：跑 set_xero_env.sh 放凭据 → 浏览器里完成 Xero 登录与 Allow（Demo Company）→ 我做 连接/自愈/断开重连 三项验收。
