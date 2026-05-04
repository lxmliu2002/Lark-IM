from __future__ import annotations

import json
import re
from pathlib import Path

from .llm import LLMJsonClient
from .models import (
    ActionItem,
    ContentBrief,
    DeadlineItem,
    DocumentSection,
    JobCreateRequest,
    OutlineSlide,
    OwnerRole,
    PlanningResult,
)


def build_content_brief(
    request: JobCreateRequest,
    plan: PlanningResult,
    llm_client: LLMJsonClient,
) -> ContentBrief:
    try:
        return llm_client.generate_model(_brief_prompt(request, plan), ContentBrief)
    except Exception:
        return _fallback_brief(request, plan)


def _brief_prompt(request: JobCreateRequest, plan: PlanningResult) -> str:
    return f"""
Analyze the IM discussion and turn it into a delivery-ready content brief.
Return JSON matching exactly this schema:

{{
  "topic": "string",
  "objective": "string",
  "audience": "string",
  "summary": ["string"],
  "action_items": [
    {{
      "task": "string",
      "owner": "string",
      "deadline": "string",
      "status": "string"
    }}
  ],
  "owners": [
    {{
      "name": "string",
      "responsibility": "string"
    }}
  ],
  "deadlines": [
    {{
      "item": "string",
      "due": "string"
    }}
  ],
  "document_sections": [
    {{
      "title": "string",
      "body": "string"
    }}
  ],
  "ppt_outline": [
    {{
      "title": "string",
      "bullets": ["string"]
    }}
  ],
  "delivery_notes": ["string"]
}}

Rules:
- Use Simplified Chinese.
- Prefer concise, presentation-ready language.
- Base the result on the request and discussion.
- If some data is missing, keep strings empty or lists short instead of inventing details.

Instruction:
{request.instruction}

Planned goal:
{plan.goal}

Chat content:
{request.chat_text or request.voice_text or "(empty)"}
""".strip()


def _fallback_brief(request: JobCreateRequest, plan: PlanningResult) -> ContentBrief:
    lines = _extract_lines(request.chat_text or request.voice_text or request.instruction)
    topic = request.instruction.strip()[:30] or "IM 讨论自动整理"
    summary = lines[:3] or ["将 IM 对话整理为可执行的办公交付流。"]
    owners = _extract_owners(lines)
    action_items = _extract_actions(lines, owners)
    deadlines = _extract_deadlines(action_items)
    doc_sections = [
        DocumentSection(
            title="需求背景",
            body=summary[0] if summary else "本次任务从 IM 对话中发起，需要产出正式汇报材料。",
        ),
        DocumentSection(
            title="Agent 执行计划",
            body=" -> ".join(step.name for step in plan.steps) or "待规划",
        ),
        DocumentSection(
            title="当前结论",
            body="；".join(summary) if summary else "待补充。",
        ),
    ]
    outline = [
        OutlineSlide(title="背景与目标", bullets=summary[:2] or ["说明任务背景与目标"]),
        OutlineSlide(
            title="执行计划与分工",
            bullets=[item.task for item in action_items[:3]] or ["整理执行计划与责任人"],
        ),
        OutlineSlide(
            title="交付物与下一步",
            bullets=[
                "形成文档草稿与演示稿",
                "同步桌面端与移动端状态",
                "输出最终报告或 Slide 交付",
            ],
        ),
    ]
    return ContentBrief(
        topic=topic,
        objective=request.instruction.strip(),
        audience="团队负责人 / 评审 / 项目成员",
        summary=summary,
        action_items=action_items,
        owners=owners,
        deadlines=deadlines,
        document_sections=doc_sections,
        ppt_outline=outline,
        delivery_notes=[
            "当前为 Agent Harness 驱动的自动化草案。",
            "后续可接入真实飞书 Doc、Slides 和事件同步 API。",
        ],
    )


def render_report_markdown(request: JobCreateRequest, plan: PlanningResult, brief: ContentBrief) -> str:
    lines = [
        f"# {brief.topic}",
        "",
        f"- 入口来源：`{request.source.value}`",
        f"- 期望产物：`{request.preferred_output.value}`",
        f"- 指令：{request.instruction}",
        "",
        "## 目标",
        "",
        brief.objective or plan.goal,
        "",
        "## 核心摘要",
        "",
    ]
    for item in brief.summary:
        lines.append(f"- {item}")

    lines.extend(["", "## 执行计划", ""])
    for step in plan.steps:
        skills = ", ".join(step.skills) or "none"
        lines.append(f"1. **{step.name}**：{step.description}（skills: `{skills}`）")

    lines.extend(["", "## 文档内容", ""])
    for section in brief.document_sections:
        lines.extend([f"### {section.title}", "", section.body, ""])

    lines.extend(["## 行动事项", ""])
    for item in brief.action_items:
        lines.append(
            f"- {item.task} | 负责人：{item.owner or '待定'} | 截止：{item.deadline or '待定'} | 状态：{item.status or '待开始'}"
        )

    lines.extend(["", "## 演示稿提纲", ""])
    for index, slide in enumerate(brief.ppt_outline, start=1):
        lines.append(f"### {index}. {slide.title}")
        for bullet in slide.bullets:
            lines.append(f"- {bullet}")
        lines.append("")

    lines.extend(["## 交付备注", ""])
    for note in brief.delivery_notes:
        lines.append(f"- {note}")
    return "\n".join(lines).strip() + "\n"


def build_manifest_payload(
    request: JobCreateRequest,
    plan: PlanningResult,
    brief: ContentBrief,
    artifact_urls: dict[str, str],
) -> dict[str, object]:
    return {
        "source": request.source.value,
        "preferred_output": request.preferred_output.value,
        "instruction": request.instruction,
        "goal": plan.goal,
        "success_criteria": plan.success_criteria,
        "suggested_skills": plan.suggested_skills,
        "topic": brief.topic,
        "artifact_urls": artifact_urls,
        "delivery_notes": brief.delivery_notes,
    }


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_lines(text: str) -> list[str]:
    parts = [segment.strip() for segment in re.split(r"[。\n！？!?；;]", text) if segment.strip()]
    return parts[:6]


def _extract_owners(lines: list[str]) -> list[OwnerRole]:
    owners: list[OwnerRole] = []
    for line in lines:
        if "：" in line:
            name, content = line.split("：", 1)
            owners.append(OwnerRole(name=name[:12], responsibility=content[:48] or "跟进任务"))
    return owners[:4] or [OwnerRole(name="项目负责人", responsibility="统筹本次 IM 到交付的闭环流程")]


def _extract_actions(lines: list[str], owners: list[OwnerRole]) -> list[ActionItem]:
    actions: list[ActionItem] = []
    owner_names = [owner.name for owner in owners]
    for index, line in enumerate(lines[:4], start=1):
        owner = owner_names[index - 1] if index - 1 < len(owner_names) else ""
        actions.append(
            ActionItem(
                task=line[:48],
                owner=owner,
                deadline="待确认",
                status="待推进",
            )
        )
    return actions or [ActionItem(task="整理本次需求并生成交付草稿", owner="项目负责人", deadline="待确认", status="待推进")]


def _extract_deadlines(actions: list[ActionItem]) -> list[DeadlineItem]:
    return [
        DeadlineItem(item=action.task[:24], due=action.deadline or "待确认")
        for action in actions[:4]
    ] or [DeadlineItem(item="最终交付", due="待确认")]
