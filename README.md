# Lark-IM Agent Pilot

飞书 AI 产品创新赛道原型项目，目标是把原来的“单次 IM 转 PPT”原型升级为一个真正的 Agent-Pilot 系统。

## 当前主流程

```text
IM / 飞书入口
-> 自然语言指令
-> Agent Harness
-> 任务拆解 / 规划
-> PPT / 文档生成
-> 多端状态同步
-> 报告或 Slide 交付
```

核心理念：

- AI Agent 是主驾驶
- GUI 是仪表盘与同步状态板
- 文档、演示稿、多端协作都由统一任务状态驱动

## 这次重构后的结构

```text
pilot_app/
  __init__.py
  content.py        # 内容简报、报告、清单生成
  harness.py        # Agent Harness 主编排器
  llm.py            # LLM JSON 输出封装
  models.py         # 统一数据模型
  planner.py        # 任务规划器
  server.py         # FastAPI 应用
  skills.py         # Lark skills 执行层抽象
  store.py          # 多端共享状态存储

main.py             # 入口，直接暴露 FastAPI app
html_slides.py      # HTML Slide 渲染
ppt_tool.py         # 浏览器截图并导出 pptx
web_ui.html         # Agent 仪表盘
```

## 已实现能力

- 从 IM / 飞书风格输入创建一个 Agent 任务
- 用 Agent Planner 生成六阶段执行计划
- 生成文档草稿、HTML Slide 和 `.pptx`
- 维护统一的任务状态、步骤状态、事件流和设备状态
- 支持桌面端 / 移动端设备签到，演示多端一致性
- 输出交付清单 `manifest.json`
- 预留 `lark-im`、`lark-doc`、`lark-slides`、`lark-drive`、`lark-event`、`lark-whiteboard`、`lark-wiki` 的 skills 层
- 已接入官方 `lark-cli`，并支持将报告同步为真实飞书 Doc（运行环境允许联网时）

## 与 larksuite/cli 的关系

本项目参考了 `larksuite/cli` 的 skill 体系来设计执行层，尤其适合接入：

- `lark-im`
- `lark-doc`
- `lark-slides`
- `lark-drive`
- `lark-event`
- `lark-whiteboard`
- `lark-wiki`

参考仓库：

- https://github.com/larksuite/cli
- https://github.com/larksuite/cli/tree/main/.github/workflows

当前代码里已经把这些能力抽象成 `pilot_app/skills.py`，默认是 `simulated` 模式，后续可以替换成真实 CLI 或 API 调用。

## 当前飞书接入状态

目前已经完成：

- `lark-cli` 官方二进制接入
- `config init --new` 应用配置
- `auth login` 用户授权
- 项目内 `lark-cli` 状态探测接口：`/api/lark/status`
- 项目内在线查询测试接口：`/api/lark/search-users`
- 任务执行时自动尝试将报告同步为飞书 Doc

当前仍受飞书应用 scope 限制的部分：

- `drive:file:upload`
- `slides:presentation:create`

如果你要继续打通飞书 Drive / Slides，需要先在飞书开放平台里为这个 CLI 应用启用对应 scope。

## 运行方式

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

启动：

```powershell
python -m uvicorn main:app --reload
```

打开：

```text
http://127.0.0.1:8000/
```

独立移动端演示页：

```text
http://127.0.0.1:8000/mobile
```

## 环境变量

复制：

```powershell
Copy-Item .env.example .env
```

常用变量：

- `ARK_API_KEY`
- `ARK_MODEL_ID`
- `ARK_BASE_URL`
- `HTML_RENDER_BROWSER`
- `LARK_SKILL_EXECUTION_MODE`

说明：

- 如果没有配置 LLM，系统会走本地 fallback 逻辑
- 如果没有安装 `lark-cli`，skills 会以模拟模式展示

## 演示建议

推荐按下面顺序演示：

1. 在 IM / 飞书入口输入自然语言指令
2. 启动 Agent 任务，展示 Harness 自动分步执行
3. 让桌面端和移动端分别签到，展示状态同步
4. 打开文档草稿、HTML Slide 预览和 `.pptx`
5. 展示最终 manifest 清单，强调完整交付链路

补充说明：

- `/` 是桌面主控页
- `/mobile` 是独立移动端跟进页
- 桌面页里可以直接打开带 `job_id` 的移动端链接，适合双窗口答辩演示
