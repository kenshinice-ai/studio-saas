# 2026-10-09 · 把 product site 的文字发布成 PWE Assist 的知识（A 块）

> 状态：**v10.20.6 已准备，未部署**。分支 `release/10.20.6`。Lee 2026-10-09 在本仓库的会话里同意发布。
> 第 1–5 步在做；第 6–9 步完成后本文件由实测回填。生产仍是 v10.20.5（2026-10-09 实测 `/v1/health`）。

## 来源

- 任务书：`PWE-AI-BOTs/docs/next-pwe-studio.md` §6.1 A。
- 格式契约的正本：paradise-production `02 WEBSITE/src/knowledge.py` 的文件头。
- 请求方：pwe-ai-bots 的会话「PWE Assist 项目总规划」，2026-10-09 转述 Lee 的安排。
- 转述不是发布授权。

## 范围

只做 A。B（窗口脚本）、C（预约表单）、D（隐私政策一节）等请求方通知。

## 改了什么

| 文件 | 内容 |
|---|---|
| `backend/studiosaas/services/assist_knowledge.py`（新） | 取可见文字、组装索引、算版本号。任何一项不成立就抛 `KnowledgeUnavailable`。 |
| `backend/server.py` | 四个路由 `/studio/assist/{version.json,index.json,knowledge.en.txt,knowledge.zh.txt}`，一份按内容失效的缓存。 |
| `backend/tests/test_assist_knowledge.py`（新） | 20 条测试。 |
| `docs/Architecture.md` | 路由表加一行。 |

设计要点：

- **内容来自服务访客的同一组函数。** `_assist_render` 直接调用 `_serve_product_home`、`_serve_pricing`、`_serve_manual`、`_serve_customer_resource_page`，取它们返回的 HTML。没有第二份文案。
- **进全文 5 页**：`home`、`pricing`、`manual`、`faq`、`support-policy`。**只进标题和地址 3 页**：`privacy-policy`、`terms-of-service`、`release-notes`。
- **不读租户数据。** 唯一的数据库读取是 `public_plan_rows()`，也就是定价页自己的查询（`plans` 表里 `is_public` 的行）。
- **版本号** = `<应用版本>-<内容哈希前 8 位>`。套餐查询每次请求都跑，所以后台改价之后，下一次读 `version.json` 就是新值。
- **四个地址同进同退。** 出任何问题都返回 503 和 `no-store`。失败不进缓存。
- **缓存头。** `version.json` 永远 `no-store`。`index.json?v=<commit>` 和 `knowledge.<lang>.txt?v=<sha>` 在 `v` 与当前内容完全相等时是 `immutable`；其它请求一律 `no-store`。
- **Edition 不提供。** `STUDIOSAAS_MODE=standalone` 时四个地址都是 404，和 `/pricing` 一致。
- 四个地址都带 `X-Robots-Tag: noindex`。

不产出知识（返回 503）的条件：

1. 套餐查询失败，或没有公开套餐。
2. 任何一页的状态码不是 200，或没有 `<title>`，或正文容器里没有文字。
3. 首页或定价页上找不到某个套餐的名字、价格、四项限额（说明页面渲染的是「定价暂时无法读取」）。
4. 首页上找不到 Let's Paint 的披露句（中英各一句）。

## 和契约正本不一样的地方

这五处已告诉请求方，等对方确认。输出格式的字段没有变。

1. `article` 和 `aside` 也算换行。否则主推套餐的徽标会粘到前一张卡片的末尾，读成「Start with StarterRecommended」。主推的是 Studio plan。
2. 披露的 `text` 只取一句，不取整段。整段后面还有「这里链接的是演示租户」，接在对话回答后面没有所指。
3. `satisfied_by` 中英共用一条正则：`our own team|我们自己团队`。
4. 没有 `[site-footer]` 一段。product site 的页脚只有导航链接。
5. `index.json` 没有 `built` 字段（契约列出的字段里没有它）。每种语言多一个 `chars`，和 pwe-house 的输出一样。

## 验证

### 测试

- `backend/tests/test_assist_knowledge.py`：**20 passed**（本机，2026-10-09，以 `studiosaas_app` 连库）。
- 三条任务书点名的断言各有测试：
  - 套餐等于数据库：`test_every_plan_in_the_knowledge_equals_the_database`（读真实的 `plans` 表）和 `test_every_plan_reads_as_its_row`（用页面上不会写死的价格 47 / 97 / 137）。
  - 披露句缺失就不产出：`test_no_knowledge_without_the_lets_paint_sentence`。
  - 出错时四个地址都是 503：数据库不可达、套餐表为空、页面渲染了回落文字、某一页 404、错误页冒充正文，各一条。
- 每条测试都弄红过。改坏实现 13 种方式，11 种直接变红。
- 剩下 2 种起初没有变红：
  - 「知识改用不抛异常的套餐查询」：结果仍是 503，由「没有公开套餐」那条检查兜住。这是同一结果的两道检查，不是缺口。
  - 「不看页面状态码」：这是真缺口。一张带 `<title>` 和 `<main>` 的错误页会被当成 FAQ。已补 `test_an_error_page_is_not_mistaken_for_the_page`，补完后该改法变红。
- 改坏的文件每次都还原，还原后与原文件逐字节相同（`cmp`）。

### local gate

`STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh` 在 worktree 里：**All checks passed**（2026-10-09）。

- pytest `2532 passed, 41 skipped`；smoke 73 通过 / 0 失败；租户隔离 `257 passed, 0 failed`；控制台冒烟通过。
- 第一次跑有 1 项失败：「CMS 源文件比 `cms-app.js` 新」。原因是新检出的文件时间戳，不是包过期。证据：`bash backend/scripts/build_cms.sh` 之后 `git diff -- backend/frontend/assets/cms-app.js` 为空。重跑后通过。

### 本机起应用（端口 8897，以 `studiosaas_app` 连本机库，2026-10-09）

| 检查 | 结果 |
|---|---|
| 四个地址 | 全部 200 |
| `index.json` 的 `commit` 与 `version.json` 的 | 相同（`10.20.5-cd8aad68`） |
| 原有页面 | `/studio`、`/zh/studio/`、`/pricing`、`/zh/pricing`、`/manual/`、`/customer-resources/FAQ.html`、`/studio/llms.txt` 全部 200 |
| `version.json` 热读 5 次 | 每次 5–9 毫秒 |
| 把本机库 Growth 的价格从 199 改成 189 | `commit` 变为 `10.20.5-6d84b576`；两种语言的 `sha` 都变；`numbers` 里出现 189、不再有 199；知识里 Growth 一段是 `$189` |
| 改回 199 | `commit` 回到 `10.20.5-cd8aad68`；`plans` 表与改之前相同 |

### 生产（只读，2026-10-09）

- `https://pwestudio.online/studio/assist/version.json` 现在返回应用自己的 404（`application/json`）。说明这个路径能到达应用，边缘不需要改。
- 生产的套餐表（读 `/pricing.md`）：49 / 99 / **189**，学员上限 50 / 250 / 500。

## 给评测用的一份快照

- 位置：worktree 的 `outputs/assist-knowledge-2026-10-09-production-plans/`（`outputs/` 被 git 忽略）。
- 内容：四个文件，`commit` 为 `10.20.5-6d84b576`。
- 它用的是生产的套餐数字。**本机库的 Growth 是 199，生产是 189**（迁移 0046 故意不改价格）。直接起本机应用拿到的知识写的是 199。
- 字符数：英文 65,381；中文 23,141。

## 没有验证的

- **CI gate 没有在这个分支上跑过**，因为分支没有推送。CI 用 Python 3.11，本机是 3.14。
- 没有在真正的 Edition 里验证 404，只有替换 `is_standalone` 的测试。
- PWE Assist 的 Worker 能不能取到这四个地址，没有验证。生产的 Cloudflare 曾以 error 1010 拒绝过非浏览器客户端（见 `2026-09-17-oracle-deploy-path.md`）。Worker 对同一个 zone 的请求是否受影响，由 pwe-ai-bots 一侧在发布后验证。
- 知识里有三处页面本来就有的噪音，没有处理：定价页计算器的默认值（「Active students 60」）、首页主视觉的渲染器标签（「Poster → Canvas → WebGL」）、同一处的「coreOne」粘连。模型会不会被它们误导，要由评测回答。
- 知识里没有电话号码。电话在首页表单里，表单整个不进知识。邮箱 `info@pwestudio.site` 在。

## pwe-clinic

不需要同样的改动。这次没有碰安全、RLS、计费、Xero 或账务代码。

## 术语

`CLAUDE.md` 的术语表里没有「PWE Assist」和「知识」（这四个地址发布的内容）。本文件按全局约定里的「PWE Assist」写。是否把这两个词加进本仓库术语表，由 Lee 定。

## 下一步（负责人）

1. Lee：决定是否发布这四个地址。
2. Claude（本仓库的会话）：Lee 同意之后，走 `docs/Release_Runbook.md` 的九步。预计是一个补丁版本，零迁移。
3. pwe-ai-bots 的会话：通知本仓库何时做 B、C、D。
