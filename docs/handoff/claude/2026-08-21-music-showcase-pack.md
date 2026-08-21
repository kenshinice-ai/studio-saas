# 2026-08-21（Claude Opus 5）音乐样板租户 —— 播种器泛化成「行业内容包」

> 起因：8/22 见 Sinobeats 的负责人。需要一个音乐行业的 showcase，既给这次用，
> 也给以后跟别的音乐机构谈的时候直接用。租户 `music-studio-showcase` 由 Lee 在
> 线上用向导建好，内容、数据、logo 全部由本轮补齐。

## 一句话

`reset_professional_demo.py` 从「只会种一间画室」变成「按内容包种任意一间演示
租户」，音乐包 `music-studio-showcase`（知音音乐 Zhiyin Music）本地全流程跑通；
顺手修掉四个只有第二个包出现才会暴露的缺陷，美术包输出一字未变。

## 一、播种器泛化（A 部分）

### 包注册表

一个「包」是数据，不是分支：内容模块 + 图片目录 + 确认短语 + 凭据文件名。

```python
PACKS = {
    "art":   {"module": "showcase_content",       "assets": "showcase",
              "confirm": "RESET-LETS-PAINT-SHOWCASE",
              "credentials": "showcase-credentials.txt"},
    "music": {"module": "music_showcase_content", "assets": "music-showcase",
              "confirm": "RESET-MUSIC-STUDIO-SHOWCASE",
              "credentials": "music-showcase-credentials.txt"},
}
```

`_select_pack(name)` 在写任何东西之前把模块级单例重新绑定到该包，并校验九个必需
导出。选择「重绑定」而不是把 pack 对象穿过二十八个 helper：一处可见的接缝，好过
六十处改动——美术包自己的 39 个测试是这个取舍的担保。

### 确认短语按租户分化

每个包带自己的短语，短语里点名自己的租户。三条路径实测：

| 命令 | 结果 |
|---|---|
| `--pack music --confirm RESET-LETS-PAINT-SHOWCASE` | 拒绝，提示要 `RESET-MUSIC-STUDIO-SHOWCASE` |
| `--pack art --confirm RESET-MUSIC-STUDIO-SHOWCASE` | 拒绝，提示要 `RESET-LETS-PAINT-SHOWCASE` |
| `--pack dance` | argparse 直接拒绝 |

**自己踩过的坑**：第一版 `main()` 先做安全检查、后选包，于是
`--pack music --confirm <美术短语>` 真的把**美术**租户重置了。现在 `_select_pack`
在 `_refuse_unsafe_context` 之前。

### 「重置演示租户」按钮的地雷

`api_v1/platform.py` 的重置端点按 id 查租户、检查**那个**租户的 `professional_demo`
标记，然后调用一个写死 slug 的播种器。一个演示租户时看不出来；两个之后，在音乐
租户上按「重置」会重建**美术**租户，而审计行记的是音乐租户——调用点读起来正确、
底下是错的。现在租户决定包：

```python
pack = pack_for_slug(row["slug"])
if pack is None:
    return _error(f"No demonstration pack owns '{row['slug']}'. Reset is refused.", 400)
required = confirmation_for_pack(pack)
```

没有任何包认领的演示租户 → 拒绝。手工设过 `professional_demo` 的租户被当成别的
工作室重建，是比拒绝更坏的唯一结果。

### 测试改的是断言对象，不是常量名

原测试断言 `"DEMO_RESET_CONFIRMATION" in body`——钉的是常量名，不是行为。改成断言
派发本身（`pack_for_slug(row[`、`confirmation_for_pack(pack)`、
`reset_showcase(_credentials_path(None), pack=pack)`），另加一条「无包认领即拒绝」。

## 二、播种器里剩下的美术字面量（B 部分）

九组文案/数据从播种器搬进包模块。美术包保留今天逐字相同的值，因此输出零位移。

`SEO_TAGLINE`、`PAYMENT_NOTE`、`ROOM_NAMES`、`PAYERS`、`INVOICE_PLAN`、
`PROGRESS_REPORTS`、`BILLING_LINKS`、`ATTENDANCE_COURSE_INDEX`、
`REGISTRATION_ANSWERS`。

后三个是这一轮新挖出来的——它们本来是**索引算术**，而索引算术记的是美术名册的
形状：

| 原写法 | 美术名册上的含义 | 音乐名册上的后果 |
|---|---|---|
| `((0, 1), (0, 4), (1, 0), (2, 3))` | 两个 Whelan 同一个账单账户 | 把不相干的成人和小孩放进同一个家庭账户 |
| `course_ids[3 if is_child else index % 3]` | 小孩都在周六儿童班 | 每个小孩的出勤都记在「乐理与视唱练耳」——包括两个学古筝的和六岁的 |
| `{"experience": "Painted years ago", ...}` | 报名表三个字段的答案 | 钢琴报名的答案是「以前画过画」，且 key 对不上音乐报名表 |

三条都不会报错，只会安静地产出一个跟自己的发票和学习报告互相矛盾的演示——带去
见客户最坏的一种结果。

美术包的 `ATTENDANCE_COURSE_INDEX` 经断言证明与旧规则逐项相等：

```
tuple(3 if i >= ADULT_COUNT else i % 3 for i in range(12)) == (0,1,2,0,1,2,0,1,2,0,3,3)
```

## 三、音乐包本身

`backend/scripts/music_showcase_content.py`（907 行）+
`backend/seed-assets/music-showcase/`（22 个文件，1.43 MB）。

- 知音音乐 Zhiyin Music，Glen Waverley，`growth` 套餐（播种时自动升级，无需人工
  去 Super Admin 改）。
- 12 名学员（3 成人 9 小孩，与美术包的 10/2 相反）、9 门课、7 个公开班次、
  4 名教职、8 件工作室作品 + 4 件学员作品、6 张琴房照片。
- 名册**按班排序**，因为 `SCHEDULES` 用连续切片寻址班级名单——重排名册＝静默重排
  五个班级名单。
- 价目表含 GST，且每个都能整除回整数澳元（$55→$50、$77→$70、$99→$90、$44→$40、
  $198→$180）。发票行按不含税单价开，实测六个单价余数全为 0。美术包广告 $65 却
  开 $71.50，音乐包没有这个缝。
- 五种发票状态齐全：paid / part_paid / 逾期 31 天（`issued` + 45 天前开票 + 14 天
  账期，让账龄自己算，不写死）/ 未到期 issued / draft。
- 一件学员作品的公开同意被**撤回**：条目仍是 `shared`，学员级同意事件关闸，公开
  相册因此只有 3 件。只授予过、从未撤回的演示证明不了 FAQ 承诺的那件事。

## 四、装配时发现并修掉的四个缺陷

1. **Logo 被压成一根头发丝**。`logo-wordmark-ink.png` 2000×242，字标只占左边
   64%，右边是一条长横线加一个**被画布边缘齐齐切断**的反复记号（末列仍满不透明）。
   页眉给的是 140×40 的盒子，于是墨迹只渲染到 9.8px 高。按美术包的参照（字标紧
   贴画布、8.26:1）裁到 1276×140，墨迹高度 +57%。两个变体同一裁切框，原图留档。

2. **manifest 的学员索引对不上名册**。古筝独奏挂在 Angela Lin（小提琴）名下，
   小提琴曲挂在 Ethan Lin（钢琴）名下——而两条 caption 里写的是 Isabella 和
   Oliver。改成 10 和 6。

3. **「两台钢琴」的标题和正文互相矛盾**。标题说两台，正文说两间小琴房各一台立式
   加一台三角＝三台；而琴房二的照片明明是电钢琴、儿童椅、打击乐筐。以照片为准：
   琴房一立式 + 大琴房三角＝要调音的两台，琴房二电钢琴给启蒙组。

4. **manifest 凭空多出第五个房间**。room-05 的 caption 写「排练厅：少年合奏团和
   乐理课在这里」，但 `ABOUT` 和 `SCHEDULES` 都把合奏与乐理放在**大琴房**（正文：
   「最大的一间放得下十几个人和一台三角钢琴，周六下午归乐团」）。改成不点名房间的
   功能描述。另：古筝数量 caption 说四台、正文说五台，统一为五台。

5. **两个包会把凭据写进同一个文件**。`STUDIOSAAS_DEMO_CREDENTIALS_FILE` 是一个
   演示租户时代的写法——它直接点名一个**文件**，线上是
   `/data/showcase-credentials.txt`。于是重置音乐租户（命令行，或者 Platform
   Admin 那个不传路径的按钮）会把音乐的凭据盖在美术的文件上。改成「环境变量给
   目录、包给文件名」：美术解析结果逐字节不变，音乐拿到自己的同级文件；
   `--credentials-file` 显式覆盖仍然最优先。

## 五、验证

| 项 | 证据 |
|---|---|
| 全量测试 | `2832 passed, 87 skipped`，零失败（新增 3 条：凭据文件按包分化、确认短语点名自己的租户、每个包的索引数据与自己的名册自洽） |
| 美术包无回归 | 重播种输出逐字相同（12 学员 / 4 角色 / 7 班次 / 15 工作室作品 / 8 学员作品(7 同意) / 6 照片 / 4 付款人 / 5 发票 / 4 报告 / studio 套餐）；报名 payload 仍是 `{"goals": ..., "experience": "Painted years ago", ...}` |
| 音乐包播种 | growth 套餐；派发实测 —— Angela+Ethan 在 Lin 家账户、Rachel Tan 自己付、Chloe 在 Zhang 家；12 个学员的出勤各归各的乐器；5 条报名答案 key 为 instrument/level/availability 且与各自留言吻合 |
| 公开页 | 中英双语首页 / 课程表 / 报名 / 作品页实测；title 取自 `SEO_TAGLINE` 两种语言；课程表两次停课都落在两周窗口内；报名表三个自定义字段带正确占位符 |
| 权限 | `/v1/entitlements` 返回 `management_reports`、`teacher_payables`、`sms_notifications`、`xero` |
| 控制台报错 | 两条 `unknown error occurred when fetching the script` 在**美术样板页上同样出现**（已上线数周），是浏览器面板产物，非本轮缺陷；网络请求全 200 |

## 六、上线前必须知道的一件事

**线上租户会拒绝播种。** `_load_or_create_tenant` 要求既有租户带
`settings.professional_demo = true`；这个标记没有任何 UI 入口，只有播种器自己
INSERT 时会写。`music-studio-showcase` 是 Lee 用向导建的，因此没有这个标记——本地
一模一样地拒绝过一次：

```
RuntimeError: Tenant 'music-studio-showcase' exists without
settings.professional_demo=true. Refusing to touch it.
```

守卫是对的，不要改。上线顺序是：**先手工打标记，再播种**。打上之后播种器会整行
更新租户（含 `plan_code` → growth），之后每次重置都自带这个标记。

```sql
UPDATE tenants
   SET settings = COALESCE(settings, '{}'::jsonb) || '{"professional_demo": true}'::jsonb
 WHERE slug = 'music-studio-showcase';
```

## 七、留给下一轮

- 提案微调（保价缩期路线）尚未动笔。
- `_seed_students` 仍用 `course_ids[...]` 之外的一处索引算术挑「一对一常驻课」学员
  （`((2, "16:00", 0), (4, "17:30", 3))`）。音乐包名册上 0 和 3 恰好都是钢琴学员，
  所以现在是对的——**是巧合，不是设计**。第三个包会踩到。
- `ROOM_NAMES` 只被常驻课用到（`index % len` → 只取前两项），排练厅没进这个列表。
