from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path

from pilot_app.models import ContentBrief

SLIDE_WIDTH = 1600
SLIDE_HEIGHT = 900

BASE_CSS = f"""
:root {{
  --bg: #f4f8ff;
  --panel: rgba(255, 255, 255, 0.94);
  --line: rgba(148, 163, 184, 0.22);
  --ink: #12233f;
  --muted: #61738d;
  --blue: #2251d1;
  --cyan: #0f8cab;
  --shadow: 0 20px 48px rgba(15, 23, 42, 0.12);
}}

* {{
  box-sizing: border-box;
}}

html, body {{
  margin: 0;
  min-height: 100%;
  font-family: "Microsoft YaHei UI", "PingFang SC", "Noto Sans SC", sans-serif;
  color: var(--ink);
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.14), transparent 24%),
    radial-gradient(circle at 90% 10%, rgba(14, 165, 233, 0.12), transparent 24%),
    linear-gradient(160deg, #f8fbff 0%, #eef4ff 55%, #f8fafc 100%);
}}

body.preview {{
  padding: 24px 0 40px;
}}

.preview-shell {{
  width: min(1660px, calc(100vw - 24px));
  margin: 0 auto;
  display: grid;
  gap: 24px;
}}

.slide-frame {{
  border-radius: 28px;
  padding: 20px;
  background: rgba(255, 255, 255, 0.5);
}}

.stage {{
  width: {SLIDE_WIDTH}px;
  min-height: {SLIDE_HEIGHT}px;
  overflow: hidden;
  border-radius: 30px;
  box-shadow: var(--shadow);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(240, 246, 255, 0.98));
}}

.slide {{
  width: {SLIDE_WIDTH}px;
  min-height: {SLIDE_HEIGHT}px;
  padding: 44px 52px 34px;
  position: relative;
}}

.eyebrow {{
  display: inline-flex;
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(34, 81, 209, 0.1);
  color: var(--blue);
  font-size: 14px;
  font-weight: 700;
}}

h1 {{
  margin: 18px 0 12px;
  font-size: 60px;
  line-height: 1.08;
}}

h2 {{
  margin: 0;
  font-size: 40px;
}}

p {{
  margin: 0;
  color: var(--muted);
  line-height: 1.76;
  font-size: 18px;
}}

.hero-grid,
.two-col,
.outline-grid {{
  display: grid;
  gap: 22px;
}}

.hero-grid {{
  grid-template-columns: 1.08fr 0.92fr;
  margin-top: 28px;
}}

.two-col {{
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 22px;
}}

.outline-grid {{
  grid-template-columns: 0.84fr 1.16fr;
  margin-top: 22px;
}}

.card {{
  border-radius: 26px;
  padding: 24px;
  background: var(--panel);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}}

.hero-title {{
  font-size: 28px;
  margin: 0 0 14px;
}}

.chips,
.stats {{
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 22px;
}}

.chip,
.stat {{
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(191, 219, 254, 0.7);
  color: var(--blue);
  font-size: 14px;
  font-weight: 700;
}}

.stack {{
  display: grid;
  gap: 14px;
}}

.item {{
  padding: 16px 18px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid rgba(226, 232, 240, 0.9);
}}

.item strong {{
  display: block;
  margin-bottom: 8px;
  font-size: 18px;
}}

.item ul {{
  margin: 8px 0 0;
  padding-left: 20px;
  color: var(--muted);
  line-height: 1.72;
}}

.footer {{
  position: absolute;
  left: 52px;
  right: 52px;
  bottom: 24px;
  display: flex;
  justify-content: space-between;
  color: var(--muted);
  font-size: 13px;
}}
"""


@dataclass
class SlideDeck:
    deck_dir: Path
    index_file: Path
    slide_files: list[Path]


def generate_slide_deck(
    brief: ContentBrief,
    deck_dir: str,
    generated_at: str,
    plan_goal: str,
) -> SlideDeck:
    output_dir = Path(deck_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    slides = _build_slides(brief, generated_at, plan_goal)
    slide_files: list[Path] = []
    for index, slide in enumerate(slides, start=1):
        file_path = output_dir / f"slide_{index:02}.html"
        file_path.write_text(_render_capture_page(slide["title"], slide["body"]), encoding="utf-8")
        slide_files.append(file_path)

    index_path = output_dir / "index.html"
    index_path.write_text(_render_preview_page(slides), encoding="utf-8")
    return SlideDeck(deck_dir=output_dir, index_file=index_path, slide_files=slide_files)


def _build_slides(brief: ContentBrief, generated_at: str, plan_goal: str) -> list[dict[str, str]]:
    slides = [
        {"title": brief.topic or "Agent Pilot Cover", "body": _cover_slide(brief, generated_at, plan_goal)},
        {"title": "Summary", "body": _summary_slide(brief)},
        {"title": "Document", "body": _document_slide(brief)},
        {"title": "Outline", "body": _outline_slide(brief)},
    ]
    for index, outline in enumerate(brief.ppt_outline[:3], start=1):
        slides.append({"title": outline.title, "body": _detail_slide(index, outline.title, outline.bullets)})
    return slides


def _render_capture_page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_safe(title)}</title>
  <style>{BASE_CSS}</style>
</head>
<body>
  <div class="stage">
    {body}
  </div>
</body>
</html>
"""


def _render_preview_page(slides: list[dict[str, str]]) -> str:
    blocks = "".join(
        f'<section class="slide-frame"><div class="stage">{slide["body"]}</div></section>'
        for slide in slides
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Agent Pilot Slides Preview</title>
  <style>{BASE_CSS}</style>
</head>
<body class="preview">
  <main class="preview-shell">{blocks}</main>
</body>
</html>
"""


def _cover_slide(brief: ContentBrief, generated_at: str, plan_goal: str) -> str:
    summary_html = "".join(f"<li>{_safe(item)}</li>" for item in (brief.summary[:3] or ["等待内容生成"])) 
    stat_html = "".join(
        f'<div class="stat">{label} {value}</div>'
        for label, value in [
            ("摘要", len(brief.summary)),
            ("行动项", len(brief.action_items)),
            ("文档段落", len(brief.document_sections)),
            ("Slides", len(brief.ppt_outline)),
        ]
    )
    return f"""
<section class="slide">
  <div class="eyebrow">Agent Pilot / IM to Delivery</div>
  <h1>{_safe(brief.topic or "从 IM 对话到智能交付")}</h1>
  <p>{_safe(brief.objective or plan_goal)}</p>
  <div class="hero-grid">
    <article class="card">
      <h3 class="hero-title">本次 Agent 目标</h3>
      <p>{_safe(plan_goal)}</p>
      <div class="chips">
        <div class="chip">自然语言指令</div>
        <div class="chip">Agent Harness</div>
        <div class="chip">文档与 Slide 双交付</div>
      </div>
      <div class="stats">{stat_html}</div>
    </article>
    <article class="card">
      <h3 class="hero-title">核心摘要</h3>
      <ul>{summary_html}</ul>
      <p style="margin-top:18px;">生成时间：{_safe(generated_at)}</p>
    </article>
  </div>
  <div class="footer"><span>Agent Harness</span><span>01</span></div>
</section>
"""


def _summary_slide(brief: ContentBrief) -> str:
    action_html = "".join(
        f'<div class="item"><strong>{_safe(item.task)}</strong><p>负责人：{_safe(item.owner or "待定")} | 截止：{_safe(item.deadline or "待定")} | 状态：{_safe(item.status or "待开始")}</p></div>'
        for item in (brief.action_items[:4] or [])
    ) or '<div class="item"><strong>暂无行动项</strong><p>等待进一步澄清。</p></div>'
    owner_html = "".join(
        f'<div class="item"><strong>{_safe(owner.name)}</strong><p>{_safe(owner.responsibility)}</p></div>'
        for owner in (brief.owners[:4] or [])
    ) or '<div class="item"><strong>项目负责人</strong><p>统筹处理本次汇报交付。</p></div>'
    return f"""
<section class="slide">
  <div class="eyebrow">Summary & Actions</div>
  <h2>任务结论与行动分解</h2>
  <div class="two-col">
    <article class="card">
      <h3 class="hero-title">行动事项</h3>
      <div class="stack">{action_html}</div>
    </article>
    <article class="card">
      <h3 class="hero-title">责任分工</h3>
      <div class="stack">{owner_html}</div>
    </article>
  </div>
  <div class="footer"><span>IM -> Agent -> Tasks</span><span>02</span></div>
</section>
"""


def _document_slide(brief: ContentBrief) -> str:
    section_html = "".join(
        f'<div class="item"><strong>{_safe(section.title)}</strong><p>{_safe(section.body)}</p></div>'
        for section in (brief.document_sections[:4] or [])
    ) or '<div class="item"><strong>文档草稿待补充</strong><p>暂无结构化文档内容。</p></div>'
    deadline_html = "".join(
        f'<div class="item"><strong>{_safe(item.item)}</strong><p>时间节点：{_safe(item.due or "待定")}</p></div>'
        for item in (brief.deadlines[:4] or [])
    ) or '<div class="item"><strong>暂无时间节点</strong><p>等待业务确认。</p></div>'
    return f"""
<section class="slide">
  <div class="eyebrow">Document Draft</div>
  <h2>文档沉淀与时间节点</h2>
  <div class="two-col">
    <article class="card">
      <h3 class="hero-title">文档章节</h3>
      <div class="stack">{section_html}</div>
    </article>
    <article class="card">
      <h3 class="hero-title">关键时间点</h3>
      <div class="stack">{deadline_html}</div>
    </article>
  </div>
  <div class="footer"><span>Doc / Whiteboard Ready</span><span>03</span></div>
</section>
"""


def _outline_slide(brief: ContentBrief) -> str:
    rows = "".join(
        f'<div class="item"><strong>{index}. {_safe(outline.title)}</strong><ul>{"".join(f"<li>{_safe(b)}</li>" for b in outline.bullets[:3])}</ul></div>'
        for index, outline in enumerate((brief.ppt_outline[:4] or []), start=1)
    ) or '<div class="item"><strong>暂无 Slide 提纲</strong><p>等待内容补充。</p></div>'
    notes = "".join(f"<li>{_safe(note)}</li>" for note in (brief.delivery_notes[:4] or ["支持继续同步到飞书交付层。"]))
    return f"""
<section class="slide">
  <div class="eyebrow">Delivery Outline</div>
  <h2>演示稿结构与交付备注</h2>
  <div class="outline-grid">
    <article class="card">
      <h3 class="hero-title">交付备注</h3>
      <ul>{notes}</ul>
    </article>
    <article class="card">
      <h3 class="hero-title">Slide 提纲</h3>
      <div class="stack">{rows}</div>
    </article>
  </div>
  <div class="footer"><span>Slides / Delivery</span><span>04</span></div>
</section>
"""


def _detail_slide(index: int, title: str, bullets: list[str]) -> str:
    bullet_html = "".join(f"<li>{_safe(item)}</li>" for item in (bullets or ["待补充页面内容"]))
    return f"""
<section class="slide">
  <div class="eyebrow">Slide Detail {index:02}</div>
  <h2>{_safe(title)}</h2>
  <div class="two-col">
    <article class="card">
      <h3 class="hero-title">页面要点</h3>
      <ul>{bullet_html}</ul>
    </article>
    <article class="card">
      <h3 class="hero-title">演示提示</h3>
      <p>这一页可以继续接入真实飞书 Slides、画布或图表能力，扩展成正式汇报页面。</p>
    </article>
  </div>
  <div class="footer"><span>Presentation Ready</span><span>{index + 4:02}</span></div>
</section>
"""


def _safe(value: str) -> str:
    return html.escape(value or "")
