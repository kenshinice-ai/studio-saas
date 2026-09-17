# 2026-09-17 · 给现在的生产主机补一条有守卫的发布路径（v10.20.1）

> 状态：**源码候选**。第 6–9 步由发布人执行。
> 上游事实：生产于 2026-09-17 由另一个会话迁到 Oracle ARM，方案正本
> `~/Documents/ClaudeCode/oracle-a1-grab/DEPLOY-PWESTUDIO-LETSPAINT.md`。

## 为什么

迁移做完之后，**仓库里没有任何一条通往生产的脚本路径**：

- `deploy/aws/pwestudio_remote.sh` 默认 `SSH_HOST=pwestudio`，而
  `~/.ssh/config` 把它解析到 `13.237.190.58` —— **旧 Lightsail 机，仍在运行**；
- 通往 Oracle 的步骤只以散文形式存在于 runbook 里；
- 于是上一轮刚给 AWS 路径装的两道守卫，**对真正在服务的那台机器不起作用**。

而按旧路径跑下去的结果是全程绿灯：包传上去、容器起来、公开边缘 `curl` 到 200
（来自**另一台**机器）、脚本 exit 0。三方提交守卫也看不见——它比的是 commit，
不是机器。

## 做了什么

### `deploy/oracle/pwestudio_arm.sh`

`status` / `verify-target` / `health` / `logs` / `deploy <commit>` / `ssh`。

部署形状和旧路径完全不同，脚本照着实际情况写，而不是照着旧脚本改：

| | AWS Lightsail | Oracle ARM |
|---|---|---|
| 交付物 | 传 tar 包 | 在机器上 `git checkout <commit>` |
| 镜像 | 包里带 | 在机器上 `docker build`（aarch64，无交叉编译） |
| 切换 | 移 `current` 符号链接 | `docker compose up -d` |
| 回滚 | 符号链接切回 | checkout 回上一个 commit，旧镜像 tag 还在 |

compose 的实际调用形状是从运行中的容器标签里读出来的，不是猜的：
`-p pwestudio --env-file /srv/pwestudio/shared/production.env`，
`-f docker-compose.yml -f docker-compose.lightsail.yml`，
工作目录 `/srv/pwestudio/app/deploy/aws`。镜像 tag 来自 `production.env` 里的
`STUDIOSAAS_VERSION`，所以那一行必须跟着版本改——和旧路径同一个坑。

### 两道守卫，两条路径都装

**上传/切换之前**：比对目标机自己的深健康与公开边缘的深健康，用磁盘占用。
两台跑同一版本的机器，在应用自述的一切上都一模一样，能区分它们的只剩机器事实。
启发式，故意放在任何东西移动之前。

**部署之后**：断言公开边缘报出**刚刚构建的那个版本**。那个版本此刻别处都不存在，
所以不匹配是铁证；这一半是任何未来的迁移都绕不过去的。

实测两个方向都对：

```
pwestudio_remote.sh verify-target   → 拒绝（旧机已不答 127.0.0.1:8899，证不出）
pwestudio_arm.sh   verify-target   → pwe-arm 6.5% / 公开 6.5%，同一台
```

### 部署前还检查的三件（在笔记本上，不在机器上）

失败代价最低的地方检查：commit 必须存在于本仓库、必须是 `origin/main` 的祖先
（机器从 origin 拉，拉不到就是半成品部署）、该 commit 的 `VERSION` 必须是安全的
版本标识。

## 本机门禁

```
bash backend/scripts/verify_local.sh   →  All checks passed ✅
pytest（按闸的角色配置）                →  见收口
```

## 零运行时改动

本版只改部署脚本、文档与测试。`VERSION` 从 10.20.0 到 10.20.1 的意义就是让这次
部署**看得见**——否则公开 `appVersion` 不变，部署后的版本断言也就验不到任何东西。

## 未做

- 旧 Lightsail 机仍在运行且未删除（回滚用）。没有停它，也没有改
  `~/.ssh/config` 里的 `pwestudio` 别名——那是本机配置，不属于这个仓库。
- `pwestudio_arm.sh` 没有 `backup` / `drill` 子命令。Oracle 上的备份目录由
  `production.env` 的 `STUDIOSAAS_BACKUP_DIR` 指定，编排还没搬过来。
- Caddy 配置与 48 条重定向仍由 `oracle-a1-grab/tools/` 生成，不在本仓库。
