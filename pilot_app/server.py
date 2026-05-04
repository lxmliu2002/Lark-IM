from __future__ import annotations

from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from .harness import AgentHarness
from .lark_cli import LarkCLIClient
from .llm import LLMJsonClient
from .models import (
    DeviceUpdateRequest,
    JobAccepted,
    JobCreateRequest,
    JobState,
    JobSummary,
    LarkConnectionStatus,
    LarkIMJobAccepted,
    LarkIMJobRequest,
    LarkIMPreview,
    SkillDefinition,
)
from .planner import AgentPlanner
from .skills import LarkSkillRegistry
from .store import InMemoryJobStore

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = BASE_DIR / "outputs" / "jobs"
WEB_UI_PATH = BASE_DIR / "web_ui.html"
MOBILE_UI_PATH = BASE_DIR / "mobile_ui.html"

OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

store = InMemoryJobStore()
llm_client = LLMJsonClient()
planner = AgentPlanner(llm_client)
lark_cli_client = LarkCLIClient(BASE_DIR)
skill_registry = LarkSkillRegistry(lark_cli_client)
harness = AgentHarness(store, planner, llm_client, lark_cli_client, skill_registry, OUTPUT_ROOT)

app = FastAPI(title="Agent Pilot Demo", version="2.0.0")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return WEB_UI_PATH.read_text(encoding="utf-8")


@app.get("/mobile", response_class=HTMLResponse)
def mobile_home() -> str:
    return MOBILE_UI_PATH.read_text(encoding="utf-8")


@app.get("/health")
def health() -> dict[str, object]:
    lark_status = lark_cli_client.status()
    return {
        "ok": True,
        "llm_enabled": llm_client.enabled,
        "lark_cli_available": skill_registry.cli_available,
        "lark_mode": lark_status.mode,
        "jobs": len(store.list_jobs()),
    }


@app.get("/api/skills", response_model=list[SkillDefinition])
def list_skills() -> list[SkillDefinition]:
    return skill_registry.list_skills()


@app.get("/api/lark/status", response_model=LarkConnectionStatus)
def lark_status() -> LarkConnectionStatus:
    return lark_cli_client.status()


@app.get("/api/lark/search-users")
def lark_search_users(q: str):
    return lark_cli_client.search_user(q)


@app.post("/api/lark/im/preview", response_model=LarkIMPreview)
def preview_lark_im(req: LarkIMJobRequest) -> LarkIMPreview:
    preview = lark_cli_client.build_chat_transcript(
        chat_id=req.chat_id,
        user_id=req.user_id,
        message_limit=req.message_limit,
    )
    if not preview.get("ok"):
        raise HTTPException(status_code=400, detail=lark_cli_client.error_message(preview))
    return LarkIMPreview(
        source_label=str(preview.get("source_label", "")),
        message_count=int(preview.get("message_count", 0)),
        chat_text=str(preview.get("chat_text", "")),
    )


@app.post("/api/lark/im/jobs", response_model=LarkIMJobAccepted)
def create_job_from_lark_im(req: LarkIMJobRequest, background_tasks: BackgroundTasks) -> LarkIMJobAccepted:
    preview = lark_cli_client.build_chat_transcript(
        chat_id=req.chat_id,
        user_id=req.user_id,
        message_limit=req.message_limit,
    )
    if not preview.get("ok"):
        raise HTTPException(status_code=400, detail=lark_cli_client.error_message(preview))

    chat_text = str(preview.get("chat_text", "")).strip()
    if not chat_text:
        raise HTTPException(status_code=400, detail="No readable IM messages were found in the selected chat.")

    job = store.create_job(
        JobCreateRequest(
            source="lark",
            instruction=req.instruction,
            chat_text=chat_text,
            preferred_output=req.preferred_output,
            client_id=req.client_id,
            device_id=req.device_id,
            device_label=req.device_label,
            platform=req.platform,
        )
    )
    store.add_event(
        job.job_id,
        "intake",
        f"已从飞书会话 {preview.get('source_label', '')} 拉取 {preview.get('message_count', 0)} 条消息。",
        metadata={"source_label": preview.get("source_label", ""), "message_count": preview.get("message_count", 0)},
    )
    if req.send_ack_to_chat:
        ack_result = lark_cli_client.send_message(
            chat_id=req.chat_id,
            user_id=req.user_id,
            markdown=(
                f"Agent Pilot 已接收任务。\n"
                f"- job_id: `{job.job_id}`\n"
                f"- 已拉取消息数: `{preview.get('message_count', 0)}`\n"
                f"- 查询地址: `http://127.0.0.1:8000/api/jobs/{job.job_id}`"
            ),
        )
        if not ack_result.get("ok"):
            store.add_event(
                job.job_id,
                "intake",
                f"飞书会话确认消息发送失败：{lark_cli_client.error_message(ack_result)}",
                level="warning",
            )

    background_tasks.add_task(harness.run_job, job.job_id)
    return LarkIMJobAccepted(
        job_id=job.job_id,
        status=job.status,
        poll_url=f"/api/jobs/{job.job_id}",
        source_label=str(preview.get("source_label", "")),
        message_count=int(preview.get("message_count", 0)),
    )


@app.get("/api/jobs", response_model=list[JobSummary])
def list_jobs() -> list[JobSummary]:
    return store.list_jobs()


@app.post("/api/jobs", response_model=JobAccepted)
def create_job(req: JobCreateRequest, background_tasks: BackgroundTasks) -> JobAccepted:
    job = store.create_job(req)
    background_tasks.add_task(harness.run_job, job.job_id)
    return JobAccepted(job_id=job.job_id, status=job.status, poll_url=f"/api/jobs/{job.job_id}")


@app.get("/api/jobs/{job_id}", response_model=JobState)
def get_job(job_id: str) -> JobState:
    try:
        return store.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc


@app.post("/api/jobs/{job_id}/devices", response_model=JobState)
def sync_device(job_id: str, req: DeviceUpdateRequest) -> JobState:
    try:
        return store.upsert_device(job_id, req)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc


@app.get("/artifacts/{job_id}/{artifact_path:path}")
def read_artifact(job_id: str, artifact_path: str):
    job_dir = (OUTPUT_ROOT / Path(job_id).name).resolve()
    target = (job_dir / artifact_path).resolve()
    if job_dir not in target.parents and target != job_dir:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return FileResponse(path=target, filename=target.name)
