# Let's Paint CMS — AWS Lightsail 快速部署

## 0. 在你截图这个页面怎么选

你现在停在 Lightsail 的「Pick your instance image」。建议：

1. Platform: 选择 **Linux/Unix**。
2. Blueprint: 不要选 OpenClaw，也不要选 WordPress/LAMP/Node/Django。
3. 切到 **Operating System (OS) only**。
4. 选择 **Ubuntu 24.04 LTS**。
5. Instance plan: 建议 **1GB RAM / 40GB SSD / $7 USD/month**。
   - 0.5GB 也能跑，但 Python + Nginx + 图片上传 + 长期运行会偏紧。
6. Region: 已创建在 **Sydney, Zone A (ap-southeast-2a)**。
7. 启动后在 Networking 里只开放：
   - 22/TCP: SSH，仅你的 IP 更好
   - 80/TCP: HTTP
   - 443/TCP: HTTPS，未来配置域名/证书时再用
   - 不建议开放 8000/TCP 给公网

> AWS Lightsail 是固定套餐计费，AWS 官方价格页显示 Linux 公网 IPv4 方案有 $5/月、$7/月、$12/月等档位，$7/月档包含 1GB RAM、40GB SSD、2TB transfer。

---

## 0.1 强烈建议：先创建并绑定 Static IP

你已经绑定 Static IP：`13.238.231.137`。以后部署、访问、PWA 主屏幕、家长/学员链接都应使用这个 Static IP。

旧的临时公网 IP 不再使用。只要这个 Static IP 保持 attached 到 `letspaintstudio`，实例 reboot/stop/start 后链接也不会变。

## 1. 上传发布包到服务器

你的 Lightsail 实例信息：

```text
Instance: letspaintstudio
Region: Sydney, Zone A (ap-southeast-2a)
Public IPv4: 13.238.231.137
Private IPv4: 172.26.1.234
Public IPv6: 2406:da1c:16b7:f000:a06d:9b7c:6e0e:f70f
Username: ubuntu
```

```bash
scp LetsPaintCMS-v4.3.3-aws-13.238.231.137-release.zip ubuntu@13.238.231.137:/home/ubuntu/
```

登录服务器：

```bash
ssh ubuntu@13.238.231.137
```

解压：

```bash
unzip LetsPaintCMS-v4.3.3-aws-13.238.231.137-release.zip -d letspaint-cms-release
cd letspaint-cms-release
```

---

## 2. 一键安装

```bash
sudo bash deploy/aws/install_lightsail.sh
```

安装完成后检查：

```bash
curl http://127.0.0.1:8000/api/ping
sudo systemctl status letspaint-cms
```

浏览器打开：

```text
http://13.238.231.137/
```

默认密码仍是 `0801`，第一次登录后建议立刻修改。

---

## 3. 从 Mac/iCloud 迁移现有数据

在 Mac 上进入当前 CMS 目录后执行：

```bash
scp database.json ubuntu@13.238.231.137:/home/ubuntu/
scp -r photos portfolio backups ubuntu@13.238.231.137:/home/ubuntu/
```

在服务器上执行：

```bash
sudo systemctl stop letspaint-cms
sudo cp /home/ubuntu/database.json /opt/letspaint-cms/data/database.json
sudo rsync -a /home/ubuntu/photos/ /opt/letspaint-cms/data/photos/
sudo rsync -a /home/ubuntu/portfolio/ /opt/letspaint-cms/data/portfolio/
sudo rsync -a /home/ubuntu/backups/ /opt/letspaint-cms/data/backups/
sudo chown -R ubuntu:ubuntu /opt/letspaint-cms/data
sudo chmod 700 /opt/letspaint-cms/data
sudo chmod 600 /opt/letspaint-cms/data/database.json
sudo systemctl start letspaint-cms
curl http://127.0.0.1:8000/api/ping
```

然后登录后台做一次：

```bash
cd /opt/letspaint-cms
CMS_DATA_DIR=/opt/letspaint-cms/data LPCMS_VENV=/opt/letspaint-cms/.venv ./cms.sh check
```

---

## 4. 日常命令

```bash
# 看服务状态
sudo systemctl status letspaint-cms

# 看实时日志
sudo journalctl -u letspaint-cms -f

# 重启
sudo systemctl restart letspaint-cms

# CMS 自检
cd /opt/letspaint-cms
CMS_DATA_DIR=/opt/letspaint-cms/data LPCMS_VENV=/opt/letspaint-cms/.venv ./cms.sh check

# 服务器本地备份
sudo /opt/letspaint-cms/deploy/aws/backup_data.sh
```

---

## 5. 以后升级

上传新 zip，解压后：

```bash
cd 新解压目录
sudo bash deploy/aws/update_lightsail.sh
```

升级脚本不会覆盖：

```text
/opt/letspaint-cms/data/database.json
/opt/letspaint-cms/data/photos/
/opt/letspaint-cms/data/portfolio/
/opt/letspaint-cms/data/backups/
/opt/letspaint-cms/data/.api_secret
/opt/letspaint-cms/data/.cms_password
/opt/letspaint-cms/data/.cms_config.json
```
