# 2026-08-22（Claude Opus 5）会面卫生 + 钱与权限 —— 一个小版本

> 出处：`docs/design/CMS_Settings_and_Roster_Integrated_Plan.md` 的层 0 与层 1。
> Lee 的指示：「先做全面卫生和钱与权限，这 2 个可以一起发一个小版本」，
> 音乐包单号前缀用 `music-`，PWE 真账本的 Xero 由 Lee 自己处理、本轮不碰。
> 层 2（两页重构）与层 3（排课页分段）不在本轮。

## 一句话

演示数据里剩下的**十处美术字面量与 index 算术**搬进内容包并重新播种；
签到路径上三条会动钱的缺陷修掉；**并且把我自己两轮前报错的一条安全结论降级**。

---

## 一、必须先说的：我把一条结论报错了

两轮前我用一张五角色表报了「front_desk / staff 能读到工作室银行账号 = 安全缺陷」，
还据此在整合方案里写了「拆 `billing:read` 为两个权限」。**那个判断的前提是错的。**

我当时验证了 `GET /billing/identity` 对 front_desk / staff 返回 200 带银行字段，
但**没有检查同一份数据是否已经通过他们本职工作的路由到达他们手里**。它是：

`GET /billing/invoices/<id>`（`api_v1/billing.py:1820`）只要 `billing:read`，
而它的 SELECT 显式取 `bi.bank_account_name / bank_bsb / bank_account_no`
（同文件 :1871-1873）。本地以 staff 身份实测，两个端点拿到的银行信息完全一致。

这是**设计如此**：收款账户印在每一张发票上，因为家长要照着它转账；前台开票、
答「钱打到哪」，就必须看得到。Lee 在会后也确认了「ABN 公开给前台没问题」。

所以：
- **不拆权限**。只锁 `/billing/identity` 而不动发票路由，是安全剧场。
- 真正成立的只剩一条，而且是**界面正确性**不是安全：`BillingIdentityPanel` 收到的
  `canManage` 是 `canManageOperations`（owner+manager），而 PUT 要 `settings:write`
  （只有 owner）。manager 拿到一张能填满、按保存必定 403 的表单。
  面板本来就有只读态，传对这一个布尔值即可 —— 已修。

整合方案里「层 1 · 设置 #1 / #4 / #5」三条应合并为这一条。`#4` 同样不成立：
Xero 的全部**写**路由早就是 `integrations:manage`（只有 owner），
只有 GET 是 `billing:read`，而那正是「推送失败要让做账的人看见」所要求的。

**教训**：判定越权之前，要先问「这份数据是否已经通过该角色本职的路由到达他」。
只查一个端点得出的越权结论会指向错误的修法。

---

## 二、卫生层：十处字面量与 index 算术

播种器里最后一批「只有第二个内容包出现才会暴露」的东西。新增五个包导出，
`_select_pack` 的必需列表相应加长。

| 原来 | 后果 | 现在 |
|---|---|---|
| 开票主体写死两处（`:687`/`:756`） | 音乐租户的发票印着 Paradise Production / Southbank / 画室的银行账号 | `BILLING_IDENTITY`，两个包各有各的；快照与 INSERT 读**同一份**，不再抄第二遍 |
| ABN `53 004 085 616` | 实测**同时通过** ABN 与 ACN 两套校验 —— 印在演示税务发票上与真号无异 | 各自换成校验位不合法的号，新增断言 |
| 单号前缀写死 `INV-` | 两个样板连**同一个** Xero Demo Company，都从 INV-0001 起，撞号守卫会逐张拒绝 | `INVOICE_PREFIX`：art `INV-`、music `music-`；断言两包不得相同 |
| 生日 `today - 365*N` | 365×N 必然落回今天附近 → 12 人生日挤在 8/23–8/29，6 人同日 | `STUDENT_BIRTHDAYS`（岁数 + 月-日），铺满 12 个月，各一个落在八月底 |
| 年龄由 index 公式推 | Chloe 被算成 10 岁却坐在「适龄 4–6」的启蒙班，而学习报告写着「六岁」 | 同上；新增断言：年龄必须落在**一对一课程**与**所在每个班次**的 age_range 内 |
| 充值手续费恒 58500 | 音乐租户首页累计收款按画室课包价算 | `CREDIT_PURCHASE`（music 取自己的钢琴十次包 55000） |
| 教师薪酬整块字面量 | 记 90 分钟 6 人，而 Hannah 三个班全是 60 分钟 | `TEACHER_PAY`（含 ABN、费率、课次形状） |
| 伪造 Xero 连接（无 token） | 集成页显示「已连接」，`refresh-check` 必 409 —— 会面现场就是这样 | 不再种连接；只种加购 |
| 预写 `mapping_confirmed_at`（无映射行） | 第三步打勾，旁边写「还差 tuition、bank」 | 不再预写；`confirm_mapping()` 的守卫不再被绕过 |
| 重播种不清集成侧 | 发票被删，`xero_object_links` / 作业队列仍指向它们 | 清理名单加四张表 |

`_birthday(today, age_years, "MM-DD")`：包里存「这个人在演示里几岁」而不是出生年份，
存年份的夹具每过一个月就老一个月，迟早和所报课程的 age_range 打架。

**实测**（本地重播种后）：

- 开票主体：`Paradise Production Pty Ltd / 53 111 222 333 / BSB 083-004`
  与 `Zhiyin Music Pty Ltd / 12 345 678 901 / BSB 063-182`，已开具单据的**冻结快照**也各自分化
- 单号：`INV-0001..4` 与 `music-0001..4`
- 生日：12 个月各有分布，无撞日；Chloe 6 岁、Jasmine 5 岁，全部落在适龄内
- Xero：两个租户各 0 连接、0 网关状态、加购有效

另修四处硬编码文案：`dashboard.jsx:213/220/230/237` 的「愿新的一年里画艺大进」——
其中两处在 `sms:` 的 body 里，点一下就是一条**预填好发给琴童家长**的短信。
改走 `renderMessage('birthday', …)`（`birthday` 是服务端模板白名单里的键，自带默认
文案，不需要新增管道）。同仓库 `cms-app.jsx:409-411` 的注释正好在说这类坑修过一次。

---

## 三、钱：签到路径上的三条

| 缺陷 | 修法 |
|---|---|
| 「谁已签到」从全局 `LIMIT 500` 的日志推（`tenant.py:857`）—— 月流水超五百条的工作室，四十多天前的签到掉出窗口，界面显示「待上课」，再按一次批量签到就是**第二次扣课时** | 改按日期查考勤本身：`/attendance?date=`（`students.py:1363` 本来就支持）。查不到时**退回**日志推导，不假装知道 |
| 界面在任何日期都渲染签到按钮：选下周三点下去弹回一句英文原文；选**明天**则静默成功，为一节还没上的课扣掉课时 | `checkInWindow` 镜像服务端的 `[今天-90, 今天+1]`。窗口外禁用按钮并在概览条说明原因；**明天仍然放行**（那 +1 是刻意的跨时区余量，不该由界面推翻），但单人签到当面问一次、批量确认框里点名 |
| 批量签到确认框写死「今日」，读的却是任意选中日期 | 第一句改成 `批量签到确认 · <日期>` |
| 批量签到失败只报姓名不报原因 | 带上服务端返回的原因 |

**没有改服务端的 +1 天规则**：它看起来是刻意留的余量，要改是产品决定不是修 bug。
真正的缺陷是「静默」，已经修掉。

---

## 四、验证

| 项 | 证据 |
|---|---|
| 全量测试 | `2838 passed, 87 skipped`（新增 6 条：适龄一致、生日铺开、单号前缀分化、开票主体分化、ABN 校验位不合法、播种器不伪造 Xero 连接） |
| 发布门禁 | `STUDIOSAAS_REQUIRE_POSTGRES=1 verify_local.sh` **All checks passed**（app 角色 `studiosaas_leastpriv`、owner 另给，隔离测试 254/254，控制台冒烟通过） |
| 产物 | `build_cms.sh` 重建；`build_asset_manifest.py --check` verified；`画艺大进` 在产物中 **0 处**，`birthdayWish` 5 处（1 定义 + 4 调用） |
| 重播种 | 两个包各跑一遍，输出与断言一致 |

**未做浏览器实测**：CMS 需要登录表单，本轮改动的界面态（按钮禁用、概览条提示、
manager 只读态）**没有在浏览器里逐个看过**，只核对了被加载的产物。
按仓库「量渲染结果，别量代码」的纪律，这一条是缺口，部署后应人工过一眼。

---

## 四·五、部署时才炸出来的一条：做过结算的演示租户重置不了

线上重播种第一步就崩了，本地从来没有：

```
ForeignKeyViolation: update or delete on table "payments" violates
  foreign key constraint "credit_financial_links_payment_tenant_fkey"
```

`_clear_showcase` 的清理名单里少两张表，**都只在这间租户真的记过一次结算之后
才会有行**（充值与退款里把课时挂到某笔收款上）。本地只播种、从没点过那个界面，
所以一次都没触发。

| 表 | 为什么挡住 |
|---|---|
| `credit_financial_links` | 对 payments / refunds / invoices / invoice_lines / credit_notes 全是 `ON DELETE RESTRICT` |
| `financial_operation_requests` | 对同一批是 `ON DELETE SET NULL`，但 `trg_financial_operation_payload_immutable` 这个 BEFORE UPDATE 触发器**拒绝**那次 SET NULL，报出来是一句看似毫不相干的「幂等键不能配不同的载荷」 |

两张都排到删钱之前。**这条是既有缺口，不是本轮引入的** —— 只是本轮第一次有人
在演示租户上真的走了一遍结算，于是它从此再也重置不了。

验证走的是真实路径，不是手造行：先用 `POST /students/<id>/credit-settlements`
（开票 + 已收款）造出一条真的结算链接 —— 手工 INSERT 会被
`assert_credit_financial_link_is_legal` 挡下，正好印证「别手造全行」——
然后带着它重播种，通过。第一次修完只加了 `credit_financial_links`，
重跑才炸出第二张表；**静态断言看不见这个，是行为验证捞出来的**。

## 五、留给下一轮

- **前台签到权**：Lee 会后明确「前台是可以有签到权限的，这点需要好好讨论」。
  查到的事实：`front_desk` **有 `credits:write`**（可直接增减课时余额）却**没有
  `attendance:write`**（不能签到扣 1 个课时）——粗放的钱路径开着，受审计的结构化
  路径关着。且 `roleTabs`（`cms-app.jsx:302`）不含 `roster`，页面本身进不去。
  `staff` 反过来：有 `attendance:write` 没有 `scheduling`。这一组要一起定。
- 整合方案的层 2（设置页 B + 排课页甲，共用一次路由改动、一个 Tab 原语）与层 3。
- Xero：`clearing_account` 选项传输层从未实现（Square 收款的必经路径）；
  集成页「已连接」徽标应先过一次 `refresh-check` 再显示。
- 一个演示运维陷阱：Demo Company 里已存在的单号会挡住重播种后的再次推送
  （守卫按单号查，新 local_id 没有链接）。Demo Company 每 28 天自重置。
