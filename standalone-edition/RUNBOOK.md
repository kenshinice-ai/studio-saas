# PWE Studio Edition v10.12.3 candidate — 交付工程师 Runbook（未发布）

适用范围：一台 Ubuntu 主机、一个客户、一个活跃租户。平台 Super Admin 与
`/v1/admin/*` 在 standalone 模式下必须返回 404。本文只覆盖正式 Edition
交付；标准路径是 Docker Compose，不是 SaaS AWS 部署。完整客户方案见
[DEPLOYMENT_PLAN.md](DEPLOYMENT_PLAN.md)。媒体文件异地备份不属于标准安装。

## 0. 服务器前置条件

- Ubuntu 22.04/24.04，2 vCPU、2 GB RAM、40 GB SSD 起；媒体较多时提前扩容。
- 固定公网 IP，DNS A 记录已指向客户域名。
- 公网只开放 80/443；SSH 22 限定维护来源；8899/5432 不得公网开放。
- 主机有 sudo/root、bash、curl、openssl、cron/systemd；首次安装允许访问
  Ubuntu 软件源、Docker Registry、PostgreSQL 软件源和 Let’s Encrypt。
- Docker Engine 与 Docker Compose v2 可由安装器检查/安装；nginx、Certbot
  和 `python3-certbot-nginx` 按第 3 节顺序安装。
- 客户已提供工作室名称、时区、Owner 邮箱、员工角色、品牌素材和迁移资料。

## 1. 交付前硬门槛

1. 本候选尚未形成可交付包；不得向客户发送或部署。发布授权后只使用
   `PWE-Studio-Edition-10.12.3.tar.gz`，同时向客户提供发布方单独保存的 SHA-256。
2. 验证 `BUILD_INFO`：

   ```bash
   grep -E '^(version|mode|commit)=' BUILD_INFO
   # 必须包含 version=10.12.3、mode=standalone
   ```

3. 如从 SaaS 迁入，导出租户包后在安全渠道单独记录整个 tar.gz 的 SHA-256；
   安装器会同时验证可信外层哈希和包内数据库/媒体文件清单。不能只把包与
   哈希放在同一封邮件里。
4. DNS 已指向客户主机；80/443 可达；客户已确认域名、工作室名称、owner
   邮箱和行业预设。

## 2. 安装

从解压后的 Edition 包根目录执行：

```bash
sudo bash standalone-edition/install.sh \
  --domain studio.example.com \
  --studio-name "Example Studio" \
  --owner-email owner@example.com \
  --slug example-studio \
  --industry art
```

从 SaaS bundle 迁入时：

```bash
sudo bash standalone-edition/install.sh \
  --domain studio.example.com \
  --studio-name "Example Studio" \
  --owner-email owner@example.com \
  --slug example-studio \
  --import-bundle /secure/example-edition-bundle.tar.gz \
  --expected-bundle-sha256 <由导出方单独提供的64位SHA-256>
```

安装器会：

- 创建独立数据库 owner 与最小权限应用账号；
- 把 secrets 固定在 `/etc/pwe-studio/<slug>.env`；
- 把数据库备份固定在 `/var/lib/pwe-studio/<slug>/backups/postgres`；
- 建立 `/opt/pwe-studio/<slug>/current` 当前版本软链接；
- 安装 `pwe-studio-<slug>` 运维命令；
- 安装 root-owned `/etc/cron.d/pwe-studio-<slug>-backup`；
- 创建第一份数据库 dump；绝不静默跳过失败。

`--force-reinstall` 会删除该实例的数据库和运行卷，只能在明确重装且完成外部
备份后使用。日常升级一律使用 `upgrade.sh`。

## 3. TLS 与反向代理

按安装器输出执行 nginx bootstrap 和 certbot 两步。完成后检查：

```bash
sudo nginx -t
systemctl is-active nginx
systemctl list-timers | grep certbot
curl -fsS "https://studio.example.com/v1/health?deep=1"
```

## 4. 数据与权限验收

```bash
pwe-studio-example-studio ps
pwe-studio-example-studio logs --tail 100 app
sudo bash /opt/pwe-studio/example-studio/current/standalone-edition/maintenance.sh \
  --slug example-studio backup
sudo ls -l /var/lib/pwe-studio/example-studio/backups/postgres
```

选取最新 dump 文件名执行恢复演练：

```bash
sudo bash /opt/pwe-studio/example-studio/current/standalone-edition/maintenance.sh \
  --slug example-studio restore-dry-run \
  --dump studiosaas_studiosaas_<UTC时间>.dump
```

恢复演练使用数据库 owner 创建临时同级库，验证迁移清单与关键表计数后删除；
线上应用始终使用 `studiosaas_app` 最小权限账号。

## 5. 交付日逐项签收

- [ ] `/` 直达客户门户；品牌、域名、行业预设正确。
- [ ] `/platform-admin`、`/super-admin`、`/v1/admin/tenants` 均返回 404。
- [ ] 数据库中恰好一个租户，且它是 active；不存在任何平台级 membership。
- [ ] owner 登录 CMS/Studio Admin 成功并当场修改临时密码。
- [ ] 4G 网络提交测试报名，CMS 能看到并完成处理闭环。
- [ ] 源数据计数、余额/课次账本与导入 reconciliation 一致。
- [ ] 第一份 dump 与 manifest 均存在、权限为 0600；恢复演练通过。
- [ ] root cron 文件存在，日志路径为
  `/var/lib/pwe-studio/<slug>/logs/postgres-backup.log`。
- [ ] TLS 自动续期 timer 有效；deep health 返回数据库正常。
- [ ] 客户离线保存服务器凭据、`/etc/pwe-studio/<slug>.env` 和发布 SHA-256。
- [ ] 明确签字：v10.12.3 candidate 标准安装只承诺 PostgreSQL 本地备份；媒体文件异地
      备份、监控、备份告警和 SLA 需另行确认。

## 6. 升级与回滚

把新官方 Edition 包解压到新的只读发布目录后，从该目录执行：

```bash
sudo bash standalone-edition/upgrade.sh --slug example-studio
```

脚本先备份数据库，再更新最小权限账号配置、切换 `current`、构建并检查 deep
health。失败时自动恢复旧配置与旧软链接；数据库、媒体和档案卷不会被删除。
禁止以 `docker compose down -v` 代替升级。

## 7. 真实恢复（事故操作）

先完成恢复演练并记录事故窗口，再执行：

```bash
sudo bash /opt/pwe-studio/example-studio/current/standalone-edition/maintenance.sh \
  --slug example-studio restore \
  --dump studiosaas_studiosaas_<UTC时间>.dump \
  --confirm studiosaas
```

脚本会先停应用写入，使用数据库 owner 恢复，随后重启并检查 deep health。
数据库备份时间之后产生的报名、课次、账本和配置会丢失；必须由客户明确批准。

## 8. 当前明确延期

- 媒体文件卷的自动备份与异地副本：暂不纳入 v10.12.3 candidate 标准验收。
- AWS/RDS/S3/SES 正式部署：代码与历史方案保留，本轮不执行。
