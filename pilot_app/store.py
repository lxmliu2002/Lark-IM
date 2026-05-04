from __future__ import annotations

from threading import Lock
from uuid import uuid4

from .models import (
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
    StepStatus,
    SyncState,
    now_iso,
)


class InMemoryJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._lock = Lock()

    def create_job(self, request: JobCreateRequest) -> JobState:
        with self._lock:
            job_id = uuid4().hex[:12]
            timestamp = now_iso()
            device = DeviceState(
                device_id=request.device_id,
                device_label=request.device_label,
                platform=request.platform,
                last_seen_at=timestamp,
            )
            job = JobState(
                job_id=job_id,
                status=JobStatus.queued,
                created_at=timestamp,
                updated_at=timestamp,
                request=request,
                devices=[device],
                sync_state=SyncState(active_devices=1, consistency="synced", last_event="Job created"),
            )
            self._jobs[job_id] = job
            return job.model_copy(deep=True)

    def get_job(self, job_id: str) -> JobState:
        with self._lock:
            job = self._jobs[job_id]
            return job.model_copy(deep=True)

    def list_jobs(self) -> list[JobSummary]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda item: item.created_at, reverse=True)
            return [
                JobSummary(
                    job_id=job.job_id,
                    status=job.status,
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                    topic=job.brief.topic if job.brief else "",
                    instruction=job.request.instruction,
                )
                for job in jobs
            ]

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

        self._mutate(job_id, mutation)

    def set_brief(self, job_id: str, brief: ContentBrief) -> None:
        self._mutate(job_id, lambda job: setattr(job, "brief", brief.model_copy(deep=True)))

    def update_step(self, job_id: str, step_id: str, status: StepStatus, output_summary: str = "") -> None:
        def mutation(job: JobState) -> None:
            for step in job.steps:
                if step.id == step_id:
                    step.status = status
                    if output_summary:
                        step.output_summary = output_summary
                    break

        self._mutate(job_id, mutation)

    def add_artifact(self, job_id: str, artifact: ArtifactRef) -> None:
        def mutation(job: JobState) -> None:
            job.artifacts.append(artifact)

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

    def _mutate(self, job_id: str, mutation) -> None:
        with self._lock:
            job = self._jobs[job_id]
            mutation(job)
            job.updated_at = now_iso()
            last_event = job.events[-1].message if job.events else job.sync_state.last_event
            job.sync_state = SyncState(
                active_devices=len(job.devices),
                consistency="synced",
                last_event=last_event,
                pending_conflicts=[],
            )

    @staticmethod
    def _set_status(job: JobState, status: JobStatus, error_message: str) -> None:
        job.status = status
        job.error_message = error_message
