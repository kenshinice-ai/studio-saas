# 2026-10-10 · Assist 知识的三处清理，和 B、C、D 的准备

> 状态：**进行中**。Lee 2026-10-10 在本仓库的会话里说「按照推荐执行」。
> 授权范围：改定价页那一句；开始准备 B、C、D，只做到分支，不发布。
> 生产是 v10.20.6（2026-10-10 实测）。本轮开始时没有任何东西发布或部署。

## 两件事，两个分支

| 分支 | 内容 | 能否单独发布 |
|---|---|---|
| `fix/assist-knowledge-cleanup` | 定价页「真数据」改「示例数据」；Assist 知识跳过计算器；修首页一处粘连 | 能。不依赖 pwe-ai-bots |
| `feat/assist-widget-form` | B 窗口脚本、C 预约表单、D 隐私政策一节 | 不能。要等 pwe-ai-bots 正式部署并通知 |

## 来源

- 上一轮：`docs/handoff/claude/2026-10-09-assist-knowledge.md`「请求方 2026-10-10 的回复」一节。
- 接口和窗口脚本：`PWE-AI-BOTs/USAGE.md` §2、§3、§3b、§5。
- 隐私文字的底稿：`PWE-AI-BOTs/docs/privacy.md`。

## 结果

（完成时回填）
