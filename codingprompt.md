# StudioSaaS Improvement Sprint Prompt (v6 — v6.6.6 收割版)

Version: v6.0
Date: 2026-07-06
Supersedes: codingprompt.md v5（v5 的 A1–A5 已全部完成：排课系统、账本统一、CMS 预编译、审核统一、界面互通。v5 的 B 级并入本清单）

## 0. 本清单的来源

租户 CMS 分叉自 LetsPaintCMS **v4.3.3-aws** 基线；成熟的单店版已演进到 **v6.6.6**（真实运营 + 多轮线上事故打磨）。本清单 = 逐条比对 CHANGELOG v4.4→v6.6.6 与租户 CMS 现状后的收割计划，目标：**稳定性对齐 + 完成度对齐**。

参照物：`~/Library/Mobile Documents/com~apple~CloudDocs/LetspaintCMS/LetsPaintCMS-v6.6.6-release.zip`（含 CHANGELOG.md、server.py 参考实现、docs/ 审查清单）。执行时优先阅读对应版本的 CHANGELOG 条目和参考实现。

**多租户适配原则**：参考实现是单店 JSON 模型；租户版一律落到 v1 账本/表结构（credit_transactions / attendance_sessions / portfolio_items / media service），禁止把 JSON 整包模型带回来。

## 1. 工作规则

1. S → A → B 顺序；每项独立 commit + 报告【改动文件/验证结果/风险/下一步】。
2. 改 CMS 界面 = 改 `legacy-root/src/cms-app.jsx` → `bash backend/scripts/build_cms.sh`；禁止直接改 index.html。
3. schema 变更走 migrations（下一编号 0009）。
4. 每项完成后全量验证：pytest（37）、test_tenant_isolation（110）、test_cms（72）、check_ui_escaping。
5. CMS 文案保持中文。
6. **反面教训（v5.2.2 线上 OOM 事故）**：禁止用 PIL `list(im.getdata())` 方式剥离 EXIF——千万像素照片会把内存打爆。任何逐像素展开的图片处理都不允许。

---

# S 级 — 稳定性修复（单店版踩过的线上事故，租户版还带着雷）

## S1 — Service Worker 不拦截非 GET（手机上传丢 body 事故）

**问题：** 我们的 `sw.js`（v4.3.3 基线）`fetch` 事件对**所有**请求 `respondWith(fetch(...))`。iOS WebKit 转发 multipart POST 时会丢失 body → 手机上传照片必失败（"No file part"）。单店版 v4.4 已修（U7），v6.6.5 进一步把 SW 作用域收紧。
**参考：** v6.6.6 `sw.js:33-38`：`if (e.request.method !== 'GET') return;`
**修复：**
1. `sw.js` fetch handler 第一行加非 GET 直接 return。
2. 顺带（v6.6.5）：SW 注册作用域评估收紧到 `/<slug>/cms` 与 `/<slug>/register`（多租户下 root 作用域会跨面拦截），并注销历史根作用域注册。
**验证：** 手机（或 Safari responsive 模式）上传作品/头像成功；PWA 图标缓存仍工作；bump CACHE_VERSION。

## S2 — iPhone HEIC/HEIF 上传支持（服务端转 JPEG）

**问题：** iPhone 默认拍照格式是 HEIC；我们的 media service 只收 jpg/png/gif/webp → iPhone 用户直接失败。单店版 v4.4 修复（U6）。
**参考：** v6.6.6 `server.py:78-122`：ALLOWED_EXT 加 heic/heif；`_convert_heic_file()` 用 pillow-heif 就地转 JPEG，失败返回 None 不抛异常。
**修复：**
1. `requirements.txt` 加 `pillow>=10,<12`、`pillow-heif>=0.16,<2`。
2. `services/media.py`：允许 heic/heif 扩展与 MIME（image/heic, image/heif），保存后转 JPEG（转换失败给出明确错误）；storage_key/mime 以转换后为准。
3. legacy 上传路径（server.py）同样处理（复用同一函数）。
**验证：** 用真实 HEIC 文件 curl 上传 → 落盘为 .jpg、媒体路由可显示；非法文件仍被拒。

## S3 — 作品集缩略图 + 懒加载

**问题：** CMS/分享页列表直接加载原图，学员多时流量与首屏都差。单店版 v4.4 加缩略图（U3）。
**参考：** v6.6.6 `server.py` THUMB_MAX=360、Pillow 缺失时优雅回退原图；前端 `loading="lazy"`。
**修复：** media service 生成缩略图（`<storage_key>.thumb.jpg`，最长边 360）；媒体路由支持 `?thumb=1`；CMS 作品集列表与 `/shared/portfolio` 网格用缩略图 + 懒加载，灯箱用原图。老图片首次请求时惰性生成。
**验证：** 列表请求体积显著下降；缩略图缺失时回退原图不报错。

## S4 — 注册接口蜜罐 + 隐私同意

**问题：** 公开注册端点无机器人防护；注册页无隐私声明。单店版 v6.6.5 加蜜罐、v5.0.1 加隐私同意勾选。
**参考：** v6.6.6 `server.py:976-978`：隐藏字段 `website` 被填 = 机器人，**静默返回成功**不入库。
**修复：**
1. `public_create_registration` 开头加蜜罐检查（同名 `website` 字段，租户注册页加对应隐藏 input）。
2. 租户注册页（legacy-root/register.html）加隐私声明短文 + 必勾 consent（payload 已可存）。
**验证：** 填了蜜罐字段返回 success 但无记录；不勾 consent 无法提交。

## S5 — 发布自检并入 verify_local.sh

**问题：** 单店版 v6.6.5 靠 `scripts/run_tests.sh` 在发布前抓到过"版本号滞留"事故；我们的 verify_local.sh 缺前端产物校验。
**参考：** v6.6.6 `scripts/run_tests.sh`：`node -e "new Function(fs.readFileSync('vendor/app.js'))"` 校验编译产物语法。
**修复：** verify_local.sh 增加：① cms-app.js 产物语法校验（node new Function）；② cms-app.jsx 比 cms-app.js 新时警告"忘了 build"；③ sw.js CACHE_VERSION 与 git 状态提示。
**验证：** 故意改坏产物/不 build → 自检抓到。

---

# A 级 — 记账与经营完成度（老板每天用的钱账）

## A1 — 消课按上课日期记账（补签记对天）

**问题：** v1 `attendance_sessions.attended_at` 永远是操作时刻——补签昨天的课记到今天，周报/家长记录都错天。单店版 v4.6 用 classDate 解决（A2 账本统一时已明确记录此限制）。
**参考：** v6.6.6 `server.py:141-148` `_checkin_display_date`（classDate 优先，回退操作时间）。
**修复：**
1. migration 0009：`attendance_sessions ADD COLUMN class_date date`；回填 `attended_at::date`。
2. check-in 端点接受 `classDate`（默认今天，只允许 ≤今天+1）；CMS 签到传 `rDate`；`GET /v1/attendance?date=` 改按 class_date 过滤。
3. CMS `rosterDone` / 日志显示 / studio-admin 考勤列表 / 桥接 logs 的日期一律以 class_date 为准（操作时间保留在 attended_at 供审计）。
**验证：** 把 rDate 调到昨天签到 → 记录落在昨天、余额正确、今天的名单不显示已签；72/110 全绿。

## A2 — 退款 / 退课（负数冲营收，单一路径）

**问题：** 学员退课只能"调整课时"硬调，退款金额没有去处，营收统计虚高。单店版 v5.3 引入、v5.5 定稿为"结算页模式切换"方案。
**参考：** CHANGELOG v5.3.0/v5.5.0：退课节数 ≤ 余额直接扣减；退款金额以**负 feePaid** 计入营收（全站 feePaid 求和自动净额）；充值/退款同页切换、选中学员先看流水再操作、二次确认+原因+退款方式。
**修复（租户版映射）：**
1. v1 credit-transactions 已有 `refund` 类型但语义是"加课时"；退课需要**减课时+负费用**：允许 `transactionType:'refund'` 携带 `direction:'out'`（或新 `legacy_type:'refund_out'`）→ amount 为负、fee_aud_cents 为负；校验退课节数 ≤ 当前余额。
2. CMS 结算页顶部「💰 充值 / 💸 退款退课」切换；选中学员显示最近流水（v1 数据已有）；退款表单（节数、金额、原因、方式）+ 二次确认卡。
3. 桥接 logs 映射：负 refund → 显示 '退款退课'、红色负数；stats 营收求和自然净额；导出 CSV 无需改（账本本来就全）。
**验证：** 退 2 节 $100 → 余额 -2、营收统计净额下降 $100、流水红色显示；不能退超余额。

## A3 — 经营真账卡（现金 vs 已赚）

**问题：** 工作台只有"历史总营收"（现金口径），老板分不清已赚收入和预收负债。单店版 v5.3 加"经营真账(估算)"。
**参考：** CHANGELOG v5.3.0：已上课人次（累计/本月）、已赚收入（人次×加权均价）、预收未耗负债（剩余课时×均价）、净现金收入。
**修复：** dashboard 端点补四个指标（由 credit_transactions 聚合：加权均价 = 充值净额/充值净课时）；CMS 工作台加「📈 经营真账（估算）」卡（可折叠，注明估算口径）。
**验证：** 手工对账一个 demo 租户：人次×均价 ≈ 已赚收入；充值-退款-已赚 ≈ 预收负债变化。

## A4 — 充值体验：最近 3 笔 + 二次确认

**参考：** v4.5 充值二次确认卡；v4.7 充值页「最近 3 笔」。
**修复：** CMS 结算页选中学员后显示其最近 3 笔充值/退款（桥接 logs 里已有数据）；提交前确认卡显示「学员/课时/金额/套餐」。与 A2 的流水核对合并实现。
**验证：** 选人即见最近 3 笔；确认卡信息正确。

## A5 — 低余额课前预警 + 一键催费

**参考：** v4.5 排课工作台：当日名单低余额学员课前预警 + 催费话术复制。
**修复：** 排课页当日名单：余额 ≤ 阈值的学员卡片黄色预警条 + 「💬 催费」按钮（复制话术：姓名/剩余课时/续费提示，含家长手机 sms: 链接）；余额=1 的批量提醒入口。
**验证：** 低余额学员显示预警；复制话术内容正确。

---

# B 级 — 排课与档案体验

## B1 — 排课工作台打磨

**参考：** v4.5：日期快捷导航（今天/昨天/明天/±1周）、迷你周视图（一周七天点选，带当天人数点标）、当日概览条（应到/已签/未签/低余额）、学员状态操作收进「···」菜单、批量工具折叠。
**修复：** 在现有排课页（已有每周课表）之上按参考补齐这五件；迷你周视图与我们的课表数据天然契合（每天人数 = dayIds 长度）。
**验证：** 手机宽度可用；点周视图切日期；概览条数字与名单一致。

## B2 — 排课冲突与重复提醒

**参考：** v5.2.0：同一天同一时段多名学员给「时段重叠」确认；重复添加同一学员明确提示而非静默。
**修复（课表版更强）：** ① 同一学员加入同 weekday 两个时间重叠的班次时提示；② 手动排班已在当日名单（含课表来源）时 toast「已在当日名单」；③ 班次编辑保存时提示与其他班次的时间重叠（同 weekday 且时间区间相交）。
**验证：** 三种场景都有明确提示且可继续/取消。

## B3 — 学员档案「上课记录」

**参考：** v4.6：档案页展示排课日期 + 签到状态。
**修复：** CMS 学员详情加「📅 上课记录」区（近 20 条，来自 v1 attendance：class_date + 状态 + 撤销标记）；家长分享页（/shared/portfolio）可选展示最近上课记录（与 v5.2 家长端一致——低优，可后置）。
**验证：** 与考勤表一致；撤销的记录不出现或标记。

## B4 — 作品集结构化：标题 + 老师评语

**参考：** v5.2.0：每张作品标题+老师评语；家长端灯箱显示标题/日期/评语，缩略图带评语标记。
**现状优势：** `portfolio_items` 表已有 title/description 字段，纯 UI 工作。
**修复：** CMS 上传/编辑作品弹窗加「标题」「老师评语」输入（写 title/description）；作品缩略图有评语时角标 💬；`/shared/portfolio` 灯箱下方显示标题/日期/评语（家长看到成长记录）。
**验证：** 录入后 CMS 与分享页都正确显示；无评语不显示空块。

## B5 — 列表体验统一

**参考：** v4.7：筛选选中高亮+清除+计数（我们已有一部分）、搜索回车打开唯一匹配、统一 EmptyState 空状态组件、卡片信息密度精简。
**修复：** CMS 内空状态统一成一个 `EmptyState` 组件（图标+主文+次文）；学员搜索回车且唯一匹配时直接打开档案；筛选条显示命中计数。
**验证：** 全部空状态视觉一致；回车行为正确。

## B6 — 深色模式（跟随系统）

**参考：** v5.0.0/5.0.1（两轮才收口：表单控件、日期选择器、透明度变体、禁用态都要适配）。
**修复：** Tailwind `dark:` 全面适配 CMS——工程量大，参考单店版逐区收口清单执行；**排最后**，做前先问用户是否要。
**验证：** 系统深色下全页无"白块/白字不可读"。

---

# C 级 — 门户联动（产品方向定为低优，仅存档不排期）

- 公开作品墙机制（v5.6/v6.6.6）：作品「🌐 允许展示到官网」勾选 + `GET /v1/public/<slug>/gallery` 只读接口（不含学员 PII）+ 灯箱 `?full=1`。CMS 侧勾选可随 B4 顺手埋字段（portfolio_items.visibility 已支持）。
- 门户 SEO 套件（v6.1）：robots/sitemap/JSON-LD/OG 卡片/`/cms` noindex——`/cms` 与 `/register` 加 noindex meta 是一行的事，可随 S1 顺手。
- 家长端 Dashboard 增强（v5.2 下次课卡/续课提示）→ 我们的余额查询/分享页，随 B3 评估。

---

## 推荐执行顺序

**第一批（稳定雷，半天）**：S1 → S2 → S4 → S5（S3 缩略图独立、次之）
**第二批（钱账完整性）**：A1 → A2（+A4 合并做）→ A3 → A5
**第三批（体验）**：B1 → B2 → B3 → B4 → B5（B6 问过再做）

## 完成定义

- S 级全部完成 = 手机上传（含 iPhone HEIC）全链路可用，公开端点有机器人防护。
- A 级全部完成 = 补签记对天、退款有单一路径且营收净额正确、老板能看清"现金 vs 已赚"。
- 每项完成后 test_cms 72 项必须全绿（行为升级允许改断言并在 commit 说明）。
