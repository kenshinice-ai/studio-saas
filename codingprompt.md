# StudioSaaS Improvement Sprint Prompt (v7 — 部署与试点加固)

Version: v7.0
Date: 2026-07-09
Supersedes: codingprompt.md v6（v6 的 S1–S5、A1–A5、B1–B6 已全部完成并验证：37 pytest / 72 test_cms / 110 isolation 全绿）

## 0. 当前态势

- 代码：v6.6.6 收割完成，三套测试全绿；`api_v1.py` 已 5700+ 行。
- 部署：本地 waitress:8899 + Cloudflare Tunnel `studiosaas` → **https://studiosaas.cc.cd 已上线**（2026-07-09，locally-managed，配置在 `~/.cloudflared/config.yml`）。
- 已修：v1 限流/审计的真实客户端 IP（`_client_ip()` 只信任来自 localhost 的 `CF-Connecting-IP`，audit 落库前做 inet 校验）——没有这个，隧道后任何爬虫都会把公共端点对所有人锁死。
- 部署全案见 `docs/Deployment.md`（本地 → tunnel → AWS 三阶段）。
- git：工作分支 `codex/keep-studio-admin-registration-review` 领先 `main` 约 30 提交。

## 1. 工作规则（沿用 v6）

1. P0 → P1 → P2 → P3 顺序；每项独立 commit + 报告【改动文件/验证结果/风险/下一步】。
2. 改 CMS 界面 = 改 `legacy-root/src/cms-app.jsx` → `bash backend/scripts/build_cms.sh`；禁止直接改 index.html。
3. schema 变更走 migrations（下一编号 0011）。
4. 每项完成后全量验证：pytest（37）、test_tenant_isolation（110）、test_cms（72）、check_ui_escaping。
5. 禁止逐像素图片处理（v5.2.2 OOM 教训）。

---

# P0 — 公网试点安全基线（域名已暴露，本周内完成）

> **状态 2026-07-09：P0-1 ✅ / P0-2 ✅（改为隧道感知 SessionInterface，本地 http 不受影响）/ P0-3 ✅（按需一键备份 + 恢复演练通过）/ P0-4 ✅（用户选择按需模式：START/STOP_STUDIOSAAS_ONLINE.command，不装常驻；LaunchAgent 模板存 `deploy/launchd/`）/ P0-5 ⚠️ 需在 Cloudflare 仪表盘手动配置。**

## P0-1 轮换默认凭据
`admin123456` 现在可从公网尝试登录（有限流但口令本身太弱）。super admin + 全部 demo tenant owner 改为强随机密码，记录到本地密码管理器（不入 git）。`seed_super_admin.py --reset-password` 已支持。

## P0-2 Secure cookie 固化
启动加 `COOKIE_SECURE=1`（server.py 已支持，S13）。写进 `start_studiosaas_local.sh` 与 `.claude/launch.json` 的隧道模式；开启后本机调试也走 https 域名（http://localhost 登录会失效——文档已注明）。

## P0-3 每日自动备份
`backend/scripts/backup_postgres.py` 已有，缺定时。加 launchd plist（每天 03:00，保留 14 份）+ 做一次真实恢复演练，步骤补进 `docs/Admin_Guide.md`。

## P0-4 cloudflared 常驻
当前隧道跑在会话后台进程，重启/睡眠即断。`sudo cloudflared service install`（LaunchDaemon 自启）；试点期间 Mac 需常供电 + `caffeinate` 或系统设置防休眠。

## P0-5 super-admin 面收紧
Cloudflare Zero Trust → Access：给 `studiosaas.cc.cd/super-admin*` 与根路径 `/`（super-admin 别名）加邮箱 OTP 策略。零代码，纯配置。

---

# P1 — 试点期工程质量

## P1-1 配置分层（原 P3-01 提前）
`STUDIOSAAS_ENV=production`：强制 secure cookie、拒绝缺省/弱 secret、访问日志结构化落文件（按天轮转）。这是 AWS 的前置件。

## P1-2 Playwright 浏览器冒烟（原 P1-06，唯一未完成的 P1）
关键链路：家长注册 → studio-admin 审核通过 → CMS 签到 → 充值 → 余额正确。跑在真实浏览器，覆盖 sw.js/PWA 行为（curl 冒烟测不到的层）。

## P1-3 邮件真实发送
notifications 现为 console backend。接 SMTP（试点期用任意事务邮件服务，AWS 后换 SES），注册确认/审批结果真的送达家长邮箱。含退订/频控考虑。

## P1-4 sw.js 多租户 PWA 残留复核（原 P2-02）
S1 已收紧作用域并注销根作用域注册；复核 manifest.json / manifest-student.json / sw.js 里最后的 "Let's Paint" 残留与图标、start_url 是否按租户品牌化。

---

# P2 — AWS 就绪（结构性，试点稳定后）

## P2-1 拆分 api_v1.py（原 P2-01）
5700 行按 target-architecture 模块边界拆（auth/tenant/student/course/credit/attendance/portfolio/media/platform）。纯移动不改行为，拆一块跑一次全量测试。

## P2-2 S3 媒体分支（原 P3-03）
media service 按 `storage_provider` 切换 boto3/S3，本地文件回退保留；缩略图生成路径同步适配。迁移脚本：本地 media/ → S3 同步 + storage_key 重写。

## P2-3 Docker + CI（原 P3-02）
Dockerfile（python-slim + waitress）+ compose（app + postgres）；GitHub Actions：push → pytest + verify_local 摘要 + 镜像构建。部署脚本见 Deployment.md §3.2。

## P2-4 分支收敛
`codex/keep-studio-admin-registration-review` 合并回 `main`（快进或 PR），此后 main 作为部署基准分支。

---

# P3 — 产品功能（v5 B 级遗留，按租户反馈排期）

- 费用提醒运营位（低余额学员列表 + 批量催费）——A5 已有单日版，这里是全员视角。
- 生日/流失运营看板（30 天未上课、生日当月）。
- staff 子账号（memberships 已支持 staff 角色，缺 UI 与权限面）。
- 备份对接 UI（studio-admin 里一键导出全部数据——CSV 导出已有，补打包）。
- C 级门户联动（公开作品墙 / SEO / 家长 Dashboard 增强）继续存档不排期。

---

## 推荐执行顺序

**本周（公网已开）**：P0-1 → P0-2 → P0-4 → P0-3 → P0-5
**试点期并行**：P1-1 → P1-3 → P1-2 → P1-4
**AWS 决定后**：P2-4 → P2-1 → P2-2 → P2-3 → 按 `docs/Deployment.md` §3 迁移

## 完成定义

- P0 全部完成 = 公网试点可以放心邀请真实家长/学员使用。
- P1 全部完成 = 有浏览器级回归保障 + 真实邮件闭环，具备 AWS 迁移前置条件。
- P2 全部完成 = 代码结构与基础设施达到 AWS 单实例生产形态。
