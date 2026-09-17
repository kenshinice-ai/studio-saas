# 2026-09-17 · 迁移之后的收尾：让编排脚本也指向真正在服务的那台机器

> 状态：**已完成、已提交、已推送 `origin/main`**。只改发布工具、测试与文档；
> 零运行时改动，**未 bump、未部署**——生产仍是 v10.20.1（commit `147458b`）。

## 起点（实测，不是读账本）

- `main` == `origin/main` == `52a2746`，工作区干净。
- `https://pwestudio.online/v1/health` → `appVersion=10.20.1`。账本说的与线上一致。

所以「提交、同步」本身没有欠账。欠的是迁移在仓库里留下的三处不一致：

## 发现

1. **`release.sh` 的 deploy / health 两个阶段仍然调用 `deploy/aws/pwestudio_remote.sh`。**
   v10.20.1 是手工跑 `deploy/oracle/pwestudio_arm.sh deploy 147458b` 发出去的；
   按编排脚本走（`release.sh <ver> --from deploy`）会在第 8 步被上一轮装的目标机
   守卫拒绝。拒绝是对的，但编排脚本因此在第 8 步是条死路——下一次发布的人要么
   绕开编排，要么去「修」守卫。
2. **`pwestudio_arm.sh` 没有任何测试。** `test_deploy_target_guard.py` 的结尾写着
   「a guard nobody asserts is a guard somebody deletes while tidying」，而它只读
   AWS 那一个脚本。真正在服务的那条路径上的两道守卫，没有一条断言。
3. **「带迁移的版本不能就这样发」只存在于散文里。** 新脚本不做部署前备份，
   handoff 和记忆里都写了，脚本本身不知道。
4. 文档：runbook 的 Oracle 小节仍写着 **Not exercised from this repository**
   （已经真跑过一次）并给出手工四行命令而不是脚本；`Architecture.md` §5 仍把
   Lightsail + nginx 写成生产；`Deployment.md` 顶部横幅之下的 Scope 一行、
   `QA_Checklist.md` §8 同样；上一轮的轮次文件状态还停在「源码候选」。
   README 与 handoff 都写「`main` 领先两个提交」——这个数字每提交一次就错一次。

## 计划

- `release.sh`：deploy → `pwestudio_arm.sh deploy <HEAD>`，health → `pwestudio_arm.sh health`。
- `pwestudio_arm.sh deploy`：若 `<上一个部署的 commit>..<要部署的 commit>` 动了
  `backend/db/migrations/`，拒绝，除非操作者显式声明刚做过备份。
- 测试：两道守卫、迁移拒绝、编排脚本的去向，各一条，先弄红再信。
- 文档对齐上面第 4 条。
- 本地文件：旧发布包归档进 `achieve/dist/`（含两个已合并 worktree 里的包），
  已合并且干净的 worktree 与本地分支清理。只移动，不删除。

## 实际做了什么

- `backend/scripts/release.sh`：deploy → `deploy/oracle/pwestudio_arm.sh deploy "$(git rev-parse HEAD)"`，
  health → `pwestudio_arm.sh health`；第 9 步的提示不再要求一个 Oracle 路径并不产生的
  「部署前 dump 文件名」。
- `deploy/oracle/pwestudio_arm.sh deploy`：`<线上 commit>..<目标 commit>` 动了
  `backend/db/migrations/` 就拒绝，列出是哪些文件；放行条件是
  `PWESTUDIO_ARM_BACKUP_TAKEN_FOR=<完整目标 commit>`。绑 commit 是故意的：`=1` 留在
  shell profile 里会放行此后每一版，这个写法下一个提交一出现就自动失效。线上 commit
  在本仓库里找不到时同样拒绝（证不出有没有迁移）。
- `backend/tests/test_oracle_deploy_path.py`（新，5 条）：把 `ssh` / `curl` / `git fetch`
  在 PATH 上换成 shim，**真的执行脚本**，断言它按什么顺序对机器做了什么。
- 文档：runbook「Step 8, by host」改为脚本命令并写明两件首次真跑才知道的事；
  `README_AWS.md` 横幅同步；`Architecture.md` §5 与目录树、`Deployment.md` 的 Scope 行、
  `QA_Checklist.md` §8 标注为迁移前记录；上一轮轮次文件的状态从「源码候选」改为已发布；
  README 与 handoff 不再写「领先两个提交」这种会过期的数字，改写核对方法。

### 一处比预想严重的

runbook 与 `README_AWS.md` 里印着的手工四行命令，最后一行是裸的
`sudo docker compose up -d`。**那正是 v10.20.1 首次真部署失败的那条命令**（少
`--profile local-db`，compose 拒绝解析整个项目）。脚本当天就修了，两份文档里的那条
命令没有——而文档还写着「Not exercised from this repository」。已删，改为指向脚本。

## 验证

```
STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh  →  All checks passed ✅
  pytest            3447 passed, 41 skipped
  smoke             73 通过 / 0 失败
  租户隔离          254 passed, 0 failed
```

新测试逐条弄红过（改脚本 → 跑 → 还原，还原后 `cmp` 与原文件逐字节一致）：

| 把脚本改坏成 | 变红的测试 |
|---|---|
| 迁移检查永不触发 | `…refused_without_a_backup_declared_for_it` |
| 任何非空声明都放行 | 同上（用上一版的 commit 当声明） |
| 不比对公开边缘的版本 | `…public_edge_does_not_report_is_rolled_back` |
| 磁盘差容忍到 100% | `…not_the_serving_machine_is_refused_before_anything_moves` |
| compose 丢掉 `--profile local-db` | `…lets_the_release_through_and_the_edge_must_confirm_it` |
| `release.sh` 改回 AWS 脚本 | `…orchestration_deploys_to_the_host_that_serves` |

同时核对了写进两份账本的那句话：`git diff --name-only 147458b HEAD` 除已取消跟踪的
`ui_matrix_out/` 外只有 `.gitignore`、`README.md`、`backend/scripts/ui_matrix.py`、
`docs/HANDOFF_LATEST.md`——确实没有一个进运行时。

## 顺带关掉的遗留项

「其它以 `urllib` 打生产的脚本还没查过」：查了。`console_smoke.py`、
`capture_manual_shots.py`（`--base` 默认 `http://localhost:8899`）、
`verify_tunnel_parity.py`（本地隧道用）——全部默认打本机，发布路径上没有第二个会被
Cloudflare 1010 静默挡掉的。`capture_manual_shots.py` 若被人指向生产会撞上同一个 403。

## 本地文件整理（不进仓库）

- 发现：`.claude/worktrees/ui-ux-pro-max-audit-073a82/dist/` 里有约 90 个发布包
  （v8.2.3 → v10.20.0），**别处没有**——`HANDOFF_LATEST.md` 按 SHA-256 引用的
  v10.15.0–v10.20.0 包只存在于那个 worktree。它「干净」且「已合并」，因为 `dist/`
  被忽略；`git worktree remove` 会把它们一起删掉。
- 处理：全部**移动**到主 checkout 的 `achieve/dist/`（同卷 rename，逐个确认无重名），
  主 `dist/` 只留当前版 v10.20.1。**移动 202 个文件，0 跳过**；移动后对 10.13+ 与
  10.9.2 / 9.9.6 的 `.sha256` 逐个 `shasum -c`，零失配；v10.18.0 / v10.19.0 / v10.20.0
  六个包的实测哈希与 `HANDOFF_LATEST.md` 记录的逐一相同。
- 两个 worktree 本身与已合并的分支**没有删**，见汇报里的建议。

## 这一轮不声称的

- **没有碰生产，也没有 SSH 上去看。** 会话的权限策略拒绝了对生产主机的只读查询，
  我没有绕。所以脚本拒绝信息里只说「在机器上做一次数据库备份」并指向 runbook，
  **没有**印一条我没验证过的 `systemctl` 命令；`pwe-backup@db` 这个单元名来自上一轮
  的实测记录，不是本轮的。
- **迁移拒绝没有在真机上触发过**——目前没有带迁移的待发版本。测试用的是
  `origin/main` 上最后一个动过迁移目录的真实提交，机器一侧是 shim。
- `pwestudio_arm.sh` 仍然不编排备份，只是不再允许人忘记它。
- 旧 Lightsail 机仍在运行；`~/.ssh/config` 的 `pwestudio` 别名未动（本机配置）。
