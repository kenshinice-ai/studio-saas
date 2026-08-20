# 2026-08-20 结构重构轮（v10.11.0）—— P1–P4 全案一步到位

> 方案：`docs/design/File_Structure_Refactor_Plan_2026-08-20.md`（rev2）。
> Lee 拍板：「全部都执行 一步到位的模式 包括 xero 做好备份和handoff」——
> 11 域一步拆完（含 Xero 域）、P2/P3/P4 全做、备份与 handoff 闭环。
> 源码回滚点：tag `pre-restructure-v10.10.3`。

## 提交链（全部纯重构，行为零变化；一提案一提交）

1. `0f54171` docs: 方案 rev2 定稿
2. `cfab504` **P1** api_v1.py（15,926 行/191 路由）→ `api_v1/` 包（11 域 + _shared + __init__）
3. `c41498f` chore: 新建 `.git-blame-ignore-revs`（拆分提交入册；本地要
   `git config blame.ignoreRevsFile .git-blame-ignore-revs`，GitHub 自动尊重）
4. `0bff84b` **P2** cms-app.jsx 7,606 → 4,148 行；components.jsx + 7 个新 panel
5. `a5b52dd` **P3①** i18n 引擎合一（i18n-runtime.js）+ 词典重复键门禁
6. `6798d4b` **P4** PBKDF2 合一（server.py → auth.py 别名，双 legacy 格式兼容）
7. `774505b` **冒烟网** console_smoke.py + 它首跑抓到的 studio-admin 登录缺陷修复
8. `45988f1` **P3②** 两控制台内联脚本外置为版本化资产

## P1 —— api_v1 原地包化（机器等价验证）

- 包沿用原名 `api_v1/`：import 路径一字不变；实测对外符号面（10 个符号 +
  Blueprint）在 `__init__.py` 显式保留，另加**全符号联邦**（把各子模块顶层名
  挂上包命名空间），历史 `from studiosaas.api_v1 import X` 全部继续工作。
- **可变状态唯一实例**：限流锁/计数器、`KEEP` 身份哨兵只存在于 `_shared.py`。
- 机械拆分器（AST 归类 + 逐行保真切片 + 前导注释随段走）；两处白名单差异：
  `UPLOAD_DIR` 与 `reset_demo_tenant` 的 `__file__` 深度修正。相对 import 全部
  升一级（`from .auth` → `from ..auth`，否则撞包内新文件名）。
- 验收：**url_map 191 条全等 + 394 个顶层符号 AST 指纹全等**（白名单外零差异）。
- 测试适配的两类坑（后来者注意）：
  - 读源码文本的测试 → 拼接包内 `*.py`（约 30 个文件，含多行表达式变体）；
  - **monkeypatch 必须打在拥有该名字的子模块上**（函数在自己模块的 globals 里
    解析名字；patch 包属性无效）。`import studiosaas.api_v1.xxx as y` 会因
    `studiosaas/__init__.py` 的 Blueprint 影子挡住 getattr 链——用
    `importlib.import_module`。
- verify_local 的 py_compile glob 已改为递归子包。

## P2 —— CMS 面板抽取

- 模块级组件/工具 → `components.jsx`（40 个导出，逐字搬家只加 export）。
- App() 的 11 个 JSX 块 → 7 个 panel 文件（dashboard / scheduling / media /
  students / topup / reports / student_profile），props 用「词法交集」计算
  （超集无害，漏了才是 ReferenceError）——**验证手段是 48 张手册截图流水线
  全量实拍** + roster/topup/stats/档案弹窗肉眼抽查，拍完 `git checkout` 还原
  截图资产（重构轮不夹带资产变更）。
- cms-app.jsx 7,606 → 4,148 行；一处契约测试字面量放宽
  （`{tab==='pending' && (` → `{tab==='pending' && `）。

## P3① —— i18n 引擎合一 + 重复键门禁

- `assets/i18n-runtime.js`：一个引擎（词典查找、整句规则、含属性监听的
  MutationObserver、开关 UI、共享语言偏好）。`cms-i18n.js` / `admin-i18n.js`
  只剩：词典 + 整句规则 + 界面策略钩子（`*En` placeholder 锁、data-no-translate、
  原生对话框包装）+ `StudioI18n.mount(config)`。
- **fail-open 出声**：引擎所有入口 try/catch + console.error，最坏是页面保持
  原文，绝不白屏。
- 新门禁 `check_i18n_dictionaries.py`（进 verify_local）：重复键直接红。
  **首跑抓出 52 个存量重复键**（cms 11 / admin 41），按 fromEntries last-wins
  语义保持行为去重（9 组值冲突的保留「现值」，其中 Principal→主理人、
  Eyebrow→眉标题、Description→正文 值得内容轮复核）。
- 三界面真浏览器实测：CMS zh→en、两控制台 en→zh、跨界面语言记忆生效。

## P4 —— 密码哈希合一（行为改动，测试先行）

- 关键发现：两处 legacy 格式**不同**——auth 验裸 `sha256(pw)`，CMS 密码文件是
  `sha256('lps-cms:'+pw)`。天真合并会静默锁死旧密码文件。
- `auth.verify_password` 现在两种 legacy 摘要都算都比（恒定成本），命中即
  `needs_upgrade`；server.py 的 `_hash_pw/_verify_pw` 变纯别名。
- `test_password_hash_consolidation.py` 先写后改：PBKDF2 往返、双 legacy、
  垃圾输入 fail-closed、以及静态断言 server.py 永不再长出自己的 pbkdf2。

## 冒烟网与它抓到的缺陷

- `backend/scripts/console_smoke.py`（CDP 驱动无头 Chrome）：零未捕获 JS 错误、
  boot 到达登录面板、i18n 挂载、**错密码登录必须渲染页面自己的持久错误提示**。
- 首跑即红：studio-admin 的 `loginStudioAdmin` 把 `.catch` 链在 `runUiAction`
  上，而 runUiAction 内部捕获并 resolve——catch 是死代码，登录失败只有 3 秒
  toast，`role=alert` 的 loginError 从不渲染（super-admin 一直是对的）。
  已按 super-admin 结构对齐修复；`Logging in…`（省略号）沿用词典既有条目。

## P3② —— 控制台脚本外置（范围裁决）

- 两页各约 4,200 行内联 `<script>` **逐字外置**为 `/assets/studio-admin.js`、
  `/assets/super-admin.js`（经典脚本、非模块非 IIFE：顶层声明仍进全局词法
  环境，与内联时代完全同语义；同文档位置、同 ?v 缓存戳）。页面瘦为纯标记
  （3,279 / 3,068 行）。
- **本轮不建 console-core.js**（偏离方案理想态，理由记录在案）：super-admin
  按 rev2 决定不共享业务运行时（救援台不与被救对象同船），共享文件只剩一个
  消费者——按本轮自己的「共享门槛」规则（同缺陷修过两遍才共享），单消费者的
  抽壳是错误抽象。等 CMS 或第二个控制台真要消费时再切缝。
- 静态测试统一经 `tests/_console_sources.py`：「页面包含 X」= 标记 + 其脚本
  资产；`script_source()` 类 helper 计入资产；i18n 覆盖测试的 HTML 解析器
  刻意只读纯标记。

## 门禁与验证状态（本文件写作时）

- 全量 pytest **2,817 通过**（拆分适配后新增 13 项：哈希 5 + 其余为适配中
  收紧的断言）；`test_cms.py` legacy 冒烟绿；console_smoke 两页绿；
  三界面浏览器实测绿。
- 发布证据（bundle SHA、dump、生产 deep health）随部署在
  `HANDOFF_LATEST.md` 四层身份表闭环。

## 后续留意

- 词典 9 组「值冲突去重」保留的是线上现值，内容轮可复核措辞。
- P2 的 App() 仍持 ~3,000 行状态与处理函数——下一步如果继续瘦身，方向是把
  域状态随 panel 下放（billing.jsx 模式），不是继续抽 JSX。
- console-core.js 的触发条件：出现第二个真实消费者。
- 集成页 Beta 徽标（X4 欠的纯文案）仍未做。
