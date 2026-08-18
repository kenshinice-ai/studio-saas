# 2026-08-19 — admin-i18n.js:同三类缺陷的审计与修复

> 范围:仅 `backend/frontend/assets/admin-i18n.js` + 重建 `asset-manifest.json`。
> 未改 JSX,未升版本号,未部署。承接
> `2026-08-18-cms-i18n-measure-words.md` 里「Studio Admin / Super Admin 走另一个
> 文件,同样三类问题未审计」的待办。

## 方向是反的:这里查的是「中文界面残留英文」

`cms-i18n.js` 是 `const en`(中文源 → 英文);`admin-i18n.js` 是 `const zh`
(**英文源 → 中文**)。两个控制台用英文书写,翻译成中文。所以审计要反过来:
以中文遍历,找仍是英文的界面文案。

这也让「合法英文」的边界比 CMS 那轮更宽——文件头自己写着
「Business values and API enums stay in English」。审计因此把租户名、邮箱、
实体 UUID、审计事件码(`invoice.issued`)、套餐代码(`starter`)、
行业预设卡的英文副标(有 `data-no-translate`)单列,不计为缺陷。

## 三类缺陷,逐一对照

### 一、重复键:13 个(CMS 那轮是 10 个)

同一英文键定义两次且译文不同,后写的静默胜出。其中三个是**语义冲突**而非同义:

| 键 | 死掉的那半 | 生效的 | 判据 |
|---|---|---|---|
| `Support` | 「支持」 | **「辅助色」** | 源码里唯一的裸 `Support` 是 `<label for="settingSecondaryColor">`,即品牌辅助色 |
| `Operations` | 「运营」 | **「运维」** | 平台控制台的检查器分区,不是工作室的经营 |
| `Created` | 「已创建」 | **「创建时间」** | `card(operations, 'Created', …)`,是时间字段 |

`Recommended` 一处**改了行为**:此前「主推」被「推荐」覆盖,而解释这个徽章的
句子仍写着「主推徽章只能有一个」——界面说推荐、说明书说主推。已统一为
**推荐**(与公开定价页、路演 deck 的用词一致),并同步改掉那句说明。
其余 9 条只删掉已失效的那半,行为不变,字典不再自相矛盾。

结果:1055 → 1042 条,重复键归零。

### 二、生成式标签没有规则:About 的 24 个字段名

`studio-admin.html:4071` 用模板串生成 `Highlight ${i+1} Title · 中文`,
六个亮点 × 标题/正文 × 中英 = 24 个字符串,字典一个都没有。于是中文界面上
读作 **「Highlight 3 Body · 中文」**——字段名英文、语言标记中文,半句半句。
改为一条规则(不是 24 条词条),并保留既有约定:**语言标记不译**
(手写的成对条目就是 `品牌标语 · English`,它标的是字段内容的语言)。

同族缺口:`Eyebrow` / `Lead` / `Description` 三组(共 6 条)是 HTML 里手写的,
只是漏收录;已按同样格式补齐。

### 三、observer 不监听属性(与 CMS 完全同款)

`observer.observe(document.body, {subtree, childList, characterData})`——
没有 `attributes`。元素挂载时 `localise` 会翻它的 placeholder/title/aria-label,
但控制台之后重写**同一个元素**的标签时(租户列表每次刷新都重新写
`aria-label="View <租户名>"`),观察者不会被唤醒,那些值永远停在英文。
已加 `attributes: true` + `attributeFilter`(过滤是必需的:`applyAttributes`
会把结果写进 `data-` 属性,不过滤就自我循环)。

## 另外补的四处

- `^Signed in as (.+)$` —— 字典里原有的规则写的是 `Signed in: (.+)`,
  而 `studio-admin.html:4523` 生成的是 `Signed in as <email>`。
  **规则为一种页面从未产出的措辞而写**,所以登录状态行一直是英文。
- `^View (.+)$` —— 平台管理租户行的 aria-label,只有 `Open`/`Edit` 有规则。
- `^(\d+) views · (\d+) registrations$` —— 官网分析行;原有
  `^(\d+) registrations$` 永远匹配不到这个复合串。
- `Website modules` / `FAQ & messages` / `Principal` —— 发布差异列表的分组名,
  六个里三个没词条。**`Principal` 是审计没看见的**:那个列表只渲染与已发布
  基线有差异的分组,当时它没差异。测量有盲区,读代码补上了。

## 验证

- 起本地栈,以中文遍历 Studio Admin 全部 12 个标签页 + Super Admin 四个视图
  (共 17 屏),逐个文本节点与 placeholder/title/aria-label 收集残留英文。
  十项目标缺口(Signed in as / View X / Website modules / FAQ & messages /
  Eyebrow · / Lead · / Description · / (direct) / views · / Highlight 家族)
  **修复后全部消失**。
- 目检两屏中文界面:Studio Admin「亮点 3 正文 · 中文 / · English」、
  「打开运营 CMS」、「草稿已保存 —— 尚未公开」;Super Admin「已登录:
  admin@studiosaas.local」、「运维」、「推荐」徽章。
- 全量 pytest:**2838 通过 / 6 skip**;`test_admin_i18n_coverage.py` 3 项全绿。
  `test_tenant_isolation_by_construction.py` 两项失败——断言原文即「应用以
  超级用户连库,RLS 被无条件绕过」,本机 Postgres 角色所致,与本轮无关。

## 一个方法论教训

中途我看审计数字从 15 降到 13,以为 Highlight 规则没生效,差点去改规则。
实测 DOM 才发现规则**早就生效了**——剩下的 13 条里有 12 条是
`亮点 1 标题 · English`,正是**正确输出**,只是被我「中文里含 3 个以上拉丁字母
即判半翻译」的启发式判成了缺陷。**只比数量不比内容,会把成功读成失败。**

## 已知未做

- 报名表单字段类型选择器的选项显示为 `text` / `textarea` / `select`。
  按文件自己的政策(API 枚举保持英文)可以留;但它们出现在运营者要点选的
  下拉里,译成「文本 / 多行文本 / 下拉选择」更合适。没动的原因是:`text`
  作为字典键会命中任何整节点为 "text" 的文本,风险不值这点收益;
  正确修法是在源码里把显示值与 `value` 分开。
- 本地演示库的套餐种子仍是 100/500/1000 学员、Growth AUD 199,而线上
  plans 表是 50/250/500、AUD 189。**这不是 i18n 问题**,是本地种子数据比
  线上旧;与 2026-08-18 那轮在销售材料里发现的是同一处漂移,记在这里备查。
- 两个 i18n 文件现在有三处同构逻辑(`applyText` / `applyAttributes` /
  observer 配置)各写了一遍,这轮的三类缺陷有两类是**两边都犯**。
  合并成一个共享模块能让下次只修一处——但那是重构,不在本轮范围。
