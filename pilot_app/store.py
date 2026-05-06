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
    EditableInputState,
    EventRecord,
    InputUpdateRequest,
    JobCreateRequest,
    JobState,
    JobStatus,
    JobSummary,
    PlanStep,
    RepairChangeLevel,
    ScenarioId,
    SessionSource,
    StepStatus,
    SyncState,
    TaskRepairDecision,
    TaskRevisionRecord,
    now_iso,
)


class InputConflictError(Exception):
    def __init__(self, job: JobState) -> None:
        super().__init__("Task input conflict detected.")
        self.job = job


class MySQLJobStore:
    def __init__(self) -> None:
        self.host = os.getenv("MYSQL_HOST", "127.0.0.1")
        self.port = int(os.getenv("MYSQL_PORT", "3306"))
        self.user = os.getenv("MYSQL_USER", "root")
        self.password = os.getenv("MYSQL_PASSWORD", "")
        self.database = os.getenv("MYSQL_DATABASE", "lark_im")
        self.charset = os.getenv("MYSQL_CHARSET", "utf8mb4")
        self._lock = Lock()
        self._change_notifier: Callable[[JobState, str], None] | None = None
        self._init_db()

    def set_change_notifier(self, notifier: Callable[[JobState, str], None]) -> None:
        self._change_notifier = notifier

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
                editable_input=_build_editable_input(normalized_request, timestamp, normalized_request.device_label),
                acceptance=AcceptanceState(
                    criteria=_default_acceptance_criteria(normalized_request),
                    status=AcceptanceStatus.pending,
                ),
                available_actions=["run_scenarios", "confirm_acceptance"],
                devices=[device],
                sync_state=SyncState(active_devices=1, consistency="synced", last_event="Job created"),
            )
            self._save_locked(job)
            snapshot = job.model_copy(deep=True)
        self._notify_change(snapshot, "job.created")
        return snapshot

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
        self._mutate(job_id, lambda job: self._set_status(job, status, error_message), "job.updated")

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

        self._mutate(job_id, mutation, "job.plan.updated")

    def set_brief(self, job_id: str, brief: ContentBrief) -> None:
        self._mutate(job_id, lambda job: setattr(job, "brief", brief.model_copy(deep=True)), "job.brief.updated")

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

        self._mutate(job_id, mutation, "job.acceptance.updated")
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

        self._mutate(job_id, mutation, "job.step.updated")

    def add_artifact(self, job_id: str, artifact: ArtifactRef) -> None:
        def mutation(job: JobState) -> None:
            for item in job.artifacts:
                if item.kind == artifact.kind and item.url == artifact.url:
                    item.label = artifact.label
                    item.path = artifact.path
                    item.status = artifact.status or "active"
                    item.revision_id = artifact.revision_id
                    break
            else:
                job.artifacts.append(artifact)
            job.available_actions = _available_actions(job)

        self._mutate(job_id, mutation, "job.artifact.added")

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

        self._mutate(job_id, mutation, "job.event.added")

    def update_editable_input(self, job_id: str, update: InputUpdateRequest) -> JobState:
        with self._lock:
            job = self._load_locked(job_id)
            current = job.editable_input
            if update.base_version != current.version:
                conflict_message = (
                    f"{update.device_label} 提交的任务输入基于旧版本 v{update.base_version}，"
                    f"当前最新版本为 v{current.version}。"
                )
                job.events.append(
                    EventRecord(
                        timestamp=now_iso(),
                        phase="input",
                        message=conflict_message,
                        level="warning",
                        metadata={
                            "device_id": update.device_id,
                            "device_label": update.device_label,
                            "requested_version": update.base_version,
                            "current_version": current.version,
                        },
                    )
                )
                job.updated_at = now_iso()
                last_event = job.events[-1].message
                job.sync_state = SyncState(
                    active_devices=len(job.devices),
                    consistency="warning",
                    last_event=last_event,
                    pending_conflicts=[conflict_message],
                )
                self._save_locked(job)
                snapshot = job.model_copy(deep=True)
                self._notify_change(snapshot, "job.conflict.detected")
                raise InputConflictError(snapshot)

            timestamp = now_iso()
            context_snapshot = [source.model_copy(deep=True) for source in update.context_snapshot]
            job.request.instruction = update.instruction
            job.request.supplement = update.supplement
            job.request.session_sources = context_snapshot
            job.request.chat_text = _compose_chat_text(context_snapshot, update.supplement)
            job.editable_input = EditableInputState(
                instruction=update.instruction,
                supplement=update.supplement,
                context_snapshot=context_snapshot,
                version=current.version + 1,
                updated_at=timestamp,
                updated_by=update.device_label,
            )
            job.events.append(
                EventRecord(
                    timestamp=timestamp,
                    phase="input",
                    message=f"{update.device_label} 已更新任务输入到 v{job.editable_input.version}。",
                    metadata={"device_id": update.device_id, "platform": update.platform.value},
                )
            )
            job.updated_at = timestamp
            job.sync_state = SyncState(
                active_devices=len(job.devices),
                consistency="synced",
                last_event=job.events[-1].message,
                pending_conflicts=[],
            )
            self._save_locked(job)
            snapshot = job.model_copy(deep=True)
        self._notify_change(snapshot, "job.input.updated")
        return snapshot

    def append_revision(
        self,
        job_id: str,
        revision: TaskRevisionRecord,
        success_criteria: list[str] | None = None,
        scenario_ids: list[ScenarioId] | None = None,
    ) -> JobState:
        def mutation(job: JobState) -> None:
            job.current_revision_id = revision.revision_id
            job.revisions.append(revision)
            if success_criteria:
                job.success_criteria = list(success_criteria)
                job.acceptance.criteria = list(dict.fromkeys(success_criteria + job.acceptance.criteria))
            if scenario_ids is not None:
                job.scenario_ids = list(scenario_ids)
            job.available_actions = _available_actions(job)

        self._mutate(job_id, mutation, "job.revision.updated")
        return self.get_job(job_id)

    def mark_artifacts_stale(self, job_id: str, artifact_kinds: list[str]) -> JobState:
        def mutation(job: JobState) -> None:
            target = set(artifact_kinds)
            for artifact in job.artifacts:
                if artifact.kind in target:
                    artifact.status = "stale"
            job.available_actions = _available_actions(job)

        self._mutate(job_id, mutation, "job.artifact.stale")
        return self.get_job(job_id)

    def apply_repair_decision(
        self,
        job_id: str,
        decision: TaskRepairDecision,
        scenario_ids: list[ScenarioId],
        replacement_steps: list[PlanStep] | None = None,
    ) -> JobState:
        def mutation(job: JobState) -> None:
            rerun_set = set(decision.rerun_steps)
            drop_set = set(decision.drop_steps)
            keep_set = set(decision.keep_steps)
            existing_steps = {step.id: step.model_copy(deep=True) for step in job.steps}
            target_steps = replacement_steps or [step.model_copy(deep=True) for step in job.steps]
            for step in target_steps:
                previous = existing_steps.get(step.id)
                if step.id in rerun_set:
                    step.status = StepStatus.pending
                    step.output_summary = ""
                elif step.id in drop_set:
                    step.status = StepStatus.pending
                    step.output_summary = "本轮修正中暂不执行。"
                elif step.id in keep_set and previous is not None:
                    step.status = previous.status
                    step.output_summary = previous.output_summary
                elif previous is not None:
                    step.status = previous.status
                    step.output_summary = previous.output_summary
            job.steps = target_steps
            if decision.updated_success_criteria:
                job.success_criteria = list(decision.updated_success_criteria)
                job.acceptance.criteria = list(dict.fromkeys(decision.updated_success_criteria + job.acceptance.criteria))
            if rerun_set.intersection({"plan", "document", "slides", "delivery"}):
                job.brief = None
                job.acceptance.status = AcceptanceStatus.pending
                job.acceptance.result_summary = _acceptance_result(job)
            if scenario_ids:
                job.scenario_ids = list(scenario_ids)
            if rerun_set:
                job.status = JobStatus.queued
            job.available_actions = _available_actions(job)

        self._mutate(job_id, mutation, "job.repair.applied")
        return self.get_job(job_id)

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

        self._mutate(job_id, mutation, "job.sync.updated")
        self.add_event(
            job_id,
            "sync",
            f"{device_update.device_label} 已同步到当前任务状态。",
            metadata={"device_id": device_update.device_id, "platform": device_update.platform.value},
        )
        return self.get_job(job_id)

    def _mutate(self, job_id: str, mutation: Callable[[JobState], None], change_type: str) -> None:
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
            snapshot = job.model_copy(deep=True)
        self._notify_change(snapshot, change_type)

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

    def _notify_change(self, job: JobState, change_type: str) -> None:
        if self._change_notifier is None:
            return
        self._change_notifier(job, change_type)


def _merge_session_transcripts(request: JobCreateRequest) -> JobCreateRequest:
    merged = _compose_chat_text(request.session_sources, request.supplement, request.chat_text.strip())
    return request.model_copy(update={"chat_text": merged})


def _compose_chat_text(
    session_sources: list[SessionSource],
    supplement: str = "",
    base_chat_text: str = "",
) -> str:
    transcripts = [
        f"[{source.label or source.source_id or source.kind}]\n{source.transcript.strip()}"
        for source in session_sources
        if source.transcript.strip()
    ]
    merged_parts = [base_chat_text.strip(), *transcripts]
    if supplement.strip():
        merged_parts.append(f"[用户补充]\n{supplement.strip()}")
    return "\n\n".join([part for part in merged_parts if part])


def _build_editable_input(request: JobCreateRequest, timestamp: str, updated_by: str) -> EditableInputState:
    return EditableInputState(
        instruction=request.instruction,
        supplement=request.supplement,
        context_snapshot=[source.model_copy(deep=True) for source in request.session_sources],
        version=1,
        updated_at=timestamp,
        updated_by=updated_by,
    )


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
    if any(
        artifact.kind in {"report_markdown", "slides_preview", "pptx", "manifest"} and artifact.status == "active"
        for artifact in job.artifacts
    ):
        actions.append("open_artifacts")
    if job.status in {JobStatus.completed, JobStatus.failed}:
        actions.append("review_result")
    return list(dict.fromkeys(actions))
