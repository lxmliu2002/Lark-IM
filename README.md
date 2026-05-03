# IM Office Assistant

这是一个基于 IM 聊天内容生成汇报材料的原型项目，当前已经跑通这条主链路：

`IM 聊天文本 -> 大模型结构化分析 -> HTML 幻灯片 -> 浏览器渲染 -> 导出为 PPT`

## 当前已完成

目前项目已经具备这些能力：

- 输入一段 IM 聊天内容
- 调用大模型提取：
  - 主题
  - 核心摘要
  - 行动事项
  - 负责人
  - 截止时间
  - 汇报提纲
- 将结构化结果渲染为 HTML 幻灯片
- 使用本机浏览器无头渲染 HTML 幻灯片
- 自动导出为真正的 `.pptx` 文件
- 提供本地网页页面进行：
  - 输入聊天内容
  - 查看结构化结果
  - 预览 HTML 幻灯片
  - 下载最终 PPT

## 项目结构

- [main.py](./main.py)
  FastAPI 服务入口，负责接口、网页入口、导出链路调度。

- [agent.py](./agent.py)
  调用大模型，返回结构化 JSON。

- [schemas.py](./schemas.py)
  定义结构化数据模型。

- [html_slides.py](./html_slides.py)
  将结构化结果渲染成 16:9 HTML 幻灯片。

- [ppt_tool.py](./ppt_tool.py)
  调用本机浏览器截图 HTML 幻灯片，并封装成 `.pptx`。

- [web_ui.html](./web_ui.html)
  本地演示页面。

- `outputs/`
  运行后生成的 HTML 幻灯片、截图中间产物和最终 PPT。

## 运行环境

建议环境：

- Python 3.9+
- Windows
- 已安装 Microsoft Edge 或 Google Chrome

说明：

- 当前导出 PPT 依赖本机浏览器无头渲染 HTML
- 默认优先查找 Edge，其次 Chrome

## 安装依赖

在项目根目录执行：

```powershell
python -m pip install -r requirements.txt
```

## 环境变量

不要直接共享真实 `.env`。

请复制 `.env.example` 为 `.env`，然后填写真实值：

```powershell
Copy-Item .env.example .env
```

需要配置的主要变量：

- `ARK_API_KEY`
  火山引擎 API Key

- `ARK_MODEL_ID`
  例如 `ep-xxxxxxxx`

- `ARK_BASE_URL`
  默认可用：`https://ark.cn-beijing.volces.com/api/v3`

- `HTML_RENDER_BROWSER`
  可选。如果浏览器不是默认安装路径，就手动填写浏览器 exe 完整路径

## 启动方式

在项目根目录执行：

```powershell
python -m uvicorn main:app --reload
```

启动后打开：

```text
http://127.0.0.1:8000/
```

## 运行流程

1. 在网页里粘贴 IM 聊天内容
2. 点击“生成 HTML 幻灯片并导出 PPT”
3. 后端调用大模型生成结构化结果
4. 后端生成 HTML 幻灯片
5. 后端调用浏览器无头渲染每一页 HTML
6. 后端把渲染结果封装成 `.pptx`
7. 前端页面展示：
   - 结构化 JSON
   - HTML 幻灯片预览
   - PPT 下载按钮

## 队友接手建议

如果要继续开发，建议按模块分工：

- 内容分析和提示词优化：
  [agent.py](./agent.py)

- 数据结构扩展：
  [schemas.py](./schemas.py)

- HTML 幻灯片视觉优化：
  [html_slides.py](./html_slides.py)

- PPT 导出链路优化：
  [ppt_tool.py](./ppt_tool.py)

- 页面交互和演示体验：
  [web_ui.html](./web_ui.html)

## 当前注意事项

- 当前视觉主导是 HTML/CSS，不是原生 PPT 排版
- 最终导出的 PPT，本质上是“每页一张浏览器渲染图片”
- 如果队友电脑上没有 Edge/Chrome，PPT 导出会失败
- 如果浏览器路径不在默认位置，需要在 `.env` 里设置 `HTML_RENDER_BROWSER`

## 可以继续优化的方向

- 接入 AI 生成配图，并自动嵌入 HTML 幻灯片
- 增加不同视觉主题切换
- 支持导出 PDF
- 支持每页单独图表或数据卡片
- 支持更多办公场景：会议纪要、周报、任务跟踪
