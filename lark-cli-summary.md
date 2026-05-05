# Lark/Feishu 官方 CLI 能力总结

基于官方仓库 `larksuite/cli` 主分支公开 README 与仓库结构整理，整理时间为 `2026-05-04`。

仓库地址：

- https://github.com/larksuite/cli
- README（英文）：https://github.com/larksuite/cli/blob/main/README.md
- README（中文）：https://github.com/larksuite/cli/blob/main/README.zh.md

## 一句话结论

`lark-cli` 是飞书官方维护的命令行工具，定位不是单一 API 封装，而是一个同时面向人类用户和 AI Agent 的操作层。它把飞书开放平台的常见办公域封装成了：

- 快捷命令（Shortcuts）
- 平台 API 命令（API Commands）
- 原始 OpenAPI 调用（Raw API Calls）
- 配套的 AI Agent Skills

按当前 README，官方重点强调的是：

- `17` 个业务域
- `200+` 条精选命令
- `24` 个 AI Agent Skills
- 底层可直达 `2500+` OpenAPI

## 官方 CLI 覆盖了哪些功能

### 1. Calendar 日历

支持：

- 查看 agenda
- 创建日程
- 邀请参会人
- 查询 free/busy
- 给出时间建议

适合场景：

- 帮用户排会
- 根据多人空闲时间推荐会议时间
- 从任务流直接生成会议邀请

### 2. Messenger 即时消息

支持：

- 发送消息
- 回复消息
- 创建和管理群聊
- 查看聊天记录与 thread
- 搜索消息
- 下载媒体文件

适合场景：

- 用机器人把任务结果发回飞书群
- 从聊天记录抽取上下文
- 做 IM 驱动的 Agent 入口

### 3. Docs 文档

支持：

- 创建文档
- 读取文档
- 更新文档
- 搜索文档
- 读写媒体与白板相关内容

适合场景：

- 把 IM 讨论沉淀成正式文档
- 自动生成周报、方案、纪要
- 用 Markdown 驱动文档生成

### 4. Drive 云盘

支持：

- 上传文件
- 下载文件
- 搜索文档与 Wiki
- 管理评论
- 管理部分共享交付动作

适合场景：

- 上传报告、PPT、附件
- 给交付物做归档和分享

### 5. Markdown

当前 README 明确写到新增了 Markdown 域，支持：

- 创建 Drive 原生 `.md` 文件
- 获取 Markdown 文件
- 覆盖写入 Markdown 文件

这说明官方已经开始把“文档操作”进一步拆成更适合代码和 Agent 自动化的文本工作流。

### 6. Base 多维表格

支持：

- 表、字段、记录、视图管理
- dashboard
- workflow
- forms
- roles & permissions
- 数据聚合与分析

适合场景：

- Agent 自动写入业务台账
- 自动化维护项目表
- 从聊天/文档同步结构化数据到 Base

### 7. Sheets 表格

支持：

- 创建表格
- 读取数据
- 写入数据
- 追加数据
- 查找数据
- 导出数据

适合场景：

- 导出报表
- 补齐看板数据
- 做轻量级运营分析

### 8. Slides 演示文稿

支持：

- 创建演示文稿
- 管理演示文稿
- 读取演示内容
- 增删页面

适合场景：

- 根据文档自动生成 Slides
- 对既有 Slides 做程序化更新

### 9. Tasks 任务

支持：

- 创建任务
- 查询任务
- 更新任务
- 完成任务
- 管理任务列表、子任务、评论、提醒

适合场景：

- 把聊天里的 action items 自动落成任务
- 让 Agent 不只产出内容，还能推动执行

### 10. Wiki 知识库

支持：

- 创建知识空间
- 管理节点
- 管理知识文档

适合场景：

- 把沉淀内容写入团队知识库
- 给 Agent 提供知识检索入口

### 11. Contact 通讯录

支持：

- 按姓名、邮箱、手机号搜索用户
- 获取用户资料

适合场景：

- 自动补全负责人
- 给任务流做组织架构映射

### 12. Mail 邮箱

支持：

- 浏览邮件
- 搜索邮件
- 阅读邮件
- 发送邮件
- 回复邮件
- 转发邮件
- 管理草稿
- 监听新邮件

适合场景：

- 邮件摘要
- 自动跟进
- 把邮件纳入统一办公 Agent

### 13. Meetings / VC 会议

支持：

- 搜索会议记录
- 查询会议纪要
- 查询录音录像

README 里的 Skill 描述还特别提到可以拿到：

- summary
- todos
- transcript

适合场景：

- 会后纪要自动整理
- 从会议内容反推任务

### 14. Attendance 考勤

支持：

- 查询个人打卡记录

### 15. Approval 审批

支持：

- 查询审批任务
- 审批通过
- 审批拒绝
- 转交审批
- 取消实例
- 抄送实例

这说明 CLI 已经覆盖到有明显副作用的业务动作，不只是“读数据”。

### 16. OKR

支持：

- 查询 OKR
- 创建 OKR
- 更新 OKR
- 管理目标、关键结果、对齐关系、指标、进展

### 17. Project / Meegle

README 当前写法是：

- Project 能力由独立的 `meegle-cli` 提供
- 需要单独安装

所以它不是 `lark-cli` 内置的一部分，但官方已经把它放进整体工作流版图里。

## AI Agent 相关能力

这是 `lark-cli` 和一般 SDK / CLI 最大的区别。

官方明确把它定义为 “built for humans and AI Agents”，当前 README 列出的 Agent Skills 包括：

- `lark-shared`
- `lark-calendar`
- `lark-im`
- `lark-doc`
- `lark-drive`
- `lark-markdown`
- `lark-sheets`
- `lark-slides`
- `lark-base`
- `lark-task`
- `lark-mail`
- `lark-contact`
- `lark-wiki`
- `lark-event`
- `lark-vc`
- `lark-whiteboard`
- `lark-minutes`
- `lark-openapi-explorer`
- `lark-skill-maker`
- `lark-attendance`
- `lark-approval`
- `lark-workflow-meeting-summary`
- `lark-workflow-standup-report`
- `lark-okr`

其中几个特别值得关注：

- `lark-event`：支持实时事件订阅、WebSocket、正则路由和适合 Agent 消费的事件格式
- `lark-openapi-explorer`：帮助 Agent 探索底层官方 API
- `lark-skill-maker`：支持自定义 skill 开发
- `lark-workflow-*`：说明官方不仅支持“单命令调用”，也在支持流程型办公自动化

## 命令体系怎么分层

官方 README 强调了三层命令模型。

### 1. Shortcuts

特点：

- 命令短
- 参数更少
- 对人和 Agent 都更友好
- 有智能默认值
- 支持表格输出
- 支持 `--dry-run`

示例：

```bash
lark-cli calendar +agenda
lark-cli im +messages-send --chat-id "oc_xxx" --text "Hello"
lark-cli docs +create --api-version v2 --doc-format markdown --content $'<title>Weekly Report</title>\n# Progress\n- Completed feature X'
```

适合：

- 高频办公动作
- Agent 直接调用
- 原型和 workflow 编排

### 2. API Commands

特点：

- 从飞书 OAPI 元数据自动生成
- 和平台端点较为一一对应
- README 说有 `100+` 条精选命令

示例：

```bash
lark-cli calendar calendars list
lark-cli calendar events instance_view --params '{"calendar_id":"primary","start_time":"1700000000","end_time":"1700086400"}'
```

适合：

- 需要更细颗粒度控制
- Shortcuts 不够用，但又不想手写原始 HTTP 请求

### 3. Raw API Calls

特点：

- 直接打任意 Open Platform API
- 官方写的是覆盖 `2500+` API

示例：

```bash
lark-cli api GET /open-apis/calendar/v4/calendars
lark-cli api POST /open-apis/im/v1/messages --params '{"receive_id_type":"chat_id"}' --data '{"receive_id":"oc_xxx","msg_type":"text","content":"{\"text\":\"Hello\"}"}'
```

适合：

- 官方快捷命令还没覆盖的接口
- 做底层调试
- 快速验证 OpenAPI 行为

## 认证与身份能力

官方 README 列出的认证命令包括：

- `auth login`
- `auth logout`
- `auth status`
- `auth check`
- `auth scopes`
- `auth list`

从官方说明看，它支持：

- OAuth 登录
- 按 domain 申请权限
- 按 scope 精确申请权限
- 推荐权限组合 `--recommend`
- `--no-wait` 的 Agent 异步登录模式
- 使用 `--device-code` 恢复登录轮询
- `--as user` / `--as bot` 身份切换执行

这个点很关键，因为它意味着同一套 CLI 不只是“机器人身份调用”，也支持带用户身份的授权操作。

## 对 Agent 和自动化特别友好的点

官方 README 里反复强调下面这些设计：

- 结构化输出
- 智能默认值
- 面向真实 Agent 测试过的参数设计
- 多种输出格式：`json`、`pretty`、`table`、`ndjson`、`csv`
- 分页控制：`--page-all`、`--page-limit`、`--page-delay`
- `--dry-run` 风险预演
- `schema` 命令可查参数、请求体、响应结构、支持身份、所需 scope

对工程接入来说，最有价值的是下面三点：

1. 既能给人手动用，也能让 Agent 稳定调用。
2. 不只支持业务动作，还支持 schema 探查和权限检查。
3. 当高级封装不够时，可以降级到 API Commands 或 Raw API。

## 安全与风险控制

官方 README 明确提醒了 AI Agent 调用飞书能力的风险，包括：

- 模型幻觉
- 不可预测执行
- prompt injection
- 敏感数据泄露
- 未授权操作

官方特别强调的安全设计包括：

- 输入注入防护
- 终端输出脱敏/清洗
- OS 原生 keychain 凭证存储

同时也建议：

- 不要随意放宽默认安全限制
- 不要把拥有权限的 bot 随便加进群聊
