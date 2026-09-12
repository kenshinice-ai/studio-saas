# PWE Studio v10.19.0 — Handoff 索引（2026-08-16 起按 AI 分目录）

> 首标题始终点名当前版本 —— `test_release_ledger.py` 据此机器强制「索引不过期」；
> 每次发布随四层身份表一起更新。

> 本文件从 505KB 单文件瘦身为**索引 + 当前身份**。历史内容一字未改，按原顺序拆入
> `docs/handoff/`；拆分经字节保真校验（拼回 == 原文件 SHA-256）。
>
> **新惯例：按 AI 分目录写轮次文件，不再向本文件追加叙事。**
> - Claude（Fable）：`docs/handoff/claude/YYYY-MM-DD-主题.md`，一轮一文件。
> - codex 时代存档（只读）：`docs/handoff/codex/`，`index.md` 列全部 95 节。
> - 每轮结束只回本文件做两件事：更新下方「当前四层身份」表、更新「最新轮次」指针。
> - 其余纪律不变：Source / Package / Production / Backup 四层分别记录；docs-only
>   closure 不得写成已部署运行时代码；发布必经 STOP GATE。

## 当前四层身份（v10.19.0，2026-09-12 · **已发布、已部署**）

> 第 6–9 步已执行，本表已由实测回填（runbook 第 9 步）。
> 轮次文件：`docs/handoff/claude/2026-09-12-brand-realignment-r1.md`。

| 层 | 精确事实 / 预期 |
|---|---|
| Source | 提交 `6f1b186a0950b763fe2cb5cc505dec7f26075648`，已在 `origin/main`；分支 `claude/ui-ux-pro-max-audit-073a82` 亦已推送。内容：品牌对齐变更单的 R1 —— 门禁先行（L1 从 0 页进入浏览器矩阵到 9 页；颜色字面量守卫与脚本语法检查覆盖门户；五个「不可能变红」的门禁改成能红），然后 P0 四条（租户站可能整片空白、三份法律文件的私人 Gmail、错误页是裸 JSON、询盘打开空邮件）、P1 七条（其中「警示色当文字」实测是 20 处而非 3 处，另有 6 处 hover 态）、L1 门户观感（主按钮改墨底纸字、琥珀只剩收尾带一处作地、买点补主按钮、标题字重与字距、手写月费、六条无效声明）、L2 租户站 + regenerate。**零迁移**，schema 仍至 `0047_xero_transport.sql`。本机 `verify_local.sh` **All checks passed**，pytest `2367 passed, 135 skipped`，租户隔离 `254 passed, 0 failed`。 |
| Package / SaaS | `dist/PWE-StudioSaaS-aws-10.19.0.tar.gz`，SHA-256 `a93690e83ce4465301cd5d7e2b606a2975931b7764eea9d432c1b2db81318d86`。 |
| Package / Edition | `dist/PWE-Studio-Edition-10.19.0.tar.gz`，SHA-256 `32bc94ad80f7f0464ca33d19404c67f9db5835dd261b9b9d031bcd8c0f71ff80`。 |
| Production | `pwestudio.online` = **v10.19.0**。2026-09-12 实测 `/v1/health?deep=1`：`db=ok`、`mode=saas`、`workspaces.stale=0`、`themes.status=ok`、`themes.unreadable=0`、5 个租户、磁盘 18.0%。 |
| Backup / migration | 部署前 dump `studiosaas_studiosaas_20260912T065503Z.dump` + 同名 manifest（实例 `/data/backups/postgres/`）。schema 仍至 `0047_xero_transport.sql`（**本版零迁移**）。 |

### 部署后验收（生产实测，2026-09-12）

| 验的东西 | 结果 |
|---|---|
| 错误页对浏览器出 HTML | `GET /nope` + `Sec-Fetch-Dest: document` → **404 `text/html`**；`GET /v1/nope` → 404 `application/json`。48 个出口共用 `api_error` 一处协商 |
| `/customer-resources/` | **301**（此前 404） |
| 租户站在脚本之后仍然可读 | `/lets-paint-showcase`：`<html class="js">`、28 个 `.reveal`、**24 个已可见**、`--glass-opacity` 解析为 `88%` |
| 全站琥珀作地只剩一处 | `/studio` 上遍历每个元素求 `backgroundColor === rgb(245,179,53)`，结果是 **`SECTION.band-amber` 一个**。此前是 5 处 |
| 主按钮 / 次按钮 / 标题 | 主 `rgb(14,23,41)` 底 `rgb(247,245,242)` 字；ghost 描边 `rgba(14,23,41,0.55)` = 3.90:1；h1 `600` / `-2.436px`（即 −0.018em @ 135px） |

### 这次收口不声称的

- **`/nope` 的响应头是 `text/html; charset=utf-8; charset=utf-8`** —— `Response(mimetype=…)`
  会自己追加 charset，而我把 charset 也写进了 mimetype。重复的参数被浏览器忽略，页面
  正常，但这是一处我发进生产的缺陷。下一轮第一件事改掉（用 `content_type=`）。
- **`ui_matrix.py` 仍然没有接进任何门禁**。本版补齐了它的覆盖面（13 → 22 页），
  接线留给单独一轮。
- **`cms_roster_teacher` 一页仍未检查**（teacher 账号密码未提供）。

## 上一版四层身份（v10.18.0，2026-09-11 · 已发布、已部署）

> **2026-09-12 由实测回填。** 本表此前把 v10.18.0 记成「源码候选，未发布 / 未推送 /
> 未构建」，Production 一行还写着 v10.17.0 —— 四处与事实不符：九步 runbook 在
> 2026-09-11 已经走完。这不是补一行记录：这张表是任何人（包括后来的会话）判断现状的
> 唯一文档，下一轮的四名独立核查里就有一名信了它，因而得出「v10.18.0 未部署」的
> 错误结论。**发布人执行完第 6–9 步就必须回写本表**，这是 runbook 第 9 步本身。

| 层 | 精确事实 |
|---|---|
| Source | 提交 `3fc745ea93635da489a17785e065fc1cf18edbf0`，已在 `origin/main`；`release/10.18.0-pwe-house` 亦已推送。内容：房子（PWE · 天域）接管根之前的四件事 —— 产品首页搬到 `/studio`（`/zh/studio/`），canonical / hreflang / og:url / sitemap / llms.txt 跟着走；`RESERVED_SLUGS` 26 → 49（房子的前缀 + 本应用一直路由却从未保留的根地址）；根 PWA manifest 的 `start_url` 不再是 `/`（`/platform-admin`、`/studio`），`sw.js` 升 `CACHE_VERSION`，租户 CMS 壳按租户盖 `manifest-cms.json`；`robots.txt` 加第二行 `Sitemap: …/sitemap-pwe.xml`；`/studio/llms.txt`；品牌文字改为「PWE · 天域 = 房子，PWE Studio = SaaS 产品线，Paradise Production · 天域影像 = 影像线」，租户页脚 `Powered by PWE`，产品站署名 `PWE · 天域出品` → `/`（只改文字，零图标）。改了 `tenant-template/`，3 个入库租户已本地重生成。**零迁移**，schema 仍至 `0047_xero_transport.sql`。本机门禁数字见 `docs/handoff/claude/2026-09-11-pwe-house.md`。 |
| Package / SaaS | `dist/PWE-StudioSaaS-aws-10.18.0.tar.gz`（主 checkout，2026-09-11 14:28 AEST 构建），SHA-256 `a83b26497d420f65f28cfc09aaa664ef90963703ed8ee51b2fba68b9aa7e1914`。 |
| Package / Edition | `dist/PWE-Studio-Edition-10.18.0.tar.gz`，SHA-256 `1f98c7895aa6782ee477fae5adc3923a6e39a66548f5b623f701cc44891d57bf`。 |
| Production | `pwestudio.online` = **v10.18.0**。2026-09-12 实测 `/v1/health?deep=1`：`db=ok`、`mode=saas`、`workspaces.stale=0`、`themes.status=ok`、`themes.unreadable=0`、5 个租户、磁盘 17.4%（47.1 GB 空闲）。 |
| Backup / migration | 部署前 dump `studiosaas_studiosaas_20260911T102700Z.dump` + 同名 manifest，在实例 `/data/backups/postgres/`（权限 `-rw-------`，与 03:15 那批 cron 产物的 `-rw-r-----` 可区分）。schema 仍至 `0047_xero_transport.sql`（**本版零迁移**）。 |

### 部署后验收（生产实测，2026-09-12 回填）

| 验的东西 | 结果 |
|---|---|
| STOP GATE 一：nginx 对 `/zh/` 是否精确匹配 | **通过。** `/zh/` `/zh/studio/` `/zh/pricing` `/zh/manual/` 全 200 —— 若配成前缀匹配，应用的全部中文页会 404 |
| STOP GATE 二：5 个生产租户 slug 是否撞上新保留名单 | **通过。** `lets-paint-showcase`、`lets-paint-studio` 均 200 |
| 新的规范地址 | `/studio` 200、`/zh/studio/` 200、`/studio/llms.txt` 200；`/` 与 `/zh/` 本版仍渲染首页（按设计，等 nginx 遮） |
| 其余公开面 | `/pricing` `/manual/` `/robots.txt` `/sitemap.xml` 全 200 |

### 这次回填顺带发现

- **`/customer-resources/` 本身是 404。** 它在 v10.18.0 里被加进 `RESERVED_SLUGS`，
  但路由只有 `@app.route('/customer-resources/<path:filename>')`（`server.py:1531`），
  Flask 的 `<path:…>` 不匹配空段，所以 `server.py:1547` 那条「目录 → Release_Notes」
  的 301 永远到不了。只有带文件名的地址能开。留给本轮 P0-03 一并处理。


## 上一版四层身份（v10.17.0，2026-09-07）

| 层 | 精确事实 |
|---|---|
| Source | v10.17.0 运行提交 `cb72f69f30252e700bb8567490310f46a29a6592` 已推送到 `main`。做的是 v10.16.0 附录 C 明写「留到下一轮」的四件事，其中两件的病因与记录不同，并顺出四个未记录的缺陷（三个在门禁自身）。本机 `verify_local.sh` **首次全绿**：`All checks passed`，pytest `2394 passed, 41 skipped`（v10.16.0 是 `2 failed, 2265 passed`）。**零迁移**，schema 仍至 `0047_xero_transport.sql`。 |
| Package / SaaS | `dist/PWE-StudioSaaS-aws-10.17.0.tar.gz`，SHA-256 `46a880291bd43fca70bfb1ea68372ddf9d0a39b8ebcd78b6f238bc873ecccf74`；`BUILD_INFO commit=cb72f69f3025…`，mode=saas。三方守卫全等（BUILD_INFO == 本地 HEAD == `origin/main`）。 |
| Package / Edition | `dist/PWE-Studio-Edition-10.17.0.tar.gz`，SHA-256 `fa590f12b9e5befdcca3e191db6ee6ff2bc72fa38bacc6839c0364a111983886`；同一提交，mode=standalone。双包通过校验和、BUILD_INFO、入口、排除项与解包冒烟。 |
| Production | `pwestudio.online` = **v10.17.0**；deep health `db=ok`、`mode=saas`、`workspaces.stale=0`、`themes.unreadable=0`、5 个租户、磁盘 16.7%。`http -> 301`、`https -> 200 proto=2`。**`GET /vendor/tailwindcss.js` 现在是 404**（此前 200、451,131 字节），`/assets/register-tailwind.css` = 16,943 字节。`ui_matrix.py --base https://pwestudio.online`：**416 条断言、0 失败、12/13 页**（`cms_roster_teacher` 因 teacher 账号密码未提供而跳过 —— 见下）。 |
| Backup / migration | 部署前 dump `studiosaas_studiosaas_20260907T003855Z.dump` 及同名 manifest（deploy 自动产出）。schema 仍至 `0047_xero_transport.sql`（**本版零迁移**）。 |

### 部署后验收（生产实测，2026-09-07）

| 验的东西 | 结果 |
|---|---|
| 注册页外观是否变了 | **逐项相同。** 改动前在生产上取过基线（166 个元素 × 21 个计算属性，digest `ba8bf82f`）；部署后同一页面同一方法：`ba8bf82f`，`matchesPreReleaseBaseline: true`。脚本列表里 `tailwindcss.js` 已消失 |
| 451KB 编译器 | `GET /vendor/tailwindcss.js` → **404**；`/assets/register-tailwind.css` → 200，16,943 字节 |
| 侧栏状态文字对比度 | `text-green-600` **8.50**（发布前 2.75）、`text-red-600` **12.02**（3.74）、课程帮助卡 `text-amber-600` **11.87**（3.61）。对照：正文 7.41 未变；`bg-gray-800` 深色面 6.07，仍正确反转 |
| 悬空选择器 | `html[data-brand-scheme] :root` 规则数 **0**（此前 1，它会静默吞掉紧随其后的规则） |
| v10.16.0 的遮罩层修复是否还在 | `bg-black/50` → `color(srgb 0.129 0.106 0.098 / 0.5)`，仍生效 |
| 层叠里的 `!important` | 32 → **28** |
| 手机编辑区宽度断言 | **首次在生产上跑过**：375px 下 `.settings-panel` = 343px（needs ≥ 300px），`.workbench-layout` = 343px。v10.16.0 收口时明写「从没在生产上跑过」，这一条现在关掉了 |

### 这次收口不声称的

- **`cms_roster_teacher` 一页仍未检查**：生产 `teacher.showcase@pwe-studio.invalid` 的密码未提供，返回 401。矩阵会自己说出来（`12/13 pages checked, 1 skipped`），不再报成「0 失败」。
- **`~/.studiosaas/showcase-credentials.txt` 里的生产密码在本轮排查中被打印到了会话输出里**（脱敏正则只覆盖同行 `label: value`，而那个值单独占一行）。建议轮换该 demo 租户口令。生产专用凭据已另存为 `showcase-credentials.production.txt`（0600），矩阵通过 `STUDIOSAAS_DEMO_CREDENTIALS_FILE` 读它。
- **`!important` 还剩 46 行**（源码计数）。把阴影/圆角移进 Tailwind 主题实测会改 14 处圆角、让 2 个 `disabled` 按钮失去阴影；收窄 `[class*="text-…"]` 的子串匹配实测会让 46 个元素失去对比度补偿。两件都留给单独一轮。

### 本版做了什么

**四件记过的事**

| 附录 C 记的 | 实际是什么 |
|---|---|
| register.html 的 Tailwind 迁移 | 做了。它是最后一个加载 451KB 浏览器内编译器的页面，而且是**公开路由**（生产实测 `GET /vendor/tailwindcss.js` 451,131 字节）。换成 16,943 字节静态表，**166 个元素 × 21 个计算属性逐项相同**；vendored 编译器已从仓库删除，不再进任何发布包 |
| 51 行 `!important` 的清理 | 只有 9 条是「为压过 Tailwind」，其余 34 条是打印、减弱动效、安全区、iOS 缩放的必需品。本版删 5 条（每条 A/B 实测无差异），另 5 条移进主题的方案**实测会改 14 处圆角**，留下一轮 |
| 本机门禁缺口 | 病因不是测试，是 **gate 用超级用户跑应用侧检查**，而超级用户绕过 RLS。改成生产用的属主／应用双角色后全绿。顺带修三个「假绿」 |
| 生产 ui_matrix 凭据 | 已解决：**416 条断言、0 失败、12/13 页**。手机编辑区宽度断言**首次在生产上跑过**（`.settings-panel` 375px → 343px） |

**顺出来的六个**

1. **侧栏状态文字对比度 2.75:1。** `aside` 被列在「深色面」名单里（侧栏当年是 `bg-indigo-900`），而它已变成 `background:var(--panel)` 的浅色面，第二个 `<aside>`（课程帮助卡）是 `bg-white`。浏览器实测 `text-green-600`：正文 7.41、`<aside>` 内 2.75；修后 8.50 / 12.02 / 11.87
2. **成长报告里五个图标一个都没画出来。** JSX 被粘进拼出来的 HTML 字符串：`className` 解析成无人读的 `classname`；`<Icon/>` 是未知元素，而 **HTML 不认未知元素的自闭合**，它张着嘴吞掉后面的按钮文字（实测 `icon.textContent === "复制成长寄语"`）
3. **四个 RT 键定义了、零调用**，英文工作室发出去的报告工具栏是中文
4. **一条注释撑着一条断言（第五次）。** `_strip_comments` 不处理 `<!-- -->`，于是 `assert "RT.welcome" in report` 被注释满足；把调用点改回写死中文，测试仍然全绿
5. **加一份样式表就让 CMS 门禁瞎了 135 个类名。** `assets/*.css` 的 glob 加一个写死的文件名跳过 —— 豁免集 772 → 933，删掉 `.bg-indigo-600` 门禁说没问题。改成按 Tailwind preflight 指纹识别
6. **`npm ci` 自 v10.16.0 起就是坏的**（锁文件缺 tailwindcss）。发出去的字节没问题 —— 用修好的固定工具链重编，产物与线上逐字节相同；坏的是可复现性

**门禁自身修的**

- 应用侧检查改用受限角色，**拒绝退回 $USER**；换角色会让两条测试**静默跳过**（RLS 隐藏 `memberships`；role administrator 判据），两条都已改成真正运行
- 陈旧产物检查只看 18 个 JSX 里的 1 个；两处 `else` 在源文件不存在时报「已是最新」；一个绿勾盖住 8 项检查（含 app 启动必需的 asset manifest）
- 媒体检查在 worktree 里量的是另一棵目录树（`backend/media` 未跟踪、数据库跨 checkout 共享），且把「原文件不存在」报成「衍生图不完整」
- `ui_matrix` 汇总行带上分母，并新增 `--require-roles`

## 上一版四层身份（v10.16.0，2026-09-06）

| 层 | 精确事实 |
|---|---|
| Source | v10.16.0 运行提交 `ff7d3031e47f162588756f0a9d857074d5cd9540` 已推送到 `main`。两份独立审计交叉核实（51 条裁决：33 成立 / 13 部分 / 3 推翻 / 1 已过时 / 1 无法静态判定）后，0–G 八批全部落地：补课额度 BLOCKER、跟进日期静默清除、发票深链接、手机 Studio Admin 编辑区、CMS 错误边界、公开面四项、钱路径五处、外壳六处、语言三级回退与词典按后果补齐、待处理队列与首屏去重、Tailwind 构建期编译。本机 pytest `2265 passed, 6 skipped`，另有 2 条 RLS 构造测试失败 —— **对照实验：未改动的 `main` 以同一命令失败同样两条**，见「已知门禁缺口」。**零迁移。** |
| Package / SaaS | `dist/PWE-StudioSaaS-aws-10.16.0.tar.gz`，SHA-256 `2a55be949227b1859c1082743c05901f6bba163edcc97e02014f20a3e904a0c7`；`BUILD_INFO commit=ff7d3031e47f162588756f0a9d857074d5cd9540`，mode=saas，built_at 2026-09-06T10:44:24Z。三方守卫全等（BUILD_INFO == 本地 HEAD == `origin/main`）。 |
| Package / Edition | `dist/PWE-Studio-Edition-10.16.0.tar.gz`，SHA-256 `1a3e63dcb6f1beabad8991460d95b814a3d2765c2fbc854680293e7647e3d84e`；同一提交，mode=standalone。双包通过校验和、BUILD_INFO、入口、排除项与解包冒烟。 |
| Production | `pwestudio.online` = **v10.16.0**，镜像 `studiosaas:10.16.0`；deep health `db=ok`、`mode=saas`、`workspaces.stale=0`、`themes.unreadable=0`、5 个租户、磁盘 17.4%；内网与公网边缘各验一次。`http -> 301`、`https -> 200 tls=0.068 proto=2`。公开路由实测全 200：`/`、`/lets-paint-showcase/`、`/…/register`、`/…/showcase`、`/…/timetable`、`/…/cms`、`/assets/cms-tailwind.css`（39913B）、`/manual/`、`/pricing`。CMS shell 里已无 `<script src=…tailwindcss.js>`，样式表带 `?v=10.16.0&h=ac5d12573095621e`，静态兜底与 `noscript` 都在下发的字节里。`ui_matrix.py --base https://pwestudio.online`：**342 条断言、0 失败**（CMS 与 studio-admin 条目被跳过，见下方缺口）。 |
| Backup / migration | 部署前 dump `studiosaas_studiosaas_20260906T104456Z.dump` 及同名 manifest（deploy 自动产出）。schema 仍至 `0047_xero_transport.sql`（**本版零迁移**）。 |

### 本版做了什么

起点是两份同日、方法不同的独立审计：一份未起后端（源码判断 + 静态站），一份起了
真 PostgreSQL + 真 Chrome 登录实测。两份的结论直接冲突（一份列了四条 P0，另一份
写着「本轮没有证据支持全产品 P0」），所以先做的不是归纳，是**逐条核实**。

| 面 | 结果 |
|---|---|
| 补课额度 | **BLOCKER，两份审计都没找到。** 点「安排补课」会把额度不可逆地消耗掉、不排出任何课、并弹绿色成功提示。服务端返回 `{"ok":true,"exceptionId":null}`（生产实测）。四层同时错，其中第四层是 `occurrences()` 按系列星期几展开，补课按定义排在别的星期几——所以前三层修好后课表**依然**看不见它。`kind='makeup'` 在整个后端被写入一次、被读取零次 |
| 静默数据丢失 | 前台每天点的「已联系」会清空已保存的跟进日期（生产实测：`30 Sep` → `NULL`）。服务端**本来就实现了**「字段不给就保持原值」，只是从来没被这样调用过 |
| 钱的路径 | 六个月经营报表算在 500 条窗口上（造 600 笔流水验证）；课酬页两个按钮没有 onClick；Xero「排队积压单据」零确认且在未连接时可点；操作日志裸 catch 吞掉一半记录；CSV 按钮下载的是另一个数据集 |
| 韧性 | CMS 补上错误边界（三层）、shell 静态兜底与 `noscript`；401 不再强制登出，改为原地重登（**不落盘**，客户与交易数据不写浏览器存储） |
| 公开面 | 五条降级横幅合并为一条并加退避重试（不再盖住 hero）；课程卡片带上选课上下文；约课报错到字段级、机器码不再上屏；切语言不再丢失家长的查询结果 |
| i18n | 三级回退 + 一次迁移（默认值会把自己写进 localStorage，只读那个键等于没修）；词典按后果补齐 19 条 |
| 前端体积 | Tailwind 改为构建期编译：451KB 浏览器内 CSS 编译器 → 40KB 静态表，且不再有一段阻塞 React 的 CPU 工作 |
| 顺带修好的既有缺陷 | **CMS 所有对话框自 v8.4.2 起就没有遮罩层**（`bg-black/50` 解析为 `rgba(0,0,0,0)`，因为颜色值是 `var()`，Tailwind 无法加 alpha）。是逐类比对运行时与编译产物时撞见的 |

### 三条门禁自己的缺陷

1. `test_v961_wide_shell_uses_available_width_before_stacking` 断言的
   `minmax(220px, 280px)` **只存在于一条为了让它变绿而留下的注释里**，真实规则是
   `233px`。它把 `.workbench-layout` 整个删掉也照样通过。已改成读规则。
2. 原生对话框守卫只列 `window.confirm(`。改成规则后**第一次运行就抓到第二个**
   `window.prompt` —— Xero 清算账户科目号。
3. `workspaces.stale` 只比租户名，看不见模板漂移。已补一条测试：模板里定义的每个
   函数都必须出现在每个租户产物里；用旧产物验证过它会红。

### 已知门禁缺口 —— 已在 v10.17.0 修掉

（这一段保留原文所指的问题，结论已改。）本机 `verify_local.sh` 曾在任何单一数据库
配置下都无法全绿。原因不在被测代码里：**应用侧的检查是以超级用户连库的**，而超级
用户绕过 RLS，所以那两条隔离测试永远不可能通过。

正确配置是生产用的那一套（属主 / 应用两个角色）：

    STUDIOSAAS_DATABASE_URL=postgresql://studiosaas_app@localhost:5432/studiosaas_local_test
    STUDIOSAAS_OWNER_DATABASE_URL=postgresql://$USER@localhost:5432/studiosaas_local_test

`verify_local.sh` 现在自己发现受限角色，并且**拒绝退回 $USER**。实测
`STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh` →
`All checks passed`，`2394 passed, 41 skipped`。


### 部署后验收（生产实测，2026-09-06，经带审计的支持会话）

本轮最重的三条在生产上逐条走了一遍，动作与今天早上审计时**完全相同**：

| 动作 | 发布前（今早实测） | 发布后 |
|---|---|---|
| 排一次补课（周五，系列是周二） | 额度消耗、`exceptionId: null`、任何名单上都没有这节课 | `2026-09-11 · Priya Raman · 16:00 · Marika Lund · kind=makeup · chargeable=false · counts_for_pay=true`，`exception_id` 存在，额度已消耗 |
| 设好跟进日期后只点「已联系」 | `30 Sep 2026` → `NULL` | `20 Oct 2026` → `20 Oct 2026`（保住） |
| 用发票 id 打开账单页 | 「还没有发票」、四个 KPI 全 `$0.00`（而工作室有 5 张） | 展开 INV-0004 明细，列表 `全部 5 / 逾期 2 / 未付清 3 / 草稿 1`；不认识的账户 id 返回 `404 No billing account with that ID.` |

顺带在生产上确认的三处：

- **补课对话框**：`window.prompt` 调用次数 **0**，日期是真的 `<input type="date">`（`min=2026-09-06`），
  对话框摆出学员、来源、有效期与「额度无法退回」。
- **对话框遮罩**：`color(srgb 0.129 0.106 0.098 / 0.5)` —— 自 v8.4.2 起 `bg-black/50`
  一直解析为 `rgba(0,0,0,0)`，本版修好，生产上可见。
- **CMS 支持模式横幅**：平台账号进到租户后台时，现在写着「你正在 Let's Paint Studio
  的后台内操作，每一步都会写进审计记录」并给出退出口；侧栏新增「使用手册」入口。

**演示数据的实际改动（`lets-paint-showcase`）**：为验证补课链条并归还审计中被消耗的那张
额度，把 Priya Raman 2026-09-15 的课按提前请假处理（产生新额度），再把补课排在
2026-09-11。净结果是一次改期，比审计后的状态更完整。Isla Moore 的报名状态停在
`contacted`、跟进日期已显式清空。支持会话已正常退出。

### 未能覆盖的验收

`ui_matrix.py` 的 CMS 与 studio-admin 条目在生产上被跳过：本机
`~/.studiosaas/showcase-credentials.txt` 是本地演示用的，对生产返回 401。
本版新增的 `assert_width`（手机 Studio Admin 编辑区）因此**没有在生产上跑过**，
它的证据来自本机对同一份样式表的 A/B 测量（375px：`34px 320px` → `375px`）。
要在生产上跑，需要一份生产 showcase 的凭据，那属于另一次决定。

## 上一版四层身份（v10.15.0，2026-09-03）

| 层 | 精确事实 |
|---|---|
| Source | v10.15.0 运行提交 `50e89dfcf4dcd29ebdd374ab094a8018d3a15ced` 已推送到 `main`。CMS 密度与排列一轮（工作台合并、排课页分标签、`Tabs` 原语滚动、对话框统一）+ 对外页面材质三条 + `hero_shape` 上配色管线 + 8 个 CMS 页面进浏览器门禁。本机门禁：smoke `73 passed, 0 failed`、租户隔离 `254 passed, 0 failed`、两个控制台冒烟通过、preflight clear；pytest `2177 passed, 6 skipped` 另有 2 条 RLS 构造测试失败 —— **对照实验：未改动的 `main`（c53d625）以同一命令失败同样两条**，属本机数据库角色所致，见下方「已知门禁缺口」。**零迁移。** |
| Package / SaaS | `dist/PWE-StudioSaaS-aws-10.15.0.tar.gz`，SHA-256 `11c45ffbe531f81297edd227aa31c6763f2af91d204f41a6c04b22a80a3a9635`；`BUILD_INFO commit=50e89dfcf4dcd29ebdd374ab094a8018d3a15ced`，mode=saas。三方守卫全等（BUILD_INFO == 本地 HEAD == `origin/main`）。 |
| Package / Edition | `dist/PWE-Studio-Edition-10.15.0.tar.gz`，SHA-256 `109c7564d5c930cd968ed32eb7e86dfda9ba93057596ba47e85cfac404680946`；同一提交，mode=standalone。双包通过校验和、BUILD_INFO、入口、排除项与解包冒烟。 |
| Production | `pwestudio.online` = **v10.15.0**，镜像 `studiosaas:10.15.0`；deep health `db=ok`、`mode=saas`、`workspaces.stale=0`、`themes.unreadable=0`、5 个租户、磁盘 17.2%；内网与公网边缘各验一次。`http -> 301`、`https -> 200 tls=0 proto=2`。公开路由实测：`/`、`/lets-paint-showcase/`、`/…/register`、`/…/showcase`、`/…/timetable`、`/…/cms`、`/assets/paper-grain.webp` 全部 200。`hero_shape` 对存量租户仍解析为 `organic`（显式值胜出，零视觉变化）。**本版改了 `tenant-template/`，四个租户工作区已重新生成，线上 `workspaces.stale=0`。** |
| Backup / migration | 部署前 dump `studiosaas_studiosaas_20260903T033024Z.dump` 及同名 manifest（deploy 自动产出）。schema 仍至 `0047_xero_transport.sql`（**本版零迁移**）。 |

### 部署后发现并修正：门禁自己有两处配置错误

公网验收时 `/lets-paint-showcase/showcase.html` 与 `…/timetable.html` 返回 404。
不是回归 —— 公开面契约给出的地址**没有扩展名**
（`/v1/public/<slug>/surface` 的 `href` 就是 `/lets-paint-showcase/showcase`，
实测 200）。`ui_matrix.yaml` 里这两条路径一直写着 `.html`，也就是说
**矩阵里四个公开页面有两个从来没被真正检查过**，而它们的失败被当成了环境噪音。

同一类的第二处：报名页刻意没有站点导航（只有品牌标记），nav 契约对它不成立，
那 9 条断言一直在失败。改用通用那组（无横向溢出 + 触控区 ≥44px）。

修正后：**226 条断言 27 失败 → 406 条断言 0 失败。**

> 这两处修正是 `backend/scripts/` 下的开发工具配置，**不在已部署的运行包内**
> （构建于第 6 步，运行提交 `50e89df`），也不影响任何运行时行为。

### 本版做了什么（实测数字）

| 面 | 结果 |
|---|---|
| 工作台 | 桌面 2243→**1284**（−43%）、手机 3410→**1870**（−46%）；顶层块 10→7 / 11→8。四条同类琥珀提醒条合并为一个「需要注意」区，「最近操作」722px 改为一行入口 |
| 排课页 | 分「今日签到 / 排课设置」两个标签；面板 −83px、顶层块 5→3、**可见按钮 55→26**；新增整月展开（只存本地）与派生「未签到」 |
| 设置页 | `Tabs` 原语补上选中项滚动：375px 下七个分区**全部可见**（原后四个被裁到视口外，深链看不出选中什么） |
| 对话框 | CMS 最后一个裸 `window.confirm` 归零；未来日期签到与撤销签到的文案改为算术（`3 → 2 课时`） |
| 门禁 | `ui_matrix.py` 新增会话与 CMS 断言，8 个 CMS 页面进矩阵，**226 条断言**；首次运行即抓到 8 个 <44px 触控区，并暴露出一条只列三个字面量的黑名单式断言（已改为规则） |
| 对外页面 | `hero_shape` 新增 `auto` 跟随视觉风格（存量零变化，实测三租户）；深色带纸纹 soft-light `.14`（实测 6 色阶，带对照组）；课程分类水印；2px 阅读进度条 |

### 已知门禁缺口（v10.16.0 时的记录 —— 三条里有两条是错的，已在 v10.17.0 修掉）

原文说：换成 `studiosaas_app` 后 xero 夹具会产生 74 个错误，而且
`connect()` 会优先用 `STUDIOSAAS_MIGRATION_DATABASE_URL`。**两条今天都不成立。**
夹具早已改走 `_cms_sources.owner_connection`（18 个测试模块），读的是
`STUDIOSAAS_OWNER_DATABASE_URL`；`connect()` 只读
`STUDIOSAAS_DATABASE_URL` / `DATABASE_URL`。`verify_local.sh` 的 `env -u` 仍要
保留，但理由不同：六个脚本在 import 时调用 `db.use_owner_connection()`，会用迁移串
覆盖应用串，其中四个被测试 import。

媒体那条是真的，原因也不是「worktree 只有 20 个目录」：`backend/media` 是未跟踪的
运行时数据，而**数据库是跨 checkout 共享的**，所以在 worktree 里跑等于拿一份数据库
从没写过的目录去对账。v10.17.0 让 gate 自己解析主 checkout 的媒体根并把路径打出来。

`showcase.html` / `timetable.html` 在本 worktree 404 —— 未复核，仍属未知。

## 上一版四层身份（v10.15.0，2026-09-03）

| 层 | 精确事实 |
|---|---|
| Source | v10.15.0 运行提交 `50e89dfcf4dcd29ebdd374ab094a8018d3a15ced` 已推送到 `main`。CMS 密度与排列一轮（工作台合并、排课页分标签、`Tabs` 原语滚动、对话框统一）+ 对外页面材质三条 + `hero_shape` 上配色管线 + 8 个 CMS 页面进浏览器门禁。本机门禁：smoke `73 passed, 0 failed`、租户隔离 `254 passed, 0 failed`、两个控制台冒烟通过、preflight clear；pytest `2177 passed, 6 skipped` 另有 2 条 RLS 构造测试失败 —— **对照实验：未改动的 `main`（c53d625）以同一命令失败同样两条**，属本机数据库角色所致，见下方「已知门禁缺口」。**零迁移。** |
| Package / SaaS | `dist/PWE-StudioSaaS-aws-10.15.0.tar.gz`，SHA-256 `11c45ffbe531f81297edd227aa31c6763f2af91d204f41a6c04b22a80a3a9635`；`BUILD_INFO commit=50e89dfcf4dcd29ebdd374ab094a8018d3a15ced`，mode=saas。三方守卫全等（BUILD_INFO == 本地 HEAD == `origin/main`）。 |
| Package / Edition | `dist/PWE-Studio-Edition-10.15.0.tar.gz`，SHA-256 `109c7564d5c930cd968ed32eb7e86dfda9ba93057596ba47e85cfac404680946`；同一提交，mode=standalone。双包通过校验和、BUILD_INFO、入口、排除项与解包冒烟。 |
| Production | `pwestudio.online` = **v10.15.0**，镜像 `studiosaas:10.15.0`；deep health `db=ok`、`mode=saas`、`workspaces.stale=0`、`themes.unreadable=0`、5 个租户、磁盘 17.2%；内网与公网边缘各验一次。`http -> 301`、`https -> 200 tls=0 proto=2`。公开路由实测：`/`、`/lets-paint-showcase/`、`/…/register`、`/…/showcase`、`/…/timetable`、`/…/cms`、`/assets/paper-grain.webp` 全部 200。`hero_shape` 对存量租户仍解析为 `organic`（显式值胜出，零视觉变化）。**本版改了 `tenant-template/`，四个租户工作区已重新生成，线上 `workspaces.stale=0`。** |
| Backup / migration | 部署前 dump `studiosaas_studiosaas_20260903T033024Z.dump` 及同名 manifest（deploy 自动产出）。schema 仍至 `0047_xero_transport.sql`（**本版零迁移**）。 |

### 部署后发现并修正：门禁自己有两处配置错误

公网验收时 `/lets-paint-showcase/showcase.html` 与 `…/timetable.html` 返回 404。
不是回归 —— 公开面契约给出的地址**没有扩展名**
（`/v1/public/<slug>/surface` 的 `href` 就是 `/lets-paint-showcase/showcase`，
实测 200）。`ui_matrix.yaml` 里这两条路径一直写着 `.html`，也就是说
**矩阵里四个公开页面有两个从来没被真正检查过**，而它们的失败被当成了环境噪音。

同一类的第二处：报名页刻意没有站点导航（只有品牌标记），nav 契约对它不成立，
那 9 条断言一直在失败。改用通用那组（无横向溢出 + 触控区 ≥44px）。

修正后：**226 条断言 27 失败 → 406 条断言 0 失败。**

> 这两处修正是 `backend/scripts/` 下的开发工具配置，**不在已部署的运行包内**
> （构建于第 6 步，运行提交 `50e89df`），也不影响任何运行时行为。

### 本版做了什么（实测数字）

| 面 | 结果 |
|---|---|
| 工作台 | 桌面 2243→**1284**（−43%）、手机 3410→**1870**（−46%）；顶层块 10→7 / 11→8。四条同类琥珀提醒条合并为一个「需要注意」区，「最近操作」722px 改为一行入口 |
| 排课页 | 分「今日签到 / 排课设置」两个标签；面板 −83px、顶层块 5→3、**可见按钮 55→26**；新增整月展开（只存本地）与派生「未签到」 |
| 设置页 | `Tabs` 原语补上选中项滚动：375px 下七个分区**全部可见**（原后四个被裁到视口外，深链看不出选中什么） |
| 对话框 | CMS 最后一个裸 `window.confirm` 归零；未来日期签到与撤销签到的文案改为算术（`3 → 2 课时`） |
| 门禁 | `ui_matrix.py` 新增会话与 CMS 断言，8 个 CMS 页面进矩阵，**226 条断言**；首次运行即抓到 8 个 <44px 触控区，并暴露出一条只列三个字面量的黑名单式断言（已改为规则） |
| 对外页面 | `hero_shape` 新增 `auto` 跟随视觉风格（存量零变化，实测三租户）；深色带纸纹 soft-light `.14`（实测 6 色阶，带对照组）；课程分类水印；2px 阅读进度条 |

### 已知门禁缺口（不是本版引入，需单独一轮）

`backend/scripts/verify_local.sh` 在本机无法全绿，且与本轮改动无关：

- `STUDIOSAAS_DATABASE_URL` 指向超级用户时，`test_tenant_isolation_by_construction`
  的两条构造测试失败 —— 它们要求应用以受限角色连库，而超级用户绕过 RLS。
- 换成 `studiosaas_app` 后这两条通过，但 `test_xero_transport` 等夹具因没有租户
  上下文被 RLS 拒绝插入，变成 74 个错误。保留 `STUDIOSAAS_MIGRATION_DATABASE_URL`
  能救夹具，但 `connect()` 会优先用它，于是 RLS 两条又回到失败 ——
  `verify_local.sh` 的 `env -u` 正是为了防止属主 URL 泄进 pytest。
- 另有两项本机环境失败：媒体衍生图在主 checkout（106M / 299 个租户目录），
  这个 worktree 只有 20 个而数据库是共享的；`showcase.html` / `timetable.html`
  在本 worktree 返回 404。

**对照实验：未改动的 `main`（c53d625）以同一命令失败同样两条 RLS 测试。**

## 上一版四层身份（v10.14.0，2026-08-24）

| 层 | 精确事实 |
|---|---|
| Source | v10.14.0 运行提交 `ba6c89774e5106349bfd8d94c2a0fdc43f8e91d2` 已推送到 `main`。Living Studio System 将 Portal / Register / Operations CMS / Studio Admin 串成一个空间故事；HTML 为事实层，浅/深海报 → Canvas → Three.js 渐进增强。PostgreSQL-required gate：`2118 passed, 8 skipped`；租户隔离 `254 passed, 0 failed`；legacy smoke `73`；两个控制台 smoke 通过。 |
| Package / SaaS | `dist/PWE-StudioSaaS-aws-10.14.0.tar.gz`，SHA-256 `d140cb435c954b82bcbb994049d47e69658b441821a4885ba8adff1eea1fdc67`；`BUILD_INFO commit=ba6c89774e5106349bfd8d94c2a0fdc43f8e91d2`，mode=saas。 |
| Package / Edition | `dist/PWE-Studio-Edition-10.14.0.tar.gz`，SHA-256 `0566e37982c1e542c21eccb039cc9b70b8e18fdb4451928bd99be725e65ebb28`；同一提交，mode=standalone。 |
| Production | `pwestudio.online` = v10.14.0，镜像 `studiosaas:10.14.0`；deep health `db=ok`、`mode=saas`、`workspaces.stale=0`、`themes.unreadable=0`、5 个租户、磁盘 19.1%；`http -> 301`、`https -> 200 tls=0 proto=2`。375px Canvas、1440px Three.js、英文/中文单 H1、零横向溢出、控制台无警告。线上 Three.js 文件 SHA-256 与提交逐字节相同，immutable，条件请求 304。 |
| Backup / migration | 部署前 dump `studiosaas_studiosaas_20260824T034213Z.dump` 及 manifest；volume `pwestudio-volumes-20260824T034214Z.tar.gz`。schema 仍至 `0047_xero_transport.sql`（本版零迁移）。 |

## 更早版本 · 四层身份（v10.12.3，2026-08-22）

| 层 | 精确事实 |
|---|---|
| Source | v10.12.3 发布提交 `474a4d8`（链：`822f136` 卫生+钱与权限 → `0d272cd` 结算租户可重置 → `38b7131` **CMS 登录修复** → `474a4d8` 发布账本） |
| Package / SaaS | `dist/PWE-StudioSaaS-aws-10.12.3.tar.gz`，SHA-256 `11a5a141b15e7216f752a2ee6bf3c3869e7a65de81cf687981e6f1d548ef891c`（三方守卫全等） |
| Package / Edition | `dist/PWE-Studio-Edition-10.12.3.tar.gz`，SHA-256 `e0477d2d246d0e1e982cc47e47d8ed8f0e17b9552a974c161d4417a113b54c66` |
| Production | `pwestudio.online` = v10.12.3；deep health `db=ok`、`mode=saas`、`stale=0`。**CMS 登录已恢复**（自 v10.11.0 起对所有租户 404，线上实测：错口令 401 带人话、未知 slug 仍 404、家长预约 400 走校验不再 500）。两间样板租户已按新内容包重播种：开票主体各自独立（Paradise Production / Zhiyin Music Pty Ltd，ABN 均为校验位不合法号），单号 `INV-####` 与 `music-####`，生日铺满全年、14 天窗口各 1 人，启蒙班学员 6 岁与 5 岁落在适龄内；Xero 侧各 0 连接 0 网关状态、加购有效（不再伪造无 token 连接） |
| Backup / migration | v10.12.1 部署前 dump（deploy 自动产出）；schema 仍至 `0047_xero_transport.sql`（三个补丁版本零迁移） |

完整证据见 `docs/handoff/claude/2026-08-16-v10.8.0-round.md`（v10.8.0）与 codex/001（v10.7.1 历史）。

## 最新轮次

- **2026-09-12（Claude）v10.19.0 品牌对齐 R1 —— 先补网，再改样式**（**已发布、已部署**）：
  轮次文件 `docs/handoff/claude/2026-09-12-brand-realignment-r1.md`，核查结论页
  <https://claude.ai/code/artifact/c6ef01d2-8e68-4c69-90f6-251f209226e5>。
  依据 `23-PWE Studio SaaS 风格与内容对齐·变更单.md`（v2.4）与本会话的只读核查：
  变更单 21 条里 16 条前提要改（2 条照做会制造它自己要修的缺陷），另发现 23 条它
  没写的。这一版做 R0（回写 v10.18.0 的部署事实）+ R1：三张给 L1 补的网、五个改成
  能红的门禁、P0 四条、P1 七条、L1 门户观感、L2 租户站。新门禁在本轮当场多找出
  17 条缺陷，其中 6 条 hover 态是逐条规则的检查看不见的。五个提交。
- **2026-09-11（Claude）v10.18.0 房子上线前置 —— 产品首页搬到 `/studio`**（**已发布、已部署**；
  轮次文件当时写的「未推送、未打包、未部署」已于 2026-09-12 按实测更正）：
  轮次文件 `docs/handoff/claude/2026-09-11-pwe-house.md`。`/studio` / `/zh/studio/`
  成为产品首页的规范地址（`/`、`/zh/` 本版仍渲染首页，留给 nginx 遮住，下一版再 301）；
  `RESERVED_SLUGS` 加入房子的前缀与本应用自己的根地址（26 → 49）；根 PWA manifest
  不再以 `/` 起步、`sw.js` 升缓存版本、CMS 壳按租户盖 manifest；robots 列出
  `sitemap-pwe.xml`；`/studio/llms.txt`；品牌文字换成「PWE · 天域 = 房子」的三层
  结构，租户页脚 `Powered by PWE`，产品站署名 `PWE · 天域出品`。零图标改动、零迁移。
  顺手修了定价页语言切换指向首页、跳过链接跨页两个既有缺陷。
- **2026-09-06（Claude）v10.16.0 两份审计的交叉核实与 0–G 八批修复**（**已发布**）：
  方案 `docs/design/Consolidated_Improvement_Plan_2026-09-06.md`（含生产实测附录 A
  与执行记录附录 B）；两份原始审计 `UX_Review_2026-09-06.md`、
  `User_Experience_Review_Verified_2026-09-06.md`（证据目录 `ux-review-2026-09-06/`）。
  51 条裁决、8 个提交、17 个新测试文件。F 与 G 同版发布是对本方案自己「G 独占窗口」
  一条的**明确偏离**：那条规则的理由是当时没有任何门禁能看见构建期编译的失败，
  所以先建了 `test_tailwind_build.py`（去掉一个 content 路径 → 570 个类缺失、
  产物 40KB→9KB），再做迁移。
- **2026-09-03（Claude）v10.15.0 CMS 密度与排列 + 对外材质**（**已发布**）：
  轮次文件 `docs/handoff/claude/2026-09-03-cms-density-and-material.md`。
  工作台四条同类提醒条合并为一个「需要注意」区、`最近操作` 722px 改为入口
  （桌面 −43%、手机 −46%）；排课页分「今日签到 / 排课设置」（可见按钮 55→26）
  并新增整月展开与派生「未签到」；`Tabs` 原语补上选中项滚动（375px 下设置页
  后四个分区原本被裁到视口外）；CMS 最后一个裸 `window.confirm` 归零，确认文案
  改为算术；8 个 CMS 页面进 `ui_matrix.py`（226 条断言，首跑抓到 8 个 <44px
  触控区，并暴露一条黑名单式空断言）；`hero_shape` 新增 `auto` 跟随视觉风格
  （存量零变化）；深色带纸纹、课程分类水印、2px 阅读进度条。零迁移。

- **2026-08-24（Codex）v10.14.0 Living Studio System 品牌首页**（**已发布**）：
  `product-home.html` 以“一个系统、四个相连界面”为核心重构；语义 HTML 承担
  内容、SEO 与转化，浅/深静态海报先显示，移动/减弱动效走 Canvas，合适桌面
  再动态加载自托管 Three.js。Portal、Register、Operations CMS、Studio Admin
  保持普通链接；Data Saver、WebGL2 不可用、context lost 均 fail-open 到完整页面。
  运行提交 `ba6c897`，双包、备份、deep health、公开路由、资产哈希、浏览器矩阵
  均验收；本版不改租户主题、数据模型、权限或 API。

- **2026-08-23（Claude Opus 5）层 2 前两步落地 + 角色权限的事实与取舍**（**已发布 v10.13.0**）：
  `docs/handoff/claude/2026-08-23-two-page-refactor-and-roles.md`
  —— 层 2 ①`?section=` 按 tab 作用域解析并按角色收敛；层 2 ②设置页七个
  `hidden` 面板换成 `Tabs`/`TabPanel`，六块共享内容各归其位，删掉不可达的
  弹窗分支与 133 行 `{false && …}` 死代码；排课页删掉重复的生日横幅，并修掉
  工作台生日**跨年那一周整周漏人**的算法。实测 4 角色 × 8 section = 32 例、
  全量 `2840 passed`。两个只有跑起来才会现形的坑：hook 写在
  `cms-app.jsx:3098` 的 `if (!loggedIn) return` 之下会触发 React #310 整页空白；
  `actorRole` 首帧为空会把合法的 `?section=` 提前收敛掉。
  同一轮内接着定了角色（前台整拿 `attendance:write`、staff=助教收成 teacher
  的真子集）、按 `/code-review` 的四条判定全修，并**落地了排课页重排**：
  第一行学员的 top 桌面 898→**542**（首屏 900）、手机 1124→**634**（首屏 844），
  桌面首屏从 0 行学员变成 5 行；顺手修掉排课 #4/#5/#6/#7 与截图脚本
  `next_class_date()` 往后找日期导致**手册最忙的一页每个按钮都是灰的**。
  排课 #8「≤360px 周视图重叠」实测**不复现**，未改。
  已复核 `PATCH /students/<id>` 只带 `balance` 时**既无 `actor_user_id`
  也无 audit 行**（已修）。排课页阶段二（页内标签）尚未开始，清单见
  `docs/design/CMS_Roster_Split_Plan.md` 第 9–19 步。
  **发布前又跑了一轮对抗式复查（该文「十一」节），推送前拦下一个越权**：
  给前台 roster 标签页，把 `canWriteScheduling` 里那条我自己判定为「死代码」的
  `front_desk` 激活了，于是前台能改「请假规则」——课酬与账单口径——而同一版
  明确不给它 `payroll:read`。新增 `scheduling:policy:write`（仅 Owner/Manager）
  修掉。同轮还修：`GET /class-bookings` 一直无权限判断却返回每个约课家庭的
  姓名与手机（改判 `class_bookings:review`，teacher 实测 403）；本轮新加的
  `firstRowInFold` 断言**在 bug 上也通过**（898 < 900）；改中文把 i18n 字典键
  改成了孤儿，英文界面回退成中文；课时流水的 `actor_user_id` 存了但日志查询
  没 select（60/60 现在带操作人）。全量 `2848 passed`，门禁 `All checks passed`。
- **2026-08-22（Claude Opus 5）v10.12.3 —— CMS 登录自 v10.11.0 起就是坏的**：
  `docs/handoff/claude/2026-08-22-hygiene-and-money-paths.md`（「四·六」节）
  —— 拆包（`cfab504`）把 `api_v1.py` 变成包，两处**函数体内**的单点相对导入
  含义随之改变：`auth.py` 的 `from .tenant_context import`（CMS 登录）与
  `public.py` 的 `from .services.student_access import`（家长预约）。
  前者的 `ModuleNotFoundError` 被 `except Exception` 收成 404「Unknown tenant」，
  **对每个租户、每次登录**；两天没人发现，因为大家都还揣着有效会话——直到
  重播种把会话清掉。后者每次提交 500。两处改回包根，except 收窄到真正表示
  「无此租户」的两个异常，登录框改显示 `message` 而非机器码 `not_found`。
  新增 AST 静态测试（函数体内导入靠 import 模块测不到；用文件系统而非
  `find_spec`，否则一处坏会让同包全部误报）。全量 `2840 passed`。

- **2026-08-22（Claude Opus 5）v10.12.2 —— 记过结算的演示租户重置不了**：
  同上一条 handoff 的「四·五」节。`_clear_showcase` 漏清两张引用钱层的表：
  `credit_financial_links`（RESTRICT）与 `financial_operation_requests`
  （SET NULL 但被 BEFORE UPDATE 触发器拒绝，报出来是「幂等键不能配不同的载荷」）。
  **既有缺口**，只在租户真的走过一次结算后才有行，所以只播种的本地永远测不出来；
  v10.12.1 上线后第一次线上重播种就炸了。走真实结算接口复现并验证（手造行会被
  `assert_credit_financial_link_is_legal` 挡下）；第一次只修一张，重跑才炸出第二张。
  全量 `2839 passed`。

- **2026-08-22（Claude Opus 5）会面卫生 + 钱与权限 —— v10.12.1**：
  `docs/handoff/claude/2026-08-22-hygiene-and-money-paths.md`
  —— 播种器里最后十处美术字面量与 index 算术搬进内容包（开票主体、ABN、单号前缀
  `music-`、生日与年龄、充值手续费、教师薪酬），并停止伪造无 token 的 Xero 连接与
  「映射已确认」。签到路径三修：已签到改按日期查考勤（原先全局 `LIMIT 500` 会导致
  四十天前的记录掉窗、批量签到二次扣课时）、未来日期当面确认、批量确认框点名日期、
  失败给原因。工作台四处写死的「画艺大进」改走租户模板（其中两处在 `sms:` body 里）。
  **并降级了我自己两轮前报错的一条**：front_desk 读到银行账号不是越权 —— 同样的字段
  经 `GET /billing/invoices/<id>`（`billing:read`）本来就到他手里，因为收款账户印在
  每张发票上；真正成立的只是开票面板把 `canManage` 传成了 owner+manager。
  全量 `2838 passed`；门禁 All checks passed。

- **2026-08-22（Claude Fable 5）Sinobeats 会后 —— Xero 链路诊断，只读不动**：
  `docs/handoff/claude/2026-08-22-xero-meeting-followup.md`
  —— Demo Company 没收到发票是**从未推送**：音乐租户 `push_enabled=false`、试跑从未
  完成、队列 0 条；「不流畅」是播种器伪造的无 token 连接让 `refresh-check` 409。
  即便开关打开，音乐 `INV-0001..6` 会与美术样板撞号（同一个 Demo Company）被守卫
  逐张拒绝 → 音乐包要自带单号前缀。Q2：发票与付款都到 Xero，但付款在 Demo Company
  里全部 Unreconciled（无流水行可配）；**`clearing_account` 选项传输层从未实现**，
  而 Sinobeats 用 Square，这是它的必经路径。真账本有一条死作业（本地已作废，重放即
  skipped）。UI 三份方案原样未动。

- **2026-08-21（Claude Opus 5）音乐样板租户 —— 播种器泛化成「行业内容包」**：
  `docs/handoff/claude/2026-08-21-music-showcase-pack.md`
  —— `reset_professional_demo.py` 改为按包播种（`--pack art|music`），每个包自带
  确认短语；**修掉「重置演示租户」按钮永远重建美术租户的地雷**（租户决定包，无包
  认领即拒绝）。九组文案/数据从播种器搬进包模块，其中 `BILLING_LINKS`／
  `ATTENDANCE_COURSE_INDEX`／`REGISTRATION_ANSWERS` 原本是**写死的索引算术**，
  在音乐名册上会安静产出自相矛盾的演示。新增音乐包 `music-studio-showcase`
  （知音音乐，growth，12 学员／9 课／22 个素材），装配时另修 logo 被切断、
  manifest 学员索引错位、「两台钢琴」标题与正文矛盾、凭空多出第五个房间。
  以及两个包把凭据写进同一个文件（环境变量改为给目录、包给文件名）。
  美术包输出逐字未变；全量 `2832 passed`。**上线须先手工给线上租户打
  `settings.professional_demo=true`，否则播种器会（正确地）拒绝。**

- **2026-08-20（Claude Fable）v10.11.1 运维卫生轮 —— A/B 两档清单一次做完**：
  `docs/handoff/claude/2026-08-20-ops-hygiene-round.md`
  —— 集成页 Beta 徽标（含移除触发条件）；两组双语标签对齐；**演示页「数据每晚
  重置」不实声明纠正**（定时器从未存在，手动重置是既定决策；模板改动随部署经
  entrypoint 的 regenerate 生效）；控制台冒烟进入发布门禁（自起实例、无 Chrome
  显式跳过）；`prune_dist.py` 释放 1.20 GB（dist 1.3G→178M）；**OPS-03** 线上
  nginx 收编（发现仓库零记录的 paradise-production 片段）；**OPS-04** 备份口令
  离开 argv（此前 `/proc/*/cmdline` 全局可读）。另：仓库根一份 0644 私钥在
  iCloud 里——核实从未进过 git，与 `~/.ssh` 正本逐字节相同，已移出。

- **2026-08-20（Claude Fable）v10.11.0 结构重构轮 —— P1–P4 全案一步到位**：
  `docs/handoff/claude/2026-08-20-structure-refactor.md`
  —— api_v1.py 15,926 行拆为 11 域包（url_map 191 条 + AST 394 符号机器等价）；
  cms-app.jsx 拆出 components.jsx + 7 panel（48 张截图流水线实拍验证）；
  i18n 引擎合一（fail-open）+ 重复键门禁（首跑清 52 个存量重复）；
  PBKDF2 合一（双 legacy 格式兼容，测试先行）；两控制台 4,200 行内联脚本
  外置为版本化资产 + 新增真浏览器冒烟（首跑抓出 studio-admin 登录静默失败
  并修复）。行为零变化；发布证据见下方四层身份表。

- **2026-08-19（Claude Fable）X4 接入完成 + v10.10.2/v10.10.3 —— 真实账本推送开启**：
  `docs/handoff/claude/2026-08-19-xero-x4-real-ledger.md`
  —— 真租户 `lets-paint-studio` 全向导对真账套走通：连 PWE GROUP PTY LTD
  （v10.10.2 按授权事件选组织实测生效）、试跑 clean、推送开启；
  首单 **LPS-INV-0002** 在真账本肉眼可见、对账 0 差异。
  途中现场抓到 **Xero POST 按单号 upsert 会改写账本现存单据** → v10.10.3
  同号冲突守卫（创建前按号预查，撞号死信）+ 真租户单号改 LPS- 前缀。
  结算月进行时；X4 出口 = 一个自然月 0 人工修账。

- **2026-08-19（Claude Fable）v10.10.0 + v10.10.1 —— Xero X3 外发 transport 与过闸修复**：
  `docs/handoff/claude/2026-08-19-xero-x3-transport.md`
  —— 队列消费真上线：迁移 0047（退避住行里 + 链接带 org）；`xero_transport.py`
  （精确分值推送、Contact 客户键 upsert、invoice/credit_note/payment(按 allocation)、
  失败分类退避/死信、backfill、逐张对账、demo cycle）；三处入队钩子；
  push-now/backfill/reconciliation/queue 四条 API；gate 的 demo_run 变真跑；
  systemd timer + `lightsail_ctl exec-app` + 安装脚本；集成页映射编辑器与队列操作面；
  产品真话契约与 FAQ/Demo_Runbook 翻到「门后单向推送」。
  测试 12 项新增，全量 2857 通过。四层身份表随部署闭环更新。

- **2026-08-19（Claude Fable）v10.9.3+v10.9.4 —— Xero 连接打通（invalid_scope →
  wrong apps scopes → 首个成功连接）**：
  `docs/handoff/claude/2026-08-17-xero-x2-round.md`（2026-08-19 更正节）
  —— v10.9.3：`invalid_scope` 根因是 Xero scope 换代（2026-03-02 后创建的应用只拿
  细粒度 scope），改细粒度集并携带四轮压队修复（0046 套餐上限、字段类型下拉、
  CMS 与 admin i18n、手册截图/路演材料）一并发布。
  v10.9.4：细粒度集仍被拒（`Requested wrong apps scopes`），线上二分定位
  `app.connections` 与 `accounting.settings.read` 不被 authorize 放行，终稿
  `openid profile email accounting.invoices accounting.payments accounting.contacts
  offline_access`；Demo Company (AU) 连接 ✔ / 取消 ✔ / 自愈 ✔，断开重连随 v10.9.4 收口。
  四层身份表随部署闭环更新。

- **2026-08-19（Claude Fable）两处漂移按线上对齐**：
  `docs/handoff/claude/2026-08-19-two-drifts-aligned.md`
  —— 套餐学员上限 100/500/1000 → 50/250/500（新增 `0046`；只改基线种子无效，
  因为 `0021` 会把 growth 抬回 1000，实测新库才发现），价格只改基线不进迁移；
  报名字段类型下拉不再把枚举当标签（value 仍是 text/textarea/select）。未部署。

- **2026-08-19（Claude Fable）admin-i18n.js 审计（Studio Admin / Super Admin）**：
  `docs/handoff/claude/2026-08-19-admin-i18n-audit.md`
  —— 与 CMS 同三类缺陷：13 个重复键（`Support` 被「支持」覆盖掉配色角色「辅助色」）、
  About 的 24 个生成式字段名读作「Highlight 3 Body · 中文」、observer 不监听属性。
  另修一条为页面从未产出的措辞而写的规则（`Signed in: ` vs 实际的 `Signed in as `）。
  未改 JSX，未升版本号，未部署。

- **2026-08-18（Claude Fable）CMS 英文界面三处修复**：
  `docs/handoff/claude/2026-08-18-cms-i18n-measure-words.md`
  —— 量词短语改为整句渲染（碎片条目 `['人）', ')']` 靠删字蒙混，渲染成 `(12 )`）；
  字典 10 个重复键（`已作废` 曾被动作词覆盖成 `Void`）；observer 不监听属性，
  导致 placeholder/title/aria-label 只在挂载时翻译过一次。界面文案残留中文
  214→0（余下 34 处是租户数据）；未升版本号，未部署。

- **2026-08-18（Claude Fable）销售材料对齐 v10.9 + 手册截图整套刷新**：
  `docs/handoff/claude/2026-08-18-roadshow-deck-refresh.md`
  —— deck 定价页对齐线上 plans 表（$189/50/250/500/席位）并新增「账务与 Xero」页（10→11 页），
  13 张截图全部换本地实拍；朋友圈软广告 v10.9 包重制；播种器发票快照缺陷与 v10.9.2 轮
  独立撞出同一修法，以已发布的 v10.9.2 版本为准。第三轮修掉 `capture_manual_shots.py`
  两处缺陷（中文侧写成短标签「学员」；`OPEN_FIRST_STUDENT` 死匹配且调用处静默丢弃结果，
  05-portfolio 一直拍成学员列表而非手册说的作品集区块），手册 48 张按单一 v10.9.2 基线
  整套重拍（33 张实质变化），`asset-manifest.json` 已重建。未升版本号，随下次发布上线。

- **2026-08-17（Claude Fable）v10.9.2 手册第 10 章截图修复轮**：
  `docs/handoff/claude/2026-08-17-manual-invoicing-screenshots.md`
  —— docs+assets 最小发布；播种器与捕捉脚本各修一处。

- **2026-08-17（Claude Fable）v10.9.0 Xero X2 轮**：`docs/handoff/claude/2026-08-17-xero-x2-round.md`
  —— OAuth 连接流（发布证据随部署闭环）。

- **2026-08-17（Claude Fable）v10.8.0 执行轮**：`docs/handoff/claude/2026-08-16-v10.8.0-round.md`
  —— Batch A–F 全量实现（发布证据在该文件随部署闭环）。

- **2026-08-16（Claude Fable）全面体检与下一轮方案（docs-only）**：
  `docs/handoff/claude/2026-08-16-full-system-audit.md`；
  权威方案：`docs/design/Full_System_Audit_Plan_2026-08-16.md`（rev2，含 Batch A 界面缺陷、
  Batch E 账务/学员优化、Batch F Xero 路线图、OPS 暂缓决定与触发条件）。
- **v10.7.1 发布轮（codex）**：`docs/handoff/codex/001-…`（发票打印修复与发布闭环）。

## 历史存档

- `docs/handoff/codex/index.md` — codex 时代全部 95 节（v7.x → v10.7.1），原文原序。
