# PWE Studio v9.2.0 — 持久化 CMS 通知（2026-08-09）

## 当前发布状态

- 版本：`9.2.0`。
- 分支：`codex/v9.2.0-cms-notifications`，已同步到
  `origin/codex/v9.2.0-cms-notifications`。
- 部署代码 commit：`438e58275c9f1351fe5d57353a6112eb9df0cb24`。
- 当前生产：`/opt/pwestudio/current` 指向
  `PWE-StudioSaaS-aws-9.2.0`，运行镜像为 `studiosaas:9.2.0`。
- 本文件和 README 的最终发布记录会在部署验收后另提交；该闭环文档提交不改变
  已部署代码和发布包。

## 本轮实际交付

1. 公开报名成功和公开课表约课成功后，在同一数据库事务内生成租户隔离的 CMS
   持久化通知；重复提交不会重复生成通知。
2. 通知按用户保存已读状态，具备未读数量、列表、全部标记已读和逐条标记已读的
   API/UI 契约；约课通知只展示给具备约课审核权限的运营人员。
3. 第一阶段采用 30 秒定时刷新，并在浏览器重新可见时立即刷新；新通知通过
   CMS 弹窗提示。没有引入 SSE、WebSocket、浏览器 Push 或外部消息服务。
4. 本轮支付范围保持暂停：在线支付、银行转账设置、Gmail/SMTP、AWS SES 和短信
   均未实现。

## Git 与发布包

- SaaS：`dist/PWE-StudioSaaS-aws-9.2.0.tar.gz`；SHA-256：
  `627b593d1ad9bfe8a0b59b1c52017893d6dcea8c28a6363fdd48219695bcc3a0`。
- Edition：`dist/PWE-Studio-Edition-9.2.0.tar.gz`；SHA-256：
  `f4609d7a979450737aa7908780cf625cdc2cd830c5b1483d77d1334376297ded`。
- 两个包的 `BUILD_INFO` 均为 `version=9.2.0`，分别为 `mode=saas` /
  `mode=standalone`，并指向部署 commit；checksum、入口文件、模式和内部/敏感
  路径排除检查通过。
- 构建时临时隔离并原位恢复了既有未跟踪的 `docs/sales/` 资料；它们没有进入
  commit 或任何发布包。

## 本地 release gate

- 全量 pytest：`1940 passed, 8 skipped`。
- PostgreSQL 租户隔离/权限：`237 passed, 0 failed`。
- 独立 CMS smoke：`73 passed, 0 failed`。
- 本地 migration `0028_cms_notifications.sql` 已应用并通过当前检查；CMS source、
  tracked bundle 与 asset manifest 一致，JS、inline script、shell、术语和
  whitespace 检查均通过。

## AWS 与线上验收

- 部署前生产为健康的 `9.1.1`；控制器在切换前创建了新的逻辑备份
  `studiosaas_studiosaas_20260809T085116Z.dump`（约 474 KB）及卷归档
  `pwestudio-volumes-20260809T085117Z.tar.gz`（约 66 MB）。
- 当前 release 标识来自生产 `BUILD_INFO`：
  `version=9.2.0`、`mode=saas`、`commit=438e58275c9f1351fe5d57353a6112eb9df0cb24`。
- 内部与公网 deep health 均通过：`appVersion=9.2.0`、`db=ok`、
  `mode=saas`、`tenants=6`、`themes.unreadable=0`；公网 HTTP → HTTPS 为
  `301`，HTTPS 为 `200`，TLS 校验为 `0`，HTTP/2。
- 生产 `schema_migrations` 最新为 `0028_cms_notifications.sql`；只读查询确认
  `cms_notifications` 与 `cms_notification_reads` 均存在。
- `/`、`/zh/manual/`、Studio 门户、快速报名、公开课表、CMS 和 Release Notes
  均返回 `200`。
- CMS shell 发出
  `/assets/cms-app.js?v=9.2.0&h=a4207ecb33f6d2d4`；响应为一年
  `immutable`，线上正文 SHA-256 与本地 tracked bundle 均为
  `a4207ecb33f6d2d4b3a51459ad4f6547b5fd42769402a077b541657228158237`。
- 当前应用与数据库容器均 `healthy`，重启次数为 `0`；部署后最近 30 秒在服务器
  端汇总的 app/db 错误关键词和 db fatal/panic 计数均为 `0`。没有把原始生产日志
  拉回本地。
- 两个公开图库当前均为空，因而没有真实生产 JPEG 可用于本轮 `ETag`/`304` 样本
  验收；这属于无样本记录，不是媒体回归失败。
- 部署控制器保留前一版本作为回滚点，并在健康门禁通过后清理过旧 release/image
  产物；未删除生产数据库或持久化卷。

---

