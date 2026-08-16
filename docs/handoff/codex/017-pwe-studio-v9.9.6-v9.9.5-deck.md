# PWE Studio v9.9.6 — 手册对齐 v9.9.5 产品事实、全套截图重拍、路演 deck 同步

> 当前阶段：文档与素材发布。**运行代码未改**（仅 `VERSION` / `APP_VERSION` 标签）。
> 本轮修掉手册里一处已经不成立的断言、补上一个从未被拍过的公开页面、
> 把 20 组截图全部按 v9.9.5 重拍，并同步销售路演 deck。

## 关于「为什么要推版本号」——发布提交里那句话是错的

提交信息里写着「同版本号重拍等于没拍，读者拿到的还是旧图」。**这不是这套缓存的工作方式。**
`_stamp_asset_versions` 同时写 `?v=` 和 `?h=<内容摘要>`，
`_cache_versioned_asset` 只在**两者都匹配**时才发 `immutable` ——
所以字节变了，`h` 就变了，URL 就变了，跟版本号无关。

推版本号是**发布账本**的要求（`test_release_ledger.py`），这个理由本身就够；
但它不是把新图送到读者手里的必要条件。已在线上核实：
`/assets/manual/02-showcase-page.zh.webp?v=9.9.6&h=d18162fbec7e0197`
返回 `public, max-age=31536000, immutable`；去掉 `h` 则返回 `no-cache`。

**教训和上一轮同一个形状**：写进文档的机制说明，也要像断言一样只写真的。

## 一处主动说错的话

第 00 章写着 slug「开通时确定、之后不可更改」。v9.9.0（`86dc30c`）已经允许更换：
`PATCH /v1/admin/tenants/<id>/slug`，`@super_admin_required`，365 天冷却，
旧地址进 `tenant_slug_aliases` 永久 301，且**任何地址都不会被重新分配**
（已删除租户留墓碑答 410）。已改写为真话，并在第 11 章「平台方」和常见问题里
各补一条 —— 这是客户签约前会问的问题，之前手册给的是「不行」。

## 截图：20 组全部重拍（v9.5.0 / v9.6.1 / v9.8.5 三个基线混在一起）

重拍前的实际状态：CMS 系列停在 v9.5.0、Studio Admin 系列停在 v9.6.1、
作品系列停在 v9.8.5。而 Studio Admin 在这之后改了 1165 行、公开外壳被重写。
最直观的一处：工作台左栏当时是 10 个面板，现在是 12 个，手册的标注也写着「十个」。

- 本地 `lets-paint-showcase` 用 `reset_professional_demo.py` 重新播种到 v9.9.2+ 形态
  （15 件工作室作品 / 8 件学员作品 / 6 张空间照片），再跑 `capture_manual_shots.py`。
- **新增 `02-showcase-page`**：作品页从 v9.8.10 起就有独立网址 `/<slug>/showcase`，
  手册此前只有文字没有图。首页是 6 件的引子，独立页每次 12 件。
- **删掉了 `TIMETABLE_PUBLIC_SEED`**：公开课表的截图原本走一份手写 fixture 桩，
  因为 v9.9.2 之前演示租户没有课表数据。现在播种器自己拥有这一半，
  fixture 成了第二事实来源 —— 而且已经漂移：在 v9.9.5 它一个约课按钮都渲染不出来，
  直接让这张截图失败。现在和其他所有截图一样，拍真实页面。
- 截图集 2.50 MB（预算 3 MB），`build_asset_manifest.py` 已重建。

## 路演 deck（`docs/sales/PWE_Studio_Roadshow_Bilingual.pptx`）

13 张产品截图里有 12 张是手册截图的旧副本（按图像签名逐张比对确认），已全部换成新的。
另外两处：

- 第 3 页「Showcase / 作品归档 · Archive + filters」原本放的是首页作品条，
  现在放真正的独立归档页 —— 标题说的就是它。
- 第 5 页那张待审核截图是 **v9.5.0 之前**的深色侧边栏 CMS，早已不存在；
  换成现在的「新报名 / 约课」双标签队列。
- 版本标签 v9.8.8 → v9.9.6（第 1、8 页），第 4 页补一条「你的公开网址，换了也不会丢」。
- 套餐页（第 9 页）逐项对过 `plans` 表：$49/$99/$199、100/500/1000 学员、
  15/60/150 作品、2/10/50 GB、Studio 推荐 —— 全部正确，未改。

## 发布证据（2026-08-13）

| 层级 | 已验证事实 |
|---|---|
| Source | 发布提交 `e92dcadf89ab62b87681f14c5afa550b56c93abf`，分支 `claude/online-manual-content-improvement-03b8f9`；`VERSION=9.9.6`。门禁全绿：`verify_local.sh` 全部通过、pytest `1755 passed, 12 skipped`、legacy CMS smoke `73 passed`、租户隔离 `237 passed, 0 failed`。 |
| Package | SaaS `PWE-StudioSaaS-aws-9.9.6.tar.gz` SHA-256 `ce2672d4a739583e00bc92d20b903bdb12e62fd1f8c0000539934e35c2388ce8`；Edition `PWE-Studio-Edition-9.9.6.tar.gz` SHA-256 `c766d654a30ac1a3c30af90de3a3c6c4c31723cf6464799b3682e1be28269665`。两个包的 `BUILD_INFO` 均为 9.9.6，模式 `saas` / `standalone`，均通过发布包校验。 |
| Backup | 部署前逻辑库备份 `studiosaas_studiosaas_20260813T101614Z.dump`，manifest 同时存在。 |
| Production | `/opt/pwestudio/current` → `PWE-StudioSaaS-aws-9.9.6`，镜像 `studiosaas:9.9.6`，容器 healthy；内网与公网 deep health 均为 `appVersion=9.9.6`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`、`workspaces.stale=0`；磁盘可用约 `44.74 GB`。 |
| Public routes | 根站、中英文手册、pricing、Release Notes、租户门户 / timetable / showcase / register / CMS / Studio Admin、platform-admin 共 12 条全部 `200`（HTTP/2）。 |
| Assets | 四组代表性手册截图的线上字节与本地 SHA-256 逐一相同（`01-brand-workbench`、`02-showcase-page`、`04-booking`、`07-settings`）；带 `h` 的 URL 返回 immutable，条件请求返回 `304`。 |
| Content | 线上手册中英文都已是改正后的那句（「它并非永远不能改」/「It is not permanent」）；`FAQPage` 结构化数据 13 条问答，含新增的网址更换那条；`dateModified=2026-08-13`。 |

## 待办

- 第 03 章仍缺：指定老师 · 地点 · **停课**（停课在公开课表上是「划掉」不是「消失」）。
- 空间介绍 About（v8.5.4）在第 01 章仍未提。
- `canReviewBookings` 含 `staff`，而 `ROLE_PERMISSIONS[Role.STAFF]` 没有
  `class_bookings:review` —— Staff 看得见「批准 / 婉拒」，按下去 server 拒绝。
  与本轮无关，手册没有写这个 bug。

---

