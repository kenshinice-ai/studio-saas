# Let's Paint CMS — AWS Lightsail 部署方案分析


## 当前实例信息

```text
Instance name: letspaintstudio
Region: Sydney, Zone A (ap-southeast-2a)
Plan: 1 GB RAM, 2 vCPUs, 40 GB SSD
Public IPv4: 13.238.231.137
Private IPv4: 172.26.1.234
Public IPv6: 2406:da1c:16b7:f000:a06d:9b7c:6e0e:f70f
SSH username: ubuntu
Browser URL: http://13.238.231.137/
Student URL: http://13.238.231.137/register
```

> 已绑定 Lightsail Static IP：13.238.231.137。后续链接以 Static IP 为准。

## 结论

推荐使用 **AWS Lightsail + Ubuntu 24.04 LTS + 1GB RAM / 40GB SSD**。这条路线比 Render/Railway 更贴合当前 CMS 的文件型数据结构，因为 CMS 目前依赖：

- `database.json`
- `photos/`
- `portfolio/`
- `backups/`
- `.api_secret`
- `.cms_password`
- `.cms_config.json`

这些数据必须长期稳定保存在服务器磁盘上，不能放进 GitHub，也不能随着代码更新被覆盖。

## 为什么不要选截图里的 OpenClaw / Apps + OS

截图里当前选中了 OpenClaw。这个不适合本 CMS。原因：

1. OpenClaw 是额外应用栈，会带来不需要的服务和安全面。
2. CMS 已经有自己的 Python/Flask/Waitress/Nginx 运行方式。
3. 最干净、最稳定的方式是选择 **Operating System (OS) only → Ubuntu 24.04 LTS**。

## 服务器架构

```text
浏览器 / iPad PWA
        ↓
Lightsail 公网 IP 或未来域名
        ↓
Nginx :80/:443
        ↓
Waitress / Flask :8000，仅监听本机反代访问
        ↓
/opt/letspaint-cms/server.py
        ↓
/opt/letspaint-cms/data/
  ├── database.json
  ├── photos/
  ├── portfolio/
  ├── backups/
  ├── .api_secret
  ├── .cms_password
  └── .cms_config.json
```

## 本次为了 AWS 已做的代码调整

1. 新增 `CMS_DATA_DIR` 支持。
   - Mac/iCloud 本地运行：默认仍使用程序目录，行为不变。
   - AWS 运行：设置 `CMS_DATA_DIR=/opt/letspaint-cms/data`，数据和代码分离。
2. 私密文件权限自动设为 `600`。
3. `cms.sh check` 支持 AWS 数据目录。
4. `cms.sh` 支持 Linux 获取内网 IP。
5. 新增 systemd 服务文件。
6. 新增 Nginx 反向代理配置。
7. 新增 Lightsail 一键安装、升级、本地备份脚本。
8. `.gitignore` 明确排除所有真实数据和密钥。

## 安全重点

### 必须做

1. GitHub 仓库建议先用 Private。
2. 不上传：
   - `database.json`
   - `photos/`
   - `portfolio/`
   - `backups/`
   - `.api_secret`
   - `.cms_password`
   - `.cms_config.json`
3. Lightsail 防火墙不要开放 8000 端口。
4. 第一次登录后修改默认密码 `0801`。
5. AWS 账号开启 MFA。
6. Lightsail 开启自动快照，至少每天或每周。
7. 后期如果买域名，配置 HTTPS 后再把 `COOKIE_SECURE=1`。

### 主要风险

1. **服务器公网长期暴露**：比本机局域网模式风险更高。
2. **弱密码风险**：必须改默认密码，建议 12 位以上。
3. **备份只在同一块磁盘**：服务器磁盘坏了会一起丢；建议 Lightsail 快照或 S3 异地备份。
4. **没有域名时只能 HTTP**：公网 IP 直接访问不是 HTTPS，不适合长期传输敏感数据；短期测试可接受，长期建议域名 + HTTPS 或 Cloudflare Tunnel/Access。
5. **JSON 文件数据库并发能力有限**：单管理员、低流量没问题；如果未来多人同时管理或数据量很大，应迁移 SQLite/PostgreSQL。

## 推荐上线节奏

### 阶段 1：云端测试，不迁移正式数据

1. 创建 Lightsail Ubuntu。
2. 安装 AWS-ready 包。
3. 用空数据库测试登录、注册、上传、余额查询、邮件设置。
4. 确认稳定。

### 阶段 2：迁移正式数据

1. 在 Mac 上暂停本地 CMS。
2. 上传 `database.json/photos/portfolio/backups`。
3. 云端启动。
4. 做一次 `./cms.sh check`。
5. 登录后台检查学员、余额、作品集。

### 阶段 3：稳定运行

1. 开启 Lightsail 自动快照。
2. 每天本地 tar 备份。
3. 每周邮件继续运行。
4. 后期决定是否加域名 + HTTPS。

## 推荐费用

- 首选：1GB RAM / 40GB SSD / 约 $7 USD/month。
- 如果图片明显增加，后期再升 2GB RAM / 60GB SSD。
