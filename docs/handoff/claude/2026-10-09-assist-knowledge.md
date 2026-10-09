# 2026-10-09 · v10.20.6：把 product site 的文字发布成 Assist 知识（A 块）

> 状态：**已发布、已部署**。生产是 v10.20.6，commit `d002008`（2026-10-10 00:05 AEDT 实测）。
> 发布（含部署）由 Lee 2026-10-09 在本仓库的会话里授权：「1. 发布 2. 提交 推送 同步 3. 加入 执行」。
> 四层身份和验收表在 `docs/HANDOFF_LATEST.md`。本文件记设计、验证和没有验证的部分。

## 来源

- 任务书：`PWE-AI-BOTs/docs/next-pwe-studio.md` §6.1 A。
- 格式契约的正本：paradise-production `02 WEBSITE/src/knowledge.py` 的文件头。
- 请求方：pwe-ai-bots 的会话「PWE Assist  项目总规划」，2026-10-09 转述 Lee 的安排。
- 转述不是发布授权。授权来自 Lee 本人（见上）。

## 范围

只做 A。B（窗口脚本）、C（预约表单）、D（隐私政策一节）等请求方通知。

## 改了什么

| 提交 | 内容 |
|---|---|
| `f68a66e` | 新模块 `backend/studiosaas/services/assist_knowledge.py`；`backend/server.py` 加四个路由和一份缓存；`backend/tests/test_assist_knowledge.py` 20 条测试；`docs/Architecture.md` 路由表加一行。 |
| `f8bf2ce` | `CLAUDE.md` 术语表加「PWE Assist」和「Assist knowledge（Assist 知识）」。Lee 2026-10-09 同意。该提交的说明把日期写成了 2026-10-10，是错的。 |
| `d002008` | 发布提交：版本账本、两份客户版本记录、README 三行、准备态的 handoff。 |

四个地址：`/studio/assist/version.json`、`/studio/assist/index.json`、`/studio/assist/knowledge.en.txt`、`/studio/assist/knowledge.zh.txt`。

设计要点：

- **内容来自服务访客的同一组函数。** `_assist_render` 直接调用 `_serve_product_home`、`_serve_pricing`、`_serve_manual`、`_serve_customer_resource_page`，取它们返回的 HTML。没有第二份文案。
- **进全文 5 页**：`home`、`pricing`、`manual`、`faq`、`support-policy`。**只进标题和地址 3 页**：`privacy-policy`、`terms-of-service`、`release-notes`。
- **不读租户数据。** 唯一的数据库读取是 `public_plan_rows()`，也就是定价页自己的查询。
- **版本号** = `<应用版本>-<内容哈希前 8 位>`。套餐查询每次请求都跑，所以平台后台改价之后，下一次读 `version.json` 就是新值。
- **四个地址同进同退。** 出任何问题都返回 503 和 `no-store`。失败不进缓存。
- **缓存头。** `version.json` 永远 `no-store`。`index.json?v=<commit>` 和 `knowledge.<lang>.txt?v=<sha>` 在 `v` 与当前内容完全相等时是 `immutable`；其它请求一律 `no-store`。
- **Edition 不提供。** `STUDIOSAAS_MODE=standalone` 时四个地址都是 404，和 `/pricing` 一致。
- 四个地址都带 `X-Robots-Tag: noindex`。

不产出 Assist 知识（返回 503）的条件：

1. 套餐查询失败，或没有公开套餐。
2. 任何一页的状态码不是 200，或没有 `<title>`，或正文容器里没有文字。
3. 首页或定价页上找不到某个套餐的名字、价格、四项限额。
4. 首页上找不到 Let's Paint 的披露句（中英各一句）。

## 和契约正本不一样的地方

输出格式的字段没有变。下面五处已在 2026-10-09 告诉请求方；到 2026-10-10 00:10 AEDT 还没有收到对方的确认。

1. `article` 和 `aside` 也算换行。否则主推徽标会粘到前一张套餐卡的末尾，读成「Start with StarterRecommended」。主推的是 Studio plan。
2. 披露的 `text` 只取一句，不取整段。整段后面还有「这里链接的是演示租户」，接在对话回答后面没有所指。
3. `satisfied_by` 中英共用一条正则：`our own team|我们自己团队`。
4. 没有 `[site-footer]` 一段。product site 的页脚只有导航链接。
5. `index.json` 没有 `built` 字段。每种语言多一个 `chars`，和 pwe-house 的输出一样。

## 验证

### 测试

- `backend/tests/test_assist_knowledge.py`：20 passed（本机，2026-10-09，以 `studiosaas_app` 连库）。
- 任务书点名的三条断言各有测试：
  - 套餐等于数据库：`test_every_plan_in_the_knowledge_equals_the_database` 和 `test_every_plan_reads_as_its_row`。
  - 披露句缺失就不产出：`test_no_knowledge_without_the_lets_paint_sentence`。
  - 出错时四个地址都是 503：数据库不可达、套餐表为空、页面渲染了回落文字、某一页 404、错误页冒充正文，各一条。
- 每条测试都弄红过。改坏实现 13 种方式，11 种直接变红。
- 剩下 2 种起初没有变红：
  - 「改用不抛异常的套餐查询」：结果仍是 503，由「没有公开套餐」那条检查兜住。这是同一结果的两道检查，不是缺口。
  - 「不看页面状态码」：这是真缺口。一张带 `<title>` 和 `<main>` 的错误页会被当成 FAQ。已补 `test_an_error_page_is_not_mistaken_for_the_page`，补完后该改法变红。
- 改坏的文件每次都还原，还原后与原文件逐字节相同（`cmp`）。

### local gate 和 CI gate

| 对象 | 结果 |
|---|---|
| local gate，功能提交 `f68a66e`（2026-10-09） | `All checks passed`。pytest 2532 passed / 41 skipped；smoke 73 / 0；租户隔离 257 / 0 |
| CI gate，分支 `feat/assist-knowledge` `f8bf2ce`（Python 3.11） | 通过，run 37933351408。pytest 2529 passed / 43 skipped |
| local gate，发布提交的工作树（2026-10-09） | `All checks passed`。pytest 2532 passed / 41 skipped；租户隔离 257 / 0 |
| CI gate，`main` `d002008` | 通过，run 37933999479 |

新 worktree 第一次跑 local gate 有 1 项失败：「CMS 源文件比 `cms-app.js` 新」。原因是新检出的文件时间戳，不是包过期。证据：`bash backend/scripts/build_cms.sh` 之后 `git diff -- backend/frontend/assets/cms-app.js` 为空。重跑后通过。

### 本机起应用（端口 8897，以 `studiosaas_app` 连本机库，2026-10-09）

| 检查 | 结果 |
|---|---|
| 四个地址 | 全部 200 |
| `index.json` 的 `commit` 与 `version.json` 的 | 相同 |
| `version.json` 热读 5 次 | 每次 5–9 毫秒 |
| 把本机库 Growth 的价格从 199 改成 189 | `commit` 变；两种语言的 `sha` 都变；`numbers` 里出现 189、不再有 199 |
| 改回 199 | `commit` 回到原值；`plans` 表与改之前相同 |

### 生产

见 `docs/HANDOFF_LATEST.md` 的「部署后验收」。四个地址都是 200，套餐数字与 `/pricing.md` 相同。

## 两件容易弄错的事

- **本机库的 Growth 是 199，生产是 189**（2026-10-09 实测；迁移 0046 故意不改价格）。从本机应用取的 Assist 知识、截图或 deck 都会带 199。
- **每次发布之后 `sha` 都会变。** 手册和 FAQ 页面上印着版本号，版本号在 Assist 知识里。2026-10-09 我对请求方说过「只发版不改字时 `sha` 不变」，这句是错的，已更正。

## 给评测用的快照

- 位置：worktree `~/Developer/worktrees/studiosaas-assist-knowledge/outputs/assist-knowledge-2026-10-09-production-plans/`（被 git 忽略）。
- 它与生产 2026-10-10 的内容只差版本号：快照里是 `v10.20.5`，生产是 `v10.20.6`。套餐数字相同。
- 生产已经可读，评测可以直接读生产的四个地址。

## 没有验证的

- PWE Assist 的 Worker 还没有读过这四个地址。2026-10-10 实测：`curl` 默认的客户端标识得到 200；Python `urllib` 默认的客户端标识得到 403。
- 没有在真正的 Edition 里验证 404，只有替换 `is_standalone` 的测试。
- 没有跑带登录的浏览器矩阵。这一版没有改登录后的界面。
- Assist 知识里有三处页面本来就有的噪音，没有处理：定价页计算器的默认值（「Active students 60」）、首页主视觉的渲染器标签（「Poster → Canvas → WebGL」）、同一处的「coreOne」粘连。模型会不会被它们误导，要由评测回答。
- Assist 知识里没有电话号码。电话在首页表单里，表单整个不进 Assist 知识。邮箱 `info@pwestudio.site` 在。

## 给 C 块的提醒

首页表单下面有一句「PWE Studio 不会静默提交或保存表单」。表单接到询盘管道之后这句话不成立。这一句、两个按钮上的字、隐私政策要在同一次发布里一起改。这一句在 `<form>` 里，所以不在 Assist 知识里。

## pwe-clinic

不需要同样的改动。这次没有碰安全、RLS、计费、Xero 或账务代码。

## 下一步（负责人）

1. pwe-ai-bots 的会话：用 Worker 读一次生产的四个地址，并确认上面五处取舍。
2. pwe-ai-bots 的会话：通知本仓库何时做 B、C、D。
3. Claude（本仓库的会话）：收到通知后做 B、C、D。发布仍要 Lee 同意。
