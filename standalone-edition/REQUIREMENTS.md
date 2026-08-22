# PWE Studio Edition · 部署前提与必备环境

> 当前源码候选：v10.12.2 Edition（未提交、未打包、未交付）；最后验证的
> Edition 运行包仍为 v10.6.3。候选 `BUILD_INFO` 必须为
> `mode=standalone`。完整实施顺序见 [DEPLOYMENT_PLAN.md](DEPLOYMENT_PLAN.md)。

## 1. 标准部署形态

Edition 的标准客户交付是“一台服务器、一个客户、一个 active 租户”的
Docker Compose 单机部署：

```text
客户服务器
├─ nginx + TLS（主机层）
├─ app 容器（Python 3.11 / Waitress / PWE Studio）
└─ db 容器（PostgreSQL 16）
```

客户不需要在主机上另行安装 Python、Flask、Waitress、PostgreSQL、Redis 或
Node。应用依赖由镜像从 `deploy/aws/requirements.lock` 安装，PostgreSQL
客户端固定为 16，与 `postgres:16-alpine` 配套。

## 2. 服务器规格

| 形态 | 最低交付规格 | 适用 |
|---|---|---|
| 云主机（推荐） | 2 vCPU / 2 GB RAM / 40 GB SSD 起 | 单店、约 500 名学员以内、少量并发员工 |
| 客户内网服务器 | 同上；必须允许出网安装依赖和证书，或由客户提供内部镜像/证书 | 有 IT 管理能力、数据必须留在内网 |

如果媒体、备份或历史数据较多，应在上线前增加磁盘；磁盘空间属于客户或
代管方的持续运维责任。macOS 仅用于演示，不作为客户生产环境。

推荐系统：Ubuntu 22.04/24.04。Debian 12 可以由实施人员适配；标准安装器
的自动安装分支以 `apt-get`、`systemd` 和 `cron` 为前提。

## 3. 主机必备软件

- Docker Engine
- Docker Compose v2（`docker compose`，不是旧版 `docker-compose`）
- nginx
- certbot 和 `python3-certbot-nginx`
- bash、curl、openssl、sudo、cron/systemd

安装器可以在 Ubuntu 上协助安装 Docker 和 Compose。nginx、Certbot 和域名
证书仍需按 [DEPLOYMENT_PLAN.md](DEPLOYMENT_PLAN.md) 的顺序配置。

## 4. 网络、DNS 和端口

- 客户提供一个正式域名，例如 `studio.example.com`。
- DNS A 记录必须指向服务器固定公网 IP。
- 公网开放 TCP `80`、`443`；SSH `22` 只允许客户或维护人员的固定来源。
- 不开放应用端口 `8899` 和数据库端口 `5432`。
- 首次安装需要访问 Ubuntu 软件源、Docker Registry、PostgreSQL 软件源和
  Let’s Encrypt；内网部署必须提前准备代理、镜像或离线安装包。
- 如果需要 `www`，必须同时准备 DNS 记录并在证书申请中明确加入该名称。

## 5. 数据库、持久化和备份

- 标准方案使用独立的 PostgreSQL 16 容器，不需要 RDS 或其他外部数据库。
- 数据库总共只能有一个 tenant，且该 tenant 必须为 `active`。
- 应用使用 `studiosaas_app` 最小权限角色；迁移、角色授权和受控恢复使用
  数据库 owner `studiosaas`。
- 数据库、媒体、归档、租户工作区和业务数据使用 Docker 持久卷。
- 每日由 root-owned cron 执行 PostgreSQL 备份，默认保留 14 份。
- 默认不包含媒体文件的异地备份；Docker volume 能保留升级数据，但不能替代
  服务器损坏后的灾难恢复副本。

## 6. 安全与运维账号

- 安装命令必须使用 `sudo` 或 root。
- 稳定配置位于 `/etc/pwe-studio/<slug>.env`；有 Docker group 时实际权限为
  `root:docker 0640`，没有该组时为 `root:root 0600`。
- 数据库 dump 和 manifest 为 `0600`。
- 安装器会生成独立的 `STUDIOSAAS_SESSION_SECRET`、`STUDIOSAAS_API_KEY`
  和数据库密码。
- 安装器会为指定运维用户加入 Docker group。Docker group 等同主机高权限，
  只能授予合同中指定的运维人员；首次安装后需要重新登录。
- Edition 不向平台回连，不包含 Super Admin、支持模式或平台遥测。

## 7. 客户交付前必须提供

1. 服务器、云账号或内网主机，以及 SSH/控制台权限。
2. 域名和 DNS 修改权限。
3. 工作室名称、时区、联系人、Logo、配色和公开文案。
4. Owner 邮箱、员工名单和角色分配。
5. 现有学员、课程、套餐、期初课时余额和数据迁移截止时间（如需迁移）。
6. 隐私、报名、家长/监护人和作品发布授权要求。
7. 可选 SMTP 配置。未配置 SMTP 时，通知保持 console/log 模式，不影响核心
   业务，但不会产生自动邮件投递。

## 8. 明确不包含在标准安装中的服务

- RDS、S3、Redis、SES 或其他托管 AWS 服务；
- 媒体文件异地备份和默认灾备副本；
- 24/7 监控、备份失败告警、值班和 SLA；
- MFA/SSO、在线支付、自动 SMS、自动邮件投递和浏览器 Push。

这些内容必须通过单独的维护协议或定制订单确认，不能从“Docker 部署成功”
推导为已包含。
