# Static IP 更新说明

已将 Lightsail 访问地址从旧公网 IP 更新为 Static IP。

```text
Old public IPv4: 3.107.210.44
Static IPv4: 13.238.231.137
Private IPv4: 172.26.1.234
Public IPv6: 2406:da1c:16b7:f000:a06d:9b7c:6e0e:f70f
Instance: letspaintstudio
Username: ubuntu
```

## 新访问地址

```text
管理后台: http://13.238.231.137/
学员入口: http://13.238.231.137/<tenant_slug>/register
```

StudioSaaS 重构后，根目录是 Super Admin；每个租户都有自己的注册页。

## 如果之前已经用旧 IP 安装过

只需要更新 Nginx 配置并 reload：

```bash
sudo sed -i 's/3.107.210.44/13.238.231.137/g' /etc/nginx/sites-available/letspaint-cms
sudo nginx -t
sudo systemctl reload nginx
```

然后浏览器访问：

```text
http://13.238.231.137/
```

## 如果还没有安装

直接使用新的发布包：

```bash
scp LetsPaintCMS-v4.3.3-aws-13.238.231.137-release.zip ubuntu@13.238.231.137:/home/ubuntu/
ssh ubuntu@13.238.231.137
unzip LetsPaintCMS-v4.3.3-aws-13.238.231.137-release.zip -d letspaint-cms-release
cd letspaint-cms-release
sudo bash deploy/aws/install_lightsail.sh
```
