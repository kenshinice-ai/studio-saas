# PWE Studio Edition v9.9.6 · Standalone 完整部署方案

> 用途：客户售前说明、实施工程师部署、交付验收和后续运维交接。
>
> 适用范围：一台客户自有或代管服务器、一个客户、一个 active tenant。
> 标准交付路径为 Docker Compose 单机部署。裸机 systemd 只作为定制路径，
> 不属于标准一键安装。

## 0. 当前交付事实

| 项目 | 当前基线 |
|---|---|
| 产品 | PWE Studio Edition |
| 版本 | `9.9.6` |
| 运行模式 | `standalone` |
| 官方包 | `PWE-Studio-Edition-10.0.0.tar.gz` |
| 包 SHA-256 | `0a75bf66059da97dc91b450933bd2a44e48200b7dda17030b62baa22ec1cd3b6` |
| `BUILD_INFO` commit | `4b436e1e2df0717b7efb01d5e7d4021a6cc23860` |
| 包构建时间 | `2026-08-11T12:11:20Z` |
| 标准数据库 | PostgreSQL 16（Docker `postgres:16-alpine`） |
| 标准反向代理 | 主机 nginx + Let’s Encrypt/客户证书 |

正式包必须同时通过 SHA-256 和 `BUILD_INFO` 检查。版本号、压缩包文件名或
工作区中的 `VERSION` 文件都不能单独证明客户正在使用哪个版本。

## 1. 产品和部署边界

Standalone Edition 保留以下客户功能：

- 工作室门户和公开报名；
- Studio Admin 品牌、网站和发布工作台；
- 运营 CMS；
- 学员、课程、套餐、课时余额和流水；
- 排课、考勤、报名处理和作品媒体；
- Owner、Manager、Teacher、Front Desk、Staff 角色权限；
- 审计日志、双语界面、主题和学生私密访问区域。

Standalone Edition 明确关闭：

- `/super-admin`、`/platform-admin`、`/v1/admin/*`；
- 多租户管理和平台支持模式；
- SaaS 订阅计费、套餐额度和租户生命周期控制；
- 平台成员、平台遥测、平台心跳和平台回连；
- 在线支付、自动 SMS、自动邮件投递、浏览器 Push、MFA/SSO。

独立版是客户自己的数据实例。平台方不会自动获得服务器访问权；后续安装、
升级、排障和恢复必须由客户按维护协议主动授权。

## 2. 标准技术架构

```
公网 DNS
   │
   ▼
客户服务器
   ├─ 防火墙：80/443，SSH 22 限定来源
   ├─ nginx：TLS、HTTP→HTTPS、反向代理
   │       └─ 127.0.0.1:8899
   ├─ app 容器：Python 3.11、Waitress、PWE Studio
   │       └─ db:5432（Docker 内部网络）
   └─ db 容器：PostgreSQL 16

持久化：
  studiosaas-data       业务数据与运行状态
  studiosaas-media      上传媒体
  studiosaas-archives   租户归档和删除证据
  studiosaas-tenants    生成的租户门户工作区
  studiosaas-pgdata     PostgreSQL 数据目录
  /var/lib/pwe-studio/<slug>/backups/postgres
                         PostgreSQL dump 和 manifest
```

### 2.1 组件责任

| 组件 | 作用 | 是否需要客户单独安装 |
|---|---|---|
| Docker Engine | 运行应用和数据库容器 | 是，主机必备 |
| Docker Compose v2 | 管理 Edition 服务 | 是，主机必备 |
| App 容器 | PWE 后台、Waitress、生产依赖和健康检查 | 否，安装器构建 |
| PostgreSQL 16 容器 | 客户独立数据库 | 否，Compose 自动运行 |
| nginx | TLS 和反向代理 | 是，主机必备 |
| Certbot | Let’s Encrypt 证书申请/续期 | 是，使用客户证书时可替换 |
| Redis/RDS/S3/SES | 当前标准 Edition 不需要 | 否 |

主机不需要安装 Python、Flask、Waitress、psycopg、Pillow、PostgreSQL
server、Node 或 npm。App image 使用 Python 3.11 和锁定的生产依赖；镜像内
的 PostgreSQL client 固定为 16。

## 3. 客户部署前提

### 3.1 服务器规格

最低交付规格：

- Ubuntu 22.04/24.04；
- 2 vCPU；
- 2 GB RAM；
- 40 GB SSD 起；
- 固定公网 IP；
- 有效的 SSH 或云控制台访问；
- 可持续获得安全更新。

客户有大量照片、作品媒体、历史数据或较长备份保留期时，应在安装前增加
磁盘。磁盘不足属于部署失败条件，不应等到上传媒体后才处理。

内网部署也必须满足以下条件：

- 主机能够出网安装 Docker、镜像和软件包；或客户提供等效的内部镜像/软件源；
- 客户提供已有 TLS 证书和私钥，或允许使用可访问的 ACME 证书；
- 客户 IT 团队负责内部 DNS、网络路由和证书续期。

### 3.2 网络和 DNS

- 配置 `studio.example.com` 的 DNS A 记录指向服务器固定 IP；
- 如使用 `www`，同时配置 `www` 的 DNS 记录；
- 公网开放 TCP `80` 和 `443`；
- SSH `22` 只允许客户或维护人员的固定 IP；
- 不开放 `8899` 和 `5432`；
- 首次安装允许访问 Ubuntu 软件源、Docker Registry、PostgreSQL 软件源和
  Let’s Encrypt；
- 若使用客户已有证书，证书、私钥、域名和续期责任必须写入交接记录。

### 3.3 客户资料

部署前收齐：

- 工作室正式名称、域名、时区、地址、电话和联系人；
- Owner 邮箱和员工名单；
- 员工角色与最小权限分配；
- Logo、主色、公开文案、课程描述和 FAQ；
- 报名字段、隐私声明和家长/监护人授权要求；
- 现有学员、课程、套餐、期初余额和迁移截止时间；
- 数据负责人对学员和媒体资料的转移授权。

SMTP 是可选项。未配置 SMTP 时，通知保持 console/log 模式，核心业务仍可
运行，但不能向客户承诺自动邮件送达、退信处理或重试机制。

## 4. 责任分工

| 事项 | 客户自有服务器 | 我们代管服务器 |
|---|---|---|
| 云账号、账单、地域和公网 IP | 客户 | 按合同约定 |
| OS 更新、磁盘和防火墙 | 客户 | 代管方 |
| DNS 和域名续费 | 客户 | 客户授权后协助 |
| Edition 安装和首次验收 | 实施方协助 | 实施方负责 |
| Owner/员工资料 | 客户提供并确认 | 客户提供并确认 |
| 日常账号和内容维护 | 客户 | 客户 |
| PostgreSQL 本地备份 | 安装器配置 | 安装器配置 |
| 媒体异地备份、监控、告警 | 不默认包含 | 仅维护协议包含 |
| 升级、恢复和故障处理 | 客户或维护协议 | 依维护协议 |

没有维护协议时，不能默认承诺 24/7 监控、备份失败告警、固定恢复时间或 SLA。

## 5. 部署前检查

### 5.1 验证正式包

在压缩包和 `.sha256` 文件所在目录执行：

```bash
shasum -a 256 -c PWE-Studio-Edition-10.0.0.tar.gz.sha256
tar xzf PWE-Studio-Edition-10.0.0.tar.gz
cd PWE-Studio-Edition-10.0.0
grep -E '^(version|mode|commit|built_at)=' BUILD_INFO
```

必须确认：

- `version=9.9.6`；
- `mode=standalone`；
- commit 与交付单一致；
- 包不是从当前未提交工作区临时压缩的副本。

### 5.2 检查主机

```bash
id
uname -a
df -h
sudo systemctl is-active docker || true
docker --version
docker compose version
curl --version
openssl version
```

如果 Docker 或 Compose 不存在，`install.sh` 可以在 Ubuntu 上询问并安装；
安装前仍须确认客户允许主机修改和软件源访问。

### 5.3 检查 DNS 和端口

```bash
dig +short studio.example.com A
curl -I "http://studio.example.com/" || true
```

DNS 未生效、80 端口不可达或域名指向错误服务器时，不得进入正式证书申请。

## 6. 标准安装

### 6.1 解包

```bash
tar xzf PWE-Studio-Edition-10.0.0.tar.gz
cd PWE-Studio-Edition-10.0.0
```

安装器会把稳定状态放在发布目录之外：

```text
/etc/pwe-studio/<slug>.env
/var/lib/pwe-studio/<slug>/
/opt/pwe-studio/<slug>/current
/usr/local/bin/pwe-studio-<slug>
/etc/cron.d/pwe-studio-<slug>-backup
```

### 6.2 全新开店

```bash
sudo bash standalone-edition/install.sh \
  --domain studio.example.com \
  --studio-name "Example Studio" \
  --owner-email owner@example.com \
  --owner-name "Studio Owner" \
  --slug example-studio \
  --industry art
```

`--industry` 可选值：`art`、`dance`、`game`、`general`、`language`、
`math`、`music`、`sports`。

安装器执行顺序：

1. 检查/安装 Docker 和 Compose v2；
2. 生成数据库、Session 和 API secrets；
3. 创建 Compose 项目 `studio-example-studio`；
4. 启动 PostgreSQL 16；
5. 应用有序数据库迁移；
6. 配置 `studiosaas_app` 最小权限数据库角色；
7. 创建一个 active tenant 和 Owner；
8. 生成租户门户工作区；
9. 关闭首次引导跳过标记，重新执行 standalone 启动检查；
10. 安装 root-owned 每日 PostgreSQL backup cron；
11. 创建并检查第一份 dump；
12. 输出 nginx、Certbot 和交付验收命令。

### 6.3 从 SaaS 平台迁入

平台侧导出包必须由实施人员单独记录可信 SHA-256。不要只把包和哈希放在
同一封普通邮件中，也不要在未完成 rehearsal 前删除 SaaS 源租户。

```bash
sudo bash standalone-edition/install.sh \
  --domain studio.example.com \
  --studio-name "Example Studio" \
  --owner-email owner@example.com \
  --slug example-studio \
  --import-bundle /secure/example-edition-bundle.tar.gz \
  --expected-bundle-sha256 <64位可信SHA-256>
```

导入器要求目标数据库和用户表为空，并验证：

- 外层 bundle SHA-256；
- manifest 中声明的数据库和媒体文件；
- 未声明或被篡改的文件；
- schema migration inventory；
- 表记录数量；
- 期初余额和课时流水金额；
- 媒体文件数量；
- 平台成员是否被剔除。

导入的用户密码不会从平台带出，交付人员必须在交接时生成并单独传递新的
登录凭据。

### 6.4 从 Excel/CSV 迁入

先在实施机器上转换和校验：

```bash
python standalone-edition/templates/csv_to_import_json.py \
  students_filled.csv \
  -o students.json
```

再执行：

```bash
sudo bash standalone-edition/install.sh \
  --domain studio.example.com \
  --studio-name "Example Studio" \
  --owner-email owner@example.com \
  --slug example-studio \
  --import-json students.json
```

标准 CSV 路径导入当前学员档案和期初课时余额；期初余额写为一条 `migration`
账本行。历史签到、排课历史、完整流水、媒体和隐私同意历史不能在没有明确
映射和验收的情况下自动猜测。

## 7. nginx、TLS 和公网入口

### 7.1 HTTP bootstrap

证书不存在前，不要直接安装引用 `/etc/letsencrypt/live/...` 的完整 TLS 配置。
先安装 HTTP-only bootstrap：

```bash
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx

sudo sed 's/server_name .*;/server_name studio.example.com;/' \
  deploy/aws/nginx/studiosaas-bootstrap.conf \
  | sudo tee /etc/nginx/sites-available/example-studio.conf >/dev/null

sudo ln -sf /etc/nginx/sites-available/example-studio.conf \
  /etc/nginx/sites-enabled/example-studio.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

### 7.2 申请证书

仅申请主域名：

```bash
sudo certbot --nginx -d studio.example.com
```

同时使用 `www` 时，必须先有 DNS 记录：

```bash
sudo certbot --nginx \
  -d studio.example.com \
  -d www.studio.example.com
```

确认续期：

```bash
systemctl list-timers | grep certbot
sudo nginx -t
```

### 7.3 公网健康检查

```bash
curl -fsS "https://studio.example.com/v1/health?deep=1"
curl -I "https://studio.example.com/"
```

公网不能直接访问 `http://服务器:8899` 或 `服务器:5432`。应用只接受主机
nginx 代理的本地连接。

## 8. 数据库和安全配置

### 8.1 数据库角色

- `studiosaas`：数据库 owner，供迁移、角色授权和受控恢复使用；
- `studiosaas_app`：应用运行时角色，仅有业务 CRUD 权限；
- 应用启动前会完成迁移和角色配置，然后移除 migration URL 和 runtime DB
  password 环境变量；
- standalone 启动会拒绝空数据库、多租户、非 active tenant 或平台成员。

### 8.2 稳定配置和 secrets

`/etc/pwe-studio/<slug>.env`

该文件包含数据库密码、Session Secret 和 API Key：

- 不得放入聊天、截图、普通工单或公共 Git；
- 客户需要离线保存一份受控副本；
- Docker group 成员等同主机高权限；
- 修改 secrets 后必须按维护流程重启并检查 health；
- Owner 临时密码必须在交付现场修改。

### 8.3 公开服务边界

| 地址 | standalone 预期 |
|---|---|
| `/` | 重定向到唯一租户门户 |
| `/<tenant>/cms` | 可用，需租户账号 |
| `/<tenant>/studio-admin` | 可用，需相应权限 |
| `/super-admin` | 404 |
| `/platform-admin` | 404 |
| `/v1/admin/*` | 404 |
| `/<tenant>/v1/*` | 按租户角色和权限工作 |

## 9. 备份、恢复和灾备

### 9.1 默认 PostgreSQL 备份

安装器创建：

```text
/etc/cron.d/pwe-studio-<slug>-backup
/var/lib/pwe-studio/<slug>/backups/postgres
/var/lib/pwe-studio/<slug>/logs/postgres-backup.log
```

默认每天 02:30 执行，保留最近 14 份。dump 和 manifest 都应为 `0600`。

手动创建备份：

```bash
sudo bash /opt/pwe-studio/example-studio/current/standalone-edition/maintenance.sh \
  --slug example-studio backup
```

### 9.2 恢复演练

```bash
sudo bash /opt/pwe-studio/example-studio/current/standalone-edition/maintenance.sh \
  --slug example-studio restore-dry-run \
  --dump studiosaas_studiosaas_<UTC时间>.dump
```

只有出现 `ok: true` 且关键表计数和 migration inventory 一致，才算恢复演练
通过。至少在交付日和之后按维护协议重复执行。

### 9.3 真实恢复

真实恢复会覆盖当前数据库，只用于确认过的数据损坏或事故：

```bash
sudo bash /opt/pwe-studio/example-studio/current/standalone-edition/maintenance.sh \
  --slug example-studio restore \
  --dump studiosaas_studiosaas_<UTC时间>.dump \
  --confirm studiosaas
```

恢复前必须：

1. 停止或冻结业务写入；
2. 记录事故时间和目标恢复点；
3. 获得客户明确批准；
4. 使用已通过 dry-run 的 dump；
5. 恢复后重新检查 deep health、登录、报名和账本。

数据库备份点之后产生的报名、考勤、课时、账本和配置会丢失。

### 9.4 媒体和异地副本边界

标准安装不自动把媒体 Docker volume 复制到异地。升级不会主动删除媒体，
但这不等于服务器损坏后可以恢复媒体。媒体备份、数据库异地副本、监控、
备份失败告警和 RPO/RTO 必须作为维护协议或定制交付项单独确认。

## 10. 交付日验收

### 10.1 版本和运行时

- [ ] 压缩包 SHA-256 正确；
- [ ] `BUILD_INFO` 的版本、commit 和 `mode=standalone` 正确；
- [ ] Docker 和 Compose v2 正常；
- [ ] app 和 db 容器均为 running/healthy；
- [ ] 日志没有启动失败、迁移失败或持续重启；
- [ ] `https://域名/v1/health?deep=1` 返回数据库正常。

### 10.2 安全和边界

- [ ] 80/443 可达，8899/5432 未暴露；
- [ ] `/super-admin`、`/platform-admin`、`/v1/admin/*` 均返回 404；
- [ ] 数据库总共只有一个 tenant 且为 active；
- [ ] 不存在 `tenant_id IS NULL` 的平台成员；
- [ ] Owner 临时密码已修改；
- [ ] 员工账号使用个人账号和最小角色；
- [ ] `.env`、dump、manifest 权限符合要求；
- [ ] 服务器和域名凭据没有写入普通聊天或公开文档。

### 10.3 业务功能

- [ ] 根路径进入客户门户；
- [ ] Logo、主题、域名、时区和公开文案正确；
- [ ] Owner 能登录 CMS 和 Studio Admin；
- [ ] 手机 4G 提交报名；
- [ ] CMS 出现待处理报名；
- [ ] 报名拒绝/处理闭环成功；
- [ ] 员工角色边界符合客户名单；
- [ ] 作品媒体上传和私密访问符合预期；
- [ ] 公开发布和隐私/肖像授权状态符合客户确认。

### 10.4 数据和恢复

- [ ] 学员、课程、套餐数量对账通过；
- [ ] 期初课时余额与来源账一致；
- [ ] 课时流水总额与来源账一致；
- [ ] 拒绝、缺失、重复和待确认记录有例外清单；
- [ ] 第一份 PostgreSQL dump 和 manifest 已生成；
- [ ] dump/manifest 权限为 `0600`；
- [ ] restore dry-run 通过；
- [ ] 媒体备份边界已由客户签字确认。

### 10.5 TLS 和交接

- [ ] `nginx -t` 通过；
- [ ] HTTPS 证书有效；
- [ ] Certbot 自动续期 timer 生效；
- [ ] HTTP 到 HTTPS 的跳转正确；
- [ ] 客户收到版本、SHA-256、服务器、DNS、备份和应急联系人记录；
- [ ] 客户知道不得执行 `docker compose down -v`；
- [ ] 客户知道如何进行每日状态检查和恢复演练；
- [ ] 客户签署交付验收单。

## 11. 日常运维

查看状态：

```bash
pwe-studio-<slug> ps
pwe-studio-<slug> logs --tail 100 app
curl -fsS "https://你的域名/v1/health?deep=1"
```

重启应用：

```bash
pwe-studio-<slug> restart app
```

检查磁盘和证书：

```bash
df -h
docker system df
systemctl list-timers | grep certbot
sudo nginx -t
```

健康检查失败、容器持续重启或日志出现 `FATAL` 时，不要反复重装；先保留
日志、检查磁盘和最近备份，再联系维护人员。

## 12. 升级和回滚

只接受带 `BUILD_INFO` 且 `mode=standalone` 的正式 Edition 包。将新包解压
到新目录后执行：

```bash
sudo bash standalone-edition/upgrade.sh --slug <slug>
```

升级器会：

1. 创建升级前 PostgreSQL 备份；
2. 备份当前配置；
3. 更新稳定 `current` 链接；
4. 构建并启动新 App；
5. 检查 deep health；
6. 失败时恢复旧版本和旧配置。

PostgreSQL、媒体、归档和租户工作区卷不会因为正常升级被删除。

禁止用以下命令代替升级：

```bash
docker compose down -v
```

该命令可能删除客户数据卷。`--force-reinstall` 只允许在明确重装、完成外部
备份并取得客户书面确认后使用。

## 13. 数据迁移签收表

| 检查项 | 来源 | Edition | 差异/例外 | 客户确认 |
|---|---:|---:|---|---|
| 学员总数 |  |  |  |  |
| active 学员 |  |  |  |  |
| 课程 |  |  |  |  |
| 套餐 |  |  |  |  |
| 期初课时余额 |  |  |  |  |
| 课时流水金额 |  |  |  |  |
| 媒体文件 |  |  |  |  |
| 拒绝/待确认记录 |  |  |  |  |

## 14. 相关文件

- [REQUIREMENTS.md](REQUIREMENTS.md)：主机、软件、网络和客户前提；
- [DATABASE.md](DATABASE.md)：数据库角色、迁移和备份边界；
- [DEPLOYMENT.md](DEPLOYMENT.md)：部署拓扑、发布包和运行边界；
- [RUNBOOK.md](RUNBOOK.md)：实施工程师交付日操作；
- [OPERATIONS.md](OPERATIONS.md)：客户日常运维；
- [COMMERCIAL.md](COMMERCIAL.md)：交付、维护和商业边界；
- `install.sh`：首次安装；
- `upgrade.sh`：升级和失败回滚；
- `maintenance.sh`：备份、恢复演练和真实恢复；
- `docker-compose.edition.yml`：单机服务和持久卷定义。

---

*A PARADISE PRODUCTION · 天域文创出品*
