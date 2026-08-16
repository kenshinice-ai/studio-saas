# PWE Studio v9.8.5 — 作品展示手册与 Platform Admin 操作上下文发布闭环

> 当前阶段：v9.8.5 已完成工作室作品展示手册的中英文重写、套餐关联作品规则与媒体链接说明、手册截图资源、移动端导航修复，以及 Platform Admin 高频操作上下文与套餐/租户编辑影响预览；已完成完整门禁、双模式打包、分支推送、生产部署和公网验收。生产运行部署代码 commit `bcd4f1ba6ed2dcd2073a1a09b0ed5cf907f8a9ab`；本节记录本轮最终证据。

## v9.8.5 修复范围与验收

- 用户手册的 Studio Showcase 章节改为中英文一致的操作说明，明确工作室作品与学员作品边界，并补充图片上传、YouTube / Vimeo / Bilibili 视频链接识别与识别失败提示。
- 手册固定记录 v9.8.x 作品额度规则：Starter `15`、Studio `60`、Growth `150`；最多保存 `500` 条、每页 `12` 条、最多 `8` 个分类。分页大小不再被描述为总量上限。
- 更新前台与后台截图为本地合成示例，补齐中英文、桌面/移动端手册资源，并修复移动端固定导航遮挡标题的问题；截图不冒充生产租户数据。
- Platform Admin 的 `Actions/操作` 保持高频租户与套餐命令；行点击仍打开快速查看，选择具体操作后才在右侧显示影响、保留内容、通知对象和下一步确认。工作室编辑与套餐编辑均展示保存前影响审查，API 继续执行双重确认。

## v9.8.5 最终发布证据（2026-08-11）

| 层级 | 已验证事实 |
|---|---|
| Source | 分支 `codex/v9.8.2-showcase-content-recovery` 已推送到 `origin`；`VERSION=9.8.5`；部署代码 commit `bcd4f1ba6ed2dcd2073a1a09b0ed5cf907f8a9ab`。本轮包含另一任务已完成的用户手册更新；未跟踪的 `docs/sales/` 资料未纳入发布。 |
| Local gates | `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh` 通过；完整 pytest `1986 passed, 8 skipped`；租户隔离 `237 passed, 0 failed`；`git diff --check`、inline-script 检查和 asset manifest 检查均通过。 |
| Package | SaaS `dist/PWE-StudioSaaS-aws-9.8.5.tar.gz` SHA-256 `1bc99fd90d5e40fddbc598e5fd01aa589b1eecedaff9dd27d92c2f566cdbef9d`；Edition `dist/PWE-Studio-Edition-9.8.5.tar.gz` SHA-256 `68409b931c76b8aef72cc66e391a6f954303cda4239ef64bc32a72876b4de4b3`。两个包的 `BUILD_INFO` 均对应 commit `bcd4f1b`，模式分别为 `saas` / `standalone`，并通过发布包校验。 |
| Production | `/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.8.5`，镜像 `studiosaas:9.8.5`；容器 healthy；公网 deep health 为 `appVersion=9.8.5`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；磁盘可用约 `46.44 GB`；HTTP→HTTPS `301`，HTTPS `200`、TLS 校验 `0`、HTTP/2。 |
| Backup / migration | 部署前后均有逻辑库与卷备份；本轮最新逻辑库备份为 `studiosaas_studiosaas_20260811T053608Z.dump`，卷归档为 `pwestudio-volumes-20260811T053609Z.tar.gz`，manifest 同时存在。启动日志显示数据库已是最新，迁移包含 `0029_showcase_plan_values_and_states.sql`；媒体衍生图检查为 `Generated variants: 0`。 |
| Public routes | 根站、中文手册、展示门户、timetable、CMS、Studio Admin、register、双语 Release Notes 与 Platform Admin 均返回 `200`。用户提到的 Ruby Studio 公共作品 API 返回 `total=12`、`3` 个分类且全部为 `active`；`lets-paint-showcase` 示例租户 API 当前为 `total=0`，因此手册中的作品截图明确为本地合成示例，不将示例误写成生产租户作品。 |
| Assets / media | 生产 CMS immutable JavaScript 与本地 SHA-256 一致，条件请求返回 `304`；中英文手册 WebP 资源均以 immutable 缓存返回且与本地 SHA-256 一致；代表性公开品牌媒体返回 `200 image/jpeg`，带 ETag 的条件请求返回 `304`。 |
| Logs / browser | 部署后的 app-only 日志当前请求均为健康的 `200/304`，未出现当前 Traceback / Exception / Fatal / Error；本地隔离数据库完成 Platform Admin 桌面与 390×844 移动端验收，无横向溢出，并确认行点击快速查看、`操作` 集中动作和套餐影响审查路径。未使用生产凭据或执行生产写操作。 |

本次部署已包含用户手册更新文件和生成的中英文截图资源；未包含用户另行保留的 `docs/sales/` 路演资料。后续文档闭环提交只更新 README、handoff 与 Release Notes，不改变运行代码，也不重新打包。

