# PWE Studio v9.9.0 — 导航、店名、公开地址：六批修复的生产闭环

> 当前阶段：v9.9.0 已完成源码、完整门禁、双模式打包、生产备份、部署、公网验收，以及存量租户工作区的一次性刷新。
> 本节记录本轮最终证据；后续文档闭环只更新发布账本，不改变已运行的 v9.9.0 包。

## v9.9.0 修复范围

按 [docs/design/Public_Surface_UX_Audit_v9.8.10.md](design/Public_Surface_UX_Audit_v9.8.10.md)
与 [docs/design/Tenant_Slug_Rename.md](design/Tenant_Slug_Rename.md) 的六个批次执行，全部是**已经在坏**的东西，不是缺的功能。

**一 · 导航。** hash 链接在每个页面都被改写成「租户首页 + 锚点」，**包括首页自己**——
在首页上，只要访客带着任何 query 进来，改写结果与当前 URL 的差异就不止 fragment，
于是每一次导航点击都是整页重载，并且顺手丢掉 `?lang=` 和所有 `utm_*`。
课表页从未在 `<body>` 上声明自己的 slug，它依赖的那次改写在那里等于没做。
首页的契约失败分支既不到 `apply()` 也不走本地兜底，导航会在加载遮罩下隐身到页面生命周期结束——
而它显示的提示写着「页面已按当前内容安全显示」。
另外修掉：两个死 id、`aria-current` 在首页恒真的判断、`.navlinks a` 把 CTA 的 `padding` 压成 `4px 0`。

**二 · 改名。** `tenants/<slug>/` 是物化的，店名在创建那一刻写进 `<title>`、社交预览标签和结构化数据，
之后没有任何东西重写它。发布现在会重渲染工作区（在 commit 之后，文件系统故障不能回滚已入账的发布），
head 文案由服务端按 portal 在浏览器里用的同一优先级组合。
deep health 新增 `workspaces` 块——它在这次部署完成的**同一分钟**就报出了 `ruby-s-studio`。

**三 · 公共 shell。** 四个公开页各自维护一份 header/footer 条目清单，已经漂移了三处。
条目改为三个共享片段，在生成工作区时拼接；页面外壳（`<nav>` 包裹层、品牌链接、语言开关）保持各页自有，
因为统一它们要改四个线上页面而访客看不到任何差别。导航标签在契约里截断
（`NAV_LABEL_LIMIT` 中文 10 / 英文 24，两个实现之间有 parity 测试），页面上的版块标题一个字不动。

**四 · Studio Admin。**「发布」有两个意思，其中一个只是存草稿。九个「是否公开」开关散在四个面板。
契约的 reasonCode 以标识符形态打给店主看。三个字段有四个名字。主理人没有自己的面板。

**五 · 中文。** 68 条可见英文串没有译文，包括发布仍在确认时显示的那一句。
新增覆盖门禁，按运行时真正遍历的规则扫描。

**六 · 公开地址。** 新增 `tenant_slug_aliases`（migration `0031`）：平台发放过的每一个地址都在册，
旧地址永久 301，地址**永不回收**（`ON DELETE SET NULL` 留墓碑，返回 410）。
每租户一年一次，仅 Platform Admin，双钥确认 + 键入当前地址。
301 的判断发生在文件系统查找之前——旧目录故意留到后续清理，顺序反了就会把访客送回工作室的过去。

未改动：套餐额度、支付能力、租户数据模型。

## v9.9.0 最终发布证据（2026-08-12）

| 层级 | 已验证事实 |
|---|---|
| Source | 分支 `claude/ui-ux-pro-max-audit-073a82`；部署代码 commit `c13d5587e4fb9b7da6424233484d310f97d3931b`；`VERSION=9.9.0`、`APP_VERSION=9.9.0`、`RELEASE_DATE=2026-08-12`。本分支已从 `codex/v9.8.10-public-shell` fast-forward，六批改动在其之上。 |
| Local gates | `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh` **全部通过**；pytest `1721 passed, 5 skipped`；legacy CMS smoke `73 passed`；租户隔离 `237 passed, 0 failed`；Python/JS 编译、UI escaping、terminology、inline scripts、CMS bundle、asset manifest、迁移 current、媒体衍生图均通过。 |
| Package | SaaS `dist/PWE-StudioSaaS-aws-9.9.0.tar.gz` SHA-256 `b02854a87e18b4629eb9f46062121ec844fdc8e101cef23a46c74582738a210a`；Edition `dist/PWE-Studio-Edition-9.9.0.tar.gz` SHA-256 `689463e8705bfc91f6118d4454fe59614edb226cfb6368999fc822312ec4b0ff`。两个 `BUILD_INFO` 均为 v9.9.0，模式分别 `saas` / `standalone`，通过 checksum、入口、版本与排除项校验。 |
| Production | `/opt/pwestudio/current` → `PWE-StudioSaaS-aws-9.9.0`，镜像 `studiosaas:9.9.0`；容器 healthy；公网 deep health `appVersion=9.9.0`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`、**`workspaces.stale=0`**；磁盘可用约 `45.96 GB`；HTTP→HTTPS `301`，HTTPS `200`、TLS 校验 `0`、HTTP/2。 |
| Backup / migration | 切换前自动生成逻辑库备份 `studiosaas_studiosaas_20260812T123256Z.dump` 与 manifest，卷归档 `pwestudio-volumes-20260812T123257Z.tar.gz`。`0031_tenant_slug_aliases.sql` 已在启动时应用。回滚目录保留 `PWE-StudioSaaS-aws-9.8.10` 与 `9.8.9`。 |
| 存量刷新 | 部署后 deep health 立刻报出 `workspaces.stale=1`（`ruby-s-studio`：文件里是 `Ruby's Studio`，数据库里是 `Mellow Pear Studio`）。用 `refresh_tenant_workspaces_from_db.py --only-slug ruby-s-studio` 重渲染，随后 `stale=0`。**该脚本写于打包之后，不在 9.9.0 运行包内**，本次是把文件拷进容器执行的；它已提交到仓库，下一个版本起随包发布。 |
| Public routes | 根站、`/zh/manual/`、`/ruby-s-studio`、`/showcase`、`/timetable`、`/register`、`/lets-paint-showcase`、`/lets-paint-showcase/timetable`、`/platform-admin`、`/ruby-s-studio/studio-admin` 全部 `200`。 |
| Public evidence | `/ruby-s-studio` 的**服务端原始 HTML** 现在是 `<title>Mellow Pear Studio</title>`，description 为工作室自己的 slogan（此前是旧店名与通用模板句）。契约里长标签已截断：`Oil Painting, Acrylic P…`（原 74 字符 / 241px）、`Original Personalised O…`、`原创油画 × 私人…`。四个公开页的 `foot*` 契约条目集合完全一致。线上 `public-surface.js` 与仓库逐字节相同，在其上复核：首页带 `?lang=en&utm_source=wechat` 时 `navFaq` 解析为 `/ruby-s-studio?lang=en&utm_source=wechat#home:faq`——同文档跳转，query 不再丢失。 |

## 未做与已知项

- **导航项过多时的「更多 ▾」降级没有做。** 截断之后单项宽度已受控，剩下的是项目数问题（最多 8 项），留待观察真实租户。
- **公共 shell 只统一了条目清单，没有统一页面外壳。** `<nav>` 包裹层、品牌链接、语言开关属性（`data-set-lang` vs `data-language`）仍各页自有；这是权衡，不是遗漏——会漂移的是清单。
- **Studio Admin 未做登录后的实际交互验证。** 本轮不处理明文密码，后台结论来自源码、静态门禁与下发的 HTML。
- **旧工作区目录的清理 sweep 尚未实现。** 改名后旧目录会留在卷上；它不再被路由命中（301 在文件系统查找之前），但目前没有自动删除。首次真实改名之前应补上。
- **前台是否能批准约课**：`review_class_booking` 仍是 `@tenant_admin_required`，前台持有 `registrations:write`。这条设计问题从 v8.10.0 起就记在这里，仍未拍板。

---

