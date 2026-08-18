# 2026-08-19 — 两处漂移按线上对齐(套餐额度 + 字段类型下拉)

> 范围:`backend/db/schema_v1.sql`、`backend/db/migrations/0001_schema_v1.sql`、
> 新增 `0046_plan_student_limits_match_published.sql`、
> `backend/frontend/studio-admin.html`、`backend/frontend/assets/admin-i18n.js`
> (+ 资产清单重建)。未升版本号,未部署。
> 承接 `2026-08-19-admin-i18n-audit.md` 的「已知未做」两条。

## 权威来源

`pwestudio.online/pricing` 的 `data-plans`(本轮重新实测,不用记忆):

| code | 月费 | 学员 | 席位 | 存储 | 作品 | 推荐 |
|---|---|---|---|---|---|---|
| starter | AUD 49 | **50** | 1 | 2048 MB | 15 | 否 |
| studio | AUD 99 | **250** | 5 | 10240 MB | 60 | 是 |
| growth | AUD **189** | **500** | 20 | 51200 MB | 150 | 否 |

仓库此前是 100 / 500 / 1000,growth AUD 199——生产在某个时点由平台控制台改过,
git 里的目录没跟上。2026-08-18 那轮已按同一次测量修正了销售 deck,这是同一处
漂移的另一半。

## 漂移一:套餐额度

### 只改基线种子是不够的 —— 实测才发现

先改了两个基线(`schema_v1.sql` 与 `0001_schema_v1.sql`,都是
`ON CONFLICT (code) DO NOTHING`,因此**只影响全新数据库**,不触碰生产)。
建了一个一次性新库跑迁移验证,结果 growth 仍是 **1000**:

`0021_plan_quota_revision.sql` 里有一条 `UPDATE plans SET student_limit = 1000
WHERE code = 'growth'`,它在每次全新 bootstrap 时把值再抬回去。**只改种子对
growth 完全无效**——如果不去量渲染后的库,这个改动会带着一个静默失效的分支发出去。

### 因此新增 0046

沿用 0021 的写法:按 code 限定、值不同才更新、幂等。三条学员上限
100→50 / 500→250 / 1000→500。不编辑 0021 本身——那是别的数据库已经applied
过的历史。

**价格故意不进迁移**,这一点跟随 0021 的先例(它明确写着 prices 不动):
生产已经是 189,基线种子也已改成 189;而价格是钱,运营方可以在平台控制台里
设定,一条每次部署都重写价格的迁移会静默盖掉那个决定。老库保留运营方自己配的价。

### 验证

- 全新库跑完 0001–0046:`49/50 · 99/250 · 189/500`,与线上逐项一致。
- 再跑一次:`Database is up to date. Nothing to apply.`(幂等)
- 既有本地库(原 100/500/1000)应用 0046 后变为 50/250/500;价格保持 199
  (符合设计);测试用套餐 `isolation-no-portfolio` 未被触碰(按 code 限定)。
- 容量安全同 0021:这是降额,应用层只做准入控制
  (`_student_capacity` 对**新增**学员返回 403),不删不归档任何既有记录。
  生产已经是这些值,所以那边是零行更新。

## 漂移二:报名字段类型下拉

`studio-admin.html` 把枚举本身当标签打出来:
`['text','textarea','select'].map(type => <option value=type>{type}</option>)`。
中文界面上运营者看到的是 `text / textarea / select`。

上一轮记的是「不修,因为把 `text` 当字典键会命中任何整节点为 text 的文本」——
那是给**错的修法**找的理由。正确修法是把**显示值与 value 分开**,和它旁边
`Required / Options` 那个下拉(Optional/Required)的写法一致:

- option 标签改为 `Short text` / `Long text` / `Dropdown`;
- `value` 仍是 `text` / `textarea` / `select`,保存路径(`[data-reg-type]` 读 `.value`)
  一个字节都没变;
- `admin-i18n.js` 补三条:单行文本 / 多行文本 / 下拉选择。

实测两种语言:
`zh → 单行文本|多行文本|下拉选择`,`en → Short text|Long text|Dropdown`,
两边 `value` 都是 `text|textarea|select`,`selectedValue=text`。

## 测试

全量 pytest **2838 通过 / 6 skip**;`test_tenant_isolation_by_construction.py`
两项失败是本机 Postgres 超级用户导致的环境失败(断言原文即「应用以超级用户
连库,RLS 被无条件绕过」),与本轮无关。

## 留给下一个 project 的两件事(本轮不做)

- 两个 i18n 文件三处同构逻辑是否合并成共享模块。
- 大文件切分(`studio-admin.html` 与 `cms-app.jsx` 都已到需要讨论的体量)。
