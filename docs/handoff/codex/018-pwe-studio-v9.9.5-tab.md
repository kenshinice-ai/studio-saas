# PWE Studio v9.9.5 — 那排 tab 从来没有被接上过

> 当前阶段：**已部署上线**。生产 `appVersion=9.9.5`。
> 审计与方案见 `docs/design/Platform_Admin_Audit_2026-08-13.md`。

## 发布证据（2026-08-13）

| 层级 | 已验证事实 |
|---|---|
| Source | `origin/main` = `8cfc54a`；`VERSION=9.9.5`。 |
| Local gates | `verify_local.sh` **All checks passed**；pytest `1812 passed, 5 skipped`。 |
| Package | `PWE-StudioSaaS-aws-9.9.5.tar.gz`，SHA-256 `edf1152cfc99a8600c7f28e32488350bbed450eaf93ec741df422a8e1c3126d1`；部署前备份 `…20260813T080947Z.dump`。 |
| Production | deep health `appVersion=9.9.5`、`db=ok`、`tenants=6`、`themes.unreadable=0`、`workspaces.stale=0`。 |
| 线上控制台 | 七项抽查全过：渲染 tablist、`wireEditorTabs` 存在、**editTenant 确实接线**、旧的失效 nav 已消失、错误计数、保存跳转、编辑器里没有手风琴。 |
| 线上词典 | 新词条已生效（基础资料 / 负责人与联系方式 / 随套餐继承 / 重置演示数据 / 放弃未保存的修改？ …）。 |

## 一 · 根因：接线接在了错的编辑器上

不是 CSS 挡住，不是事件冒泡，是**监听器从来没被绑上**：

| 行号 | 事实 |
|---|---|
| `editTenant()` 内 | 渲染出 `<nav class="editor-section-nav">` 和五个按钮 |
| `editTenant()` 内 | 调用 `openWorkspaceEditor()` 挂进 DOM |
| **整个 `editTenant()`** | **没有一次 `wireEditorSectionNav()`** |
| `addPlan()` 内 | 唯一的调用点——而套餐编辑器根本没有这条 tab 条 |

手风琴还能用，是因为 `<details>` 是浏览器原生的、不需要 JS。
**这正是它一整个版本没被发现的原因**：表单照常可用，tab 只是失效的装饰。

而且旧测试 `assert "function wireEditorSectionNav" in html` 只问「这个函数存在吗」，
所以那段时间它一直是绿的。现在改成问「editTenant 有没有接上它渲染的 tablist」。

## 二 · 按方案 B 重做：真 tab

复用**文件里已有的** tab 组件（租户详情面板在用），不新造第三套导航：
`role="tablist"` / `role="tab"` / `aria-controls` / `aria-selected`、
roving tabindex、←→/Home/End 切换。

分页会藏起内容，所以配套做了三件事——这是方案 B 的前提，不是附加功能：

1. **每个 tab 上有错误计数**。数的是该面板内的 `[aria-invalid="true"]`
   加上可见的 `[role="alert"]`。
2. **每个 tab 上有改动圆点**。原本 `markEditedSections()` 已经在按段追踪，
   现在把结果显示到 tab 上。
3. **保存失败自动跳到出问题的那个 tab**。
   「检查订阅日期」这句话在订阅页被藏起来时是一条死路。

### 线上真实 DOM 验证（不是只看代码）

用 fixture 直接驱动 `editTenant()`，在真实页面里断言：

| 动作 | 结果 |
|---|---|
| 打开 | 5 个 tab、5 个面板，只有 `basic` 可见，tabindex `[0,-1,-1,-1,-1]` |
| 点「订阅与套餐」 | 选中并只显示该面板 |
| ← → / Home | 正确移动，**任何时刻只有一个面板可见** |
| 在隐藏的「负责人」页改字段 | 该 tab 出现改动圆点，**当前页不动** |
| 制造非法日期 | 「订阅」tab 出现 `error:1`，当前仍在 `basic` |
| 点保存 | **自动跳到 `subscription`** 并显示该面板 |

## 三 · i18n 门禁有个盲区，而且新代码一直在往里加

门禁**确实覆盖** `super-admin.html` 且是绿的，但它把 `<script>` 当作不透明——
而这个控制台的编辑器几乎全由模板字符串拼出（`editTenant()` 一个函数 148 行模板）。

量出来：script 里可见界面文案 98 条，**11 条不在词典里**，
其中四条是上一版我自己加的重置对话框。

修法：给提取器写了一个**处理嵌套的扫描器**（正则会把
`${/*safe*/editorPanelLead('Basic', )}` 当成英文文案报出来），
把模板字符串里的 HTML 片段喂进同一个提取器。

打开之后暴露 33 条，处理如下：

- **不该翻译的**用语义标记排除：示例值（`Northside Art Studio`、`mellow-pear-studio`、
  `e.g. studio-pro`）加 `data-i18n-lock`；要照着敲的短语放进 `<code>`；URL 路径由提取器跳过。
- **真正缺的 35 条**补进 `admin-i18n.js`。

## 四 · 拼接的句子翻译不了

词典按**整句**查表，`Inherited from ${plan} plan.` 永远查不到。
拆成 `<span>Inherited from plan</span> · {套餐名}` —— 词是词，专名是专名。

确认短语同理：`Type RESET-... to confirm` 被拆成「Type」+ 字面量 +「to confirm」三段，
改成标签「输入确认短语」+ 独立一行 `<code>`。

`window.confirm('Discard unsaved changes?')` **不用改代码**——
`admin-i18n.js` 早就包装了 `window.confirm`，缺的只是词条，已补。

## 五 · 状态

- 本地全量 **1812 passed, 5 skipped**；`verify_local.sh` 全绿。
- 新增 `backend/tests/test_platform_admin_editor.py`（9 条）。
- 两条旧测试按新结构更新，都写清了为什么改。
- 尚未打包部署。

---

