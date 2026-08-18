# 2026-08-18 — CMS 英文界面:量词缺口、字典重复键、属性从不重译

> 范围:`legacy-root/src/*.jsx`(5 处整句化)+ `backend/frontend/assets/cms-i18n.js`
> (字典与规则、observer)+ 重建 `cms-app.js` 与 `asset-manifest.json`。
> 未升版本号,未部署。起因是上一轮手册截图里那句
> `Birthdays in the next 14 days (12 )`。

## 一、量词缺口:病根不在字典,在渲染

React 把 `近 14 天生日（{n} 人）` 拆成三个文本节点(前半句 / 数字 / ` 人）`),
翻译层逐节点查表,所以永远看不到完整短语。此前的应对是给碎片建条目——其中
`['人）', ')']` **靠删掉「人」蒙混**,而 `applyText` 会保留每个节点自己的空白,
于是源码里「人」前面那个空格活了下来,渲染成 `(12 )`。

**改法**:让源码把这类短语整句发出(模板字符串),字典用整句规则翻译。
共 5 处(第 5 处覆盖 5 个调用点):

| 位置 | 短语 |
|---|---|
| `cms-app.jsx` 生日横幅 | `近 14 天生日（N 人）` |
| `cms-app.jsx` 班次学员 | `班次学员（N 人）` |
| `cms-app.jsx` 班组下拉 | `{组名}（N 人）` |
| `cms-app.jsx` 课表提示 | `（课表 N 班）` |
| `panels/filter_bar.jsx` 结果计数 | `共 N {张/件/位/人/条}` —— 5 个面板共用 |

最后一处是关键:量词决定名词(`张` 既是发票也是作品),**一个英文词服务不了两种读法**,
所以必须让量词和数字待在同一个节点里,再按 `共 N 张`→`N invoices`、
`共 N 件`→`N works`、`共 N 位`→`N teachers` 分别匹配。
`张`/`个`/`位` 因此**故意不做碎片条目**,理由写在字典注释里。

## 二、字典有 10 个键被定义了两次(后写的静默覆盖)

745 条里有 10 个中文键出现两次且英文不同。JS 对象后者胜出,所以其中一个意图
一直是死字。最有害的一条:`已作废` 先定义为状态词 `Voided`,后又被动作词
`Void` 覆盖——发票状态在英文界面上读作「Void」。已恢复为 `Voided`;
其余 9 条删除已失效的那半,让行为显式而非取决于书写顺序
(`学员`/`作品`/`排课`/`应到`/`专区`/`系统设置`/`批准建档`/`确认记录`/`人`)。

## 三、属性只在挂载那一刻翻译过一次(本轮最实的一个修复)

`MutationObserver` 只监听 `childList` 与 `characterData`,**没监听 `attributes`**。
元素插入时 `localise` 会翻它的 placeholder/title/aria-label;但 React 之后重写
同一个元素的标签时(课表七个日期按钮每次导航都会重新播报日期与人数),
观察者根本不会被唤醒,那些值就永远停在中文——**屏幕阅读器用户拿到的是中文**。
已加 `attributes: true` + `attributeFilter: ['placeholder','title','aria-label']`;
过滤是必需的:`applyAttributes` 会把结果盖章写进 `data-` 属性,不过滤就自我循环。

## 四、量出来的结果(单位:去重后的节点/属性)

| | 起点 | 收尾 |
|---|---|---|
| 文本节点残留中文 | 214 | 34 |
| 其中**界面文案** | ~110 | **0** |
| 属性残留中文 | 47 | 11 |
| 其中**界面文案** | ~30 | **0** |
| 拼接畸形(如 `(12 )`) | 1 | **0** |

收尾剩下的 34 + 11 全部是**租户数据**:演示租户的课程名(`油画基础 Foundation Oil`)、
套餐名、付款方名(`Whelan 一家`)、家长留言、以及语言切换器自身的 `Language / 语言`。
**这些不该翻译**——那是工作室自己的文案。

新增约 110 条界面词条,集中在 v10.8/v10.9 才上线、当时没配字典的面：工作台、
作品工作区、账务与结算、全部设置分区、以及整个 Xero 集成面板。

## 五、方法与证据

审计不是读代码猜的:起本地栈,以 owner 身份用英文遍历 17 个 CMS 界面,
遍历每个文本节点与 placeholder/title/aria-label,收集残留中文与畸形英文
(脚本在会话 scratchpad,未入库)。每改一轮就重跑一次,数字见上表。

- 全量 pytest:**2838 通过 / 6 skip**;`test_admin_i18n_coverage.py` 与
  `test_shape_language.py` 共 17 项全绿。仍有
  `test_tenant_isolation_by_construction.py` 两项失败——断言原文即
  「应用以超级用户连库,RLS 被无条件绕过」,本机 Postgres 角色所致,与本轮无关。
- 目检英文课表与账务两屏:`Birthdays in the next 14 days (12)`、
  `NET RECEIVED (AFTER REFUNDS)`、`Draft · unnumbered`、`5 invoices` 均正确。

## 六、踩到的坑,记给下一个人

- **`cms-app.js` 是 esbuild 产物**(`build_cms.sh`,源码在 `legacy-root/src/`)。
  手改产物会被下一次构建抹掉;本轮所有 JSX 改动都走生成器。
- **改了 `frontend/assets/` 里任何文件,必须重建 `asset-manifest.json`**。
  漏了这一步,服务器**拒绝启动**:`RuntimeError: Frontend asset does not match
  its manifest: cms-i18n.js`。这个校验是对的,但报错发生在启动期,
  表现为「本地栈起不来」,容易被误判成别的问题。
  (`build_cms.sh` 自己会顺手重建;单独改 `cms-i18n.js` 时不会。)

## 七、已知未做

- 本轮只覆盖 CMS(`cms-i18n.js`)。Studio Admin / Super Admin 走
  `admin-i18n.js`,同样的三类问题(碎片量词、重复键、属性重译)未审计。
- 审计脚本是一次性的,没有进仓库。要防止再次漂移,值得把「英文界面不得残留
  中文界面文案」做成测试——难点是它需要一个跑起来的浏览器,
  和 `capture_manual_shots.py` 同一套代价。
