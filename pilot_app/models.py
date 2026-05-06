from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class StepStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class Platform(str, Enum):
    desktop = "desktop"
    mobile = "mobile"


class EntrySource(str, Enum):
    im = "im"
    lark = "lark"
    manual = "manual"


class DeliveryMode(str, Enum):
    report = "report"
    slides = "slides"
    both = "both"


class RepairChangeLevel(str, Enum):
    minor = "minor"
    partial_replan = "partial_replan"
    full_replan = "full_replan"


class ScenarioId(str, Enum):
    intake = "intake"
    plan = "plan"
    document = "document"
    slides = "slides"
    sync = "sync"
    delivery = "delivery"


class AcceptanceStatus(str, Enum):
    draft = "draft"
    pending = "pending"
    confirmed = "confirmed"
    passed = "passed"
    failed = "failed"


class SessionSource(BaseModel):
    kind: str = "chat"
    source_id: str = ""
    label: str = ""
    transcript: str = ""


class AcceptanceState(BaseModel):
    criteria: list[str] = Field(default_factory=list)
    status: AcceptanceStatus = AcceptanceStatus.draft
    confirmed_by: str = ""
    confirmed_at: str = ""
    result_summary: str = ""
    note: str = ""


class ActionItem(BaseModel):
    task: str
    owner: str = ""
    deadline: str = ""
    status: str = ""


class OwnerRole(BaseModel):
    name: str
    responsibility: str


class DeadlineItem(BaseModel):
    item: str
    due: str


class OutlineSlide(BaseModel):
    title: str
    bullets: list[str] = Field(default_factory=list)


class DocumentSection(BaseModel):
    title: str
    body: str


class ContentBrief(BaseModel):
    topic: str
    objective: str = ""
    audience: str = ""
    summary: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    owners: list[OwnerRole] = Field(default_factory=list)
    deadlines: list[DeadlineItem] = Field(default_factory=list)
    document_sections: list[DocumentSection] = Field(default_factory=list)
    ppt_outline: list[OutlineSlide] = Field(default_factory=list)
    delivery_notes: list[str] = Field(default_factory=list)


class EditableInputState(BaseModel):
    instruction: str = ""
    supplement: str = ""
    context_snapshot: list["SessionSource"] = Field(default_factory=list)
    version: int = 1
    updated_at: str = ""
    updated_by: str = ""


class JobCreateRequest(BaseModel):
    source: EntrySource = EntrySource.im
    instruction: str
    chat_text: str = ""
    voice_text: str = ""
    supplement: str = ""
    preferred_output: DeliveryMode = DeliveryMode.both
    session_sources: list[SessionSource] = Field(default_factory=list)
    scenario_ids: list[ScenarioId] = Field(default_factory=list)
    auto_run: bool = True
    client_id: str = "web-console"
    device_id: str = "desktop-console"
    device_label: str = "Desktop Console"
    platform: Platform = Platform.desktop


class DeviceUpdateRequest(BaseModel):
    device_id: str
    device_label: str
    platform: Platform
    current_view: str = "dashboard"
    note: str = ""


class PlanStep(BaseModel):
    id: str
    name: str
    description: str
    skills: list[str] = Field(default_factory=list)
    status: StepStatus = StepStatus.pending
    output_summary: str = ""


class PlanningResult(BaseModel):
    goal: str
    success_criteria: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)
    suggested_skills: list[str] = Field(default_factory=list)
    steps: list[PlanStep] = Field(default_factory=list)


class ArtifactRef(BaseModel):
    kind: str
    label: str
    path: str
    url: str
    status: str = "active"
    revision_id: str = ""


class TaskRepairDecision(BaseModel):
    change_level: RepairChangeLevel = RepairChangeLevel.partial_replan
    summary: str = ""
    reasoning: list[str] = Field(default_factory=list)
    keep_steps: list[str] = Field(default_factory=list)
    rerun_steps: list[str] = Field(default_factory=list)
    add_steps: list[str] = Field(default_factory=list)
    drop_steps: list[str] = Field(default_factory=list)
    invalidate_artifact_kinds: list[str] = Field(default_factory=list)
    updated_success_criteria: list[str] = Field(default_factory=list)


class TaskRevisionRecord(BaseModel):
    revision_id: str
    created_at: str
    trigger: str = "input_update"
    summary: str = ""
    change_level: RepairChangeLevel = RepairChangeLevel.partial_replan
    based_on_input_version: int = 1


class DeviceState(BaseModel):
    device_id: str
    device_label: str
    platform: Platform
    current_view: str = "dashboard"
    note: str = ""
    last_seen_at: str
    status: str = "online"


class EventRecord(BaseModel):
    timestamp: str
    phase: str
    message: str
    level: str = "info"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActiveEventRecord(BaseModel):
    job_id: str
    status: JobStatus
    topic: str = ""
    instruction: str = ""
    timestamp: str
    phase: str
    message: str
    level: str = "info"


class SyncState(BaseModel):
    active_devices: int = 0
    consistency: str = "synced"
    last_event: str = ""
    pending_conflicts: list[str] = Field(default_factory=list)


class JobState(BaseModel):
    job_id: str
    status: JobStatus
    created_at: str
    updated_at: str
    request: JobCreateRequest
    goal: str = ""
    success_criteria: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)
    suggested_skills: list[str] = Field(default_factory=list)
    scenario_ids: list[ScenarioId] = Field(default_factory=lambda: list(ScenarioId))
    editable_input: EditableInputState = Field(default_factory=EditableInputState)
    current_revision_id: str = "rev-1"
    revisions: list[TaskRevisionRecord] = Field(default_factory=list)
    acceptance: AcceptanceState = Field(default_factory=AcceptanceState)
    available_actions: list[str] = Field(default_factory=list)
    steps: list[PlanStep] = Field(default_factory=list)
    brief: Optional[ContentBrief] = None
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    devices: list[DeviceState] = Field(default_factory=list)
    events: list[EventRecord] = Field(default_factory=list)
    sync_state: SyncState = Field(default_factory=SyncState)
    error_message: str = ""


class JobAccepted(BaseModel):
    job_id: str
    status: JobStatus
    poll_url: str


class LarkIMJobRequest(BaseModel):
    instruction: str
    chat_id: str = ""
    user_id: str = ""
    session_sources: list[SessionSource] = Field(default_factory=list)
    scenario_ids: list[ScenarioId] = Field(default_factory=lambda: list(ScenarioId))
    preferred_output: DeliveryMode = DeliveryMode.both
    message_limit: int = 20
    client_id: str = "lark-im-trigger"
    device_id: str = "desktop-console"
    device_label: str = "Desktop Console"
    platform: Platform = Platform.desktop
    send_ack_to_chat: bool = True


class LarkIMPreview(BaseModel):
    source_label: str
    message_count: int
    chat_text: str


class LarkIMJobAccepted(JobAccepted):
    source_label: str = ""
    message_count: int = 0


class JobSummary(BaseModel):
    job_id: str
    status: JobStatus
    created_at: str
    updated_at: str
    topic: str = ""
    instruction: str
    scenario_ids: list[ScenarioId] = Field(default_factory=list)


class ScenarioRunRequest(BaseModel):
    scenario_ids: list[ScenarioId]
    device_id: str = "web-console"
    platform: Platform = Platform.desktop
    note: str = ""


class AcceptanceUpdateRequest(BaseModel):
    confirmed: bool = True
    note: str = ""
    confirmed_by: str = "user"


class InputUpdateRequest(BaseModel):
    instruction: str
    supplement: str = ""
    context_snapshot: list[SessionSource] = Field(default_factory=list)
    base_version: int = 1
    device_id: str = "web-console"
    device_label: str = "Web Console"
    platform: Platform = Platform.desktop


class BotWebhookRequest(BaseModel):
    event_id: str = ""
    instruction: str = ""
    chat_id: str = ""
    user_id: str = ""
    sender_id: str = ""
    text: str = ""
    message_type: str = "text"


class BotWebhookAccepted(JobAccepted):
    reply_mode: str = "reserved"
    event_id: str = ""


class LarkSessionSearchResult(BaseModel):
    kind: str
    source_id: str
    label: str
    available: bool = True
    note: str = ""


class LarkSessionPreviewRequest(BaseModel):
    kind: str
    source_id: str
    label: str = ""
    message_limit: int = 20


class SkillDefinition(BaseModel):
    name: str
    title: str
    category: str
    description: str
    available: bool = False
    execution_mode: str = "simulated"


class LarkConnectionStatus(BaseModel):
    installed: bool = False
    configured: bool = False
    user_linked: bool = False
    authenticated: bool = False
    doc_sync_enabled: bool = True
    slides_sync_enabled: bool = False
    drive_upload_enabled: bool = False
    cli_path: str = ""
    mode: str = "offline"
    summary: str = ""
    next_step: str = ""
    active_identity: str = ""
    linked_user: str = ""
    note: str = ""
    scope_hints: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    auth: dict[str, Any] = Field(default_factory=dict)
    doctor: dict[str, Any] = Field(default_factory=dict)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
