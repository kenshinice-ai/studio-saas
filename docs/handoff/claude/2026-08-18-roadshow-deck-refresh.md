# 2026-08-18 — 销售材料对齐 v10.9(docs/sales 素材轮)

> 范围:`docs/sales/`(deck、朋友圈软广告、客户提案)。播种器缺陷与 v10.9.2 轮
> 撞车,最终不改运行代码(见第二轮第 2 条)。未打包、未部署;
> Source 四层身份以 HANDOFF_LATEST 首表(v10.9.2)为准。

## 为什么要动

deck 停在 v9.9.6 轮(codex 017 同步),此后产品发生了 v9.9.6 → v10.9.1 的跨越:
发票/贷记/退款事务(v10.7.x)、账务工作台/月结单/学员时间线(v10.8.0)、
Xero OAuth 连接(v10.9.0/1)。**更严重的是定价页已在超卖**:线上 `data-plans`
(pwestudio.online/pricing 实测)是 $49/$99/**$189**,学员上限 **50/250/500**,
席位 1/5/20;而 deck 还写着 $199 与 100/500/1000 学员。
注意:v9.9.6 轮核对时 deck 与当时的 plans 表一致——是套餐表后来改了,
不是当年没对过。销售材料里硬编码的套餐数字会随表漂移,下次发布前要再对一遍。

## 本轮改动(10 页 → 11 页)

1. 版本徽章:第 1、9 页 `v9.9.6` → **`v10.9`**(不带补丁号,避免补丁发布即过期)。
2. 定价页(现第 10 页)逐项对齐线上 plans 表:$49/$99/$189;
   50/250/500 学员;新增席位数 1/5/20;15/60/150 作品与 2/10/50 GB 未变;
   免责行补上「一次性 Setup 服务费 AUD 299–999(配置、迁移与培训)」,与
   pricing 页一致。
3. **新增第 8 页「Reconciliation moves into daylight / 对账搬进白天」**
   (复制第 2 页三栏版式):01 发票与贷记单、02 月结单与学员时间线、
   03 Xero 连接。Xero 措辞按事实:「connect now · push staged /
   可连接·推送分阶段」——连接已上线,单据推送仍在门后,不许说成已同步。
   该页正面回应第 2 页痛点 03「晚上还要对账」。
4. 页码全部改为 `NN / 11`。

## 实现要点(下次改 deck 的人看)

- deck 无生成器,是手工 XML 维护:unzip → 改 `ppt/slides/slideN.xml` → zip。
  所有文本是单一 `<a:t>` run,整串替换即可;本轮脚本对每处替换断言恰好命中一次。
- 用 pptx skill 的 `add_slide.py` 复制页时注意:此 deck 的 `presentation.xml`
  根元素**不声明 `xmlns:r`**(每个元素内联声明),脚本插入的 `<p:sldId>` 缺内联
  命名空间会让文件校验失败,需手动补
  `xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"`。
- validate.py 全绿;LibreOffice 渲染 11 页逐页目检通过。定价卡中文行贴卡片
  下沿是**原版既有排版**,非回归(已与原版第 9 页渲染对比确认)。

## 第二轮(同日):截图重拍与其余材料

1. **deck 13 张产品截图全部换新**(v10.9.1 本地实拍)。映射靠感知哈希与
   v9.9.6 时代手册图逐张比对得出,13 张全部 d=0:
   image4=02-portal.en、image5=02-showcase-page.en、image6/11=04-timetable.en、
   image7=02-register.en、image8/16=01-brand-workbench.en、image9=02-register.zh、
   image10=02-pending.en、image12=03-roster.en、image13=04-log.en、
   image14=01-showcase-workbench.en、image15=02-showcase-portal.en。
   新截图 1600×1000 与 deck 媒体同尺寸,直接换字节,XML 未动。
2. **播种器发票快照缺陷:与 v10.9.2 轮撞车,以远端为准**。本轮独立发现并修了
   同一缺陷(签发发票缺 0043 强制的 supplier/recipient 快照,播种直接崩),
   修法与 2026-08-17 的 v10.9.2 轮(`3e725fd`,另一会话)几乎一字不差——都用
   `studiosaas.services.billing.supplier_snapshot / recipient_snapshot` 构造。
   区别仅在快照来源:远端用镜像 INSERT 的字面量,本轮从库里读回。rebase 时
   丢弃本轮版本,保留已发布的 v10.9.2 版本;两个会话独立撞出同一修法,
   互为正确性旁证。本轮截图是在该修复(本地同款)之上采集的。
3. **截图流程实录**:本地栈 `start_studiosaas_local.sh`(端口 8901)→
   `reset_professional_demo.py --confirm RESET-LETS-PAINT-SHOWCASE`
   (需 `STUDIOSAAS_SHARED_DEMO_PASSWORD` ≥12 字符)→
   `capture_manual_shots.py --base http://localhost:8901`。
   采集在 **05-portfolio 响亮失败**:TAB 映射里的「学员」标签在 v10.2.0
   real tabs 改版后已不可按名点击;05 之后的 05-works/08-stats/07-settings/
   06-student-area 未拍。deck 所需 11 张全在失败点之前,不受影响。
   **手册资产未动**(拍完取走所需后 `git checkout` 恢复)——整套手册截图刷新
   要等 TAB 漂移修好后作为独立文档轮,已挂后台任务。
4. **`docs/sales/朋友圈软广告_v10.9/` 新建**(v9.8.8 包原样保留作历史):
   截图改为自带 `shots/` 子目录(9 张 v10.9.1 webp,不再依赖手册资产)、
   版本标识 v9.8.8→v10.9,9 张 1080×1080 PNG 用无头 Chrome 逐卡重导,
   contact-sheet 重拼。包内无价格,符合「页面里不许写价格」不变量。
5. **sinobeats 提案**只更新页脚版本戳(v9.9.6·08-14 → v10.9.1·08-18);
   商务内容(定制报价、范围)一字未动。机会点:提案把发票系统与 Xero 连接
   写成待开发交付,如今平台核心已上线(v10.7 发票文档/贷记、v10.9 OAuth),
   是否改写成「平台已具备」由商务决定。

## 第三轮(同日):采集脚本两处修复 + 手册 48 张整套刷新

上一轮把「学员 TAB 漂移」列为待办,本轮修掉,并顺带查出第二个更隐蔽的缺陷。

1. **TAB 漂移(诊断修正)**:上一轮记成「real tabs 改版后标签不可点」,不准确。
   实情是**只有中文侧漂移**——`05-portfolio.en` 当时是拍成功的。侧栏渲染
   `NAV_GROUPS` 的长标签 `l`(「学员档案」),而 TAB 映射写的是短标签 `s`
   (「学员」);两者经 `cms-i18n.js` 都译作 "Students",所以英文那一遍看不出来。
   已改为「学员档案」,并在 `manual_shots.md` 第 73 行按本文件既有惯例
   写成「Students / 学员档案 tab」,让标签对在两处都可见。

2. **`OPEN_FIRST_STUDENT` 是死匹配 + 静默兜底(本轮真正的收获)**:
   它找的是 `(\d+课` 这种旧文案,**线上探针实测命中数为 0**;找不到就退回去
   点第一个 `li/tr`,返回 `'MISSING'`——而**调用处把返回值丢掉了**,是这一串
   prepare 步骤里唯一不检查结果的。后果:`05-portfolio` 拍的是学员列表,而
   手册给这张图的 alt 写着「学员档案打开,停在作品集区块」、图注写着「作品集
   区块既是上传的地方,也是能看到授权状态的地方」——图与说明对不上,而且没人
   会被告知。又一次印证 [[silent-fallbacks-are-the-defect]]。
   现在:按渲染出的标签点「详情 / Details」开档案,再点「作品集 / Portfolio」
   进到手册说的那一块,**两步都断言**,漏一步就响亮失败并指明要同时改哪两处。

3. **48 张全部重拍**(单次运行、单一 v10.9.2 基线,避免 codex 017 抱怨过的
   「三个基线混在一起」)。与提交版逐张感知哈希比对:**33 张实质变化**,
   最大 `07-settings`(d=122)——设置页现在是 7 个标签(含「集成」与
   「开票信息」),旧图那个形态已经不存在;其余 15 张只是重编码(d≤7)。
   总量 2.76 MB,仍在 `test_manual.py` 的 3 MB 预算内;
   `build_asset_manifest.py` 已重建并 `--check` 通过。

### 两处**没有**动,及理由

- **手册文案未改**。`05-portfolio` 的标注 1 说「余额与最近流水就在档案里」。
  探针实测:头部绿色徽章是余额(每一个标签页都在),而「最近流水」在**记录**
  标签下的学员时间线里。这句说的是「档案里有」,不是「这一帧里有」,且
  `manual_shots.md` 明确写着标注是 DOM 文本、不是钉在像素上的箭头——所以它
  仍然成立。图片与 alt / 图注这两处具体断言现已完全对上。对外文案不替用户改。
- **未升版本号**。VERSION 仍是 10.9.2;`test_release_ledger.py` 与
  `test_manual.py` 全绿(46 项)。按 [[immutable-asset-versioning]],缓存键是
  `v` + `h` 两个,内容变了 `h` 就变,不推版本号也不会让读者拿到旧图;
  这批资产随下一次发布上线即可。

### 验证

- 全量 pytest:**2838 通过 / 6 skip**,另有 `test_tenant_isolation_by_construction.py`
  两项失败——断言原文即「应用以超级用户 llmacbookpro 连库,RLS 被无条件绕过」,
  是本机 Postgres 角色所致的环境失败,与本轮改动(截图脚本与图片)无关。
- `05-portfolio.zh/en` 逐张目检:档案弹窗停在作品集,公开授权状态、作品与
  「+ 上传」都在画面里。

### 已知未做

- 英文移动版 `03-roster-mobile.en` 出现「Birthdays in the next 14 days (12 )」,
  括号里的量词「人」丢了。这正是 `manual_shots.md` 早就记着的 i18n 已知缺口
  (数字旁的 `人`/`次`/`笔`/`条`/`分钟` 被 React 拆成独立文本节点,单独翻译会
  打乱语序),需要字典先支持模式匹配。本轮不碰。
- `manual_shots.md` 里 `10-statement` / `10-timeline` / `10-receivables` 三张
  仍标着 pending capture;它们不在 SHOTS 里,也没有资产,文档如实标注,不算欠账。
