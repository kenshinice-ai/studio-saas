# PWE Studio v9.9.4 — 三处修正：会变的表头、炸掉的按钮、借来的房子

> 当前阶段：**已部署上线并重种**。生产 `appVersion=9.9.4`。

## 发布证据（2026-08-13）

| 层级 | 已验证事实 |
|---|---|
| Source | `origin/main` = `9.9.4` 提交；`verify_local.sh` **All checks passed**；`1801 passed, 5 skipped`。 |
| Production | deep health `appVersion=9.9.4`、`db=ok`、`tenants=6`、`workspaces.stale=0`；部署前备份 `…20260813T061647Z.dump`。 |
| **重置按钮（线上实测）** | 真实租户 `lets-paint-studio` → **400 拒绝**；错误短语 → **400**；正确 → **200，7.2 秒**，15 件主理人作品 / 8 件学员作品（7 件公开）/ 12 名学员 / 6 张空间照。 |
| 文案 | 线上已是「一间朝南的后院画室 / A garden studio facing south」、三条亮点新文案、Caulfield North。 |

## 一 · 「有时对有时不对」是语言差

同一个页面，有时正常、有时店名旁边一排被截断的标签。真因不是随机：

| 语言 | 导航需要 | 隐藏店名后可用 | 结果 |
|---|---|---|---|
| 中文 | 726px | 878px | 只隐藏店名，导航全显示 |
| 英文 | 926px | 878px | 收进菜单 |

**两种语言的正确答案本来就不同**，而语言是首屏之后由客户端切换的。
v9.9.3 只测量一次，哪次先跑就定死哪个——这就是那个「有时」。

除了语言，还有两件事会在首屏之后改变答案：网页字体到达（每个标签宽度都变）、
契约把占位标签换成店主自己的文字。所以现在改为**有界结算**：
`fonts.ready`、`load`，外加 120 / 400 / 1200ms 三次补测。

**故意不用 ResizeObserver**：这个函数会改变它自己测量的布局，
观察自己的输出在慢机器上就是个循环。固定、有界、可预测的时间表更安全。

实测：1440px 下六次采样全部一致，零溢出零截断；
中文全导航 + 隐藏店名，英文折叠 —— 和你两张截图各自的正确形态都对上了。

## 二 · 重置按钮 500

生产日志里的堆栈很直接：

```
File "/app/backend/scripts/reset_professional_demo.py", line 939, in reset_showcase
    import server
AssertionError: The setup method 'register_error_handler' can no longer be
called on the blueprint 'studiosaas_api_v1'.
```

`reset_showcase()` 需要一个 Flask 应用上下文（`store_media_asset` 从
`current_app.config` 读媒体根目录），命令行下靠 `import server` 自己造一个。
但从接口调用时**进程里已经有应用了**，再 import 一次等于在活着的进程里
重新执行 server.py，把已挂载的蓝图又注册一遍。

改成先问 `has_app_context()`：有就复用，没有才造。
两条路径都实测过：接口 200（1.9 秒），命令行照常。

**这个 500 在本地复现不出来**——本地测试脚本自己就没有上下文，走的是命令行那条路。
只有从 Platform Admin 真的按一次才会炸。

## 三 · 房子是借来的

「1960 年代旧车间、五米层高、南墙一整排窗」是照 Brunswick 仓库区写的。
Caulfield North 是梧桐和砖房。改成：

> 画室在一栋 1920 年代砖房的后院，原本是马厩改的车库，屋顶掀高了，
> 南墙换成一整面玻璃。门口有两棵梧桐，风大的时候能听见。

主理人故事同步改（「邻居敲门问能不能一起」），三条亮点的语气也提了一档：
「八张画架，不多放」→「八张画架，不加第九张」；
「画完了可以放着」→「没干的画留下来……走的时候不必迁就一张还没想好的画」。
朝南没动——南半球画室要的就是南边那道恒定的冷光。

## 四 · 状态

- 本地全量 **1801 passed, 5 skipped**；`test_showcase_tenant.py` 增至 38 条。
- 尚未打包部署。上线后要重跑一次重置，文案才会生效（地址在数据库里，不在代码里）。

---

