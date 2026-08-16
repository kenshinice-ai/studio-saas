# PWE Studio v9.8.4 — 套餐变更安全与 Platform Admin 交互闭环

> 当前阶段：v9.8.4 已完成套餐升级/降级的影响预览与双重确认、内容保留保护、Platform Admin 快速查看与集中操作、中英文套餐命名规范，并已完成完整门禁、双模式打包、分支推送、生产部署和公网验收。生产运行部署代码 commit `c0e344aa82a4a2358c0052123ba7b6dd633fb057`；本节以下为本次闭环证据。

## v9.8.4 修复范围与验收

- 套餐变更在保存前读取服务端影响摘要，明确列出会变化的价格/额度/功能、继续保留的网站与业务内容，以及必须通知工作室的事项；未勾选“已检查影响并会通知”时，API 以结构化 `409` 拒绝保存。
- 套餐更新在租户行锁内合并商业字段，保留未提交的品牌、官网、首屏、FAQ、作品、主题、消息模板、学员、课程、报名、媒体和审计数据；接受的变更写入审计记录。
- Platform Admin 的工作室与套餐行点击直接打开只读 Inspector；编辑、生命周期、支持、归档和删除统一收进中间列表的 `操作`，右侧只负责快速查看。
- 套餐名称统一为 Starter / 入门版、Studio / 工作室版、Growth / 成长版；API code 保持 `starter` / `studio` / `growth` 不变。

## v9.8.4 最终发布证据（2026-08-11）

| 层级 | 已验证事实 |
|---|---|
| Source | 分支 `codex/v9.8.2-showcase-content-recovery` 已推送到 `origin`；部署代码 commit `c0e344aa82a4a2358c0052123ba7b6dd633fb057`；`VERSION=9.8.4`。部署后文档闭环提交只更新 README 与 handoff，不改变运行代码。 |
| Local gates | `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh` 全部通过：完整 pytest `1982 passed, 8 skipped`、CMS smoke `73 passed`、PostgreSQL 迁移与安全媒体衍生图检查、租户隔离 `237 passed`；`git diff --check` 通过。 |
| Package | SaaS `dist/PWE-StudioSaaS-aws-9.8.4.tar.gz` SHA-256 `b323ac360b4f13386b6a76d591ac90f773371777aaa340b355176642a60f76ae`；Edition `dist/PWE-Studio-Edition-9.8.4.tar.gz` SHA-256 `b9317a92374f58e17b681206029704f8493a59d046704d32a68a722c04b506c1`。两个包通过 checksum、`BUILD_INFO`、入口和排除项检查，均对应 commit `c0e344aa82a4a2358c0052123ba7b6dd633fb057`，模式分别为 `saas` / `standalone`。 |
| Production | `/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.8.4`，镜像 `studiosaas:9.8.4`；容器 healthy；公网 deep health 为 `appVersion=9.8.4`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；磁盘可用 `46.62 GB`；HTTP→HTTPS `301`，HTTPS `200`、TLS 校验 `0`、HTTP/2。 |
| Migration / recovery | 生产启动已应用 `0029_showcase_plan_values_and_states.sql`；生产媒体安全检查为 `Generated variants: 0`；套餐变更不会删除 Ruby Studio 或其他租户的作品/品牌/业务数据。 |
| Backup | 部署切换自动生成 `/data/backups/postgres/studiosaas_studiosaas_20260811T035703Z.dump` 与对应 manifest，以及 `/data/backups/volumes/pwestudio-volumes-20260811T035705Z.tar.gz`。 |
| Public edge / media | 根站、中文手册、Ruby Studio 门户 / timetable / CMS / Studio Admin、双语 Release Notes、Platform Admin 均返回 `200`；版本化 `ui-common.js` 与 `admin-i18n.js` 的本地/生产 SHA-256 一致且带 immutable 缓存；代表性 Ruby 媒体返回 `200 image/jpeg`，带 ETag 的条件请求返回 `304`。 |
| Logs | 生产 app-only 日志的当前请求均为健康的 `200/304`；未出现当前 Traceback / Exception / Fatal / Error。旧探索命令产生的数据库日志未作为当前应用错误引用。 |
| Browser | 应用内 Browser 未使用生产凭据、未执行生产写操作；本地仅使用隔离测试数据库完成真实登录验收：桌面确认租户/套餐行点击为 Quick view、`操作` 打开集中动作，套餐编辑显示“将发生变化/将继续保留/需要通知工作室”和强制勾选；390×844 手机视口确认 Platform Admin 无横向溢出（`scrollWidth=clientWidth=390`），并完成 viewport reset。 |

本次未修改或打包未跟踪的 `docs/sales/` 路演资料已保留，不纳入提交或发布包。

---

