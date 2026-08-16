# PWE Studio v9.9.3 — 头部、锚点，和一个只对演示租户可见的按钮

> 当前阶段：**已部署上线并重种**。生产 `appVersion=9.9.3`。
> 四条都由真实截图或真实点击报出，全部量过再改。

## 发布证据（2026-08-13）

| 层级 | 已验证事实 |
|---|---|
| Source | `origin/main` = `256aa6c`；`VERSION=9.9.3`。 |
| Local gates | `verify_local.sh` **All checks passed**；pytest `1797 passed, 5 skipped`。 |
| Package | `PWE-StudioSaaS-aws-9.9.3.tar.gz`；部署前备份 `…20260813T054808Z.dump`。 |
| Production | deep health `appVersion=9.9.3`、`db=ok`、`tenants=6`、`themes.unreadable=0`、**`workspaces.stale=0`**。 |
| 演示密钥 | compose 透传**已生效**：容器内 `STUDIOSAAS_SHARED_DEMO_PASSWORD` 已就位（48 字符），`STUDIOSAAS_DEMO_CREDENTIALS_FILE=/data/showcase-credentials.txt`。再不需要 `docker exec -e`。 |
| 重种 | 线上已重跑：15 件主理人作品、8 件学员作品（7 件公开）、12 名学员、7 节公开课。地址已变为 **Caulfield North**，七个版块全部 `ready`。 |
| Public | 六条路由 200；timetable / register 的新 description 已生效。 |

**注意**：地址存在数据库里，不在代码里。改 `showcase_content.py` 只决定「下次重种写什么」——
线上要生效必须重跑重置。这一版是手动跑的；下次可以直接用 Platform Admin 的按钮。


## 一 · logo 压在导航上（真因不是响应式）

截图里「Let's Paint」紧接着一个「L..」——量出来是：`.brand` 盒子只有 124px，
里面的 logo 是 281px，**图片溢出自己的容器 157px** 压在第一个导航项上，
店名被压成 0 宽所以只剩一个字母加省略号。

再往下量才是真因：`.navrow` 的 `max-width` 是 **1180px**，不管屏幕多宽都封顶。
品牌区 419 + 导航 926 = 1345 > 1138 可用 —— **它永远放不下**，跟视口无关。
之前当响应式问题查是走错了方向。

改成**测量驱动的降级阶梯**（`public-surface.js` 里一份实现，四个页面共用）：

1. 先扔掉重复的店名 —— logo 本身就写着 "Let's Paint"，`<img alt>` 仍带着它；
2. 还放不下，导航整体收进菜单键。

断点只作为**地板**（900px），不再当作判据：导航有几项是**每个租户不同的事实**，
按最满的租户定死断点，等于让只开三个版块的租户在笔记本上也顶个汉堡。
实测：满配租户（9 项）折叠；隐藏 3 个版块的普通租户**店名和完整导航都保留**。
菜单面板里语言切换仍在，折叠不丢功能。

## 二 · 跨页 `#` 锚点点了没反应

`/lets-paint-showcase#home:artist` 从别的页面点进来只回首页不定位，
点点别处又好了 —— 这个「第二次就好」正是线索。

`applyRoute` 在脚本执行时就跑，30ms 后 `scrollIntoView`；
那时契约还没返回，版块还是 `display:none`，而**对隐藏元素滚动是空操作**。
点别处触发 `hashchange` 时版块已经显示，所以第二次成功。

改成记住锚点、在**版块变可见的那一刻**重试（`resolveSection` 里），
带 8 秒上限，并且无锚点导航会清掉待定锚点——
晚到的版块不能把已经在读别处的人拽回去。

## 三 · 地址改为 Caulfield North

内容模块、文档、handoff 全量替换并重种。
一处留着没动：主理人故事里的「1960 年代旧车间、五米层高」原本是照 Brunswick
仓库区写的，Caulfield North 是林荫住宅带。车站附近有轻工业，说得通。

## 四 · Platform Admin 的一键重置

`POST /v1/admin/tenants/<id>/demo-reset`，`@super_admin_required`，四道守卫：
SaaS 模式 → 租户带 `professional_demo=true` → 确认短语 → 密钥已配置。
短语和命令行脚本**是同一个**，只要记一次。

**放在哪**：租户操作菜单里单独一组「Demonstration」，
而且**只在服务端标记为演示租户时才渲染**——不是灰掉，是根本不出现。
一个操作员如果能在真实画室的菜单里看见「Reset demonstration data」，
就离误点只差一次手滑，而确认框拦不住习惯。

实测四条路径：错短语 400、非演示租户 400、不存在 404、正确 200（1.9 秒重建）。
接口返回凭据文件的**路径**，从不返回内容。

## 五 · 顺手补的两个小洞

- `timetable` 和 `register` **完全没有 meta description** —— 转发到聊天软件里
  只有一条光秃秃的网址。补上了。
- `public-surface.js` 现在在无浏览器环境里也能安全加载（契约测试用 node 跑它，
  `apply()` 调用 `requestAnimationFrame` 一度打挂了九条测试）。

## 六 · 查过但不是 bug 的

灯箱 Escape 关不掉——**是自动化的锅**。对照实验：一个全新的、没有任何应用代码的
原生 `<dialog>`，在同样的合成按键下也不关闭、`cancel` 也不触发。
合成按键不算「用户激活」，走不到 CloseWatcher。灯箱的 `cancel` 接线是对的。

## 七 · 状态

- 本地全量 **1791 passed, 5 skipped**；`test_showcase_tenant.py` 增至 34 条。
- 术语、转义、内联脚本、版本账本全绿。
- **模板改了 → 所有租户工作区必须重新生成**，否则 deep health 的 `workspaces.stale` 会报。
- 上一版（v9.9.2）已上线；这一版尚未打包。

---

