# PWE Studio v9.9.2 — 定价页，和一间真的画室

> 当前阶段：**已部署上线，演示租户已重种完毕**。生产 `appVersion=9.9.2`。

这一版有两件事：上一轮做完但没发的**定价页**，以及把 `lets-paint-showcase`
从测试租户改造成**真样板 + 演示租户**。改造过程中挖出四个产品缺陷，都在下面。

## 一 · 定价页（上一轮遗留）

`/pricing` 与 `/zh/pricing`，一 URL 一语言、hreflang 互指、尾斜杠 301。
计算器读服务端已渲进页面的 `data-plans`，**不发第二次请求**——
两个数据源就是同一个套餐出现两个价格的原因。
推荐同时看学员数和登录名额，并说出**是哪条约束决定的**（「Starter 只有 1 个登录名额」）。
掏钱前 FAQ 八条，其中两条不许含糊：降级只影响**发布**、绝不删数据；没有任何抽成。

顺带把页头做成了真共享：445 行样式抽成 `marketing.css`，
导航/移动菜单/吸顶/reveal/页脚年份抽成 `marketing-shell.js`。
原来的 `product-home.js` 在找不到咨询表单时会直接抛错——
对有表单的那一页是对的，对任何复用这个页头的页面都是错的。

## 二 · Let's Paint 样板租户

方案与全部决策记在 `docs/design/Showcase_Tenant_Build.md`。

**改造前**：三件作品标题是 `Test`、`fasd` 和两个空字符串，没有分类、没有主理人、
没有「空间与体验」，logo 在暖纸背景上看不见。
原因很具体——seeder 只种 CMS 侧（课程、学员、签到），
**门户侧留给最后一个在控制台里打字的人**。

**改造后**（`backend/scripts/reset_professional_demo.py` 现在两侧都管）：

| | |
|---|---|
| 身份 | 墨尔本 Caulfield North，成人小班，主理人 **Janet M**，第 7 年 |
| 文案 | 全部双语，写在 `backend/scripts/showcase_content.py`——文案是数据，不是散在 seeder 里的字面量 |
| 主理人作品 | 15 件（13 active / 1 draft / 1 archived），三个抽屉，`featured_rank` 1–6 |
| 学员作品 | 8 件署名到 8 位学员，**其中 1 件同意已撤回**，公开 7 件 |
| 空间 | 6 张照片 + alt，手动切换不自动轮播 |
| 套餐 | **studio 档**（作品上限 60）。`lets-paint-studio` 是真实租户，全程未碰 |
| 图片 | 28 张生成图，75 MB PNG → **8.2 MB WebP**（部署包是 `git archive HEAD`，每次发布都要背着走） |

**「人像」这个抽屉不存在**，因为还没有人像作品。
分类由 manifest 里**实际已发布的作品**推导，不由那张分类表推导——
一个点下去空空如也的筛选按钮，比没有这个按钮更糟。

## 三 · 改造中挖出的四个产品缺陷（都已修，都带回归测试）

**1. 任何租户都不可能拥有一张透明 logo。**
公开品牌图片一律走 `display` 变体，而 `_build_safe_variants()` 只产 JPEG，
`_jpeg_bytes()` 把 RGBA 压到白底。传 PNG 也会被拍成白方块。
修法：源图带 alpha 时变体输出 PNG，`media_variants.mime_type` 跟随实际格式而不是写死。
**这修的是每一个租户。**

**2. 学员作品有两道同意门，seeder 只开了一道。**
公开画廊要求学员有一条最新为 `confirmed` 的 `student_publication_consent_events`，
**并且**作品是 `shared` 且带 `public_consent_at`。
只写后者 → 画廊永远空着、契约报 `no_consented_student_work`——
看起来像产品有 bug，其实是记录没建。

**3. 宽 logo 会把店名挤出手机屏幕。**
`.brand img{height:34px;width:auto}` 不设上限。8:1 的手写体 wordmark
在 375px 手机上占 281px，店名折成三行压在汉堡按钮下面。
两个方向都封顶 + `object-fit:contain`，店名允许省略号。

**4. 分类推导依赖列表顺序。**（我自己写的，改成两趟遍历。）

## 四 · 演示披露

四个公开页面页脚新增一行（双语，默认隐藏）：
「演示站点：画室、人物与作品均为虚构，数据每晚重置。」
由 `/brand` 的 `demoTenant` 驱动，读**租户记录**而不是 slug——
绑在名字上的标记，改名当天就不成立了。

这不是装饰。页面用虚构人物的名义、在公开地址上展示合成作品，
还写着「下面这些是 Janet 自己的画」。

## 五 · 发布证据（2026-08-13）

| 层级 | 已验证事实 |
|---|---|
| Source | `origin/main` = `34b6733`；`VERSION=9.9.2`；`RELEASE_DATE=2026-08-13`。 |
| Local gates | `verify_local.sh` **All checks passed**；pytest `1790 passed, 5 skipped`；legacy CMS smoke `73/73`；租户隔离 `237/237`；术语、转义、版本账本全绿。 |
| Package | `PWE-StudioSaaS-aws-9.9.2.tar.gz` 24 MB，SHA-256 `66a452e7ec55cf012b0c28a5a1b807892cc18559021e46071de4961f1eddb213`；`BUILD_INFO` commit `34b6733`。 |
| Backup | 部署前 `studiosaas_studiosaas_20260813T032433Z.dump`。 |
| Production | `/opt/pwestudio/current` → `PWE-StudioSaaS-aws-9.9.2`，镜像 `studiosaas:9.9.2`；deep health `appVersion=9.9.2`、`db=ok`、`tenants=6`、`themes.unreadable=0`、**`workspaces.stale=0`**；磁盘 45.44 GB 空闲。回滚目录保留 9.9.1。 |
| Public | 七条路由全部 200（含 `/pricing`、`/zh/pricing`）；`/brand` 返回 `demoTenant=true`；四个页面都带 `demoNotice`；`index/showcase/timetable` 的 logo 上限已生效（`register` 本来就是 42×42 方框，不需要）。 |

## 六 · 状态

- 本地全量：**1790 passed, 5 skipped**（v9.9.1 时是 1754）。
- 新增 `backend/tests/test_showcase_tenant.py`（29 条）、
  `test_pricing_page.py`（10 条）、媒体透明度回归。
- **模板改了 → 所有租户工作区必须重新生成**（`regenerate_tenant_workspaces.py`），
  否则 deep health 的 `workspaces.stale` 会报。
- **尚未打包部署。** 发布前按 `docs/Release_Runbook.md` 的九步走，
  先跑 `backend/scripts/release_preflight.sh`。

## 七 · 已确认：标记是对的，但重置从来没跑过

上线时逐条查了：

- `settings.professional_demo` = **`true`** ✅ —— 脚本不会拒绝执行。
- `plan_code` = **`studio`** ✅。
- **没有 cron，没有 systemd timer** ❌ —— 每晚重置**从未运行过**。
- 容器里**没有** `STUDIOSAAS_SHARED_DEMO_PASSWORD`，
  `/opt/pwestudio/shared/production.env` 里也没有 ❌。

第四条解释了前面所有事：重置脚本要求这个密钥（≥12 字符）才肯跑，
而它在生产环境根本不存在——所以脚本**一次都没能执行**，
那三件 `Test` / `fasd` 只能是人手敲进去的。

## 八 · 演示密钥已配置，租户已重种（2026-08-13）

密钥**在服务器上生成**：`openssl rand -hex 24`（48 字符，十六进制——
env 文件没有引号语义，值里出现 `/` 或 `+` 迟早出事），
追加进 `/opt/pwestudio/shared/production.env`（0600，改前留了 `.bak-` 备份）。
值从未打印、从未作为命令行参数出现（`argv` 可以被 `ps` 读到），从未离开实例。

重种时密码走 **stdin** 进容器，不走 `docker exec -e`，理由同上。
凭据写在 `/data/showcase-credentials.txt`（0600）——`/data` 是 named volume，
下次发布不会把它带走。

**要看演示账号密码，在服务器上：**

```bash
sudo docker exec pwestudio-app-1 cat /data/showcase-credentials.txt
```

### 重种结果（线上实测）

| | |
|---|---|
| 数据库 | `works=15`、`students=12`、`public_classes=7`、`student_works=8` |
| 契约 | 七个版块**全部 `ready`**（`gallery` 从 `no_consented_student_work` 变成 `ready`） |
| 作品墙 | 公开 13 件，每页 12，`hasMore=true`；三个抽屉；精选 1–6 顺序正确 |
| 图片 | 画作 `image/jpeg` 524 KB；**logo `image/png`、RGBA、角落 alpha=0** |

最后一行是这个产品**第一次**真的服务出一张透明 logo。

### 为什么以前 env 文件里写了也没用

`docker-compose.yml` 的 `environment:` 是一张**白名单**——
不在里面的键，无论 `production.env` 写得多认真都到不了容器。
这一版把 `STUDIOSAAS_SHARED_DEMO_PASSWORD` 和
`STUDIOSAAS_DEMO_CREDENTIALS_FILE` 加了进去，
所以**下一次发布之后**定时器可以直接调脚本，不必再用 `docker exec -e`。

### 定时器还没装——先决定一件事

`lets-paint-showcase` 现在**既是给客户看的样板，又是演示租户**。
定时器一开，任何人在控制台里为了让样板更好看做的调整，当晚就会被抹掉；
样板的唯一持久编辑入口就变成 `showcase_content.py` 和 `manifest.json`。
接受这一点再装，别反过来。

## 九 · 已知缺口（未修，已记）

1. `courses.name / description / category` 是单语言字段，中英门户渲染同一个字符串。
   这一轮按 `油画基础 Foundation Oil` 双语并置写。
2. 公开课程卡片按 `ORDER BY category, name` 排——店主无法控制顺序，
   于是入门班可能排在最后。已开背景任务。

---

