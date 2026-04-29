# 架构说明

## 产品原则

Agent-Pilot 将 AI Agent 放在主驾驶位置：用户从 IM 通过文本或语音表达目标，Agent 负责理解、拆解、调用办公工具并推进交付。GUI 只承担状态仪表盘、必要确认、人工精修和异常恢复。

## 场景模块

| 场景 | 模块 | 当前原型 | 工程化实现 |
| --- | --- | --- | --- |
| A | 意图/指令入口 | IM 面板、文本输入、语音入口 | 飞书 IM Bot、移动端语音、上下文引用 |
| B | 任务理解与规划 | 本地规则 Planner | LLM Planner、工具选择、澄清问题 |
| C | 文档/白板生成与编辑 | Doc blocks、Canvas cards | 云文档 API、自由画布/白板 API、富媒体插入 |
| D | 演示稿生成与排练 | Slides cards、rehearsal notes | PPT/幻灯片 API、讲稿、计时排练 |
| E | 多端协作与一致性 | localStorage、BroadcastChannel、离线队列 | Sync Service、操作日志、CRDT/OT、权限 |
| F | 总结与交付 | 分享链接、归档清单 | Drive/知识库归档、导出、审计记录 |

## 数据流

1. 用户在任一端 IM 输入指令。
2. 客户端生成 `USER_MESSAGE` 操作。
3. 在线端写入服务端快照并广播；离线端写入本地队列。
4. Planner 解析意图，决定需要执行的场景组合。
5. Agent 按场景写入 `AGENT_STEP` 操作，更新文档、画布、演示稿和交付信息。
6. 离线端恢复在线后按时间顺序回放队列，正文补充以增量块合并，避免覆盖。

## 冲突策略

- IM 消息：追加合并。
- 文档补充：追加为独立内容块，保留端来源与时间。
- 画布补充：追加卡片，避免抢占已有布局。
- 任务状态：按最新 Agent 步骤推进，完成态优先。
- 交付归档：保留已有链接，缺失时补齐。

## 后续落地切分

- `Agent Runtime`：Planner、Memory、Tool Registry、Executor、Guardrails。
- `Office Tool Adapter`：IM、Doc、Canvas、Slides、Drive 的统一工具接口。
- `Sync Store`：操作日志、快照、端状态、离线队列、冲突解决。
- `Client Runtime`：移动端、桌面端、公用状态层、语音与通知能力。
