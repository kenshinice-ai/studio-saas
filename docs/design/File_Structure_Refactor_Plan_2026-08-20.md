# 文件拆分与功能共享方案（2026-08-20，讨论稿 rev2）

> 状态：**方案，未拍板，未动代码。** 讨论定稿后按提案逐个独立排轮，
> 拆分轮绝不夹带功能改动；每轮出口都是「路由/行为逐条等价 + 全量门禁绿」。
>
> rev2（同日第二轮）：补拆/共享的**利弊权衡说实话版**与**稳定性总则**；
> P1 形态从「新建 `api/` 包 + shim」改为「包就叫 `api_v1/`，import 面零变化」
> （依据实测：对外 import 面 = 10 个符号 + Blueprint，散布 20+ 测试文件）；
> P3 第二步范围缩为租户面（super-admin 救援台不共享业务运行时）；
> P4 哈希合一从「顺带」重新归类为独立行为改动（安全路径，须带双格式回归）。

## 0. 现状体检（全部实测数字）

### 后端

| 文件 | 行数 | 判断 |
|---|---|---|
| `backend/studiosaas/api_v1.py` | **15,926** | **全库最大单体**：191 条路由、34 个 URL 域、一个 Blueprint |
| `backend/server.py` | 2,673 | WSGI 骨架 + 安全中间件 + 静态服务，域尚单一 |
| `backend/studiosaas/services/`（22 文件） | 最大 882 | **健康**——Xero 三件套（xero / xero_oauth / xero_transport）就是分层该有的样子 |
| `backend/tests/`（87 文件） | 最大 2,006 | 健康，按域清晰 |

### 前端

| 文件 | 行数 | 判断 |
|---|---|---|
| `legacy-root/src/cms-app.jsx` | 7,606 | `App()` 一个组件约 **6,400 行**；panels 已抽出 9 个（模式已验证） |
| `backend/frontend/studio-admin.html` | 7,490 | 无构建内联 JS **4,225 行 / 140 个函数** |
| `super-admin.html`（仓库根） | 7,433 | 同款形态，**169 个函数** |
| `cms-i18n.js` + `admin-i18n.js` | 1,014 + 1,100 | **结构性同构**：同样的字典 + MutationObserver 引擎写了两遍 |
| `tenant-template/index.html` | 2,401 | 生成器源模板 |

### 已实证的重复（不是理论）

1. **同一套缺陷修两遍**：2026-08-18/19 两轮 i18n 修复，CMS 与 admin 控制台是
   「同三类缺陷」（重复键互相覆盖、observer 不监听属性、碎片短语）——引擎同构、
   各自漂移的直接代价。
2. **PBKDF2 密码哈希实现了两份**：`server.py _hash_pw/_verify_pw`（legacy CMS
   密码文件）与 `auth.py hash_password/verify_password`（用户表），存储格式同为
   `pbkdf2$iter$salt$hash`，逻辑重复。
3. **三个 API client**：cms-app.jsx 的 `api()`、studio-admin.html 内联
   `api()`（:4449）、super-admin.html 内联 `api()`（:4120）——CSRF 头、错误形状
   各写各的。
4. **超大单文件是脚本化编辑的重灾区**（memory: scripted-edit-discipline）：
   15,926 行里做精确 replace，失手成本远高于千行级文件。

### rev2 补充实测（决定方案形态的三个事实）

- **api_v1 的对外 import 面很小但很散**：`server.py` 拿 Blueprint；20+ 个测试
  文件直接 `from studiosaas.api_v1 import …`，去重后**只有 10 个符号**：
  `KEEP`、`_subscription_date`、`_default_visual_theme`、`_normalize_visual_theme`、
  `_published_schemes`、`_plan_change_impact`、`_plan_payload`、
  `_project_legacy_data_for_role`、`_resolve_credit_movement`、`_tenant_write_payload`。
  另有历史怪癖：`studiosaas/__init__.py` 里 `from .api_v1 import api_v1` 会让
  包属性 `studiosaas.api_v1` 被 **Blueprint 影子盖过子模块**（test_dark_framework
  里有注释存证）——测试因此普遍用 `importlib.import_module`。
- **文件里有可变模块级状态**：`_public_rate_limit_lock` + `_rate_limit_calls_since_prune`
  （限流窗口共享状态）、`KEEP = object()`（**身份哨兵**，全库靠 `is KEEP` 比较）。
  拆分若产出两份实例：限流窗口分裂、`KEEP` 恒不相等——**全部静默失效**，
  测试未必抓得住。这是 P1 最大的真实风险点，对策见 P1。
- 仓库**尚无** `.git-blame-ignore-revs`；`backend/scripts/capture_manual_shots.py`
  的 48 张手册截图流水线**现成可当视觉回归**用。

---

## 1. 第二轮权衡：拆与共享的利弊（说实话版）

### 拆单体：收益是复利，代价是一次性的

**未来维护的「好」**：
- 定位、评审、diff 都按域收束——改学员域只 touch students 文件，评审者不用在
  1.6 万行里找上下文；
- 并行工作不再互相踩：两轮改动只要不同域就零冲突；
- 脚本化/精确编辑的失手面从 15,926 行降到千行级（这是已付过学费的坑）；
- 编辑器与 LSP 在千行级文件上的响应完全不同；
- 新会话/新人上手：域文件名就是目录，不再靠全文扫描建立地图。

**未来维护的「坏」（不粉饰）**：
- git blame 在拆分提交处断层——对策是 `.git-blame-ignore-revs`（要新建；
  GitHub 网页端自动尊重，本地各自 `git config blame.ignoreRevsFile` 一次）；
- 16k 行里函数自由互引，**内部调用图必须先测绘**：跨域引用要么下沉 `_shared`
  要么显式跨模块 import，弄错就是循环 import（好在这是响亮失败，启动即炸，
  不是静默错）；
- 可变模块级状态与身份哨兵（上文实测）拆错了是**静默失败**——必须唯一实例；
- 「这个函数在哪」从单文件 Cmd-F 变成 rg 全包——真实但可接受的税。

**判断**：单文件的维护成本随行数**继续复利增长**（每轮都在往里加路由），
拆分的代价是**一次性**的且每条都有机械对策。拆，但形态按 P1 rev2 优化——
第一稿「新建 `api/` 包 + 留 `api_v1.py` shim 一版」**作废**，改为
**包就叫 `api_v1/`**：import 路径一字不变，10 个外部符号在 `__init__.py`
显式 re-export，20+ 测试文件零改动，无 shim、无过渡期、无二次删除轮。

### 共享：门槛规则 + 设计规则

**收益**：一处修复处处生效；一致性从「靠记得」变「机器管」。

**代价（不粉饰）**：
1. **爆炸半径**：共享代码一个 bug 同时打穿所有挂它的界面。尤其
   super-admin 是出事时的**救援台**——把救援工具和被救对象绑上同一条船，
   是运维上的坏主意；
2. **错误抽象比重复更贵**：共享之后每次改动都要过「另一个界面会不会碎」的
   心智税；为迁就两个界面而长出的参数开关，比两份直白的重复更难读；
3. 无构建页面共享 = 新增运行时资产依赖——缓存键 v+h 体系已覆盖
   （memory: immutable-asset-versioning），但每个共享文件都要走同一发布纪律。

**门槛规则（本方案的裁决标准）**：**同一缺陷修过两遍，才有共享资格。**
三个候选（i18n 引擎、PBKDF2、api client）全部有双修实证，这就是它们上榜、
其他看起来相似的重复不上榜的原因。没到门槛的重复：容忍，重复比错误耦合便宜。

**设计规则**：
- 共享的是**引擎，不是数据**——词典各留各的，界面词表本不同；
- 共享运行时必须 **fail-open 且出声**：i18n 引擎异常时页面照常可用（只是不翻译），
  同时 `console.error` 报出来。这与「静默兜底就是缺陷」纪律不冲突——
  它出声、可观测，且不在钱/权限路径上；
- **救援台例外**：super-admin 只共享纯化妆层（i18n 运行时），
  **不共享业务运行时**（api client / toast / 表格渲染保持自带）。

---

## 2. 稳定性总则（过程工艺，适用每一轮）

1. **纯搬家轮与行为改动轮绝不混同**。哈希合一（P4#1）因涉及安全路径行为，
   rev2 起归类为行为改动，不再「顺带」。
2. **一域 / 一 panel = 一个提交**，每个提交处等价验收与门禁全绿——
   轮内任何回归可 `git bisect` 到单域粒度。
3. **机器等价优先于人眼**：
   - 后端：拆前后 dump `app.url_map` 逐条全等（191 条 rule/methods/endpoint）
     + **搬家函数 AST 全等**（`ast.dump` 逐函数比对，抓「搬家时顺手改了一行」）
     + 全量 pytest（2,857）+ 隔离 254 + `verify_local`；
   - 前端：拆前用 `capture_manual_shots.py` 定 48 张截图基线，拆后重拍逐张
     diff——**现成流水线，零新建成本**。
4. **每轮独立版本、独立 dump、回滚路径照常**（发布纪律不变）；
   发布窗口**避开月末对账周**（X4 结算月到 2026-09-19 前后）。
5. **X4 结算月内不 touch Xero 域**：`xero*.py` 三件套 + `/integrations`
   13 条路由 + 推送 worker，一行不动。
6. **共享切换一步到位，不留双实现对照**——双实现并存正是我们要消灭的
   漂移温床；安全网是 fail-open 设计 + 冒烟，不是旧代码。

---

## 3. 提案 P1（rev2）—— `api_v1.py` 原地包化（import 面零变化）

**形态**：`backend/studiosaas/api_v1/` **包，沿用原名**：

```
api_v1/
  __init__.py        # 创建 api_v1 Blueprint；按原文件顺序 import 各域模块完成
                     # 路由注册；显式 re-export 实测的 10 个外部符号 + Blueprint
  _shared.py         # 唯一实例区：限流锁/计数器、KEEP 哨兵、通用常量、
                     # _error/_json_payload/_clean_text/_audit_request/
                     # _tenant_context/_require_feature… 等被 2+ 域引用的助手
  public.py          # /public (21)     auth.py      # /auth /team (9)
  students.py        # /students /registrations /attendance (23)
  scheduling.py      # /scheduling /daily-roster /class-schedules /class-bookings /courses (26)
  billing.py         # /billing /plans /packages /export (30)
  teaching.py        # /teaching /progress-reports /calendar (12)
  xero.py            # /integrations (13) —— X4 期间可延后，见「待讨论」#2
  media.py           # /media /portfolio /share-links (7)
  tenant.py          # /tenant /legacy-cms /operational-settings… (~20)
  platform.py        # /admin (18)
  misc.py            # /health /dashboard /notifications /reports… 余量
```

- **原则**：纯移动。单 Blueprint 不变、URL 面一字不动、函数体一行不改
  （AST 全等机器验证）；`studiosaas.api_v1` import 路径不变，
  `from studiosaas.api_v1 import KEEP` 等 10 个符号照常可用——
  **20+ 测试文件零改动，无 shim 过渡期**。
- **预拆分测绘（先于任何搬家）**：脚本生成文件内函数级调用图；
  被 2+ 域引用的助手下沉 `_shared`，单域私有的跟域走。
  可变状态（限流锁/计数器）与身份哨兵（`KEEP`）**只准存在于 `_shared` 一处**，
  其他模块一律 import 引用——这是防静默失效的硬规矩。
- **执行**：一域一提交、每提交 url_map 等价 + 门禁绿；整轮一次做完不留半途态；
  拆分提交写入新建的 `.git-blame-ignore-revs`。
- **验收清单（机器）**：url_map 191 条全等 → AST 逐函数全等 → pytest 2,857 →
  隔离 254 → `verify_local` → 部署后 deep health + 读一次
  `/integrations/xero/reconciliation` 确认对账面无恙。

## 4. 提案 P2（rev2）—— CMS `App()` 续拆 panels（延续已验证模式）

billing.jsx（1,545 行）等 9 个 panel 就是从 App() 里抽出来的，构建链
（esbuild → cms-app.js）不变。把剩下的 ~6,400 行按 view 继续抽：

```
panels/students.jsx     档案 + 时间线（StudentTimeline 组件已在）
panels/scheduling.jsx   课程表 + daily roster
panels/courses.jsx      课程目录 + 套餐
panels/media.jsx        作品集 + 照片
panels/settings.jsx     系统设置壳（billing_identity/integrations 已是独立 panel）
panels/dashboard.jsx    工作台
```

目标：cms-app.jsx 降到 ~2,000 行以内（App 只剩状态编排 + 视图路由 + 通用组件）。
`_shared.jsx`（现 31 行）顺带扩容：api client、fmtApiDate、Toast/ConfirmDialog
等通用件归位。

- **执行（rev2 收紧）**：**一 panel 一提交**；props 显式化（抽出时列全该 panel
  实际读写的 App 状态，杜绝闭包暗引）；每提交跑 bundle 构建 + UI 契约测试。
- **视觉回归（rev2 新增）**：拆前 `capture_manual_shots.py` 定 48 张基线，
  全部抽完后重拍逐张 diff——像素级抓「搬家搬丢了状态」。
- **收益**：最大前端文件按域可读；i18n/样式等横切修复不再在 7,600 行里游泳。
- **风险**：低——纯组件搬家；有 9 个先例；`verify_local` 的 bundle 校验 +
  三静态页打开检查 + 截图 diff 三层兜底。

## 5. 提案 P3（rev2）—— 双控制台共享（两步走，第二步缓行且缩范围）

**第一步（低风险，建议做）：i18n 运行时合一**

- `assets/i18n-runtime.js`：字典查找 + 整句渲染 + MutationObserver（含属性监听）
  一个来源；`cms-i18n.js` / `admin-i18n.js` 退化为**纯字典 + 一行挂载**。
- **fail-open 硬要求（rev2 新增）**：引擎任何异常不得阻断页面——退回原文显示，
  `console.error` 出声。挂载失败的最坏结果是「没翻译」，不是白屏。
- 三类历史缺陷从此只可能修一处；再加一条静态检查进 verify_local：
  字典重复键直接红（两轮修复里重复键各 10/13 个，值得机器管）。
- 字典**不合并**：两个界面词表本不同；若引入「公共基础词表 + 界面覆盖」，
  覆盖规则必须显式（后者胜且打印告警），否则重蹈重复键覆盖的坑。

**第二步（默认缓行，X4 结算月内不动；rev2 范围收缩）：控制台内联 JS 外置**

- 事实：两个 ~7.4k 行页面各持 140/169 个内联函数、各一份 `api()`。
- **范围缩为租户面**：`console-core.js`（api client / toast / dialog / 表格渲染）
  只服务 CMS 与 studio-admin；**super-admin 不参与业务运行时共享**——
  它是出事时的救援台，救援工具不和被救对象同船（它只挂 fail-open 的
  i18n 运行时这类纯化妆层）。super-admin 自身的内联 JS 可以做**外置不共享**
  （拆文件、不合源），获得可读性收益而不引入耦合。
- **为什么缓行**：三静态页不进测试（memory: three-static-pages-must-be-opened），
  一个 ReferenceError 会静默中止整个函数；这是全库测试覆盖最薄的面。
  动它之前必须先补两个控制台的浏览器冒烟（扩展 check_inline_scripts.mjs +
  真浏览器开页断言），**先补网再走钢丝**。
- **明确反对**：把两个控制台合成一个页面。受众（租户 owner vs 平台）、权限面、
  部署面（super-admin 可被 Cloudflare Access 罩住）都不同——合并是伪共享。

## 6. 提案 P4（rev2）—— 零散整合

1. **密码哈希合一**（**rev2 重新归类：独立的行为改动，不再「顺带」**）：
   `server.py _hash_pw/_verify_pw` 收敛到 `auth.py`。安全路径的搬家必须带
   **双格式回归**：两处调用点的**存量哈希**（含 legacy SHA-256 升级路径）
   在合一前后都必须验证通过——测试先行，改动其后。可与 P3 第一步同版本发布，
   但独立提交、独立测试。
2. **仓库根的四个散页**（manual / pricing / product-home / super-admin.html + sw.js）：
   位置是历史约定，牵动打包与 `_public_file` 白名单。**默认不动**，仅记录；
   若未来动，与 P3 第二步同轮。
3. `tenant-template/index.html`（2,401 行）：privacy 十节等静态大块可抽片段，
   但生成器逻辑简单（61 行），**收益一般，不主动做**，下次改公开页顺带。

## 7. 明确不拆清单

- `services/` 22 个文件——现状就是目标形态；
- `server.py`——中间件骨架域单一（P4#1 只是搬走重复的哈希函数）；
- 测试布局——按域清晰，最大 2,006 行可接受；
- Xero 三件套——保持（且结算月内一行不动）。

## 8. 顺序与版本建议（rev2，待讨论）

| 轮 | 内容 | 版本 | 稳定性安排 |
|---|---|---|---|
| 1 | P2 CMS 续拆 | v10.11.0 | 纯前端，结算月内安全；一 panel 一提交 + 截图 diff |
| 2 | P1 api_v1 原地包化（xero.py 延后与否见问题#2） | v10.12.0 | 预拆分测绘 + url_map/AST 等价脚本先写；发布避开 9/19 对账周 |
| 3 | P3① i18n 运行时合一 + P4① 哈希合一（独立提交） | v10.13.0 | 字典重复键检查、哈希双格式回归先进门禁 |
| 4 | P3② 控制台外置（范围：租户面；super-admin 只外置不共享） | 结算月后再议 | 先补控制台浏览器冒烟 |

## 9. 待 Lee 拍板的问题

1. **P1 的粒度**：按 11 个域文件，还是更粗（比如只拆 public/billing/platform/
   其余 四块）？我倾向 11 域——一步到位，避免二次搬家。
2. **X4 期间动不动 Xero 域**：保守版是 P1 时先不动 `/integrations` 13 条路由
   （xero.py 结算月后补一小轮），激进版是一次拆完靠逐张对账兜底。我倾向保守版。
3. **P3② 的时点与范围**：时点绑「结算月后」还是「第一个付费租户前必须完成」
   （与 OPS-01/02 同一触发器）？范围收缩（super-admin 不共享业务运行时，
   只外置不合源）是否同意？
4. **顺序**：P2 先行是否同意？（也可以 P1 先——如果你更在意后端可读性。）
