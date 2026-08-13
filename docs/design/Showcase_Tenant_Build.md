# Let's Paint Showcase —— 从测试租户改造成真样板

> 目标：`https://pwestudio.online/lets-paint-showcase/` 现在是个测试租户——
> 三件作品的标题是 `Test`、`fasd` 和两个空字符串，没有分类，没有主理人，
> 没有「空间与体验」，logo 在暖纸背景上看不见。
> 这一轮把它改造成一间**真的画室**：既是给客户看的样板，也是可以随便点的演示租户，
> 保留每晚重置。

版本：v9.9.2 · 2026-08-13 · 分支 `claude/ui-ux-pro-max-audit-073a82`

---

## 0 · 图从哪来

计划最初写的是「这个会话没有生图能力」。执行到一半，用户把 28 张生成好的图放进了
`backend/seed-assets/lets-paint-showcase-generated/`，正好覆盖 §6 列的清单：
主理人作品 12、学员作品 8、主理人头像 1、空间照片 6、首屏 1。

两组作品的**水平差距是真的拉开了**——主理人那组是层叠、克制、灰调子；
学员那组更平、更亮、边缘更硬。这一点很重要：没有这个差距，
「学员作品」和「主理人作品」两个版块就只是同一堆图分了两次，
同意机制也就没有东西可演示。

加上仓库里原有的三张（水彩、油画刮刀、炭笔），主理人作品共 **15 件**。

### 转成 WebP

原图是 1254²～1536×1024 的 PNG，28 张共 **75 MB**。
部署包是 `git archive HEAD`，这 75 MB 会跟着**每一次**发布走到 AWS，永远。
变体管线本来就在 2000px 封顶，所以按 1600px、WebP q88 重编码：

```
75 MB PNG  →  8.2 MB WebP
```

命令记在这里，以后补图照做：

```python
image = Image.open(source).convert("RGB")
image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
image.save(target, format="WEBP", quality=88, method=6)
```

原来那三张 PNG **不转、不删**——`deploy/aws/verify_release_bundles.sh:83`
按文件名把它们钉在发布包清单里。

## 1 · 身份（A）

参考 `letspaintstudio.com` 的**形态**，不搬它的**事实**。

真实的 Let's Paint Studio 有一位真实的创办人和真实的履历（美院、清华、RMIT、
路易威登定制画师）。**把一个真人的真履历写进一个演示租户，是冒充。**
所以这里取的是形状——墨尔本、成人绘画、以颜色换松弛的语气——具体内容全部虚构。
主理人名字用用户指定的 `Janet M`，只留姓氏首字母，正是为了不指向任何真人。

| 项 | 值 |
|---|---|
| 画室名 | Let's Paint Studio（沿用，slug 不变） |
| 城市 | 墨尔本 Caulfield North |
| 开办 | 2019 年，第 7 年 |
| 教什么 | 成人为主：油画、丙烯、水彩、素描；周六一节儿童班；另有一对一 |
| 班型 | 小班，一次最多 8 人（八张画架是硬上限） |
| 主理人 | **Janet M** · 创办人 · 主理人 |
| 语气 | 慢、克制、把颜色当休息。不说「激发潜能」 |
| 定位 | **样板 + 演示租户**，每晚重置，页面上有明确的演示标识 |

**slogan**（`localized_copy.slogan`，同时派生 `hero_title`——不写字面量，见记忆「行业预设文案」）

- zh：颜色会把人放慢下来。
- en：Colour is a slower way to spend an afternoon.

**主理人金句**（`principal_quote`，≤180）

- zh：你眼睛里的灰，永远不是灰色。
- en：The grey you're looking at is never grey.

---

## 2 · 文案（C）

全部双语成对，写进 `backend/scripts/showcase_content.py`——**文案是数据，不是散落在 seeder 里的字面量**。

### 2.1 版块名称即导航文字（契约裁剪：中文 ≤10、英文 ≤24；行动按钮中文 ≤7、英文 ≤18）

| 键 | 中文 | 英文 | 中/英字数 |
|---|---|---|---|
| `showcase_label` | 主理人作品 | Work by Janet | 5 / 13 |
| `courses_label` | 课程与班次 | Courses & Classes | 5 / 17 |
| `gallery_label` | 学员作品 | Student Work | 4 / 12 |
| `timetable_label` | 课程安排 | Timetable | 4 / 9 |
| `faq_label` | 常见问题 | Questions | 4 / 9 |
| `contact_label` | 联系我们 | Contact | 4 / 7 |
| `primary_cta` | 预约体验 | Book a trial | 4 / 12 |
| `secondary_cta` | 看看作品 | See the work | 4 / 12 |

`show_showcase` 打开后，`secondary_cta_target` 设为 `showcase`——首屏第二个按钮指向作品墙，
而不是靠 `auto` 猜。

### 2.2 两个作品版块，必须一眼看出区别

产品里这是两个不同的问题，文案要把这件事说破：

**主理人作品**（`showcase_*`）——答「教我的人水平如何」
- 眉标题：主理人作品 / Work by Janet
- 标题：教画的人，自己也在画 / The person teaching also paints
- 引导语：下面这些是 Janet 自己的画。看老师的画，比看老师的简历更能判断要不要来上课。
  / These are Janet's own paintings. Looking at a teacher's work tells you more than reading their CV.

**学员作品**（`gallery_*`）——答「在这里能学成什么样」
- 标题：在这里学，能学成什么样 / What people make here
- 引导语：学员的画，每一张都经本人同意才放上来。
  / Student work, published one piece at a time and only with the artist's consent.

引导语本身就在演示同意机制——这是我们相对竞品最强的一条，写在文案里比藏在后台里有用。

### 2.3 空间与体验（`about_*`，最多 6 张图）

- 眉标题：空间 / The room
- 标题：一间朝南开窗的旧车间 / An old workshop with a south window
- 正文：车间是 1960 年代的，天花板五米高，南墙一整排窗。我们没装射灯——
  南边的光一整天都不变色，这是画画的人唯一挑不出毛病的光。
  颜料、画布、画架、围裙都在，你带一件不怕脏的衣服就行。

  （**朝南**是刻意的：南半球画室要的是恒定的冷光，朝南才对。写成朝北是外行。）

- 三条亮点：
  1. 一次最多八个人 / Eight easels, no more
  2. 材料都在这里 / Materials included
  3. 画完了可以放着 / Leave the wet ones here（油画干得慢，架子上有你的位置）

### 2.4 FAQ（8 条，真画室会被问的）

完全没画过可以来吗 · 要自己买材料吗 · 一节课多久 · 请假怎么办 ·
小孩可以来吗 · 可以只上一次吗 · 画完的画归谁 · **会把我的画发到网上吗**

最后一条是故意的：它让访客在公开页面上就读到同意机制。

### 2.5 报名表问题

按成人油画班改，不用默认模板：现在画到哪一步了 / 想解决什么 / 什么时段方便。

---

## 3 · 作品与分类（B、E）

### 分类规则：抽屉由作品决定

用户确认的分类是 **静物 / 人像 / 城市风景**。执行时有两处调整，都记在这里：

1. `showcase-coast.png` 是海岸，不是城市。分类改为 **城市与风景 / City & Landscape**，
   一个抽屉装得下城市和自然，对一间墨尔本画室也更诚实。
2. **分类由 manifest 里实际存在的作品生成，不由这张表生成。**
   没有人像作品时，「人像」这个抽屉不会出现——
   因为一个筛选按钮点下去空空如也，比没有这个按钮更糟。
   等人像画进了 manifest，抽屉自己会长出来。

### 落地结果

**主理人作品 15 件**：静物 5、城市与风景 9、写生与素描 1。
其中 13 件 `active`、1 件 `draft`（画室一角，未完成）、1 件 `archived`（冬园，个展后收起）。
`featured_rank` 1–6 决定首页预览，与归档页共用同一套排序。
公开 13 件、每页 12 件 —— 分页也真的被走到了。

**学员作品 8 件**，署名到 8 位不同学员（含两名儿童）。
其中 **1 件的同意已撤回**：作品留在后台，公开页面上没有。公开 7 件。

**「人像」抽屉不存在**——因为还没有人像作品。这是规则，不是遗漏。

作品说明按真作品的写法给：媒介、尺寸、年份，加一句为什么画它。

### 分级演示（E）

按用户指示：**只动 `lets-paint-showcase`，`lets-paint-studio` 是真实租户，不碰。**

- `lets-paint-showcase` 跑 **studio 档**（作品上限 60，原为 growth 150）。
- 三种发布状态各留活样本：`active` 公开、`draft` 编辑中、`archived` 已归档——
  后台看得见，前台看不见。
- `featured_rank` 决定首页 6 件预览的顺序，与归档页共用同一套排序。

---

## 4 · CMS 侧数据（D）

契约是 `intent × contentReady × dependencyReady`。**开关打开而没有内容，版块照样不显示**——
所以下面每一项都是「让某个版块能出现」的前提，不是装饰。

| 项 | 内容 | 让什么变可见 |
|---|---|---|
| 课程 | 4 门：油画基础 / 水彩与速写 / 人像专题 / 周六儿童班 | 「课程与班次」版块 |
| 排课 | 每周 7 节，全部勾选「在公开课表上显示」，带老师、教室、容量 | 公开课表页 + 导航入口 |
| 老师 | 3 位；Janet 与另一位公开署名，前台不公开 | 课表上的老师姓名 |
| 学员 | 10 位成人 + 2 位儿童，带课时余额、充值与签到记录 | CMS 截图、学员专区 |
| 约课 | 3 条待审核申请 | 演示「不占座、批准才占」 |
| 停课 | 2 条（公众假期、私人原因） | 演示课表例外 |

**顺带发现**：`courses.name / description / category` 是单语言字段，
门户在中英两种模式下都原样渲染。这是产品的真实缺口。
这一轮不改结构，课程名按 `油画基础 Foundation Oil` 这种双语并置写——
墨尔本的华人画室本来就这么写招牌。缺口记在 §7。

---

## 5 · Logo（B6）

现状：`logo_url` 指向一张 **1000×889 的 JPEG，白底上一个近乎白色的手写体标记**。
它是为深色背景做的反白稿，而门户背景是 `#f3ecea` 暖玫瑰纸——所以它双重不可见：
标记看不见，白底还盖出一个白方块。

**执行时发现的真原因**：公开品牌图片一律走 `display` 变体，
而 `_build_safe_variants()` 只产 JPEG，`_jpeg_bytes()` 把 RGBA **压到白底**。
也就是说，**当前任何租户都不可能拥有一个透明 logo**——传 PNG 也会被拍成白方块。

所以 B6 分两步：

1. **修管线**：源图带 alpha 时，变体输出 PNG 而不是 JPEG（同样经 PIL 重编码，
   元数据照样剥干净），`media_variants.mime_type` 改为跟随实际格式而不是写死 `image/jpeg`。
   这修的是**每一个**租户的 logo，不只是演示租户的。
2. **做反向稿**：按亮度键出原标记的笔画，换成深墨色，输出透明 PNG。
   **键出而不是重画**——那手写体是原稿的资产，重画只会更差。
   同时保留白色版供深色模式。

---

## 6 · 执行中发现的四件事

写方案时看不见，动手才看得见。四条都已修，都带回归测试。

**一 · 任何租户都不可能拥有一张透明 logo。**
公开品牌图片一律走 `display` 变体，而 `_build_safe_variants()` 只产 JPEG，
`_jpeg_bytes()` 把 RGBA **压到白底**。传 PNG 也会被拍成白方块。
修法：源图带 alpha 时变体输出 PNG，`media_variants.mime_type` 跟随实际格式
而不是写死 `image/jpeg`。这修的是**每一个**租户，不只是演示租户。

**二 · 学员作品有两道同意门，seeder 只开了一道。**
公开画廊要求：学员有一条最新为 `confirmed` 的
`student_publication_consent_events`，**并且**作品是 `shared` 且带
`public_consent_at`。原来的 seeder 只写了后者，于是画廊永远空着，
契约报 `no_consented_student_work`——看起来像产品有 bug，其实是记录没建。
顺带补了一条**已撤回**的样本：只演示「能授权」，等于没演示同意机制。

**三 · 宽 logo 会把店名挤出手机屏幕。**
`.brand img{height:34px;width:auto}` 不设上限。这个手写体 wordmark 是 8:1，
34px 高就是 281px 宽，375px 的手机只剩 90px 放店名和菜单键，
店名于是折成三行压在汉堡按钮底下。
修法：两个方向都封顶 + `object-fit:contain`，店名允许省略号。
这是通用弱点，任何上传横版 logo 的租户都会踩。

**四 · 分类推导依赖列表顺序。**
第一版在同一次遍历里既决定「哪些抽屉存在」又写 `category_id`，
于是一件草稿如果排在同分类第一件已发布作品**之前**，就会静默丢掉分类。
改成两趟：先算抽屉，再写条目。挪动 manifest 里两行不该改变后台显示的东西。

---

## 6b · 演示披露

这个页面用虚构人物的名义、在公开地址上、展示合成作品，
还写着「下面这些是 Janet 自己的画」。这句话对虚构成立，对世界不成立，
而从搜索引擎点进来的人分不出来。

所以四个公开页面的页脚都有一行（双语，默认隐藏）：

> 演示站点：画室、人物与作品均为虚构，数据每晚重置。

由 `/brand` 的 `demoTenant` 驱动——读的是租户记录 `settings.professional_demo`，
**不是 slug**。绑在名字上的标记，改名当天就不成立了，而改名是支持的操作。

---

## 7 · 执行顺序与交付

| 批次 | 内容 | 产出 |
|---|---|---|
| C | 内容模块，全部双语文案 | `backend/scripts/showcase_content.py` |
| B6 | 媒体管线保 alpha + 反向 logo | `services/media.py`、`seed-assets/showcase/logo-*.png` |
| B | 作品 manifest + 走真实上传路径的 seeder | `seed-assets/showcase/manifest.json` |
| D | seeder 补齐门户侧（现在只种了 CMS 侧） | `reset_professional_demo.py` |
| E | studio 档 + 三种发布状态 + featured_rank | 同上 |
| F | 测试、逐页验收、每晚重置、演示标识 | `tests/test_showcase_tenant.py` |

### 记在这里的产品缺口

1. `courses` 三个字段不是双语——中英门户渲染同一个字符串。
2. logo 透明度在修复前对所有租户失效（§5）。
3. 线上租户 `settings.professional_demo` 若不为 `true`，重置脚本会拒绝执行——
   上线时要先确认，否则每晚重置根本没在跑。
