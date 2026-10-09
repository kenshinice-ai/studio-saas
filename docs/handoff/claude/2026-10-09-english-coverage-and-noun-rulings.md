# 2026-10-09 · CMS 英文覆盖一轮，和两条用词裁定

> 状态：**已提交、已推 `main`，未发布、未部署。** 生产仍是 v10.20.3（`3a7b36a`）。
> 授权：Lee 2026-10-09「1. 单独做一轮 … 2. 按照推荐 3. 按照推荐 4. 提交 同步 推送」。
> 提交：`8277b17`（`.gitignore`）、`2551815`（两条用词裁定）、本轮英文覆盖一笔。

## 结论

- CMS 源码里的静态中文，英文界面下没有词条的从 579 句降到 0 句无理由的。剩 24 句有理由，逐条列在 `backend/tests/_cms_english_exemptions.py`。
- 这道检查从「只看充值页」扩到「看全部 CMS 源文件」。新增一句没有词条的静态中文，测试就失败。
- 公开页面不再写死「作品」。展示页和报名页改用 `%WORK%`，按租户行业解析。
- Studio Admin 的导航组 `Insights / 经营洞察` 改为 `Analytics / 数据分析`。
- 本轮没有动安全、RLS、计费逻辑、Xero、账务代码。pwe-clinic 不需要同步修复。它的英文缺口和公开页用词**未核实**：本轮没有打开那个仓库。

## 一、英文覆盖

### 怎么做的

1. 把每个 `legacy-root/src/**/*.jsx` 里的静态中文送进真的 `translateCore`。返回值还有中文的记为未覆盖。2026-10-09 实测：1,441 句里 579 句，去重 568 句。
2. 给每句配上源码前后 5 行，交给 Anthropic API 起草。模型 `claude-sonnet-5-5`，16 次请求。每句判成三类：整句上屏、拼接句、不该翻。
3. 逐条审。509 句整句译稿改了 11 句，弃 2 句。33 条拼接规则没有照用：对着源码重写成 21 条规则和 2 个兜底。
4. 在本机用英文走了 13 个 CMS 视图，把静态提取看不到的再补 36 条。

API 用法来自 `~/Documents/ClaudeCode/claude-credit-2026-10/tasks/_common.md`。密钥从 `~/.config/anthropic/env` 读进环境变量，没有打印，没有写进任何文件。
用量（2026-10-09）：输入 121,680、缓存写 33,328、缓存读 533,248、输出 108,787 token。按那份文件的价目估算约 US$1.52；缓存写按输入价 1.25 倍算，这个倍数**未核实**。
送出去的内容：界面中文、源码片段、`docs/Glossary.md`、现有字典。没有租户数据。

### 改了什么

| 文件 | 改动 |
|---|---|
| `backend/frontend/assets/cms-i18n.js` | 加 575 条词条、21 条句子规则、2 个兜底。`充值与退款` 的英文从 `Recharge & refunds` 改为 `Top-up & refunds`：全字典 35 处用 top-up，只有这一处不同。 |
| `backend/tests/test_cms_english_coverage.py` | 由 `test_topup_panel_is_fully_translated.py` 改名并扩到全部 CMS 源文件。加 9 条拼接句探针。 |
| `backend/tests/_cms_english_exemptions.py` | 新增。24 句不翻的静态中文和各自的理由。理由只有五种。 |
| `backend/scripts/capture_manual_shots.py` | 英文导航标签跟着改成 `Top-up & refunds`。 |

两个兜底都在 `translateCore` 末尾，只在其中一段已有词条时才生效：

- `标签：值`。`加载失败：${e.message}` 变成 `Could not load: …`。标签最长 12 个字。
- ` · ` 和 `；` 连接的列表。每段各查一次，名字和日期原样通过。

### 没有覆盖的（已知缺口）

- **模板字符串拼出来的句子。** 源码里有 185 行带中文的模板字符串（2026-10-09 实测）。它们没有静态形态，提取不到。本轮只为其中 21 种写了规则，测试里探了 9 句。其余**未核实**。
- **紧挨着变量的 JSX 文字。** 例如 `今日名单{count}`。把提取放宽到这一类后是 1,678 句候选、170 句未覆盖。这个数含噪声：模板字符串的切片也会被抓到。这一类没有进门禁。
- **导出的 CSV。** 表头是中文，不经过 DOM，字典管不到。7 句，记在豁免清单里。
- **发给家长的话术和成长报告。** 按租户语言写，不翻。7 句，记在豁免清单里。

### 验证（2026-10-09，本机）

- local gate：`STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh` 输出 `All checks passed`。pytest 2540 passed、41 skipped；租户隔离 257 passed、0 failed。
- 覆盖测试验过会红：删掉 `确认撤销` 一条词条，测试失败并点名这一句。
- 浏览器，英文，owner 角色，`lets-paint-showcase`：13 个视图（dashboard、roster、students、new_student、pending、courses、topup、billing、finance、stats、logs、works、settings）。`html lang=en`，0 个页面错误。剩下的中文都是租户自己录入的课程名、课包名、家庭名和跟进备注。
- **没有看的：** 弹窗和抽屉（确认框、学员档案、发票详情、Xero 集成面板、私教课）、teacher 角色、手机宽度、生产环境。充值确认框的英文只有字典探针作证，没有在浏览器里点出来看。

## 二、两条用词裁定

### 「作品」：家长读到的地方禁，员工界面保留

- 解析器收成一处：`public-surface.js` 的 `fillNouns()`。首页、展示页、报名页都调用它。此前只有首页有，另两页就把「作品」写死了。
- 名词不添意思的地方直接去掉：灯箱按钮是「上一个 / 下一个」，加载提示是「正在加载…」。
- 数量不带量词：「13 件公开作品」改为「共 13 项」。量词过不了占位符（「12 件公开曲目」是错的）。
- 「画室」「画艺」全界面禁。Studio Admin 两处占位符改为显示 `%VENUE%`；删 2 条死词条。
- `check_terminology.py`：公开模板改为从目录读取，三个 `_shell-*-links.html` 此前不在名单里；新加「作品」「画室|画艺」「经营洞察」三条规则。
- 新测试 `test_every_page_that_carries_noun_tokens_resolves_them`：模板里有占位符却不调用解析器就失败。
- 顺带修了一处：报名页、展示页、课表页的演示站提示在英文下一直显示中文。

规则写在 `docs/Glossary.md` 的「Where 作品 is banned」一节。

浏览器核对（2026-10-09，本机，中英文各一遍）：

| 租户 | 行业名词 | 展示页 | 报名页同意条款 |
|---|---|---|---|
| `music-studio-showcase` | 曲目 / piece | 「目前还没有公开的曲目。」「共 6 项」「6 published pieces」 | 「展示学员曲目」 |
| `lets-paint-showcase` | 作品 / work | 「主理人作品」「查看全部作品」「共 13 项」 | 未看 |

页面上没有露出 `%`，控制台 0 个错误。

**这一条改了同意条款的字面。** 报名页的展示授权和隐私说明里，非美术租户看到的名词从「作品」变成本行业的词（音乐租户是「曲目」）。首页的同一句早就这样。授权的含义和记录方式没有变，`privacyNoticeVersion` 没有动。

没有改的：

- 产品站定价文案 `public_site.py:337`「官网展示 N 件工作室作品」。这是品牌文案，不在租户模板里。
- 展示页的英文标题 `Selected Work`、`Work from this studio`。英文的 work 不是美术专用词。

### `Insights` → `Analytics / 数据分析`

- `studio-admin.html` 导航组标签、`admin-i18n.js` 词条、`Studio_Owner_Guide.md` 一处。
- 发布说明里的历史记录保留原词。

## 三、给下一个会话

1. 发布前按 `docs/Release_Runbook.md` 走九步。本轮有模板改动，`regenerate_tenant_workspaces.py` 已跑，产物已提交。
2. 手册截图里的英文导航还写着 `Recharge & refunds`。发布前用 `capture_manual_shots.py` 重拍。成功判据：`04-topup.en.webp` 的侧栏显示 `Top-up & refunds`。
3. 如果做下一轮英文覆盖，从「紧挨着变量的 JSX 文字」那 170 句开始。提取脚本的写法在覆盖测试的 `RUNNER` 里，把第一条正则放宽到 `[>}]…(?=[<{])` 即可复现。
