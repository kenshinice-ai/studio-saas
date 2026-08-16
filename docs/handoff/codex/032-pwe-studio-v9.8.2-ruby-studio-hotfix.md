# PWE Studio v9.8.2 — Ruby Studio 内容恢复与作品灯箱 hotfix

> 当前阶段：v9.8.2 已从生产 v9.8.1 的精确 commit 基线完成修复、完整门禁、双模式打包、生产部署、Ruby Studio 内容恢复与公网浏览器验收。生产运行 commit `25d782c994b7c0de36c73c1e4f4472ed50f5f1f5`；本节以下为本次闭环证据。

## v9.8.2 修复范围与验收

- 套餐/联系人等 Platform Admin 更新在行锁内读取现有 `settings`；请求未携带的官网、主理人、首屏、FAQ、作品、视觉主题和消息模板必须原样保留。
- 作品灯箱使用固定居中的 viewport 容器、`minmax(0,1fr)` 媒体轨道和 `object-fit: contain`；横版/竖版图都不得溢出到底部信息栏或偏向单侧。
- 恢复只取 Ruby Studio 已发布 v44 的品牌内容，保留刚切换的 `growth` 套餐；写入前创建新逻辑/卷备份，写入后核对 12 件作品、媒体可读性和公开页面。
- 完整 pytest、CMS smoke、PostgreSQL 租户隔离、生成资产、双模式发布包、桌面/手机浏览器、生产 deep health、日志与回滚点均须通过。

## v9.8.2 最终发布证据（2026-08-11）

| 层级 | 已验证事实 |
|---|---|
| Source | 分支 `codex/v9.8.2-showcase-content-recovery`；`VERSION=9.8.2`；部署候选 commit `25d782c994b7c0de36c73c1e4f4472ed50f5f1f5`。未推送 Git 远端，避免在发布目标未确认时替用户决定仓库归属。 |
| Local gates | 完整 pytest `1960 passed, 8 skipped`；完整发布门禁 `All checks passed`；CMS smoke `73 passed`；PostgreSQL 租户隔离 `237 passed`；发布后追加结构断言再次通过完整 pytest；`git diff --check` 通过。 |
| Package | SaaS SHA-256 `f11c7f9bceba0ea8bac3e5ae752af49e8cb969845bc8c84eca2e39fba73760c5`；Edition SHA-256 `661869d273b0b3684494b767c112bbbb55bc30f7b63522923542dd1290249530`。两个包的 `BUILD_INFO` 均为 v9.8.2 / commit `25d782c994b7c0de36c73c1e4f4472ed50f5f1f5`，模式分别为 `saas` / `standalone`，并通过 checksum、入口与排除项检查。 |
| Production | `/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.8.2`，镜像 `studiosaas:9.8.2`；内部和公网 deep health 均为 `appVersion=9.8.2`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；HTTP→HTTPS `301`，HTTPS `200`、TLS 校验 `0`、HTTP/2。 |
| Recovery | 切换套餐造成的覆盖发生于 `2026-08-11 01:38:57 UTC`。恢复前 dry-run 确认 v44 含 12 件作品且目标套餐为 `growth`；恢复后产生关联版本 v45 和 `brand.version_recovered` 审计。数据库确认 12 件作品、4 个分类、作品展示开启、主理人资料存在，并且 tenant/subscription 套餐均仍为 `growth`。 |
| Backup | 部署自动备份：`studiosaas_studiosaas_20260811T020647Z.dump` / `pwestudio-volumes-20260811T020648Z.tar.gz`；恢复前再备份：`studiosaas_studiosaas_20260811T021148Z.dump` / `pwestudio-volumes-20260811T021149Z.tar.gz`，manifest 均存在。 |
| Browser / media | 公网 Ruby Studio 已显示作品区；实际 1500×2000 图片在 1440×1000 视口内以 `object-fit: contain` 完整居中，未进入底部信息/操作栏，弹窗计数为 `1 / 12`；浏览器控制台错误为 0。生产媒体接口对 12 件作品均返回 200，媒体衍生图检查 `Generated variants: 0`。本地另以 390×844 手机视口验证全屏灯箱、标题/说明、前后与关闭按钮可用且无横向溢出。 |

本次未修改或打包未跟踪的 `docs/sales/` 路演资料。发布包已部署；本闭环文档提交仅记录生产证据，不改变运行代码，也不重新打包。

---

