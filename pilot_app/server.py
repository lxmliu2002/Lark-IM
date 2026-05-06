from __future__ import annotations

import asyncio
import io
import mimetypes
import zipfile
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse

from .conversation import TaskConversationService
from .harness import AgentHarness
from .lark_cli import LarkCLIClient
from .llm import LLMJsonClient
from .models import (
    AcceptanceStatus,
    ActiveEventRecord,
    AcceptanceUpdateRequest,
    BotWebhookAccepted,
    BotWebhookRequest,
    ConversationRequest,
    ConversationResponse,
    DeviceUpdateRequest,
    JobAccepted,
    JobCreateRequest,
    JobState,
    JobSummary,
    InputUpdateRequest,
    LarkConnectionStatus,
    LarkIMJobAccepted,
    LarkIMJobRequest,
    LarkIMPreview,
    LarkSessionPreviewRequest,
    LarkSessionSearchResult,
    ScenarioRunRequest,
    SessionSource,
    SkillDefinition,
)
from .planner import AgentPlanner
from .realtime import RealtimeHub
from .skills import LarkSkillRegistry
from .store import InputConflictError, MySQLJobStore

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = BASE_DIR / "outputs" / "jobs"
WEB_UI_PATH = BASE_DIR / "web_ui.html"
MOBILE_UI_PATH = BASE_DIR / "mobile_ui.html"

OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

store = MySQLJobStore()
llm_client = LLMJsonClient()
planner = AgentPlanner(llm_client)
lark_cli_client = LarkCLIClient(BASE_DIR)
skill_registry = LarkSkillRegistry(lark_cli_client)
harness = AgentHarness(store, planner, llm_client, lark_cli_client, skill_registry, OUTPUT_ROOT)
realtime_hub = RealtimeHub()
conversation_service = TaskConversationService(store, planner, llm_client, harness)

app = FastAPI(title="Agent Pilot Demo", version="2.0.0")


def _publish_job_change(job: JobState, change_type: str) -> None:
    realtime_hub.publish_job(
        job.job_id,
        change_type,
        {"job": job.model_dump(mode="json")},
    )
    for scope in ("latest", "running", "completed"):
        realtime_hub.publish_events(
            scope,
            {"scope": scope, "events": [event.model_dump(mode="json") for event in store.list_events(scope=scope, limit=40)]},
        )


store.set_change_notifier(_publish_job_change)


@app.on_event("startup")
async def bind_realtime_loop() -> None:
    realtime_hub.bind_loop(asyncio.get_running_loop())


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return WEB_UI_PATH.read_text(encoding="utf-8")


@app.get("/mobile", response_class=HTMLResponse)
def mobile_home(request: Request):
    target = "/"
    if request.url.query:
        target = f"/?{request.url.query}"
    return RedirectResponse(url=target, status_code=307)


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


@app.get("/api/lark/session-sources", response_model=list[LarkSessionSearchResult])
def search_lark_session_sources(q: str = "") -> list[LarkSessionSearchResult]:
    results: list[LarkSessionSearchResult] = []
    chat_result = lark_cli_client.search_chats(q, page_size=8) if q else {}
    if chat_result.get("ok"):
        chat_data = chat_result.get("data") or {}
        chat_items = (chat_data.get("chats") or chat_data.get("items") or [])[:8]
        results.extend(
            [
                LarkSessionSearchResult(
                    kind="chat",
                    source_id=str(item.get("chat_id") or item.get("chatId") or ""),
                    label=str(item.get("name") or item.get("chat_name") or item.get("chatName") or "飞书群聊"),
                    available=True,
                    note="来自飞书群聊查询。",
                )
                for item in chat_items
                if item.get("chat_id") or item.get("chatId")
            ]
        )

    user_result = lark_cli_client.search_user(q) if q else {}
    if user_result.get("ok"):
        users = ((user_result.get("data") or {}).get("users") or [])[:5]
        results.extend(
            [
                LarkSessionSearchResult(
                    kind="user",
                    source_id=str(user.get("open_id") or user.get("user_id") or ""),
                    label=str(user.get("localized_name") or user.get("name") or user.get("email") or "飞书用户"),
                    available=True,
                    note="来自飞书通讯录查询。",
                )
                for user in users
                if user.get("open_id") or user.get("user_id")
            ]
        )

    if results:
        deduped: list[LarkSessionSearchResult] = []
        seen: set[tuple[str, str]] = set()
        for item in results:
            key = (item.kind, item.source_id)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    return []


@app.post("/api/lark/session-sources/preview", response_model=LarkIMPreview)
def preview_lark_session_source(req: LarkSessionPreviewRequest) -> LarkIMPreview:
    preview = lark_cli_client.build_session_transcript(
        kind=req.kind,
        source_id=req.source_id,
        message_limit=req.message_limit,
        label=req.label,
    )
    if not preview.get("ok"):
        raise HTTPException(status_code=400, detail=lark_cli_client.error_message(preview))
    return LarkIMPreview(
        source_label=str(preview.get("source_label", req.label or req.source_id)),
        message_count=int(preview.get("message_count", 0)),
        chat_text=str(preview.get("chat_text", "")),
    )


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
            session_sources=req.session_sources,
            scenario_ids=req.scenario_ids,
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


@app.get("/api/events/active", response_model=list[ActiveEventRecord])
def list_active_events(limit: int = Query(40, ge=1, le=200)) -> list[ActiveEventRecord]:
    return store.list_active_events(limit=limit)


@app.get("/api/events", response_model=list[ActiveEventRecord])
def list_events(
    scope: str = Query("running", pattern="^(latest|completed|running)$"),
    limit: int = Query(40, ge=1, le=200),
) -> list[ActiveEventRecord]:
    return store.list_events(scope=scope, limit=limit)


@app.post("/api/jobs", response_model=JobAccepted)
def create_job(req: JobCreateRequest, background_tasks: BackgroundTasks) -> JobAccepted:
    job = store.create_job(req)
    if req.auto_run:
        background_tasks.add_task(harness.run_job, job.job_id)
    return JobAccepted(job_id=job.job_id, status=job.status, poll_url=f"/api/jobs/{job.job_id}")


@app.get("/api/jobs/{job_id}", response_model=JobState)
def get_job(job_id: str) -> JobState:
    try:
        return store.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc


@app.patch("/api/jobs/{job_id}/input", response_model=JobState)
def update_job_input(job_id: str, req: InputUpdateRequest, background_tasks: BackgroundTasks):
    try:
        previous_job = store.get_job(job_id)
        updated_job = store.update_editable_input(job_id, req)
        background_tasks.add_task(harness.repair_job, job_id, previous_job.request.model_copy(deep=True))
        return updated_job
    except InputConflictError as exc:
        latest_job = exc.job
        return JSONResponse(
            status_code=409,
            content={
                "detail": {
                    "type": "input_conflict",
                    "message": "任务输入已被其他端更新，请重新加载后再修改。",
                    "job": latest_job.model_dump(mode="json"),
                    "editable_input": latest_job.editable_input.model_dump(mode="json"),
                }
            },
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc


@app.post("/api/jobs/{job_id}/conversation", response_model=ConversationResponse)
def talk_to_job(job_id: str, req: ConversationRequest) -> ConversationResponse:
    try:
        return conversation_service.handle(job_id, req)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc


@app.post("/api/jobs/{job_id}/devices", response_model=JobState)
def sync_device(job_id: str, req: DeviceUpdateRequest) -> JobState:
    try:
        return store.upsert_device(job_id, req)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc


@app.post("/api/jobs/{job_id}/scenarios", response_model=JobState)
def run_job_scenarios(job_id: str, req: ScenarioRunRequest) -> JobState:
    try:
        store.add_event(
            job_id,
            "scenario",
            f"{req.platform.value} 端触发场景：{', '.join(item.value for item in req.scenario_ids)}。",
            metadata={"device_id": req.device_id, "note": req.note},
        )
        harness.run_scenarios(job_id, req.scenario_ids, finalize=False)
        return store.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc


@app.post("/api/jobs/{job_id}/acceptance", response_model=JobState)
def confirm_acceptance(job_id: str, req: AcceptanceUpdateRequest) -> JobState:
    try:
        status = AcceptanceStatus.confirmed if req.confirmed else AcceptanceStatus.pending
        job = store.set_acceptance(job_id, status=status, note=req.note, confirmed_by=req.confirmed_by)
        store.add_event(
            job_id,
            "acceptance",
            "验收标准已确认。" if req.confirmed else "验收标准已退回继续调整。",
            metadata={"note": req.note, "confirmed_by": req.confirmed_by},
        )
        return store.get_job(job.job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc


@app.post("/api/bot/webhook", response_model=BotWebhookAccepted)
def bot_webhook(req: BotWebhookRequest, background_tasks: BackgroundTasks) -> BotWebhookAccepted:
    instruction = req.instruction.strip() or req.text.strip() or "飞书机器人入口任务"
    source_label = req.chat_id or req.user_id or req.sender_id or "lark-bot"
    job = store.create_job(
        JobCreateRequest(
            source="lark",
            instruction=instruction,
            chat_text=req.text,
            session_sources=[
                SessionSource(
                    kind="chat" if req.chat_id else "user",
                    source_id=source_label,
                    label=f"机器人入口 {source_label}",
                    transcript=req.text,
                )
            ],
            client_id="lark-bot-webhook",
            device_id="lark-bot",
            device_label="Lark Bot",
        )
    )
    store.add_event(
        job.job_id,
        "bot",
        "飞书机器人 webhook 已预留接入，本次请求已转为 Agent 任务。",
        metadata={"event_id": req.event_id, "sender_id": req.sender_id},
    )
    if job.request.auto_run:
        background_tasks.add_task(harness.run_job, job.job_id)
    return BotWebhookAccepted(
        job_id=job.job_id,
        status=job.status,
        poll_url=f"/api/jobs/{job.job_id}",
        reply_mode="reserved",
        event_id=req.event_id,
    )


@app.get("/artifacts/{job_id}/{artifact_path:path}")
def read_artifact(job_id: str, artifact_path: str, download: bool = Query(False)):
    job_dir = (OUTPUT_ROOT / Path(job_id).name).resolve()
    target = (job_dir / artifact_path).resolve()
    if job_dir not in target.parents and target != job_dir:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found.")
    media_type, _ = mimetypes.guess_type(str(target))
    inline_suffixes = {".html", ".htm", ".md", ".json", ".txt", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
    filename = target.name if download or target.suffix.lower() not in inline_suffixes else None
    return FileResponse(path=target, filename=filename, media_type=media_type)


@app.get("/api/jobs/{job_id}/artifacts.zip")
def download_job_artifacts(job_id: str):
    job_dir = (OUTPUT_ROOT / Path(job_id).name).resolve()
    if not job_dir.exists() or not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="Job artifacts not found.")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(job_dir.rglob("*")):
            if not file_path.is_file():
                continue
            archive.write(file_path, arcname=str(file_path.relative_to(job_dir)))

    buffer.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="{Path(job_id).name}-artifacts.zip"'}
    return StreamingResponse(buffer, media_type="application/zip", headers=headers)


@app.websocket("/ws/jobs/{job_id}")
async def job_updates_socket(websocket: WebSocket, job_id: str) -> None:
    try:
        job = store.get_job(job_id)
    except KeyError:
        await websocket.accept()
        await websocket.send_json(
            {
                "type": "job.missing",
                "job_id": job_id,
                "scope": "job",
                "timestamp": "",
                "payload": {"message": "Job not found."},
            }
        )
        await websocket.close(code=4404)
        return

    await realtime_hub.connect_job(job_id, websocket)
    await websocket.send_json(
        {
            "type": "job.updated",
            "job_id": job_id,
            "scope": "job",
            "timestamp": "",
            "payload": {"job": job.model_dump(mode="json")},
        }
    )
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await realtime_hub.disconnect_job(job_id, websocket)


@app.websocket("/ws/events/{scope}")
async def events_socket(websocket: WebSocket, scope: str) -> None:
    if scope not in {"latest", "running", "completed"}:
        await websocket.accept()
        await websocket.send_json(
            {
                "type": "events.invalid_scope",
                "job_id": "",
                "scope": scope,
                "timestamp": "",
                "payload": {"message": "Unsupported scope."},
            }
        )
        await websocket.close(code=4400)
        return

    await realtime_hub.connect_events(scope, websocket)
    await websocket.send_json(
        {
            "type": "events.updated",
            "job_id": "",
            "scope": scope,
            "timestamp": "",
            "payload": {"scope": scope, "events": [event.model_dump(mode="json") for event in store.list_events(scope=scope, limit=40)]},
        }
    )
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await realtime_hub.disconnect_events(scope, websocket)
