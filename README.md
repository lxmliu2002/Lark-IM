# Lark-IM Agent Pilot

面向“基于 IM 的办公协同智能助手”赛题的参赛原型。项目围绕比赛 PDF 中的核心要求实现：以 **AI Agent 为主驾驶**，以 **GUI 为仪表盘与辅助操作台**，完成从 **IM 对话入口 -> 任务理解与规划 -> 文档/演示材料生成 -> 总结与交付** 的闭环。

本项目当前重点对齐比赛中的必完成项，尤其是：

- 多端协同框架
- Agent 驱动的模块化场景与可组合编排
- 覆盖 `IM + Doc + PPT`
- 自然语言驱动任务启动与执行

## 赛题对齐

比赛 PDF 的核心要求可以归纳为三点：

1. Agent 是主驾驶，GUI 不是传统表单工具，而是任务主控台。
2. 必须覆盖 `IM、文档、演示文稿/自由画布` 三类办公组件。
3. 必须支持多端协同，且至少演示一次多场景组合编排。

本项目对应关系如下：

- `场景 A：意图/指令入口`
  - 支持从飞书群聊/单聊检索会话
  - 支持选择并勾选聊天消息作为任务上下文
  - 支持自然语言指令和用户补充内容
- `场景 B：任务理解与规划`
  - 后端 `Agent Planner` 基于自然语言指令自动识别意图
  - 自动拆分为子任务、步骤和验收标准
- `场景 C：文档生成与编辑`
  - 生成结构化文档内容、报告草稿
  - 可尝试同步为真实飞书 Doc
- `场景 D：演示稿生成`
  - 生成 HTML Slide
  - 在环境允许时导出 `.pptx`
- `场景 E：多端协作与一致性`
  - 单一响应式 Web 同时适配桌面端和移动端
  - 状态、事件流、产物和验收信息统一落到 MySQL
- `场景 F：总结与交付`
  - 输出报告、Slide、清单等交付物
  - 前端支持打开和下载产物

## 当前产品形态

当前实现不是“固定流程表单”，而是一个 **任务主控台**：

- 左侧负责输入自然语言任务与上下文
- 右侧负责飞书会话搜索、选择与消息勾选
- 下方主控区负责查看计划、事件、验收和交付物
- 页面可在桌面端和手机浏览器中共用，手机端自动切换为单列布局

这和比赛 PDF 中“AI Agent 为主，GUI 为辅”的要求是一致的：
用户不手动选择场景链路，而是由后端 Agent 根据自然语言指令自动判断需要走哪些模块。

## 已实现能力

### 1. IM 入口与上下文接入

- 接入官方 `lark-cli`
- 支持搜索飞书群聊和单聊
- 支持选择多个飞书会话源
- 支持读取会话消息并以复选框方式勾选
- 支持将勾选消息与用户补充内容一起提交给 Agent

### 2. Agent 驱动的任务规划

- 用户只输入自然语言任务，不需要手动勾选场景
- 后端自动推断执行链路
- 自动生成：
  - 任务步骤
  - 任务事件
  - 验收标准
  - 交付产物

### 2.1 任务对话自然语言控制

- 当前任务主控中新增 `任务对话` 模块
- 用户可以围绕当前任务继续输入自然语言，而不只是依赖按钮
- 第一版支持：
  - 查询进度
  - 查询当前产物
  - 查询或确认验收
  - 追加任务补充要求
  - 要求重跑文档 / PPT / 交付
  - 总结当前任务结果或解释最近一次 repair

### 3. 文档 / 演示材料交付

- 生成 Markdown 报告
- 生成 HTML Slide
- 在浏览器环境满足时导出 `.pptx`
- 支持将报告同步为飞书 Doc
- 支持展示产物路径、在线打开和下载
- 支持“下载全部（zip）”

### 4. 多端协同与任务恢复

- `/` 为唯一主页面，桌面和手机共用同一套前端
- 页面刷新后可自动恢复最近运行中任务
- MySQL 持久化任务状态，避免刷新丢失上下文
- 主控台支持通过事件总览切换查看不同任务

### 5. 事件流与验收

- 展示当前任务事件流
- 聚合展示最近/运行中/已完成任务摘要
- 验收标准支持状态更新与确认
- 交付阶段会输出报告、文档、Slides 等结果

## 技术结构

```text
pilot_app/
  __init__.py
  content.py        # 内容简报、报告、清单生成
  harness.py        # Agent 主编排器
  llm.py            # LLM JSON 输出封装
  models.py         # 数据模型
  planner.py        # 任务理解与规划
  server.py         # FastAPI 接口
  skills.py         # 飞书能力封装层
  store.py          # MySQL 持久化与事件读取

main.py             # FastAPI 入口
html_slides.py      # HTML Slide 渲染
ppt_tool.py         # 浏览器渲染并导出 pptx
web_ui.html         # 单一响应式主页面
```

## 后端与接口

核心接口：

- `GET /`
  - 主页面，桌面和移动共用
- `GET /mobile`
  - 重定向到 `/`
- `GET /api/lark/status`
  - 飞书 CLI 状态
- `GET /api/lark/session-sources?q=...`
  - 搜索飞书群聊/单聊
- `POST /api/lark/session-sources/preview`
  - 读取指定会话的聊天内容
- `POST /api/jobs`
  - 创建 Agent 任务
- `GET /api/jobs`
  - 获取任务列表
- `GET /api/jobs/{job_id}`
  - 获取任务详情
- `POST /api/jobs/{job_id}/conversation`
  - 针对当前任务发送自然语言控制或查询消息
- `GET /api/events`
  - 获取任务摘要事件列表
- `GET /api/jobs/{job_id}/artifacts.zip`
  - 下载当前任务全部产物
- `POST /api/bot/webhook`
  - 预留飞书机器人入口

## 数据存储

项目现在固定使用 **MySQL**。

主要用途：

- 持久化任务状态
- 持久化步骤、事件、验收、产物信息
- 支持刷新恢复最近任务
- 支持从多个任务中聚合事件摘要

默认数据库配置见 `.env.example`：

```text
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DATABASE=lark_im
MYSQL_CHARSET=utf8mb4
```

初始化数据库：

```sql
CREATE DATABASE IF NOT EXISTS lark_im
DEFAULT CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

## 飞书接入说明

本项目优先通过官方 `lark-cli` 接入飞书能力。

当前已打通或已封装的方向：

- `IM`
- `Doc`
- `Slides`
- `Drive`
- `Event`
- `Whiteboard`
- `Wiki`

其中当前页面已经直接用到的是真实飞书会话搜索与消息读取能力。Doc / Slides / Drive 是否能真实执行，还取决于：

- 当前 `lark-cli` 是否已登录
- 当前应用是否具备对应 scope
- 当前运行环境是否满足浏览器导出条件

常见限制：

- 若未配置浏览器，PPT 导出会降级为仅生成 HTML Slide
- 若飞书权限不足，Doc 可能创建成功但授权失败
- 若本机未安装 `lark-cli`，飞书能力无法实际执行

## 环境变量

复制环境变量模板：

```bash
cp .env.example .env
```

主要变量：

- `ARK_API_KEY`
- `ARK_MODEL_ID`
- `ARK_BASE_URL`
- `HTML_RENDER_BROWSER`
- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_DATABASE`
- `MYSQL_CHARSET`
- `LARK_SKILL_EXECUTION_MODE`
- `LARK_DOC_SYNC_ENABLED`
- `LARK_SLIDES_SYNC_ENABLED`
- `LARK_DRIVE_UPLOAD_ENABLED`

说明：

- 若未配置 LLM，系统会回退到本地规划逻辑
- 若未安装或未登录 `lark-cli`，飞书链路会受限
- 若未设置 `HTML_RENDER_BROWSER`，PPT 导出可能被跳过

## 运行方式

### 1. 安装依赖与创建环境

```bash
conda create -n lark-im python=3.11 -y
conda activate lark-im
python -m pip install -r requirements.txt
```

### 2. 准备 MySQL

先在本机 MySQL 中创建数据库：

```sql
CREATE DATABASE IF NOT EXISTS lark_im
DEFAULT CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

项目启动后会自动创建所需表。

### 3. 配置环境变量

复制模板：

```bash
cp .env.example .env
```

至少需要检查这几项：

- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_DATABASE`

如果你要启用大模型规划，再补：

- `ARK_API_KEY`
- `ARK_MODEL_ID`
- `ARK_BASE_URL`

如果你要启用真实飞书能力，再补：

- 本机已安装 `lark-cli`
- 已完成 `lark-cli` 登录
- 应用具备所需 scope

如果你要导出 `.pptx`，建议配置：

- `HTML_RENDER_BROWSER`

说明：

- 不配置 LLM 也能运行，但会走本地 fallback 规划
- 不配置飞书能力也能运行，但无法真实读取飞书会话或同步飞书文档
- 不配置浏览器路径时，Slide 仍可生成 HTML，但 PPT 导出可能跳过

### 4. 启动服务

本机调试：

```bash
uvicorn main:app --reload --port 8000
```

手机联调：

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5. 打开页面

本机：

```text
http://127.0.0.1:8000/
```

同一局域网手机：

```text
http://<你的电脑局域网IP>:8000/
```

### 6. 可选：检查飞书 CLI 是否可用

在终端执行：

```bash
lark-cli --version
```

如果要确认当前登录态，可在页面底部查看“飞书状态”，也可以直接在终端执行你常用的 `lark-cli` 查询命令。

## 使用方式

页面的核心逻辑是：**先提供任务指令和上下文，再由 Agent 自动规划并执行。**

### 页面使用顺序

1. 在右侧“飞书会话选择”中搜索群聊或单聊。
2. 选择一个或多个会话源。
3. 点击“读取已选会话”，把聊天记录同步出来。
4. 在“已同步对话内容”里勾选你希望提交给 Agent 的消息。
5. 在左侧输入自然语言任务指令。
6. 如有需要，在“用户补充内容”里增加背景、约束、输出偏好。
7. 点击“启动 Agent 任务”。
8. 在下方“事件总览 / 当前任务主控”中查看执行过程、验收状态和交付产物。
9. 若任务已启动，可继续在 `任务对话` 中输入自然语言，例如：
   - `现在进展怎么样`
   - `重新生成 PPT`
   - `总结一下当前结果`
   - `确认验收`

### 推荐输入方式

自然语言指令建议尽量包含这三类信息：

- 你要完成什么任务
- 最终希望交付什么
- 有没有额外约束

例如：

```text
请根据选中的飞书群聊内容，提炼比赛需求，生成一份汇报文档和一份演示稿，并输出最终交付结果。文档中要突出比赛必完成项，演示稿控制在 6 到 8 页。
```

### 主控台怎么看

创建任务后，主控台主要看四类信息：

- `计划总览`
  - Agent 对任务的拆解步骤
- `当前任务事件流`
  - 当前任务执行过程中发生了什么
- `交付产物`
  - 报告、Slide、PPT、manifest 等结果文件
- `验收标准`
  - 当前任务的通过条件和状态

如果有多个任务：

- 可以通过上方 `事件总览` 下拉切换不同任务范围
- 点击对应任务卡片后，下面主控台会切换到那个任务

### 如何下载结果

桌面端和移动端都支持下载：

- 单个产物：
  - 在“交付产物”中点击 `打开` 或 `下载`
- 全部产物：
  - 点击 `下载全部（zip）`

常见产物包括：

- `report.md`
- `manifest.json`
- `slides/index.html`
- `.pptx`
- 飞书 Doc 链接类产物

### 如何测试移动端

如果你想用手机浏览器测试：

1. 电脑和手机连接到同一个局域网。
2. 用下面命令启动服务：

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

3. 查电脑的局域网 IP，例如：

```bash
ipconfig getifaddr en0
```

4. 在手机浏览器打开：

```text
http://<你的电脑局域网IP>:8000/
```

手机端会自动变成单列布局，不需要访问单独的移动页面。

## 推荐演示路径

为了更贴近比赛验收，推荐这样演示：

1. 在页面中搜索飞书群聊或单聊，并勾选部分聊天记录作为任务上下文。
2. 输入自然语言指令，例如“根据群聊内容生成汇报文档和演示稿，并给出交付结果”。
3. 启动任务，展示 Agent 自动完成任务理解、规划和执行，而不是人工手动编排。
4. 在桌面端和手机端分别打开同一页面，展示同一任务状态与结果同步。
5. 展示生成的报告、飞书 Doc、HTML Slide、PPT 下载与交付清单。

这样能够覆盖比赛要求中的：

- `IM 入口`
- `Agent 驱动主流程`
- `Doc + PPT`
- `多端协同`
- `总结与交付`

## 当前限制

- 当前语音入口尚未实现，第一版优先完成文本指令链路
- 文本链路已经覆盖任务启动、进度查询、内容重生成和结果总结等关键节点；语音后续只需先转写为文本即可复用同一套逻辑
- 当前“多端协同”基于响应式 Web + MySQL 持久化，不是原生 iOS/Android App
- 飞书部分能力仍受 `lark-cli` 登录态、scope 和本地环境影响
- Slides 导出依赖本机浏览器环境

## 与比赛说明文档的关系

本 README 已按仓库中的比赛 PDF《基于 IM 的办公协同智能助手（公开版）》重新整理，重点突出：

- AI Agent 为主、GUI 为辅
- IM -> Doc -> PPT 的核心闭环
- 多端协同与统一任务状态
- 必完成项 b 中 A-F 场景的自动编排与组合执行

如果后续继续完善，优先建议补齐三项：

1. 语音指令入口
2. 更完整的飞书 Slides / Drive 真正落库与分享链路
3. 离线编辑与断网恢复后的冲突合并
