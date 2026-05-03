import html
from dataclasses import dataclass
from pathlib import Path

from schemas import ActionItem, AnalysisResult, DeadlineItem, OutlineSlide, OwnerRole

SLIDE_WIDTH = 1600
SLIDE_HEIGHT = 900

BASE_CSS = f"""
:root {{
  --bg: #edf3ff;
  --panel: rgba(255, 255, 255, 0.96);
  --panel-soft: rgba(239, 246, 255, 0.98);
  --panel-cyan: rgba(236, 254, 255, 0.98);
  --panel-amber: rgba(255, 251, 235, 0.98);
  --panel-deep: rgba(15, 23, 42, 0.9);
  --ink: #14213d;
  --muted: #5f708a;
  --blue: #1d4ed8;
  --blue-deep: #102a83;
  --cyan: #0891b2;
  --violet: #4338ca;
  --amber: #d97706;
  --green: #15803d;
  --red: #dc2626;
  --line: rgba(148, 163, 184, 0.2);
  --shadow: 0 24px 48px rgba(15, 23, 42, 0.12);
  --shadow-strong: 0 36px 70px rgba(15, 23, 42, 0.18);
}}

* {{
  box-sizing: border-box;
}}

html, body {{
  margin: 0;
  width: 100%;
  min-height: 100%;
  font-family: "Microsoft YaHei UI", "PingFang SC", "Noto Sans SC", sans-serif;
  color: var(--ink);
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.2), transparent 24%),
    radial-gradient(circle at 88% 8%, rgba(8, 145, 178, 0.14), transparent 20%),
    linear-gradient(160deg, #f8fbff 0%, #edf4ff 45%, #f8fafc 100%);
}}

body.capture {{
  overflow: hidden;
}}

.preview-shell {{
  width: min(1660px, calc(100vw - 24px));
  margin: 22px auto 32px;
  display: grid;
  gap: 26px;
}}

.slide-frame {{
  padding: 22px;
  border-radius: 30px;
  background: rgba(255, 255, 255, 0.42);
  backdrop-filter: blur(10px);
  box-shadow: 0 28px 56px rgba(15, 23, 42, 0.08);
}}

.stage {{
  width: {SLIDE_WIDTH}px;
  min-height: {SLIDE_HEIGHT}px;
  overflow: hidden;
  position: relative;
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.18), transparent 22%),
    radial-gradient(circle at 85% 10%, rgba(8, 145, 178, 0.12), transparent 20%),
    linear-gradient(160deg, #f8fbff 0%, #eef4ff 50%, #f8fafc 100%);
}}

.stage::before {{
  content: "";
  position: absolute;
  inset: 24px;
  border-radius: 28px;
  border: 1px solid rgba(255, 255, 255, 0.46);
  pointer-events: none;
}}

.stage::after {{
  content: "";
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.06) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.16), transparent 80%);
  pointer-events: none;
}}

body.capture .stage {{
  margin: 0;
}}

body.preview .stage {{
  box-shadow: var(--shadow);
  border-radius: 32px;
}}

.slide {{
  width: {SLIDE_WIDTH}px;
  min-height: {SLIDE_HEIGHT}px;
  position: relative;
  padding: 44px 52px 42px;
}}

.slide::before {{
  content: "";
  position: absolute;
  top: 26px;
  right: 34px;
  width: 180px;
  height: 180px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(37, 99, 235, 0.14), rgba(37, 99, 235, 0) 70%);
  pointer-events: none;
}}

.cover {{
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 26px;
  align-items: stretch;
}}

.cover-left {{
  padding: 18px 0;
  position: relative;
}}

.cover-eyebrow {{
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 11px 16px;
  border-radius: 999px;
  background: rgba(16, 42, 131, 0.08);
  color: var(--blue-deep);
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.04em;
}}

.cover-title {{
  margin: 20px 0 14px;
  font-size: 66px;
  line-height: 1.08;
  letter-spacing: -0.035em;
  max-width: 760px;
}}

.cover-subtitle {{
  margin: 0;
  font-size: 23px;
  line-height: 1.72;
  color: var(--muted);
  max-width: 720px;
}}

.cover-highlight {{
  margin-top: 24px;
  width: max-content;
  max-width: 720px;
  padding: 16px 18px;
  border-radius: 22px;
  background: linear-gradient(135deg, rgba(16, 42, 131, 0.94), rgba(67, 56, 202, 0.9));
  color: #fff;
  box-shadow: var(--shadow);
  font-size: 18px;
  line-height: 1.7;
}}

.chip-row {{
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 24px;
}}

.chip {{
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(191, 219, 254, 0.82);
  color: var(--blue);
  font-size: 14px;
  font-weight: 700;
}}

.meta-bar {{
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 26px;
}}

.meta-item {{
  padding: 12px 14px;
  min-width: 150px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(226, 232, 240, 0.85);
  box-shadow: 0 14px 30px rgba(148, 163, 184, 0.12);
}}

.meta-item span {{
  display: block;
  font-size: 13px;
  color: var(--muted);
}}

.meta-item strong {{
  display: block;
  margin-top: 8px;
  font-size: 25px;
  color: var(--blue-deep);
}}

.cover-right {{
  position: relative;
  display: grid;
  gap: 18px;
}}

.cover-side-stack {{
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}}

.glass {{
  border-radius: 28px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(16px);
  box-shadow: var(--shadow-strong);
}}

.hero-card {{
  padding: 28px 28px 24px;
  min-height: 320px;
  position: relative;
  overflow: hidden;
}}

.hero-card::after {{
  content: "";
  position: absolute;
  inset: auto -40px -54px auto;
  width: 180px;
  height: 180px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(8, 145, 178, 0.18), rgba(8, 145, 178, 0) 72%);
}}

.hero-card h3,
.card h3 {{
  margin: 0 0 14px;
  font-size: 24px;
}}

.hero-card ul,
.outline-card ul,
.bullet-list {{
  margin: 0;
  padding-left: 24px;
  line-height: 1.8;
  color: var(--muted);
  font-size: 20px;
}}

.hero-kpi {{
  padding: 18px 18px 16px;
  border-radius: 22px;
  background: linear-gradient(135deg, rgba(236, 254, 255, 0.96), rgba(255, 255, 255, 0.98));
  border: 1px solid rgba(165, 243, 252, 0.82);
}}

.hero-kpi span {{
  display: block;
  font-size: 13px;
  color: var(--muted);
}}

.hero-kpi strong {{
  display: block;
  margin-top: 10px;
  font-size: 30px;
  color: var(--blue-deep);
}}

.hero-footnote {{
  padding: 18px 22px;
  background: linear-gradient(135deg, rgba(8, 145, 178, 0.95), rgba(29, 78, 216, 0.92));
  color: #fff;
}}

.hero-footnote p {{
  margin: 0;
  line-height: 1.75;
  font-size: 15px;
}}

.section-header {{
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 22px;
  position: relative;
  z-index: 2;
}}

.section-header h2 {{
  margin: 0;
  font-size: 42px;
  line-height: 1.15;
  letter-spacing: -0.03em;
}}

.section-header p {{
  margin: 8px 0 0;
  color: var(--muted);
  font-size: 19px;
}}

.slide-badge {{
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(16, 42, 131, 0.9);
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  box-shadow: 0 14px 30px rgba(16, 42, 131, 0.18);
}}

.grid-2 {{
  display: grid;
  grid-template-columns: 1.3fr 0.7fr;
  gap: 22px;
}}

.card {{
  border-radius: 28px;
  padding: 24px 26px;
  background: var(--panel);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}}

.card.soft-blue {{
  background: var(--panel-soft);
}}

.card.soft-cyan {{
  background: var(--panel-cyan);
}}

.card.soft-amber {{
  background: var(--panel-amber);
}}

.topic-banner {{
  padding: 18px 22px;
  border-radius: 22px;
  background: linear-gradient(135deg, rgba(219, 234, 254, 0.92), rgba(255, 255, 255, 0.98));
  border: 1px solid rgba(147, 197, 253, 0.86);
  font-size: 30px;
  line-height: 1.5;
  font-weight: 700;
  box-shadow: 0 18px 38px rgba(59, 130, 246, 0.12);
}}

.summary-stack,
.owner-stack,
.outline-stack,
.timeline-stack,
.action-grid {{
  display: grid;
  gap: 16px;
}}

.summary-item,
.owner-item,
.timeline-item,
.outline-card,
.action-card {{
  border-radius: 22px;
  padding: 18px 20px;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(226, 232, 240, 0.9);
  box-shadow: 0 14px 30px rgba(148, 163, 184, 0.12);
}}

.summary-item {{
  display: grid;
  grid-template-columns: 56px 1fr;
  gap: 16px;
  align-items: start;
}}

.summary-no {{
  width: 56px;
  height: 56px;
  border-radius: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(16, 42, 131, 0.92), rgba(29, 78, 216, 0.88));
  color: #fff;
  font-size: 20px;
  font-weight: 700;
  box-shadow: 0 16px 30px rgba(29, 78, 216, 0.2);
}}

.summary-item strong,
.owner-item strong,
.timeline-item strong,
.outline-card strong {{
  display: block;
  margin-bottom: 8px;
  font-size: 19px;
}}

.summary-item p,
.owner-item p,
.timeline-item p,
.outline-card p {{
  margin: 0;
  font-size: 16px;
  line-height: 1.78;
  color: var(--muted);
}}

.owner-item {{
  background: linear-gradient(135deg, rgba(236, 254, 255, 0.96), rgba(255, 255, 255, 0.98));
  border-color: rgba(165, 243, 252, 0.82);
}}

.metrics-stack {{
  display: grid;
  gap: 14px;
}}

.metric-item {{
  padding: 16px 18px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(226, 232, 240, 0.9);
  position: relative;
  overflow: hidden;
}}

.metric-item::after {{
  content: "";
  position: absolute;
  right: -16px;
  top: -14px;
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(37, 99, 235, 0.16), rgba(37, 99, 235, 0) 72%);
}}

.metric-item span {{
  display: block;
  font-size: 13px;
  color: var(--muted);
}}

.metric-item strong {{
  display: block;
  margin-top: 8px;
  font-size: 28px;
  color: var(--blue-deep);
}}

.action-grid {{
  grid-template-columns: repeat(2, minmax(0, 1fr));
}}

.action-card {{
  min-height: 320px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(239, 246, 255, 0.9));
  position: relative;
  overflow: hidden;
}}

.action-card::before {{
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: 8px;
  background: linear-gradient(90deg, rgba(16, 42, 131, 1), rgba(8, 145, 178, 0.92));
}}

.action-top {{
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}}

.action-index {{
  width: 48px;
  height: 48px;
  border-radius: 16px;
  background: rgba(29, 78, 216, 0.12);
  color: var(--blue-deep);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 18px;
  flex: 0 0 auto;
  box-shadow: inset 0 0 0 1px rgba(147, 197, 253, 0.5);
}}

.action-title {{
  margin: 0;
  font-size: 25px;
  line-height: 1.4;
  letter-spacing: -0.02em;
}}

.status {{
  padding: 9px 15px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
  box-shadow: 0 10px 20px rgba(15, 23, 42, 0.08);
}}

.action-meta {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 18px;
}}

.meta-box {{
  padding: 14px 14px 12px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(226, 232, 240, 0.82);
  min-height: 92px;
}}

.meta-box span {{
  display: block;
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 8px;
}}

.meta-box strong {{
  display: block;
  font-size: 16px;
}}

.action-note {{
  margin-top: 16px;
  color: var(--muted);
  font-size: 15px;
  line-height: 1.7;
}}

.two-columns {{
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 22px;
}}

.timeline-line {{
  display: grid;
  gap: 14px;
}}

.timeline-item {{
  display: grid;
  grid-template-columns: 92px 1fr;
  gap: 14px;
  align-items: stretch;
  background: linear-gradient(135deg, rgba(255, 251, 235, 0.96), rgba(255, 255, 255, 0.98));
  border: 1px solid rgba(253, 230, 138, 0.82);
  position: relative;
}}

.timeline-date {{
  padding: 16px 12px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.76);
  color: var(--amber);
  text-align: center;
  font-weight: 700;
  line-height: 1.5;
}}

.timeline-content {{
  padding: 16px 18px 16px 0;
}}

.timeline-content strong {{
  display: block;
  font-size: 18px;
  margin-bottom: 6px;
}}

.timeline-content p {{
  margin: 0;
  color: var(--muted);
  line-height: 1.7;
  font-size: 15px;
}}

.outline-overview {{
  display: grid;
  grid-template-columns: 0.8fr 1.2fr;
  gap: 22px;
}}

.dark-card {{
  border-radius: 28px;
  padding: 26px 28px;
  background: linear-gradient(160deg, rgba(16, 42, 131, 0.98), rgba(29, 78, 216, 0.92));
  color: #fff;
  box-shadow: var(--shadow-strong);
  position: relative;
  overflow: hidden;
}}

.dark-card::after {{
  content: "";
  position: absolute;
  inset: auto -56px -64px auto;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.16), rgba(255, 255, 255, 0) 70%);
}}

.dark-card h3 {{
  margin: 0 0 16px;
  font-size: 26px;
}}

.dark-card p,
.dark-card li {{
  color: rgba(255, 255, 255, 0.86);
  line-height: 1.78;
  font-size: 17px;
}}

.dark-card ul {{
  margin: 0;
  padding-left: 22px;
}}

.outline-list {{
  display: grid;
  gap: 14px;
}}

.outline-row {{
  display: grid;
  grid-template-columns: 48px 1fr;
  gap: 14px;
  align-items: center;
}}

.outline-no {{
  width: 48px;
  height: 48px;
  border-radius: 16px;
  background: rgba(16, 42, 131, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--blue-deep);
  font-size: 18px;
  font-weight: 700;
}}

.outline-title {{
  padding: 14px 18px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid rgba(226, 232, 240, 0.9);
  font-size: 18px;
  line-height: 1.6;
  box-shadow: 0 10px 24px rgba(148, 163, 184, 0.1);
}}

.detail-layout {{
  display: grid;
  grid-template-columns: 0.92fr 1.08fr;
  gap: 22px;
}}

.detail-panel {{
  position: relative;
}}

.giant-index {{
  position: absolute;
  right: 22px;
  bottom: 12px;
  font-size: 160px;
  line-height: 1;
  font-weight: 800;
  color: rgba(255, 255, 255, 0.08);
  pointer-events: none;
}}

.detail-title {{
  margin: 8px 0 0;
  font-size: 42px;
  line-height: 1.18;
}}

.detail-sub {{
  margin: 14px 0 0;
  color: var(--muted);
  line-height: 1.8;
  font-size: 18px;
}}

.callout {{
  margin-top: 24px;
  padding: 18px 18px 16px;
  border-radius: 22px;
  background: linear-gradient(135deg, rgba(219, 234, 254, 0.88), rgba(255, 255, 255, 0.96));
  border: 1px solid rgba(147, 197, 253, 0.72);
}}

.callout strong {{
  display: block;
  margin-bottom: 8px;
  font-size: 15px;
  color: var(--blue-deep);
}}

.callout p {{
  margin: 0;
  font-size: 15px;
  color: var(--muted);
  line-height: 1.7;
}}

.footer {{
  position: absolute;
  left: 52px;
  right: 52px;
  bottom: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--muted);
  font-size: 13px;
  z-index: 2;
}}
"""


@dataclass
class SlideDeck:
    deck_dir: Path
    index_file: Path
    slide_files: list[Path]


def generate_slide_deck(
    analysis: AnalysisResult,
    deck_dir: str,
    generated_at: str,
) -> SlideDeck:
    output_dir = Path(deck_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    slides = _build_slides(analysis, generated_at)
    slide_files: list[Path] = []

    for index, slide in enumerate(slides, start=1):
        filename = f"slide_{index:02}.html"
        file_path = output_dir / filename
        file_path.write_text(_render_capture_page(slide["title"], slide["body"]), encoding="utf-8")
        slide_files.append(file_path)

    index_path = output_dir / "index.html"
    index_path.write_text(_render_preview_page(slides), encoding="utf-8")

    return SlideDeck(deck_dir=output_dir, index_file=index_path, slide_files=slide_files)


def _build_slides(analysis: AnalysisResult, generated_at: str) -> list[dict[str, str]]:
    slides: list[dict[str, str]] = []
    slides.append({
        "title": analysis.topic or "协同分析封面",
        "body": _cover_slide(analysis, generated_at),
    })
    slides.append({
        "title": "沟通摘要",
        "body": _summary_slide(analysis),
    })

    action_items = analysis.action_items or [ActionItem(task="暂无行动事项", owner="", deadline="", status="")]
    for offset in range(0, len(action_items), 4):
        chunk = action_items[offset : offset + 4]
        page = offset // 4 + 1
        title = "行动事项" if len(action_items) <= 4 else f"行动事项（第 {page} 页）"
        slides.append({
            "title": title,
            "body": _action_slide(chunk, title),
        })

    slides.append({
        "title": "分工与节点",
        "body": _owner_deadline_slide(
            analysis.owners or [OwnerRole(name="暂无责任分工", responsibility="待补充")],
            analysis.deadlines or [DeadlineItem(item="暂无时间节点", due="待补充")],
        ),
    })
    slides.append({
        "title": "汇报提纲",
        "body": _outline_overview_slide(analysis.ppt_outline or [OutlineSlide(title="暂无提纲内容", bullets=[])]),
    })

    for index, outline in enumerate(analysis.ppt_outline or [OutlineSlide(title="暂无提纲内容", bullets=[])] , start=1):
        slides.append({
            "title": f"汇报页 {index}",
            "body": _outline_detail_slide(index, outline),
        })

    return slides


def _render_capture_page(title: str, slide_body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_safe(title)}</title>
  <style>{BASE_CSS}</style>
</head>
<body class="capture">
  <div class="stage">
    {slide_body}
  </div>
</body>
</html>
"""


def _render_preview_page(slides: list[dict[str, str]]) -> str:
    slide_blocks = []
    for slide in slides:
        slide_blocks.append(
            f'<section class="slide-frame"><div class="stage">{slide["body"]}</div></section>'
        )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>HTML 幻灯片预览</title>
  <style>{BASE_CSS}</style>
</head>
<body class="preview">
  <main class="preview-shell">
    {"".join(slide_blocks)}
  </main>
</body>
</html>
"""


def _cover_slide(analysis: AnalysisResult, generated_at: str) -> str:
    chips = "".join(
        f'<div class="chip">{label}</div>'
        for label in ["结构化分析", "HTML 幻灯片渲染", "自动封装为 PPT"]
    )
    metrics = [
        ("摘要条数", len(analysis.summary)),
        ("行动事项", len(analysis.action_items)),
        ("责任角色", len(analysis.owners)),
        ("提纲页数", len(analysis.ppt_outline)),
    ]
    metric_html = "".join(
        f'<div class="meta-item"><span>{_safe(label)}</span><strong>{value}</strong></div>'
        for label, value in metrics
    )
    side_kpis = "".join(
        f'<div class="hero-kpi"><span>{_safe(label)}</span><strong>{value}</strong></div>'
        for label, value in [
            ("当前主题", "已提炼"),
            ("导出形式", "PPT"),
            ("视觉方式", "HTML"),
            ("页面风格", "幻灯片"),
        ]
    )
    bullets = "".join(
        f"<li>{_safe(line)}</li>"
        for line in [
            "自动提炼主题、摘要与任务分工",
            "将 HTML 视觉稿渲染为幻灯片页面",
            "最终输出可交付的 .pptx 文件",
        ]
    )
    topic = _safe(analysis.topic or "自动识别聊天主题并生成汇报内容")
    return f"""
<section class="slide cover">
  <div class="cover-left">
    <div class="cover-eyebrow">HTML 渲染幻灯片</div>
    <h1 class="cover-title">办公协同智能助手</h1>
    <p class="cover-subtitle">{topic}</p>
    <div class="cover-highlight">把 IM 沟通转换为可展示、可交付、可继续导出的高质量视觉稿。</div>
    <div class="chip-row">{chips}</div>
    <div class="meta-bar">{metric_html}</div>
  </div>
  <div class="cover-right">
    <article class="glass hero-card">
      <h3>本次输出包含</h3>
      <ul>{bullets}</ul>
    </article>
    <div class="cover-side-stack">{side_kpis}</div>
    <article class="glass hero-footnote">
      <p>生成时间：{_safe(generated_at)}<br>当前这套页面会先用 HTML/CSS 排版，再回写进真正的 PPT 文件。</p>
    </article>
  </div>
  <div class="footer">
    <span>IM 办公协同智能助手</span>
    <span>01</span>
  </div>
</section>
"""


def _summary_slide(analysis: AnalysisResult) -> str:
    summary_html = "".join(
        f'<div class="summary-item"><div class="summary-no">{index}</div><div><strong>摘要 {index}</strong><p>{_safe(item)}</p></div></div>'
        for index, item in enumerate(analysis.summary or ["暂无摘要内容"], start=1)
    )
    metrics_html = "".join(
        f'<div class="metric-item"><span>{_safe(label)}</span><strong>{value}</strong></div>'
        for label, value in [
            ("行动事项", len(analysis.action_items)),
            ("责任角色", len(analysis.owners)),
            ("时间节点", len(analysis.deadlines)),
            ("提纲页数", len(analysis.ppt_outline)),
        ]
    )
    return f"""
<section class="slide">
  <header class="section-header">
    <div>
      <h2>沟通摘要</h2>
      <p>把聊天中的核心共识提炼成适合汇报展示的结论。</p>
    </div>
    <div class="slide-badge">Summary</div>
  </header>
  <div class="topic-banner">{_safe(analysis.topic or "未识别到明确主题")}</div>
  <div class="grid-2" style="margin-top:22px;">
    <article class="card">
      <h3>核心摘要</h3>
      <div class="summary-stack">{summary_html}</div>
    </article>
    <article class="card soft-blue">
      <h3>概览指标</h3>
      <div class="metrics-stack">{metrics_html}</div>
    </article>
  </div>
  <div class="footer">
    <span>HTML 幻灯片渲染预览</span>
    <span>02</span>
  </div>
</section>
"""


def _action_slide(items: list[ActionItem], title: str) -> str:
    cards = "".join(_action_card_html(item, index) for index, item in enumerate(items, start=1))
    return f"""
<section class="slide">
  <header class="section-header">
    <div>
      <h2>{_safe(title)}</h2>
      <p>直接把沟通结果落成可执行任务，并用状态标签突出优先级。</p>
    </div>
    <div class="slide-badge">Action Items</div>
  </header>
  <div class="action-grid">{cards}</div>
  <div class="footer">
    <span>结构化结果可继续同步到任务系统</span>
    <span>03</span>
  </div>
</section>
"""


def _owner_deadline_slide(owners: list[OwnerRole], deadlines: list[DeadlineItem]) -> str:
    owner_html = "".join(
        f'<div class="owner-item"><strong>{_safe(item.name or "未命名角色")}</strong><p>{_safe(item.responsibility or "待补充职责")}</p></div>'
        for item in owners
    )
    deadline_html = "".join(
        f'<div class="timeline-item"><div class="timeline-date">{_safe(item.due or "待定")}</div><div class="timeline-content"><strong>{_safe(item.item or "未命名节点")}</strong><p>建议围绕该时间点安排后续对齐、评审和交付动作。</p></div></div>'
        for item in deadlines
    )
    return f"""
<section class="slide">
  <header class="section-header">
    <div>
      <h2>分工与节点</h2>
      <p>统一查看责任角色、职责范围和交付时间。</p>
    </div>
    <div class="slide-badge">Owners & Timeline</div>
  </header>
  <div class="two-columns">
    <article class="card soft-cyan">
      <h3>责任分工</h3>
      <div class="owner-stack">{owner_html}</div>
    </article>
    <article class="card soft-amber">
      <h3>关键节点</h3>
      <div class="timeline-line">{deadline_html}</div>
    </article>
  </div>
  <div class="footer">
    <span>责任到人，节点清晰</span>
    <span>04</span>
  </div>
</section>
"""


def _outline_overview_slide(outlines: list[OutlineSlide]) -> str:
    rows = "".join(
        f'<div class="outline-row"><div class="outline-no">{index}</div><div class="outline-title">{_safe(item.title or "未命名页面")}</div></div>'
        for index, item in enumerate(outlines, start=1)
    )
    return f"""
<section class="slide">
  <header class="section-header">
    <div>
      <h2>汇报提纲</h2>
      <p>这是后续正式演示稿的页面顺序建议。</p>
    </div>
    <div class="slide-badge">Outline</div>
  </header>
  <div class="outline-overview">
    <article class="dark-card">
      <h3>建议汇报逻辑</h3>
      <ul>
        <li>先用摘要页建立背景与共识</li>
        <li>再展开行动事项、责任人和关键节点</li>
        <li>最后给出后续推进或汇报提纲</li>
      </ul>
    </article>
    <article class="card">
      <h3>提纲总览</h3>
      <div class="outline-list">{rows}</div>
    </article>
  </div>
  <div class="footer">
    <span>HTML 幻灯片结构可继续定制主题样式</span>
    <span>05</span>
  </div>
</section>
"""


def _outline_detail_slide(index: int, outline: OutlineSlide) -> str:
    bullet_html = "".join(f"<li>{_safe(item)}</li>" for item in (outline.bullets or ["暂无要点"]))
    title = _safe(outline.title or "未命名页面")
    return f"""
<section class="slide">
  <header class="section-header">
    <div>
      <h2>汇报页 {index}</h2>
      <p>这个页面可以继续细化成最终给评委或老师展示的正式内容。</p>
    </div>
    <div class="slide-badge">Slide {index:02}</div>
  </header>
  <div class="detail-layout">
    <article class="dark-card detail-panel">
      <div class="cover-eyebrow">Page {index:02}</div>
      <h3 class="detail-title">{title}</h3>
      <p class="detail-sub">保留这份提纲后，后续可以继续接图表、图示或业务数据，把它升级成最终展示用的高保真页面。</p>
      <div class="callout">
        <strong>延展建议</strong>
        <p>下一步可在这一页加入图表、流程图或关键数据高亮，让内容更像正式汇报。</p>
      </div>
      <div class="giant-index">{index:02}</div>
    </article>
    <article class="card">
      <h3>页面要点</h3>
      <ul class="bullet-list">{bullet_html}</ul>
    </article>
  </div>
  <div class="footer">
    <span>页面内容来自结构化 JSON，可持续复用</span>
    <span>{index + 5:02}</span>
  </div>
</section>
"""


def _action_card_html(item: ActionItem, index: int) -> str:
    status_bg, status_color = _status_style(item.status)
    return f"""
    <article class="action-card">
      <div>
        <div class="action-top">
          <div style="display:flex; gap:14px; align-items:flex-start;">
            <div class="action-index">{index}</div>
            <h3 class="action-title">{_safe(item.task or "待补充事项")}</h3>
          </div>
          <div class="status" style="background:{status_bg}; color:{status_color};">{_safe(item.status or "待开始")}</div>
        </div>
        <div class="action-meta">
          <div class="meta-box"><span>负责人</span><strong>{_safe(item.owner or "待定")}</strong></div>
          <div class="meta-box"><span>截止时间</span><strong>{_safe(item.deadline or "待定")}</strong></div>
          <div class="meta-box"><span>推进建议</span><strong>{_safe(_action_hint(item.owner, item.deadline))}</strong></div>
        </div>
      </div>
      <div class="action-note">建议围绕这项任务同步状态变化，让系统后续支持自动更新与追踪。</div>
    </article>
    """


def _status_style(status: str) -> tuple[str, str]:
    value = (status or "").lower()
    if any(token in value for token in ["完成", "done", "complete", "已结束"]):
        return ("rgba(220, 252, 231, 1)", "#15803d")
    if any(token in value for token in ["进行", "推进", "处理中", "in progress"]):
        return ("rgba(219, 234, 254, 1)", "#1d4ed8")
    if any(token in value for token in ["风险", "延期", "阻塞", "delay", "blocked"]):
        return ("rgba(254, 226, 226, 1)", "#dc2626")
    return ("rgba(255, 251, 235, 1)", "#d97706")


def _action_hint(owner: str, deadline: str) -> str:
    owner_text = owner or "待定负责人"
    deadline_text = deadline or "待定时间"
    return f"{owner_text} 在 {deadline_text} 前推进"


def _safe(value: str) -> str:
    return html.escape(value or "")
