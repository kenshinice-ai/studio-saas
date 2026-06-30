# Lightsail 实例信息 — letspaintstudio

```text
Instance name: letspaintstudio
Plan: 1 GB RAM, 2 vCPUs, 40 GB SSD
OS: Ubuntu
AWS Region: Sydney, Zone A (ap-southeast-2a)
Public IPv4: 13.238.231.137
Private IPv4: 172.26.1.234
Public IPv6: 2406:da1c:16b7:f000:a06d:9b7c:6e0e:f70f
Username: ubuntu
Admin URL: http://13.238.231.137/
Student URL: http://13.238.231.137/<tenant_slug>/register
```

StudioSaaS 重构后，根目录是 Super Admin；学员入口使用租户路径。

## 下一步建议

1. Static IP 已绑定：13.238.231.137。
2. Networking 防火墙只开放 22、80、443；不要开放 8000。
3. 使用浏览器 SSH 或本地 SSH 登录。
4. 上传 `LetsPaintCMS-v4.3.3-aws-13.238.231.137-release.zip`。
5. 执行 `sudo bash deploy/aws/install_lightsail.sh`。
6. 安装后立刻修改默认后台密码。

## 本地 SSH 示例

如果你下载了 Sydney 区域默认 key：

```bash
chmod 600 ~/Downloads/LightsailDefaultKey-ap-southeast-2.pem
ssh -i ~/Downloads/LightsailDefaultKey-ap-southeast-2.pem ubuntu@13.238.231.137
```

如果使用 Lightsail 页面里的 “Connect using SSH”，不需要本地 key。
