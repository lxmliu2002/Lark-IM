# Agent-Pilot · 从 IM 对话到演示稿的一键智能闭环

这是一个面向「基于 IM 的办公协同智能助手」赛题的公开版原型。项目采用无依赖静态实现，直接展示 Agent 主驾驶、GUI 辅助操作台、多端状态同步、IM/Doc/Canvas/Slides/Delivery 串联。

## 运行

直接用浏览器打开 [index.html](./index.html)。

无需安装依赖或启动服务。页面使用 `localStorage` 与 `BroadcastChannel` 保存和同步状态，因此可以打开多个浏览器窗口验证跨窗口同步。

## 已覆盖的验收点

- 多端协同：页面同时呈现桌面端与移动端，两端共享服务端快照。任一端发送指令、补充文档、排练或归档，在线端会实时更新。
- 离线支持：点击任一端电源按钮进入离线。本端操作进入本地队列，恢复在线后回放并合并。
- Agent 驱动主流程：从 IM 输入自然语言指令，Agent 进行任务理解、场景规划、文档/画布生成、演示稿生成与交付归档。
- Office 套件覆盖：IM、Doc、Canvas、Slides、Delivery 均可见，并通过同一任务状态串联。
- 自然语言交互：支持文本指令；浏览器支持 Web Speech API 时可使用语音输入，不支持时会填入一条默认指令便于演示。
- 高级 Agent 能力：指令过于模糊时，Agent 会主动澄清。

## 推荐演示脚本

1. 点击「载入评审任务」，观察 IM、Agent 场景、Doc、Canvas、Slides 和 Delivery 自动生成。
2. 在移动端切换到离线，输入「补充上线风险，第三方 API 限流时保留本地草稿」或在 Doc 中合并补充。
3. 回到桌面端确认内容未被阻塞，继续点击「排练」或「归档」。
4. 将移动端恢复在线，观察队列回放，文档与 IM 状态同步到两端。
5. 在 IM 中输入含糊指令，例如「帮我处理一下」，观察 Agent 主动澄清。

## 原型边界

当前实现是本地可演示原型，不调用真实 LLM 或飞书开放平台 API。后续工程化版本建议将 `src/app.js` 中的本地 Planner、内容生成和同步存储替换为：

- Agent Runtime：LLM Planner、工具调用、确认节点、失败恢复。
- Office Adapter：飞书 IM、云文档、多维表格、妙记或幻灯片/画布 API。
- Sync Service：账号态、权限、操作日志、CRDT/OT 合并、端到端审计。
- Client Shell：移动端可用 React Native/Flutter，桌面端可用 Electron/Tauri 或原生壳。
