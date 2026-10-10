# 2026-10-10 · Assist 知识的清理，和 B、C、D 的准备

> 状态：**两版都已发布、已部署。** v10.20.7（`dd6610e`，2026-10-10 14:37 AEDT）和 v10.20.8（`40ba01b`，14:45 AEDT）。
> 授权：Lee 2026-10-10 在本仓库的会话里逐条答复：改正主机位置；隐私草稿可以；可以发布；窗口可以开；本机价格改成 189。
> 四层身份和验收表在 `docs/HANDOFF_LATEST.md`。下文「两个分支」到「下一步」是发布前写的，保留原样；发布时又改了的地方记在最后一节。

## 两个分支

| 分支 | 提交 | 在哪 | 内容 | 能否现在发布 |
|---|---|---|---|---|
| `fix/assist-knowledge-cleanup` | `59bf538` | 已推送到 `origin` | 定价页「真数据」改「示例数据」；Assist 知识跳过计算器控件；修两处粘连 | 能。不依赖 pwe-ai-bots |
| `feat/assist-widget-form` | 见 `git log` | **只在本机**（worktree `~/Developer/worktrees/studiosaas-assist-knowledge`） | B 窗口脚本、C 预约表单、D 隐私政策一节 | 不能。要等 pwe-ai-bots 正式部署并通知 |

第二个分支叠在第一个上面。它没有推送，因为里面有等 Lee 过目的隐私政策草稿，而仓库是公开的。

## 第一个分支：清理

- `pricing.html:200–201`：「with real data in it」改为「with a full set of sample data in it」；「里面是真数据」改为「里面是一整套示例数据」。Lee 2026-10-10 定。
- 页面可以把一块区域标成 `data-assist="skip"`。定价页计算器的控件和首页主视觉的渲染器标签带这个标记。
- `<small>` 也算换行。「One studio coreOne record」变成两行；同一条规则顺带分开了「One studiobrand · people · ledger」。
- 计算器的标题和那句「结果在你的浏览器里算出」仍在 Assist 知识里。Setup 费 `AUD 299–999` 仍在，来自说明它的那一节。

验证（2026-10-10）：

| 对象 | 结果 |
|---|---|
| 新测试 4 条 | 通过。每条都靠还原对应规则弄红过，4 种改法 4 种变红 |
| local gate | `All checks passed`。pytest 2536 passed / 41 skipped；租户隔离 257 / 0 |
| CI gate，分支 `fix/assist-knowledge-cleanup`（Python 3.11） | 通过，run 38009249115 |
| 与生产的 Assist 知识逐行对比（英文） | 只有预期的行变了；另有两行 `$189` 对 `$199`，那是本机库的价格，不是改动 |

## 第二个分支：B、C、D

### B · 窗口脚本

- `public_site.py` 加 `render_assist_widget(language, mode)` 和开关 `ASSIST_WIDGET_MODE`，三档：`off`、`gate`、`on`。现在是 `gate`。
- `gate`：只有带 `?assist=1` 进来的那个标签页会加载 `/v1/assist/widget.js`。写法照 `PWE-AI-BOTs/USAGE.md` §5。
- 八个页面文件在 `</body>` 前加占位 `<!--ASSIST-WIDGET-->`：产品首页、定价、手册、五份客户文件。
- 四个页面函数替换占位：`_serve_product_home`、`_serve_pricing`、`_serve_manual`、`_serve_customer_resource_page`。别的函数不调用它。
- Edition 下替换成空字符串。客户自己的主机上没有 `/v1/assist/`。
- product site 的页面右下角没有固定定位的元素（2026-10-10 查 `marketing.css`、`product-home.css`、`manual.css`、`pricing.css`、`customer-resources.css`），不用给窗口让位。

### C · 首页表单

- 表单提交到同源的 `POST /v1/assist/enquiries`，`site` 是 `pwe-studio`，`source` 是 `form`。
- 多两项必填：姓名、邮箱。工作室名称标成选填，作为 `organisation` 发出。主题进 `type`，内容进 `brief`（上限 4000）。
- 加陷阱字段 `website`，放在屏幕外，不用 `display:none`。
- 各种回应各有一种结果：201 换成成功态；429 提示稍后再发；400 带 `fields` 时在对应字段下报错并聚焦第一个；其余和网络失败都走回落。
- 回落：显示一段说明，露出「打开邮件」「打开信息」两个按钮。任何失败都不清空访客写的东西。
- 成功态用 Lee 2026-10-05 定的那一句，前面加「已收到。」/「Received.」。
- 表单下的说明换了。旧的那句「不会静默提交或保存表单」已删。
- 电话链接一直可见。

### D · 文字（**草稿，等 Lee 过目**）

- `Privacy_Policy.html` 新增第十节「我们自己的网站：留言与 AI 助手」，原第十节「本政策的变更」改为第十一节。锚点 `#website-enquiries`，首页表单链到这里。
- 第五节那句「不会为自身目的将个人信息传输至境外」收窄为「工作室的个人信息」，并指向第十节。
- `Support_Policy.html`「当前联系路径」一段改为描述现在的表单。没有写回复时限。
- 底稿是 `PWE-AI-BOTs/docs/privacy.md`（Lee 2026-10-02 为 pwe-house 定稿）。和底稿不同的三处：
  1. 没有写「10 个工作日内处理」。本政策第八节明说不在这里写答复期限，新的一节指向第八节。
  2. 没有电话一项。这张表单不收电话。
  3. 多一条「它看不到什么」：助手无法访问任何工作室的记录。

### 验证（2026-10-10）

| 对象 | 结果 |
|---|---|
| 新测试 `test_assist_widget_and_form.py` | 32 条通过。改坏实现 6 种方式，6 种都变红 |
| local gate | `All checks passed`。pytest 2569 passed / 41 skipped；smoke 73 / 0；租户隔离 257 / 0 |
| 浏览器，`/studio`，桌面宽度 | 见下表 |
| 浏览器，`/zh/studio/`，375 宽 | 中文标签和报错；单列，控件高 54px，输入框字号 16px；没有横向溢出；隐私链接指向 `/zh/…#website-enquiries` |
| 浏览器，隐私政策 | `#website-enquiries` 落在第十节上 |

表单在浏览器里走过的状态（本机，端口 8897）：

| 做了什么 | 看到什么 |
|---|---|
| 不带 `?assist=1` 打开 | 页面里没有窗口脚本 |
| 带 `?assist=1` 打开中文页 | 加载了一次脚本，`data-site="pwe-studio"`、`data-lang="zh"`。本机没有 Worker，脚本是 404，页面其余部分正常 |
| 空着点「发送」 | 三个必填项各有一句报错，边框加粗，焦点在姓名 |
| 邮箱填 `not-an-email` | 邮箱下报错，焦点在邮箱 |
| 填好再发（真请求） | 请求体字段齐全；按钮变「Sending…」并禁用；本机返回 404，于是露出回落区，焦点在「Open Mail」，内容原样保留 |
| 把接口换成返回 429 | 一句限流提示，内容保留，按钮可用 |
| 把接口换成返回 400 和 `fields` | 对应字段下报错，焦点在第一个 |
| 把接口换成网络失败 | 回落区 |
| 把接口换成返回 201 | 表单换成成功态，焦点移过去 |

后四行是在浏览器里临时替换 `fetch` 做的，只用于验证。

### 没有验证的

- **成功路径没有对着真的询盘接口走过。** 本机没有 Worker；预备环境的 Worker 只接受它自己页面的请求。发布后用陷阱字段走一次：它返回 201，不存、不发邮件。
- **窗口本身没有在这些页面上出现过。** 本机没有 `widget.js`。
- CI gate 没有在 `feat/assist-widget-form` 上跑，因为它没有推送。
- 手机宽度只有量出来的数字，没有截图：浏览器面板在手机宽度下截不到滚动后的位置。
- 没有看深色模式。product site 目前没有深色模式入口，未核实系统深色下的表现。
- 隐私政策里关于 Anthropic 的两句（默认不用于训练、处理在澳大利亚境外）抄自 `PWE-AI-BOTs/docs/privacy.md`。那份文件的 D 项写着「未核实」（2026-10-08）。发布前由 pwe-ai-bots 一侧核实。

## 读页面时发现的：公开页面写的主机位置是错的

**这不在本轮范围里，没有改。** 需要 Lee 定。

- 生产 2026-09-17 从 AWS Lightsail 迁到了 Oracle Cloud。2026-10-10 读主机的实例元数据：区域是 `ap-melbourne-1`（墨尔本）。
- 2026-10-10 读主机的备份单元：`pwe-backup@.service` 的说明是「Encrypted off-site backup to Cloudflare R2」。
- 下面四个公开页面仍然写着 AWS 悉尼：

| 页面 | 位置 | 现在写的 |
|---|---|---|
| `product-home.html` | 458–459 | 数据在悉尼，`ap-southeast-2` |
| `customer-resources/FAQ.html` | 52、58–60、65–66、71–72 | 运行于 AWS Lightsail 悉尼区域；Let's Encrypt 证书；备份在同一实例上，没有异地副本 |
| `customer-resources/Privacy_Policy.html` | 145–146、160–161 | 数据在 AWS 悉尼；备份与服务在同一实例 |
| `customer-resources/Terms_of_Service.html` | 118–119 | 服务运行于 AWS 悉尼区域 |

- 首页 FAQ 和服务 FAQ 进了 Assist 知识全文。PWE Assist 现在会按这些句子回答「数据放在哪」。
- 改之前还缺三个事实，我没有：R2 存储桶在哪个区域；旧的 Lightsail 实例上是否还留着一份 2026-09-17 之前的数据，打算留到什么时候；从 R2 恢复有没有演练过。

## pwe-clinic

- 清理分支：不需要同样的改动。
- B、C、D：不涉及安全、RLS、计费、Xero 或账务代码。pwe-clinic 没有 product site，不需要同样的改动。
- 主机位置那件事：pwe-clinic 的容器在同一台主机上（2026-10-10 `docker ps` 看到 `pweclinic-app-1`）。它的文档是否也写着 AWS，没有打开核对。

## 下一步（负责人）

1. Lee：定「等 Lee」里的四件事。
2. pwe-ai-bots 的会话：正式部署之后通知本仓库。
3. Claude（本仓库的会话）：收到通知并得到 Lee 同意后，发布 B、C、D；发布后用陷阱字段验一次表单，用 `?assist=1` 验一次窗口。

## 发布时又做了什么（2026-10-10 下午）

1. **主机位置**（`4a5ddd3`）。四个公开页面改为 Oracle Cloud 墨尔本。每句话对应一次当天的实测：实例元数据、响应头、`docker ps`、备份定时器、备份说明里的恢复演练记录。
2. **这句错话为什么能留三周。** `test_customer_resources_brand.py` 断言页面里有 `AWS Lightsail`、`ap-southeast-2` 和「off-box copy is still an open item」。把页面改对会让 local gate 变红。这些断言已改为当天量到的事实。
3. **隐私政策第十节里 Anthropic 那几句**，按 pwe-ai-bots 的会话 2026-10-10 核实的内容写：默认不用于训练；至多保留 30 天；短期保留的那一份在美国；对话记录由我们保存在 Cloudflare，不由 Anthropic 保存。
4. **本机库** Growth 的价格从 199 改为 189，与生产一致。恢复原值：`update plans set monthly_price_aud = 199 where code = 'growth'`。
5. **v10.20.7** 带着 `gate` 档发布。在生产上用过窗口和表单之后，**v10.20.8** 把开关改成 `on`。
6. **`on` 档的加载方式改过一次。** 最初用的是带 `data-lang="zh"` 属性的静态标签，local gate 拦下了：这些页面上 `data-lang` 是写作标记，已有测试断言它不出现在发出的页面里。改为和 `gate` 档相同的脚本加载，去掉条件。测试没有放宽。

本节之前写着「没有验证」的两条，现在已在生产上验证：窗口在这些页面上出现并回答；表单的成功路径（用陷阱字段）。
