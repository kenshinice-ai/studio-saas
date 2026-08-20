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
期间任何本地账号都能从 `ps` 里读到数据库口令。现在 `owner_db_password` 只返回
口令，用 `-e STUDIOSAAS_DB_PASSWORD`（**不带 =值**）转发，compose 从自己的环境
取值，`/proc/<pid>/environ` 只有同用户与 root 可读。URL 由
`backup_postgres.py._database_url()` 组装并 percent-encode，bash 手写的
`urlencode()` 随之删除（不留死代码）。测试先行：含 `@ : / ? # % & =` 的口令
往返完整、显式 URL 仍优先、没有任何凭据时**大声失败**而不是退回默认连接——
这条路径是写备份的。

## 门禁与发布证据

（随部署闭环补齐；见下方与 `HANDOFF_LATEST.md` 四层身份表。）

## 后续留意

- pem 冗余副本在本会话 scratchpad，Lee 确认后删除即可（`~/.ssh` 的正本完好）。
- C 档未动且触发器不变：X4 月末对账（约 9/19）、OPS-01/02（第一个付费租户前
  强制先行）、X5 GA（第一个付费租户有真实需求时）。
- `.runtime/` 仍在 iCloud 内（0700、已 gitignore）。要不要一并移出同步目录，
  是 Lee 的运行环境决定，本轮只记录不动。
