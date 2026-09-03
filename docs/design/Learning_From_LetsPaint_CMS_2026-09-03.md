# 从 Let's Paint CMS 可借鉴的清单

**日期：** 2026-09-03
**状态：** 方案 / 未实施
**参照系统：** Let's Paint CMS v7.5.3（`LetspaintCMS`，独立仓库，单租户单品牌）
**目标系统：** PWE Studio SaaS v10.14.0（多租户，主题由生成器产出）
**范围：** 设计感 / 艺术感、排课系统
**不在范围：** 本文不改任何代码。

---

## 0. 两条约束

**一、抄结构，不抄颜色。** Let's Paint 是一间画室的自有站点，暖纸白 + 陶土可以硬编码；
StudioSaaS 颜色只有一个来源（生成器），界面不许自己声明、回退值也算。
凡是要引入具体 hex 的条目一律不列。

**二、先查再荐。** 本文第一版把「补 token 阶梯」和「引入有机形状」列为最高优先级，
**两条都是错的** —— StudioSaaS 早已实现，而且比 Let's Paint 更完整。
错因是只 grep 了 `tenant-template/index.html` 的 `:root{`，
而 token 实际在 `backend/frontend/assets/portal-theme.css`。§3 如实记录了核查结果。

---

## 1. 设计感 / 艺术感

### 1.1 有机形状 —— 已实现，真正的问题是「上不上管线」

**现状（逐条核对）：**

| 项 | Let's Paint | StudioSaaS | 结论 |
|---|---|---|---|
| 基础曲率 | `42% 58% 48% 52% / 34% 42% 58% 66%` | **逐字符相同** | 已有 |
| 过渡 | `border-radius .8s var(--ease-out)` | **完全相同**（`index.html:147`） | 已有 |
| hover 变形 | 无 | `48% 52% 43% 57% / 41% 54% 46% 59%`（`:157`） | **StudioSaaS 更多** |
| 可选方案 | 无（写死一种） | **三选一** `organic` \| `oval` \| `square`，后端校验、studio-admin 可编辑 | **StudioSaaS 更多** |

后端 `_shared.py:659` 的注释已经把取舍写清楚了：

> Organic is the default because it is the one mark that makes the page read as a
> studio rather than a form, but it is a strong opinion and a studio showing
> architectural or product work will want the rectangle.

**所以这条不是「要不要做」，是你提的那个问题：形状要不要和配色走一条线。**

#### 现在是两条线

| 维度 | 来源 | 管线 |
|---|---|---|
| 配色 | `VISUAL_STYLE_PRESETS` + `accent_hue` 求解 | 生成器 |
| 按钮圆度 `button_style` | **`STYLE_SHAPE[style_id]`** | **跟着配色** |
| 字体气质 `font_mood` | **`STYLE_SHAPE[style_id]`** | **跟着配色** |
| Hero 形状 `hero_shape` | `hero_profile`，固定默认 `"organic"` | **独立手动开关** |

`presets.py:425` 的 `STYLE_SHAPE` **已经是那条线**——它给 9 个视觉风格各自挂了两个
非颜色属性。`hero_shape` 是唯一一个本该在里面、却不在的设计属性。

```python
STYLE_SHAPE = {
    "atelier-clay":   {"button_style": "soft",    "font_mood": "serif"},
    "studio-ink":     {"button_style": "sharp",   "font_mood": "modern"},
    "recital-plum":   {"button_style": "rounded", "font_mood": "classic"},
    …
}
```

#### 一个必须先解决的问题：现在的默认值和「选择」长得一模一样

所有存量租户的 `hero_profile.hero_shape` 都是 `"organic"` ——
**不管他们是真的选了，还是从没打开过那个设置。** 直接把默认改成风格派生，
要么对存量租户毫无作用，要么就得判定「存的 organic 等于没选」，
那正是「存量记录不是用户输入」的坑。

**建议方案：复用同一个函数里已有的 `"auto"` 模式。**
`secondary_cta_target` 就在 `hero_shape` 上面 6 行，注释写着：

> `auto` preserves old tenants without guessing at save time.

所以：

- 新增第四个合法值 `"auto"`，含义是**跟随视觉风格**
- **新建租户默认 `"auto"`**
- 存量租户的 `"organic"` 保持不动 —— 它现在是一个显式选择，且渲染结果不变
- `STYLE_SHAPE` 每个风格增加 `hero_shape` 键，作为 `"auto"` 的解析目标

零破坏、零迁移、零视觉变化，而且新租户从此自动获得与配色一致的形状。

#### 建议的映射（**需要你拍板**）

| style_id | button/font | 建议 hero_shape | 理由 |
|---|---|---|---|
| `atelier-clay` | soft / serif | `organic` | 画室本色 |
| `vintage-press` | soft / serif | `square` | 活字印刷是矩形的 |
| `studio-ink` | sharp / modern | `square` | 已经是 sharp，形状要跟上 |
| `harbour-calm` | soft / modern | `oval` | |
| `cedar-grove` | soft / modern | `organic` | |
| `recital-plum` | rounded / classic | `oval` | rounded 对应椭圆 |
| `rehearsal-rose` | rounded / classic | `oval` | |
| `arcade-lime` | sharp / modern | `square` | |
| `custom` | soft / serif | `organic` | 自由强调色沿用默认 |

这是跨 8 个策展主题的视觉身份决定，不是实现细节。

- **成本：** 低（一个枚举值 + 9 个键 + 解析分支）
- **风险：** 低（`auto` 模式使存量零变化）
- **优先级：** ★★★

---

### 1.2 `attr()` 水印

```css
.course::before{
  content: attr(data-medium);
  font: 500 68px/1 var(--font-latin);
  color: color-mix(in srgb, var(--clay) 6%, transparent);   /* ← 不引入新颜色 */
  position:absolute; right:-8px; top:-24px; letter-spacing:-.04em;
}
```

课程卡右上角浮一个 68px 的巨型衬线水印，内容是卡片**自己的 data 属性**，
不透明度 **5.5%**。不新增内容、不新增请求。

**核查：** `tenant-template/index.html` 中 `attr(` 出现 **0 次**，`.course` 目前只有边框与
hover 背景（`:350–359`），没有装饰层。这条确实缺。

**对 StudioSaaS 的意义：** 课程分类、乐器名、班级层级已经在渲染的数据里，
直接抬成装饰层，多语言天然成立（水印跟着 i18n 的实际文本走）。

**两个坑（Let's Paint 踩过）：**
1. 字号必须落在封闭尺度内。他们曾用 92px，超出尺度且 `.course` 没有 `overflow:hidden`，
   实际溢出卡片，v7.5.2 才收敛到 68px。StudioSaaS 的 `.course` 同样没有 `overflow:hidden`。
2. 不透明度必须极低（5–6%）。一旦可读就从装饰变成噪音。

- **成本：** 低 · **风险：** 低 · **优先级：** ★★★

---

### 1.3 揭幕式入场

```css
.reveal-mask{
  clip-path: inset(0 0 100% 0 round var(--radius-card));
  transition: clip-path calc(var(--dur-enter) * 4) var(--ease-out);
}
.reveal-mask.in{ clip-path: inset(0 0 0 0 round var(--radius-card)); }
```

关键是 `round var(--radius-card)` —— **裁切路径带着卡片自己的圆角**，
揭幕过程中边缘始终是圆的，不会先露一个直角再变圆。
比 `opacity + translateY` 更像"作品被揭开"。

**核查：** `clip-path` 在公开模板中出现 **0 次**。缺。

时长用 `calc(var(--dur-enter) * 4)` ≈ 932ms，而不是硬写 1.1s ——
这样 `prefers-reduced-motion` 下 `--dur-enter: 0ms` 自动生效（见 §1.6）。

- **成本：** 低（一个 IntersectionObserver，`.reveal` 机制已存在） · **风险：** 低 · **优先级：** ★★

---

### 1.4 材质：加纹理，不加颜色

```css
.pull::before{
  content:""; position:absolute; inset:0; pointer-events:none;
  background: url('/assets/paper-texture.webp') center/cover;
  mix-blend-mode: soft-light;
  opacity: .08;
}
```

**为什么这条对多租户特别重要：** `mix-blend-mode` 让纹理**跟着底色走**，
不引入任何自己的颜色。同一张纹理放在任何租户的深色区块上都成立 ——
这是唯一一种「不违反单一颜色来源、又能增加质感」的手段。

**核查：** `soft-light` / `multiply` 在公开模板中 **0 次**。缺。
StudioSaaS 已有 `.pull` 深色节奏区块（2 处），是现成的落点。

- **成本：** 低（一张 WebP + 两条 CSS） · **风险：** 低 · **优先级：** ★★★（性价比最高）

---

### 1.5 滚动进度条

```css
.scroll-progress{
  position:fixed; top:0; left:0; right:0; height:2px;
  transform-origin:left; transform:scaleX(0);
  background: linear-gradient(90deg, var(--clay), color-mix(in srgb, var(--clay) 45%, var(--panel)));
  z-index: var(--z-progress); pointer-events:none;
}
```

只用 `transform:scaleX()`，不触发布局。渐变的第二个颜色用 `color-mix` 从强调色派生 ——
Let's Paint 为此专门定义了 `--blush`，StudioSaaS 不必新增 token。

**核查：** `scroll-progress` / `scaleX` **0 次**。缺。

- **成本：** 低 · **风险：** 低 · **优先级：** ★★

---

### 1.6 每一条新动效自带减弱动效处理

StudioSaaS 现有做法**比 Let's Paint 更好**：`prefers-reduced-motion` 下直接把
`--dur-enter` / `--dur-exit` 归零（`portal-theme.css:225–226`），
所有引用这两个 token 的过渡自动失效 —— 不需要 Let's Paint 那种 `*!important` 通配轰炸。

**但 token 归零覆盖不到三类东西**，而 §1.2–1.5 每一条都踩中其中之一：

| 新增项 | token 归零能否覆盖 | 必须补 |
|---|---|---|
| §1.3 揭幕 | ✅ 能（时长用 `calc(var(--dur-enter)*4)`） | — |
| §1.4 材质 | ❌ 不是动效，但 `background-attachment` 需注意 | `body{background-attachment:scroll}` |
| §1.5 进度条 | ❌ JS 驱动的 `transform` | JS 侧查 `matchMedia` 后不注册滚动监听 |
| §1.7 标语带 | ❌ 无限动画 | `animation:none` 单独点名 |

**纪律：§1 每引入一条，同一次改动里必须带上它自己的 reduced-motion 处理。**

- **成本：** 低 · **优先级：** ★★★（与各条目同批，不单独排期）

---

### 1.7 无限标语带（可选）

```css
.manifesto-track{ display:flex; width:max-content; gap:72px; animation:manifesto 36s linear infinite; }
.manifesto-track:hover{ animation-play-state: paused; }
```

**36 秒**一圈，慢到几乎察觉不到在动。`hover` 暂停是关键 —— 想读的人能读完。

- **成本：** 低 · **风险：** 低 · **优先级：** ★

---

### 1.8 已确认不做

**笔触光标（`.cursor-brush`）** —— 已决定不加。
（自定义光标是无障碍敏感项，且后台需要的是可预测而非氛围。）

---

## 2. 排课系统

### 2.1 周日期条 + 人数徽标

**现状：** 排课页只有 `shiftDate` 的前一天 / 后一天。
`legacy-root/src/panels/scheduling.jsx`（619 行）无日期条；产物中 `rosterCounts` **0 次**。

Let's Paint：日期条默认本周 7 天，**每格标注当日排课人数**，点击直接跳转。

**为什么排第一：** 排课的实际动作是"看看这周哪天空着"。
一天一天点过去，是把空间问题变成了序列问题。

- **成本：** 中 · **风险：** 低 · **优先级：** ★★★

---

### 2.2 月视图展开（**只存本地**）

```js
const first = new Date(year, month - 1, 1);
const lead  = (first.getDay() + 6) % 7;              // 周一为一周之首
const start = new Date(year, month - 1, 1 - lead);
const cells = Array.from({length: 42}, (_, i) => { /* … */ });
// 末行整行属于下个月时裁掉,避免出现空白的第 6 行
const rows  = cells.slice(35).every(c => c.outside) ? cells.slice(0, 35) : cells;
```

四个容易漏的细节：

1. **42 格固定**，跨月补白日淡化显示
2. **末行整行属于下月时裁掉** —— 否则一半的月份多出一条空行
3. **周一起始**：`(first.getDay() + 6) % 7`
4. **人数为 0 的日期不显示徽标** —— "排过又清空"的残留在生产库里确实存在，
   否则整月一片无意义的"0 人"

**存储：已确认只存本地。** 展开态写管理员浏览器 `localStorage`，不进数据库、不跨设备。
日期格需 `min-height:var(--tap-min)`（Let's Paint 此前是 41.5px，v7.5.3 才补到 44px）。

- **成本：** 中 · **风险：** 低（纯前端，只读既有数据） · **优先级：** ★★

---

### 2.3 一条产品决策，比代码更值得抄

Let's Paint 的 CHANGELOG 明确记录了**为什么不做另一种实现**：

> 原生 `<input type="date">` 弹出的系统日历面板由浏览器／操作系统在页面 DOM 之外渲染，
> 没有任何标准途径注入人数标注 —— 这是平台限制而非代码问题。因此采用「升级日期条」
> 而非「替换选择器」，既拿到了想要的直观效果，又完整保留了 iOS 系统选择器的体验与
> 无障碍能力，且不影响另外 9 处使用 `DateField` 的地方。

**要抄的是方法：遇到平台限制时，改需求的形状，而不是砸掉平台组件。**
顺带避免了"为了一个页面的效果，把全站 9 处日期输入换成自研控件"这种过度工程。

写进 `docs/design/Design_Constraints.md`。

- **成本：** 0 · **优先级：** ★★★

---

### 2.4 派生的「缺席」状态（**只在显示层**）

```js
if (checked.has(date))                                          status = 'done';
else if (ms.status && !['planned','done'].includes(ms.status))  status = ms.status;
else if (date < today)                                          status = 'absent';   // 排了课但无签到
else                                                            status = 'planned';
```

**`absent` 不是存储字段，是推导的**：排了课 + 日期已过 + 无签到 = 缺席。
没人需要维护它，也不会出现"忘了标记"导致的假数据。

StudioSaaS 的 `daily_roster_entries.status` 枚举是 `scheduled | makeup | cancelled`，
出勤维度不在里面（**这是对的，见 §3.1**）。但显示层也没有这个推导 ——
一节过去了没人来的课，和一节明天的课，界面上长得一样。

> **⚠ 这条只做显示层推导。绝不要把 `done` / `absent` 加进枚举** —— 那会摧毁 §3.1 的结构优势。

- **成本：** 低 · **风险：** 低 · **优先级：** ★★★

---

### 2.5 临时签到也要出现

```js
checked.forEach(date => { if (!(date in map)) map[date] = 'done'; });   // 临时签到(无排课)
```

有签到记录但当天没排课的，照样显示为已完成。

**原则：现实胜过计划。** 学员没排课直接来了、老师现场加人 —— 每周都发生。
界面只认排课表就会和现实分叉。

- **成本：** 低 · **优先级：** ★★

---

### 2.6 两段式确认，显示算术

```js
const [armed, setArmed] = useState(false);
useEffect(() => {                                    // 3 秒自动解除
    if (!armed) return;
    const t = setTimeout(() => setArmed(false), 3000);
    return () => clearTimeout(t);
}, [armed]);
…
{busy ? '处理中…' : armed ? `再点确认 · ${b}→${Math.max(0,b-1)} 课时` : label}
```

三个设计点：

1. **确认文案是算术，不是问句**：`再点确认 · 8→7 课时`。用户看到的是**将要发生的结果**；
   "确定吗？"提供不了任何新信息。
2. **不用模态框**。按钮自己变确认态，鼠标不用移动，节奏不断。
3. **3 秒自动解除**。走开了就不算数，不留一个"武装态"按钮等着误触。

**对 StudioSaaS 的意义：** Platform Admin 审计已记「两套对话框系统」
（`openModal()` 与 `window.confirm()` 并存）为未解决项，CMS 产物中 `window.confirm(` 出现 1 次。
这给了第三条路：**触及课时/金额的轻量操作根本不需要对话框** ——
把确认做进按钮，把后果写进文案。

- **成本：** 低（一个组件） · **风险：** 低 · **优先级：** ★★★

---

### 2.7 当日变更记录内嵌在排课页

```js
const actions = new Set(['加入排课','移出排课','撤销移出排课','修改排课状态','撤销排课状态',
                         '修改上课时间','标记一对一','改为普通班课','套用班组模板','生成固定排课']);
return (db.logs||[]).filter(l => l.classDate===rDate && actions.has(l.action)).slice(0,8);
```

**九类动作、当天、最近 8 条、默认折叠**，嵌在排课页底部。

StudioSaaS 有完整操作日志，但在**另一个页面**。"今天这张表怎么变成这样的"
是排课页当场的问题，答案应该在同一屏。

- **成本：** 低（日志数据已有，换个位置查询渲染） · **风险：** 低 · **优先级：** ★★

---

### 2.8 导出工具组与主操作分层

```jsx
<div role="group" aria-label="导出当日排课">
    <button title="下载 Apple / Google 通用日历（.ics）" aria-label="下载 Apple 和 Google 通用的当日排课日历文件">日历</button>
    <button title="复制当日排课日报" aria-label="复制当日排课日报">日报</button>
</div>
```

用 `role="group"` 归组，与签到主操作保持视觉与语义分层；手机端收进「当日操作」面板。
每个按钮有**可访问名称 + 用途提示**两层文本。

对应原则：**每个页面或操作区只保留一个实心主操作**。

- **成本：** 低 · **优先级：** ★★

---

## 3. 核查结果：StudioSaaS 已经有的（不要重复做）

### 3.1 `status` 枚举里没有 `done`，所以不需要守卫

Let's Paint 的 `status` 能存 `done`，于是写了**两道守卫**：

```js
// 读路径:没有签到日志的 done 一律降级
return stored === 'done' ? 'planned' : stored;
//   "A persisted done without a matching check-in log never deducted a credit."

// 写路径:直接拒绝把状态设成 done
if (status === 'done') { showToast('请使用「签到并扣 1 课时」完成签到', 'warn'); return; }
```

StudioSaaS 的 `CHECK (status IN ('scheduled','makeup','cancelled'))`
**结构上就没有出勤维度**。同一条不变量（只有真实签到能宣称完成、能动余额），
StudioSaaS 靠约束免疫，Let's Paint 靠两段代码守。

### 3.2 设计 token —— StudioSaaS 比 Let's Paint 更完整

`backend/frontend/assets/portal-theme.css`：

| Token 组 | StudioSaaS | Let's Paint |
|---|---|---|
| 圆角 | `--radius-xs/​-/-card/-lg/-xl/-pill` 六档，`test_shape_language.py` **锁死为封闭集合** | 五档，无测试 |
| 阴影 | `--shadow-soft` `--shadow-float`，用 `color-mix` 从 `--ink` 派生 | 两档，硬编码 rgba |
| 缓动 | `--ease-out` + **`--ease-in`** | 只有 `--ease-out` |
| **时长** | **`--dur-enter:233ms` `--dur-exit:144ms`（斐波那契），减弱动效下归零** | **无时长 token** |
| **φ 间距** | **`--space-phi-xs…2xl`** | 无（CSS 里硬写） |
| **φ 分栏** | **`--golden-columns: minmax(0,1.618fr) minmax(0,1fr)`** | 无（写 `1.618fr` 但实际渲染 1.45:1） |
| 触控下限 | `--tap-min: 44px` | 无 token |

> **一处有意思的反转：** Let's Paint 的设计规范明确写「**不要**为了凑比例给列加 `minmax(0,…)`」——
> 因为那会压扁他们的正方形二维码面板导致溢出，所以他们接受了实际 1.45:1 而非 1.618:1。
> StudioSaaS 的 `--golden-columns` 正是用 `minmax(0, 1.618fr)`，拿到了真正的 φ 分栏。
> **同一个技术选项，不同内容下的正确答案相反** —— 不能照抄结论，只能照抄推理。

### 3.3 其余已有能力

| 能力 | StudioSaaS | Let's Paint |
|---|---|---|
| Hero 三形状 | `organic` \| `oval` \| `square`，后端校验 + 后台可编辑 + hover 变形 | 写死一种，无 hover |
| `.ics` 导出 | 有（`backend/studiosaas/calendar_export.py`，服务端 + 测试） | 有（前端 `src/calendar-export.js`） |
| 签到窗口限制 | 有（`checkInWindow` + `reason`） | 无 |
| 排课来源可追溯 | `source IN ('manual','group','profile','import','booking')` | 无 |
| 取消可逆 | `status_before_cancel` + `cancelled_by_user_id` + `cancelled_at` | 无 |
| 多租户隔离 | RLS ENABLE+FORCE + 会话变量 + 受限角色 | 不适用 |

**明确不要抄的：** `database.json` 整库读写模型、`rosters` 的 `{date:[id]}` 极简结构、
任何具体配色值。

---

## 4. 上一轮提出、仍然成立的两条（指针）

1. **真 Chrome 多视口发布门禁**（`scripts/check_ui_browser.mjs`）—— 375/768/1024/1440
   逐视口断言无横向溢出、可见按钮 ≥44×44、模拟减弱动效与深色、200% 缩放。
   StudioSaaS 只有静态检查。**这是两个项目最大的工程差距**，
   也是唯一能自动验证 §1 全部条目是否真正落地的手段。
2. **否定式静态契约**（`scripts/check_ui_ux.py`）—— 每条断言对应一个不许复发的历史缺陷，
   而不是"函数存在吗"。

---

## 5. 执行计划（一批做完）

已确认三批合并为一轮。建议内部顺序按依赖排，不按主题分：

**第 1 步 · 零风险、解锁其余**
- §2.3 把「升级而非替换平台组件」写进 `Design_Constraints.md`
- §1.1 `hero_shape` 增加 `"auto"` + `STYLE_SHAPE` 补 9 个键（**待映射拍板**）

**第 2 步 · 排课（用户每天在用）**
- §2.1 周日期条 + 人数徽标
- §2.4 派生 `absent`（显示层）
- §2.5 临时签到显示
- §2.6 两段式算术确认
- §2.7 当日变更记录内嵌
- §2.8 导出工具组分层
- §2.2 月视图（localStorage，只存本地）

**第 3 步 · 艺术层（对外页面）**
- §1.4 材质（性价比最高）
- §1.2 `attr()` 水印
- §1.3 揭幕式入场
- §1.5 滚动进度条
- §1.7 标语带（可选，最后做，看前面的实际观感再定）

**每一条都必须同批带上 §1.6 的 reduced-motion 处理。**

**不做：** §1.8 笔触光标。

---

## 6. 唯一待拍板项

**§1.1 的 `hero_shape` 映射表** —— 8 个策展主题各自配哪种形状。
这是跨主题的视觉身份决定，不是实现细节。我的建议见 §1.1 表格，
其中三条最需要你确认：

- `vintage-press` → `square`（活字印刷是矩形的，但它 `button_style` 是 soft，可能想要 organic）
- `studio-ink` → `square`（已经是 sharp，形状跟上）
- `recital-plum` / `rehearsal-rose` → `oval`（rounded 按钮对应椭圆）

其余五个（`atelier-clay`、`cedar-grove`、`custom` → organic；`harbour-calm` → oval；
`arcade-lime` → square）我认为没有争议。
