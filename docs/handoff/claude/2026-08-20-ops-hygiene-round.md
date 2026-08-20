# 2026-08-20 运维卫生轮（v10.11.1）—— A/B 两档清单一次做完

> 来源：v10.11.0 收口后列的优化清单，Lee 指示「把 A 和 B 的内容都一起做掉，
> 小版本更新部署」。A = 结算月内可做的五项，B = 审计计划 Batch B 里方案已定稿
> 的两项（OPS-03/04）。C 档（X4 月末对账、OPS-01/02、X5）仍绑各自触发器，未动。

## 做了什么（六个提交）

| 提交 | 内容 |
|---|---|
| `49555c9` | 集成页 Beta 徽标 + 两组双语标签对齐 |
| `daf0203` | 演示页「每晚重置」不实声明纠正（OPS-05） |
| `291f853` | 控制台冒烟进入发布门禁 |
| `b69a363` | `prune_dist.py`（OPS-06 的 dist 部分） |
| `6a1b95a` | 线上 nginx 收编进仓库（OPS-03） |
| `eb9ef05` | 备份口令离开 argv（OPS-04） |

## 途中发现的两件事（都不在清单上）

**1. 演示页对访客说了假话。** 四个公开页（portal / showcase / register /
timetable）的页脚写着「数据每晚重置 / the data resets nightly」。那个定时器
**从未存在**（memory: showcase-demo-reset-never-ran），而按 2026-08-16 审计
rev2，手动重置是既定决策而非缺口。所以这句话不是「暂时不准」，是对公开地址上的
访客的不实陈述。已改为「数据由运营手动重置」。

关键机制（后来者注意）：公开页是从 `tenants/<slug>/index.html` 静态文件服务的，
改 `tenant-template/` 不等于改线上——但容器 entrypoint 每次启动都会跑
`regenerate_tenant_workspaces.py`，所以模板改动随**下一次部署**生效，无需手工
刷新工作区。（这与 `refresh_stored_themes` / `refresh_tenant_workspaces_from_db`
那类「改生成器≠改线上」的情况不同，因为后者读数据库、前者读 tenant.json。）

**2. 仓库根有一份私钥在 iCloud 里。** `LightsailDefaultKey-ap-southeast-2.pem`，
权限 0644，位于 iCloud 同步目录。核对结论：`*.pem` 已在 .gitignore、
`git log --all -- "*.pem"` 为空——**从未进过公开仓库**，没有泄露到 GitHub。
但它与 `~/.ssh/` 下那份 0600 的副本**逐字节相同**，即纯冗余，且正在被同步到
Apple 与该账号的每台设备。已移出 iCloud（放到本会话 scratchpad，Lee 确认后可删）。
`~/.ssh/` 的三份 pem 权限均为 0600，正常。`.runtime/`（含 online.env 与
credentials）是 0700 且已 gitignore、从未跟踪——未动，仅记录。

## 各项细节

**Beta 徽标**：`integrations.jsx`，`!preview` 时显示，amber（映射到 --warning，
语义「未定稿，按此对待」）。**移除触发条件写在代码注释里**：X4 出口达成转 X5 GA
时删掉那个 span。另加一句说明，让徽标对工作室有可操作含义。

**双语标签**：v10.11.0 的重复键去重暴露出两组真不一致——`Eyebrow · 中文`→小标题
但 `· English`→眉标题；`Description · 中文`→简介 但 `· English`→正文。这两组标签
在同一个 form-group 里并排显示。统一取中文半边的值；Description 顺带不再与
Body（`Highlight N Body` 规则已占用「正文」）撞词。`Principal`→主理人 与
`Owner & Contact`→负责人与联系方式 对照标记核对后保持不变。

**冒烟进门禁**：`console_smoke.py` 现在能自起实例（free port，继承门禁的
`STUDIOSAAS_DATABASE_URL`），所以 verify_local 不再需要人先起服务器。无 Chrome
时**显式跳过并打印一行**——没有 Chrome 的机器不该因此挂掉发布门禁，有 Chrome 的
机器也不该静默略过。挂在 PostgreSQL 可用分支、隔离测试之后（控制台要解析租户）。

**dist 清理**：53 个归档 / 23 个过期版本 / 1.3 GB，全在 iCloud 里。
`prune_dist.py` 保留最近 3 版（与线上 `prune-artifacts` 同策略），默认干跑。
本轮实跑释放 **1.20 GB**，dist/ 降到 178 MB。安全依据：归档可复现（tag +
build_aws_bundle），且每个已发布 SHA-256 都在 handoff 账本里可比对。

**OPS-03 nginx**：`fetch_live_nginx.sh` 早就写好但从未跑过。抓回后发现线上
`pwestudio.conf` 比仓库模板多一条 `include /etc/nginx/snippets/paradise-production.conf`
——一个挂在 `/paradise-production/` 的完整营销站，**仓库此前零记录**。该片段
一并收编。TLS 片段与仓库副本逐字节相同，不重复存。唯一其余差异是仓库模板多了
一段关于 text/javascript 的注释（`gzip_types` 指令本身一致）。
`deploy/aws/nginx/live/README.md` 写明「仓库先改 → 主机逐行应用 → 重跑 fetch
直到报 unchanged」，并说明为什么绝不能整体覆盖。

**OPS-04 备份口令**：此前 `docker compose exec -e STUDIOSAAS_DATABASE_URL=<url>`
把口令放进命令行，而 `/proc/<pid>/cmdline` 在主机上是**全局可读**的——备份运行
期间任何本地账号都能从 `ps` 里读到数据库口令。现在 URL 仍由 shell 的
`owner_db_url()`（含既有 bash `urlencode`）组装，但**用 `-e STUDIOSAAS_DATABASE_URL`
（不带 =值）经环境转发**，赋值前缀只作用于那一条命令；compose 从自己的环境取值，
`/proc/<pid>/environ` 只有同用户与 root 可读。容器侧脚本**一行未改**。

### 这里翻过一次车，教训值钱（第一次 v10.11.1 部署被自己的预备份拦下）

第一版改法是新建 `STUDIOSAAS_DB_PASSWORD` 契约、让 `backup_postgres.py` 自己
组装 URL。部署直接失败：

```
pg_dump: error: query failed: ERROR:  query would be affected by
row-level security policy for table "credit_financial_links"
```

**结构性原因**：`pwestudio_remote.sh` 是「**先铺候选控制器 → 用它做预备份 →
再切版本**」。所以预备份永远是**新控制器 + 上一版镜像**。脚本是从**镜像内**跑的
（WORKDIR /app），不是从主机发布树跑的——我把修好的脚本 copy 到主机发布树、
再跑一次仍然失败，就是这么证实的（容器里 `grep -c STUDIOSAAS_DB_PASSWORD` = 0）。
换言之：**任何控制器↔容器脚本的契约改动，都会在引入它的那次部署上打断预备份。**
要改这个契约得分两版走：先教会脚本，下一版再切控制器。

第一版还叠了第二个错：容器本来就带着 `STUDIOSAAS_DATABASE_URL`（受限角色
`studiosaas_app`），而我让「已有 URL」优先于「注入的口令」，于是 pg_dump 用受限
角色跑、撞 FORCE RLS。**而我写的测试断言的正是这个错误的优先级**——测试锁住了
形状，没锁住真实环境里的相互作用。

**护栏表现正确**：备份失败 → 部署拒绝切换 → 生产始终停在 v10.11.0，未受影响。
但「保护部署的那份备份」不该是发现版本错配的地方。

**定稿前的实测**（不再只信测试）：
1. 主机上用部署同款命令真跑备份 → 产出真 dump
   `studiosaas_studiosaas_20260820T063152Z.dump`；
2. `-e VAR` 透传能**覆盖**容器内同名变量（实测 `role=OVERRIDE_PROBE`）；
3. 哨兵探针（非密钥）确认 **0 个进程**在 argv 里暴露该值——旧写法下
   docker compose 进程会明文显示。

`test_backup_credential_path.py` 现在锁的是：只按名转发不按值、`owner_db_url`
组装、bash `urlencode` 对含 `@ : / ? # % & =` 的口令真跑一遍，以及
**容器契约不许再变**（断言 `backup_postgres.py` 里没有 `STUDIOSAAS_DB_PASSWORD`，
并在断言里写明原因）。

## 门禁与发布证据（2026-08-20 闭环）

- 门禁：`All checks passed`（leastpriv 三变量形状），**控制台冒烟首次跑在门禁里**；
  全量 pytest 2,825 通过。
- 发布提交 `4ff7efe`；SaaS SHA-256 `292993ef…bf5ed`、Edition `35f42cd5…cab019`；
  三方守卫全等。
- 部署前 dump `studiosaas_studiosaas_20260820T063742Z.dump`——**经改正后的凭据
  路径产出，这就是 OPS-04 的验收**（第一次部署正是死在这一步）。
- deep health `appVersion=10.11.1 / db=ok / mode=saas / stale=0`。
- 线上实测：四个公开演示页均已换成「数据由运营手动重置」，`nightly` 残留 **0**；
  集成页 Beta 文案已在线上 bundle；`xero-push` tick 干净
  （`tenants=6 gate-closed=4 jobs=0 tenant-errors=0`）。

## 后续留意

- pem 冗余副本在本会话 scratchpad，Lee 确认后删除即可（`~/.ssh` 的正本完好）。
- C 档未动且触发器不变：X4 月末对账（约 9/19）、OPS-01/02（第一个付费租户前
  强制先行）、X5 GA（第一个付费租户有真实需求时）。
- `.runtime/` 仍在 iCloud 内（0700、已 gitignore）。要不要一并移出同步目录，
  是 Lee 的运行环境决定，本轮只记录不动。
