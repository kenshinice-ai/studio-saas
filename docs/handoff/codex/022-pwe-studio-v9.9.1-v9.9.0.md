# PWE Studio v9.9.1 — v9.9.0 的两处修正

> 当前阶段：v9.9.1 已完成源码、完整门禁、双模式打包、生产备份、部署与公网验收。两处都由真实控制台的截图报出。

## 修复内容

**一 · 草稿向自己的记录问错了问题。**「工作室作品」开关显示「还没有已发布的作品」，
而工作室的官网正在展示两件作品，**并且上传区上方的计数写着 `2/60 件 active 作品`**——
同一个界面自相矛盾，这就是线索：计数读的是编辑器自己的记录，
草稿契约读的却是 `collectShowcaseItems()`，而那个函数在送往服务端的路上已经把字段映射成 camelCase。
于是过滤条件里的 `image_url` 和 `publication_state` 在每一条上都是 `undefined`，
`showcaseHasContent()` 对每一件作品都返回 false。公开页面自始至终是对的，因为它读的是服务端契约。

这个错答案从草稿契约引入时就存在；是 v9.9.0 把原因显示到开关旁边，才让它暴露出来。

**二 · 长标签被截断了两次。** `16ch` 约等于 8em，比契约已经允许的 10 个汉字还窄，
于是浏览器又剪了一次服务端已经剪过的文字——省略号套省略号，行动按钮顶到自己的边框。
现在只有契约裁剪，CSS 退回成兜底（`13em` / `11em`，都宽于契约允许的长度）。
行动按钮拿到比其他条目更紧的额度（`CTA_LABEL_LIMIT` 中文 7 / 英文 18）：
它空间最小、内边距最大，而它背后那个字段最容易被店主填成一句话。
首屏按钮直接读那个字段，仍然显示全文。

## v9.9.1 最终发布证据（2026-08-12）

| 层级 | 已验证事实 |
|---|---|
| Source | 分支 `claude/ui-ux-pro-max-audit-073a82`；部署代码 commit `aeda04e98b9faaa062c1938285a1b10cc008bd9b`；`VERSION=9.9.1`。 |
| Local gates | `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh` **全部通过**；pytest `1726 passed, 5 skipped`；legacy CMS smoke `73 passed`；租户隔离 `237 passed, 0 failed`。 |
| Package | SaaS SHA-256 `f62c355b6e89fde18632314945ac6058d702bd9b5dd2010825f2a8763a6c83db`；Edition SHA-256 `b7fc586677f9c5686b00384e3ec8fb8cad4b922fc64ba60a4de56917dc9f2f19`。两个 `BUILD_INFO` 均为 v9.9.1。 |
| Production | `/opt/pwestudio/current` → `PWE-StudioSaaS-aws-9.9.1`，镜像 `studiosaas:9.9.1`；deep health `appVersion=9.9.1`、`db=ok`、`tenants=6`、`themes.unreadable=0`、`workspaces.stale=0`；磁盘 `45.93 GB`；HTTP→HTTPS `301`，HTTPS `200`、TLS `0`、HTTP/2。回滚目录保留 `9.9.0` 与 `9.8.10`。 |
| Public evidence | 线上契约的导航标签现在只被裁剪一次：`原创油画 ×…` / `Original Personal…`（行动按钮，更紧的额度）、`Artworks…`（版块条目）。八条公开路由全部 `200`。 |

## 回归测试

- `test_public_shell.py`：行动按钮的额度、服务端与浏览器的 parity、CSS `max-width` 必须以 `em` 计并且不小于 `11em`（`16ch` 正是这条会拦住的写法）。
- `test_studio_admin_vocabulary.py`：草稿契约不许再读 `collectShowcaseItems()` 的输出。

---

