from __future__ import annotations

import os
from pathlib import Path

from html_slides import generate_slide_deck
from ppt_tool import render_html_slides_to_ppt

from .content import build_content_brief, build_manifest_payload, render_report_markdown, write_json
from .lark_cli import LarkCLIClient
from .llm import LLMJsonClient
from .models import ArtifactRef, ContentBrief, JobStatus, StepStatus
from .planner import AgentPlanner
from .skills import LarkSkillRegistry
from .store import InMemoryJobStore


class AgentHarness:
    def __init__(
        self,
        store: InMemoryJobStore,
        planner: AgentPlanner,
        llm_client: LLMJsonClient,
        lark_cli: LarkCLIClient,
        skills: LarkSkillRegistry,
        output_root: Path,
    ) -> None:
        self.store = store
        self.planner = planner
        self.llm_client = llm_client
        self.lark_cli = lark_cli
        self.skills = skills
        self.output_root = output_root

    def run_job(self, job_id: str) -> None:
        job = self.store.get_job(job_id)
        job_dir = self.output_root / job_id
        deck_dir = job_dir / "slides"
        delivery_dir = job_dir / "delivery"
        job_dir.mkdir(parents=True, exist_ok=True)
        deck_dir.mkdir(parents=True, exist_ok=True)
        delivery_dir.mkdir(parents=True, exist_ok=True)

        try:
            self.store.set_status(job_id, JobStatus.running)
            self.store.add_event(job_id, "harness", "Agent Harness 已接管任务。")

            plan = self.planner.plan(job.request)
            self.store.set_plan(
                job_id,
                goal=plan.goal,
                success_criteria=plan.success_criteria,
                clarification_questions=plan.clarification_questions,
                suggested_skills=plan.suggested_skills,
                steps=plan.steps,
            )

            self._run_phase(job_id, "intake", "已完成 IM / 飞书入口整理。")
            self._run_phase(
                job_id,
                "plan",
                f"已生成执行计划，推荐 skills：{', '.join(plan.suggested_skills) or 'none'}",
            )

            brief = build_content_brief(job.request, plan, self.llm_client)
            self.store.set_brief(job_id, brief)

            report_path = delivery_dir / "report.md"
            report_path.write_text(render_report_markdown(job.request, plan, brief), encoding="utf-8")
            self.store.add_artifact(
                job_id,
                ArtifactRef(
                    kind="report_markdown",
                    label="汇报文档草稿",
                    path=str(report_path),
                    url=f"/artifacts/{job_id}/delivery/report.md",
                ),
            )

            document_notes = ["文档草稿已生成。"]
            doc_sync_summary = self._sync_report_to_feishu_doc(job_id, report_path, brief.topic or "Agent Pilot 报告")
            if doc_sync_summary:
                document_notes.append(doc_sync_summary)
            self._run_phase(job_id, "document", " ".join(document_notes))

            slide_deck = generate_slide_deck(brief, str(deck_dir), self.store.get_job(job_id).updated_at, plan.goal)
            self.store.add_artifact(
                job_id,
                ArtifactRef(
                    kind="slides_preview",
                    label="HTML Slide 预览",
                    path=str(slide_deck.index_file),
                    url=f"/artifacts/{job_id}/slides/index.html",
                ),
            )

            slide_notes = ["HTML Slide 已生成。"]
            ppt_path = delivery_dir / f"{job_id}.pptx"
            try:
                render_html_slides_to_ppt([str(path) for path in slide_deck.slide_files], str(ppt_path))
                self.store.add_artifact(
                    job_id,
                    ArtifactRef(
                        kind="pptx",
                        label="PPT 交付文件",
                        path=str(ppt_path),
                        url=f"/artifacts/{job_id}/delivery/{ppt_path.name}",
                    ),
                )
                slide_notes.append("PPT 文件已导出。")
            except Exception as exc:
                self.store.add_event(
                    job_id,
                    "slides",
                    f"PPT 导出因当前环境限制被跳过：{exc}",
                    level="warning",
                )
                slide_notes.append("PPT 导出在当前环境中被跳过。")

            lark_slide_summary = self._sync_outline_to_feishu_slides(job_id, brief)
            if lark_slide_summary:
                slide_notes.append(lark_slide_summary)
            self._run_phase(job_id, "slides", " ".join(slide_notes))

            self.store.add_event(
                job_id,
                "sync",
                "当前任务状态已广播到多端状态板，可由桌面端和移动端继续接管。",
                metadata={"skills": ["lark-event"]},
            )
            self._run_phase(job_id, "sync", self.skills.phase_summary(["lark-event"]))

            drive_summary = self._upload_delivery_artifacts_to_drive(
                job_id,
                [report_path, ppt_path] if ppt_path.exists() else [report_path],
            )

            manifest_path = delivery_dir / "manifest.json"
            artifact_urls = {artifact.kind: artifact.url for artifact in self.store.get_job(job_id).artifacts}
            write_json(manifest_path, build_manifest_payload(job.request, plan, brief, artifact_urls))
            self.store.add_artifact(
                job_id,
                ArtifactRef(
                    kind="manifest",
                    label="交付清单",
                    path=str(manifest_path),
                    url=f"/artifacts/{job_id}/delivery/manifest.json",
                ),
            )

            manifest_upload_summary = self._upload_delivery_artifacts_to_drive(job_id, [manifest_path])
            if manifest_upload_summary and drive_summary:
                drive_summary = f"{drive_summary} {manifest_upload_summary}"
            elif manifest_upload_summary:
                drive_summary = manifest_upload_summary

            artifact_urls = {artifact.kind: artifact.url for artifact in self.store.get_job(job_id).artifacts}
            write_json(manifest_path, build_manifest_payload(job.request, plan, brief, artifact_urls))

            delivery_notes = ["已生成报告、Slide 与交付清单。"]
            if drive_summary:
                delivery_notes.append(drive_summary)
            self._run_phase(job_id, "delivery", " ".join(delivery_notes))

            self.store.set_status(job_id, JobStatus.completed)
            self.store.add_event(job_id, "delivery", "任务已完成，可在任意端查看和交付。")
        except Exception as exc:
            self.store.set_status(job_id, JobStatus.failed, str(exc))
            self.store.add_event(job_id, "error", f"任务失败：{exc}", level="error")

    def _run_phase(self, job_id: str, step_id: str, summary: str) -> None:
        self.store.update_step(job_id, step_id, StepStatus.running)
        self.store.add_event(job_id, step_id, f"{step_id} 阶段执行中。")
        self.store.update_step(job_id, step_id, StepStatus.completed, summary)
        self.store.add_event(job_id, step_id, summary)

    def _sync_report_to_feishu_doc(self, job_id: str, report_path: Path, topic: str) -> str:
        if not _env_flag("LARK_DOC_SYNC_ENABLED", True):
            return ""

        status = self.lark_cli.status()
        if not status.installed or not status.configured:
            self.store.add_event(
                job_id,
                "document",
                "飞书 Doc 未同步：lark-cli 尚未完成配置。",
                level="warning",
            )
            return ""

        folder_token = os.getenv("LARK_DOC_FOLDER_TOKEN", "").strip()
        title = f"{topic} | Agent Pilot"
        result = self.lark_cli.create_doc_from_markdown(report_path, title, folder_token=folder_token)
        if result.get("ok"):
            data = result.get("data", {})
            doc_url = data.get("doc_url") or self.lark_cli.first_url(result)
            doc_id = data.get("doc_id", "")
            if doc_url:
                self.store.add_artifact(
                    job_id,
                    ArtifactRef(
                        kind="feishu_doc",
                        label="飞书 Doc 交付",
                        path=doc_id or doc_url,
                        url=doc_url,
                    ),
                )
            permission_grant = data.get("permission_grant", {})
            if permission_grant and permission_grant.get("status") == "failed":
                self.store.add_event(
                    job_id,
                    "document",
                    f"飞书 Doc 已创建，但自动授权失败：{permission_grant.get('message', '')}",
                    level="warning",
                )
            else:
                self.store.add_event(job_id, "document", "飞书 Doc 已创建并加入交付列表。")
            return "飞书 Doc 已同步。"

        self._record_lark_warning(job_id, "document", "飞书 Doc 同步失败", result)
        return ""

    def _sync_outline_to_feishu_slides(self, job_id: str, brief: ContentBrief) -> str:
        if not _env_flag("LARK_SLIDES_SYNC_ENABLED", False):
            return ""

        status = self.lark_cli.status()
        if not status.installed or not status.configured:
            self.store.add_event(
                job_id,
                "slides",
                "飞书 Slides 未同步：lark-cli 尚未完成配置。",
                level="warning",
            )
            return ""

        slides = [
            {"title": slide.title, "bullets": slide.bullets}
            for slide in brief.ppt_outline[:6]
        ] or [{"title": brief.topic or "Agent Pilot", "bullets": brief.summary[:4]}]
        result = self.lark_cli.create_slides_from_outline(f"{brief.topic or 'Agent Pilot'} | Slides", slides)
        if result.get("ok"):
            slide_url = self.lark_cli.first_url(result)
            if slide_url:
                self.store.add_artifact(
                    job_id,
                    ArtifactRef(
                        kind="feishu_slides",
                        label="飞书 Slides 交付",
                        path=slide_url,
                        url=slide_url,
                    ),
                )
            self.store.add_event(job_id, "slides", "飞书 Slides 已创建。")
            return "飞书 Slides 已同步。"

        self._record_lark_warning(job_id, "slides", "飞书 Slides 创建失败", result)
        return ""

    def _upload_delivery_artifacts_to_drive(self, job_id: str, files: list[Path]) -> str:
        if not _env_flag("LARK_DRIVE_UPLOAD_ENABLED", False):
            return ""

        status = self.lark_cli.status()
        if not status.installed or not status.configured:
            self.store.add_event(
                job_id,
                "delivery",
                "飞书 Drive 未上传：lark-cli 尚未完成配置。",
                level="warning",
            )
            return ""

        folder_token = os.getenv("LARK_DRIVE_FOLDER_TOKEN", "").strip()
        uploaded_count = 0
        for file_path in files:
            if not file_path.exists():
                continue
            result = self.lark_cli.upload_file(file_path, folder_token=folder_token, name=file_path.name)
            if result.get("ok"):
                uploaded_count += 1
                drive_url = self.lark_cli.first_url(result)
                self.store.add_artifact(
                    job_id,
                    ArtifactRef(
                        kind=f"feishu_drive_{file_path.stem}",
                        label=f"飞书 Drive：{file_path.name}",
                        path=str(file_path),
                        url=drive_url or f"/artifacts/{job_id}/delivery/{file_path.name}",
                    ),
                )
                self.store.add_event(job_id, "delivery", f"{file_path.name} 已上传到飞书 Drive。")
                continue

            self._record_lark_warning(job_id, "delivery", f"{file_path.name} 上传到飞书 Drive 失败", result)
            if self.lark_cli.missing_scope(result):
                break

        if uploaded_count:
            return f"飞书 Drive 已上传 {uploaded_count} 个交付文件。"
        return ""

    def _record_lark_warning(self, job_id: str, phase: str, prefix: str, result: dict[str, object]) -> None:
        message = self.lark_cli.error_message(result)
        scope = self.lark_cli.missing_scope(result)
        if scope:
            message = f"{message} 请先在飞书开放平台启用 scope `{scope}`。"
        self.store.add_event(job_id, phase, f"{prefix}：{message}", level="warning")


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
