from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from .models import (
    AcceptanceStatus,
    ConversationActionResult,
    ConversationIntent,
    ConversationRequest,
    ConversationResponse,
    ConversationRole,
    InputUpdateRequest,
    JobState,
    ScenarioId,
    TaskConversationEntry,
    now_iso,
)


@dataclass
class IntentResult:
    intent: ConversationIntent
    arguments: dict[str, object]
    requires_llm_reply: bool = False


class TaskConversationService:
    def __init__(self, store, planner, llm_client, harness) -> None:
        self.store = store
        self.planner = planner
        self.llm_client = llm_client
        self.harness = harness

    def detect_intent(self, message: str) -> IntentResult:
        text = message.strip().lower()
        if any(key in text for key in ["为什么", "为何", "影响", "修正", "重跑原因"]):
            return IntentResult(ConversationIntent.explain_repair, {}, requires_llm_reply=True)
        if any(key in text for key in ["进展", "状态", "做到哪", "卡在", "完成了吗"]):
            return IntentResult(ConversationIntent.status_query, {})
        if any(key in text for key in ["产物", "报告", "ppt", "slide", "演示稿", "生成了什么", "交付结果"]):
            return IntentResult(ConversationIntent.artifact_query, {})
        if any(key in text for key in ["验收状态", "验收怎么样", "验收情况"]):
            return IntentResult(ConversationIntent.acceptance_query, {})
        if "确认验收" in text:
            return IntentResult(ConversationIntent.acceptance_confirm, {"confirmed": True})
        if any(key in text for key in ["重跑", "重做", "重新生成"]):
            return IntentResult(ConversationIntent.rerun_step, {"steps": self._extract_steps(text)})
        if any(key in text for key in ["总结", "概括", "汇总", "说明一下", "介绍一下"]):
            return IntentResult(ConversationIntent.summary_request, {}, requires_llm_reply=True)
        if any(key in text for key in ["补充", "改成", "修改任务", "更新任务", "新增要求"]):
            return IntentResult(ConversationIntent.input_update, {"message": message})
        return IntentResult(ConversationIntent.unknown, {}, requires_llm_reply=True)

    def handle(self, job_id: str, request: ConversationRequest) -> ConversationResponse:
        job = self.store.get_job(job_id)
        user_entry = self._entry(
            role=ConversationRole.user,
            message=request.message.strip(),
            metadata={"device_id": request.device_id, "device_label": request.device_label, "platform": request.platform.value},
        )
        self.store.append_conversation_entries(job_id, [user_entry])

        intent_result = self.detect_intent(request.message)
        action = ConversationActionResult()
        if intent_result.requires_llm_reply:
            reply = self._reply_with_llm(job, request.message, intent_result.intent)
            reply_entry = self._entry(
                role=ConversationRole.assistant,
                message=reply,
                action_type=intent_result.intent.value,
                action_status="completed",
            )
            updated_job = self.store.append_conversation_entries(job_id, [reply_entry])
            return ConversationResponse(
                reply=reply,
                action=ConversationActionResult(type=intent_result.intent.value, status="completed"),
                entries=[user_entry, reply_entry],
                job=updated_job,
            )

        handler = {
            ConversationIntent.status_query: self._handle_status_query,
            ConversationIntent.artifact_query: self._handle_artifact_query,
            ConversationIntent.acceptance_query: self._handle_acceptance_query,
            ConversationIntent.acceptance_confirm: self._handle_acceptance_confirm,
            ConversationIntent.input_update: self._handle_input_update,
            ConversationIntent.rerun_step: self._handle_rerun_step,
        }.get(intent_result.intent)

        if handler is None:
            reply = "我还不能稳定处理这类任务对话。你可以试试问我进度、产物、验收，或者直接要求我重跑文档/PPT。"
            reply_entry = self._entry(role=ConversationRole.assistant, message=reply)
            updated_job = self.store.append_conversation_entries(job_id, [reply_entry])
            return ConversationResponse(reply=reply, entries=[user_entry, reply_entry], job=updated_job)

        reply, action, role = handler(job_id, request, intent_result.arguments)
        reply_entry = self._entry(
            role=role,
            message=reply,
            action_type=action.type,
            action_status=action.status,
            metadata=action.details,
        )
        updated_job = self.store.append_conversation_entries(job_id, [reply_entry])
        return ConversationResponse(reply=reply, action=action, entries=[user_entry, reply_entry], job=updated_job)

    def _handle_status_query(
        self,
        job_id: str,
        request: ConversationRequest,
        arguments: dict[str, object],
    ) -> tuple[str, ConversationActionResult, ConversationRole]:
        del request, arguments
        job = self.store.get_job(job_id)
        completed = len([step for step in job.steps if step.status == "completed"])
        total = len(job.steps)
        latest_event = job.events[-1].message if job.events else "还没有新的执行事件。"
        current_step = next((step.name for step in job.steps if step.status == "running"), "")
        reply = f"当前任务状态为 {job.status.value}，已完成 {completed}/{total} 个步骤。"
        if current_step:
            reply += f" 正在执行：{current_step}。"
        reply += f" 最近事件：{latest_event}"
        return reply, ConversationActionResult(type="status_query", status="completed"), ConversationRole.assistant

    def _handle_artifact_query(
        self,
        job_id: str,
        request: ConversationRequest,
        arguments: dict[str, object],
    ) -> tuple[str, ConversationActionResult, ConversationRole]:
        del request, arguments
        job = self.store.get_job(job_id)
        active_artifacts = [item for item in job.artifacts if item.status == "active"]
        if not active_artifacts:
            reply = "当前还没有可用的最新交付产物。你可以先让我继续执行，或者重跑相关步骤。"
            return reply, ConversationActionResult(type="artifact_query", status="empty"), ConversationRole.assistant

        parts = [f"{item.label}（{item.kind}）" for item in active_artifacts[:5]]
        reply = f"当前最新产物有：{'；'.join(parts)}。"
        return reply, ConversationActionResult(type="artifact_query", status="completed"), ConversationRole.assistant

    def _handle_acceptance_query(
        self,
        job_id: str,
        request: ConversationRequest,
        arguments: dict[str, object],
    ) -> tuple[str, ConversationActionResult, ConversationRole]:
        del request, arguments
        job = self.store.get_job(job_id)
        reply = f"当前验收状态为 {job.acceptance.status.value}。"
        if job.acceptance.result_summary:
            reply += f" {job.acceptance.result_summary}"
        elif job.acceptance.criteria:
            reply += f" 当前共有 {len(job.acceptance.criteria)} 条验收标准。"
        return reply, ConversationActionResult(type="acceptance_query", status="completed"), ConversationRole.assistant

    def _handle_acceptance_confirm(
        self,
        job_id: str,
        request: ConversationRequest,
        arguments: dict[str, object],
    ) -> tuple[str, ConversationActionResult, ConversationRole]:
        del arguments
        self.store.set_acceptance(
            job_id,
            status=AcceptanceStatus.confirmed,
            confirmed_by=request.device_label,
            note="通过任务对话确认验收。",
        )
        self.store.add_event(
            job_id,
            "acceptance",
            f"{request.device_label} 通过任务对话确认了验收标准。",
            metadata={"device_id": request.device_id, "platform": request.platform.value},
        )
        reply = "已确认当前任务的验收标准。"
        return (
            reply,
            ConversationActionResult(type="acceptance_confirm", status="completed"),
            ConversationRole.system_action,
        )

    def _handle_input_update(
        self,
        job_id: str,
        request: ConversationRequest,
        arguments: dict[str, object],
    ) -> tuple[str, ConversationActionResult, ConversationRole]:
        job = self.store.get_job(job_id)
        previous_request = job.request.model_copy(deep=True)
        delta = str(arguments.get("message") or request.message).strip()
        supplement = job.editable_input.supplement.strip()
        appended = f"{supplement}\n\n[任务对话补充]\n{delta}".strip() if supplement else f"[任务对话补充]\n{delta}"
        self.store.update_editable_input(
            job_id,
            InputUpdateRequest(
                instruction=job.editable_input.instruction or job.request.instruction,
                supplement=appended,
                context_snapshot=[item.model_copy(deep=True) for item in job.editable_input.context_snapshot],
                base_version=job.editable_input.version,
                device_id=request.device_id,
                device_label=request.device_label,
                platform=request.platform,
            ),
        )
        self.harness.repair_job(job_id, previous_request)
        reply = "我已经把这条自然语言补充并入任务输入，并开始按最小影响范围修正任务。"
        return (
            reply,
            ConversationActionResult(type="input_update", status="completed", details={"mode": "append_supplement"}),
            ConversationRole.system_action,
        )

    def _handle_rerun_step(
        self,
        job_id: str,
        request: ConversationRequest,
        arguments: dict[str, object],
    ) -> tuple[str, ConversationActionResult, ConversationRole]:
        raw_steps = list(arguments.get("steps") or [])
        scenario_ids = self._expand_scenarios(raw_steps)
        if not scenario_ids:
            reply = "我暂时没识别出你想重跑哪一步。你可以直接说“重新生成 PPT”或“重跑文档和交付”。"
            return reply, ConversationActionResult(type="rerun_step", status="rejected"), ConversationRole.assistant

        self.store.add_event(
            job_id,
            "conversation",
            f"{request.device_label} 通过任务对话触发重跑：{', '.join(item.value for item in scenario_ids)}。",
            metadata={"device_id": request.device_id, "platform": request.platform.value},
        )
        self.harness.run_scenarios(job_id, scenario_ids, finalize=False)
        reply = f"已按你的要求触发重跑：{', '.join(item.value for item in scenario_ids)}。"
        return (
            reply,
            ConversationActionResult(
                type="rerun_step",
                status="completed",
                details={"scenario_ids": [item.value for item in scenario_ids]},
            ),
            ConversationRole.system_action,
        )

    def _reply_with_llm(self, job: JobState, message: str, intent: ConversationIntent) -> str:
        prompt = self._build_summary_prompt(job, message, intent)
        try:
            if self.llm_client.enabled:
                return self.llm_client.generate_text(prompt)
        except Exception:
            pass
        return self._fallback_summary(job, message, intent)

    def _build_summary_prompt(self, job: JobState, message: str, intent: ConversationIntent) -> str:
        step_lines = [f"- {step.name} | {step.id} | {step.status.value} | {step.output_summary}" for step in job.steps]
        event_lines = [f"- {event.timestamp} | {event.phase} | {event.level} | {event.message}" for event in job.events[-8:]]
        artifact_lines = [f"- {artifact.label} | {artifact.kind} | {artifact.status} | {artifact.url}" for artifact in job.artifacts]
        latest_revision = job.revisions[-1].summary if job.revisions else "无"
        return f"""
请基于当前任务状态，面向用户输出一段简洁中文回复。

任务说明：
{job.request.instruction}

用户提问：
{message}

当前意图：
{intent.value}

步骤状态：
{chr(10).join(step_lines) or "- 无"}

最近事件：
{chr(10).join(event_lines) or "- 无"}

当前产物：
{chr(10).join(artifact_lines) or "- 无"}

验收状态：
- status: {job.acceptance.status.value}
- summary: {job.acceptance.result_summary or job.acceptance.note or "无"}

最近一次修正：
- {latest_revision}

要求：
- 不要输出 JSON
- 不要编造不存在的步骤或产物
- 用 2 到 4 句话说明现状，并在必要时给出下一步建议
""".strip()

    def _fallback_summary(self, job: JobState, message: str, intent: ConversationIntent) -> str:
        del message
        completed = len([step for step in job.steps if step.status == "completed"])
        active_artifacts = [item.label for item in job.artifacts if item.status == "active"]
        if intent == ConversationIntent.explain_repair and job.revisions:
            latest = job.revisions[-1]
            return f"最近一次任务修正等级为 {latest.change_level.value}，摘要是：{latest.summary}"
        return (
            f"当前任务状态为 {job.status.value}，已完成 {completed}/{len(job.steps)} 个步骤。"
            f" 当前最新产物有：{'、'.join(active_artifacts[:4]) or '暂无'}。"
        )

    @staticmethod
    def _entry(
        role: ConversationRole,
        message: str,
        action_type: str = "",
        action_status: str = "",
        metadata: dict[str, object] | None = None,
    ) -> TaskConversationEntry:
        return TaskConversationEntry(
            entry_id=f"conv-{uuid4().hex[:10]}",
            role=role,
            message=message,
            timestamp=now_iso(),
            action_type=action_type,
            action_status=action_status,
            metadata=metadata or {},
        )

    @staticmethod
    def _extract_steps(text: str) -> list[str]:
        steps: list[str] = []
        if any(key in text for key in ["规划", "计划"]):
            steps.append("plan")
        if any(key in text for key in ["文档", "报告", "纪要"]):
            steps.append("document")
        if any(key in text for key in ["ppt", "slide", "slides", "演示稿"]):
            steps.append("slides")
        if any(key in text for key in ["交付", "清单", "输出结果"]):
            steps.append("delivery")
        return list(dict.fromkeys(steps))

    @staticmethod
    def _expand_scenarios(steps: list[str]) -> list[ScenarioId]:
        selected = list(steps)
        if "plan" in selected:
            selected.extend(["document", "slides", "delivery"])
        if "document" in selected:
            selected.extend(["slides", "delivery"])
        if "slides" in selected:
            selected.append("delivery")
        lookup = {item.value: item for item in ScenarioId}
        return [lookup[item] for item in dict.fromkeys(selected) if item in lookup]
