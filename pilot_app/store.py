from __future__ import annotations

import json
import os
from threading import Lock
from typing import Callable
from uuid import uuid4

import pymysql
from pymysql.cursors import DictCursor

from .models import (
    AcceptanceState,
    AcceptanceStatus,
    ActiveEventRecord,
    ArtifactRef,
    ContentBrief,
    DeviceState,
    DeviceUpdateRequest,
    EventRecord,
    JobCreateRequest,
    JobState,
    JobStatus,
    JobSummary,
    PlanStep,
    ScenarioId,
    StepStatus,
    SyncState,
    now_iso,
)


class MySQLJobStore:
    def __init__(self) -> None:
        self.host = os.getenv("MYSQL_HOST", "127.0.0.1")
        self.port = int(os.getenv("MYSQL_PORT", "3306"))
        self.user = os.getenv("MYSQL_USER", "root")
        self.password = os.getenv("MYSQL_PASSWORD", "")
        self.database = os.getenv("MYSQL_DATABASE", "lark_im")
        self.charset = os.getenv("MYSQL_CHARSET", "utf8mb4")
        self._lock = Lock()
        self._init_db()

    def create_job(self, request: JobCreateRequest) -> JobState:
        with self._lock:
            job_id = uuid4().hex[:12]
            timestamp = now_iso()
            normalized_request = _merge_session_transcripts(request)
            device = DeviceState(
                device_id=normalized_request.device_id,
                device_label=normalized_request.device_label,
                platform=normalized_request.platform,
                last_seen_at=timestamp,
            )
            job = JobState(
                job_id=job_id,
                status=JobStatus.queued,
                created_at=timestamp,
                updated_at=timestamp,
                request=normalized_request,
                scenario_ids=normalized_request.scenario_ids,
                acceptance=AcceptanceState(
                    criteria=_default_acceptance_criteria(normalized_request),
                    status=AcceptanceStatus.pending,
                ),
                available_actions=["run_scenarios", "confirm_acceptance"],
                devices=[device],
                sync_state=SyncState(active_devices=1, consistency="synced", last_event="Job created"),
            )
            self._save_locked(job)
            return job.model_copy(deep=True)

    def get_job(self, job_id: str) -> JobState:
        with self._lock:
            return self._load_locked(job_id).model_copy(deep=True)

    def list_jobs(self) -> list[JobSummary]:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT payload FROM jobs ORDER BY created_at DESC")
                rows = cursor.fetchall()
        jobs = [self._decode_job(row["payload"]) for row in rows]
        return [
            JobSummary(
                job_id=job.job_id,
                status=job.status,
                created_at=job.created_at,
                updated_at=job.updated_at,
                topic=job.brief.topic if job.brief else "",
                instruction=job.request.instruction,
                scenario_ids=job.scenario_ids,
            )
            for job in jobs
        ]

    def list_events(self, scope: str = "running", limit: int = 40) -> list[ActiveEventRecord]:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT payload FROM jobs ORDER BY updated_at DESC")
                rows = cursor.fetchall()

        if scope == "completed":
            target_statuses = {JobStatus.completed}
        elif scope == "latest":
            target_statuses = {JobStatus.queued, JobStatus.running, JobStatus.completed, JobStatus.failed}
        else:
            target_statuses = {JobStatus.queued, JobStatus.running}

        events: list[ActiveEventRecord] = []
        for row in rows:
            job = self._decode_job(row["payload"])
            if job.status not in target_statuses:
                continue
            if not job.events:
                continue
            topic = job.brief.topic if job.brief else ""
            event = job.events[-1]
            events.append(
                ActiveEventRecord(
                    job_id=job.job_id,
                    status=job.status,
                    topic=topic,
                    instruction=job.request.instruction,
                    timestamp=event.timestamp,
                    phase=event.phase,
                    message=event.message,
                    level=event.level,
                )
            )

        events.sort(key=lambda item: item.timestamp, reverse=True)
        return events[: max(1, limit)]

    def list_active_events(self, limit: int = 40) -> list[ActiveEventRecord]:
        return self.list_events(scope="running", limit=limit)

    def set_status(self, job_id: str, status: JobStatus, error_message: str = "") -> None:
        self._mutate(job_id, lambda job: self._set_status(job, status, error_message))

    def set_plan(
        self,
        job_id: str,
        goal: str,
        success_criteria: list[str],
        clarification_questions: list[str],
        suggested_skills: list[str],
        steps: list[PlanStep],
    ) -> None:
        def mutation(job: JobState) -> None:
            job.goal = goal
            job.success_criteria = success_criteria
            job.clarification_questions = clarification_questions
            job.suggested_skills = suggested_skills
            job.steps = [step.model_copy(deep=True) for step in steps]
            if success_criteria:
                job.acceptance.criteria = list(dict.fromkeys(success_criteria + job.acceptance.criteria))
            job.available_actions = _available_actions(job)

        self._mutate(job_id, mutation)

    def set_brief(self, job_id: str, brief: ContentBrief) -> None:
        self._mutate(job_id, lambda job: setattr(job, "brief", brief.model_copy(deep=True)))

    def set_acceptance(
        self,
        job_id: str,
        criteria: list[str] | None = None,
        status: AcceptanceStatus | None = None,
        note: str = "",
        confirmed_by: str = "",
    ) -> JobState:
        def mutation(job: JobState) -> None:
            if criteria is not None:
                job.acceptance.criteria = list(criteria)
            if status is not None:
                job.acceptance.status = status
            if note:
                job.acceptance.note = note
            if confirmed_by:
                job.acceptance.confirmed_by = confirmed_by
                job.acceptance.confirmed_at = now_iso()
            job.acceptance.result_summary = _acceptance_result(job)
            job.available_actions = _available_actions(job)

        self._mutate(job_id, mutation)
        return self.get_job(job_id)

    def update_step(self, job_id: str, step_id: str, status: StepStatus, output_summary: str = "") -> None:
        def mutation(job: JobState) -> None:
            for step in job.steps:
                if step.id == step_id:
                    step.status = status
                    if output_summary:
                        step.output_summary = output_summary
                    break
            job.available_actions = _available_actions(job)

        self._mutate(job_id, mutation)

    def add_artifact(self, job_id: str, artifact: ArtifactRef) -> None:
        def mutation(job: JobState) -> None:
            existing = {(item.kind, item.url) for item in job.artifacts}
            if (artifact.kind, artifact.url) not in existing:
                job.artifacts.append(artifact)
            job.available_actions = _available_actions(job)

        self._mutate(job_id, mutation)

    def add_event(
        self,
        job_id: str,
        phase: str,
        message: str,
        level: str = "info",
        metadata: dict[str, object] | None = None,
    ) -> None:
        def mutation(job: JobState) -> None:
            job.events.append(
                EventRecord(
                    timestamp=now_iso(),
                    phase=phase,
                    message=message,
                    level=level,
                    metadata=metadata or {},
                )
            )

        self._mutate(job_id, mutation)

    def upsert_device(self, job_id: str, device_update: DeviceUpdateRequest) -> JobState:
        def mutation(job: JobState) -> None:
            timestamp = now_iso()
            for device in job.devices:
                if device.device_id == device_update.device_id:
                    device.device_label = device_update.device_label
                    device.platform = device_update.platform
                    device.current_view = device_update.current_view
                    device.note = device_update.note
                    device.last_seen_at = timestamp
                    device.status = "online"
                    return

            job.devices.append(
                DeviceState(
                    device_id=device_update.device_id,
                    device_label=device_update.device_label,
                    platform=device_update.platform,
                    current_view=device_update.current_view,
                    note=device_update.note,
                    last_seen_at=timestamp,
                )
            )

        self._mutate(job_id, mutation)
        self.add_event(
            job_id,
            "sync",
            f"{device_update.device_label} 已同步到当前任务状态。",
            metadata={"device_id": device_update.device_id, "platform": device_update.platform.value},
        )
        return self.get_job(job_id)

    def _mutate(self, job_id: str, mutation: Callable[[JobState], None]) -> None:
        with self._lock:
            job = self._load_locked(job_id)
            mutation(job)
            job.updated_at = now_iso()
            last_event = job.events[-1].message if job.events else job.sync_state.last_event
            job.sync_state = SyncState(
                active_devices=len(job.devices),
                consistency="synced",
                last_event=last_event,
                pending_conflicts=[],
            )
            self._save_locked(job)

    def _init_db(self) -> None:
        with self._connect(database=False) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{self.database}` "
                    f"DEFAULT CHARACTER SET {self.charset} COLLATE {self.charset}_unicode_ci"
                )
            conn.commit()

        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS jobs (
                        job_id VARCHAR(32) PRIMARY KEY,
                        status VARCHAR(32) NOT NULL,
                        created_at VARCHAR(64) NOT NULL,
                        updated_at VARCHAR(64) NOT NULL,
                        payload JSON NOT NULL,
                        INDEX idx_jobs_created_at (created_at),
                        INDEX idx_jobs_status (status)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
            conn.commit()

    def _connect(self, database: bool = True):
        kwargs = {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "charset": self.charset,
            "cursorclass": DictCursor,
            "autocommit": False,
        }
        if database:
            kwargs["database"] = self.database
        return pymysql.connect(**kwargs)

    def _load_locked(self, job_id: str) -> JobState:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT payload FROM jobs WHERE job_id = %s", (job_id,))
                row = cursor.fetchone()
        if row is None:
            raise KeyError(job_id)
        return self._decode_job(row["payload"])

    def _save_locked(self, job: JobState) -> None:
        payload = json.dumps(job.model_dump(mode="json"), ensure_ascii=False)
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO jobs (job_id, status, created_at, updated_at, payload)
                    VALUES (%s, %s, %s, %s, CAST(%s AS JSON))
                    ON DUPLICATE KEY UPDATE
                        status = VALUES(status),
                        updated_at = VALUES(updated_at),
                        payload = VALUES(payload)
                    """,
                    (job.job_id, job.status.value, job.created_at, job.updated_at, payload),
                )
            conn.commit()

    @staticmethod
    def _decode_job(payload: object) -> JobState:
        if isinstance(payload, (bytes, bytearray)):
            payload = payload.decode("utf-8")
        if not isinstance(payload, str):
            payload = json.dumps(payload, ensure_ascii=False)
        return JobState.model_validate(json.loads(payload))

    @staticmethod
    def _set_status(job: JobState, status: JobStatus, error_message: str) -> None:
        job.status = status
        job.error_message = error_message
        job.acceptance.result_summary = _acceptance_result(job)
        job.available_actions = _available_actions(job)


def _merge_session_transcripts(request: JobCreateRequest) -> JobCreateRequest:
    transcripts = [
        f"[{source.label or source.source_id or source.kind}]\n{source.transcript.strip()}"
        for source in request.session_sources
        if source.transcript.strip()
    ]
    if not transcripts:
        return request
    merged = "\n\n".join([part for part in [request.chat_text.strip(), *transcripts] if part])
    return request.model_copy(update={"chat_text": merged})


def _default_acceptance_criteria(request: JobCreateRequest) -> list[str]:
    criteria = [
        "覆盖 IM 入口、文档生成、演示稿或自由画布交付。",
        "Agent 输出任务拆解、执行步骤和可验收结果。",
        "桌面端与移动端可查看同一任务状态与产物。",
    ]
    if request.session_sources:
        criteria.append("多个飞书群聊/单聊上下文已合并进入任务输入。")
    return criteria


def _acceptance_result(job: JobState) -> str:
    required = {"intake", "plan", "document", "slides", "delivery"}
    completed = {step.id for step in job.steps if step.status == StepStatus.completed}
    if job.status == JobStatus.completed and required.intersection(completed):
        return "Agent 已完成已选择场景，并生成可交付产物。"
    if completed:
        return f"已完成 {len(completed)} 个场景，等待剩余场景或人工确认。"
    return "等待 Agent 执行场景并生成验收证据。"


def _available_actions(job: JobState) -> list[str]:
    actions = ["run_scenarios", "confirm_acceptance"]
    if any(artifact.kind in {"report_markdown", "slides_preview", "pptx", "manifest"} for artifact in job.artifacts):
        actions.append("open_artifacts")
    if job.status in {JobStatus.completed, JobStatus.failed}:
        actions.append("review_result")
    return list(dict.fromkeys(actions))
