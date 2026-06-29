Let's Paint CMS v4.3.3-aws-13.238.231.137 发布包

包含：程序文件、PWA 文件、logo/icon、测试脚本和教程。
不包含：database.json、photos/、portfolio/、backups/、.api_secret、.cms_password、.cms_config.json。AWS 推荐把这些放在 CMS_DATA_DIR=/opt/letspaint-cms/data。

部署：
1. 先备份线上 CMS 目录。
2. 解压本 zip 到 CMS 目录，覆盖同名程序文件。
3. 运行 ./cms.sh restart
4. 运行 ./cms.sh check
