from __future__ import annotations

from .llm import LLMJsonClient
from .models import (
    DeliveryMode,
    JobCreateRequest,
    JobState,
    PlanStep,
    PlanningResult,
    RepairChangeLevel,
    ScenarioId,
    TaskRepairDecision,
)


CANONICAL_PHASES = [
    {
        "id": "intake",
        "name": "IM / 飞书入口",
        "description": "接收原始聊天内容和自然语言指令，建立本次任务上下文。",
        "skills": ["lark-im", "lark-event"],
        "keywords": ["im", "飞书", "入口", "接收", "采集", "解析指令"],
    },
    {
        "id": "plan",
        "name": "任务拆解与规划",
        "description": "由 Agent Harness 输出目标、执行计划、成功标准和澄清问题。",
        "skills": ["lark-event", "lark-wiki"],
        "keywords": ["规划", "计划", "拆解", "harness", "调度", "解析"],
    },
    {
        "id": "document",
        "name": "文档生成",
        "description": "将讨论内容沉淀为结构化汇报文档，并同步到飞书 Doc。",
        "skills": ["lark-doc", "lark-whiteboard"],
        "keywords": ["文档", "doc", "报告", "纪要"],
    },
    {
        "id": "slides",
        "name": "PPT / Slide 生成",
        "description": "将文档内容转成演示稿，生成本地预览并同步到飞书 Slides。",
        "skills": ["lark-slides"],
        "keywords": ["slide", "slides", "ppt", "演示稿", "汇报"],
    },
    {
        "id": "sync",
        "name": "多端状态同步",
        "description": "同步任务进度、设备状态和关键事件，保证桌面端与移动端一致。",
        "skills": ["lark-event"],
        "keywords": ["同步", "多端", "桌面", "移动", "状态"],
    },
    {
        "id": "delivery",
        "name": "报告或 Slide 交付",
        "description": "整理交付链接、分享物料和归档文件，完成最终交付。",
        "skills": ["lark-drive"],
        "keywords": ["交付", "drive", "上传", "归档", "分享"],
    },
]


class AgentPlanner:
    def __init__(self, llm_client: LLMJsonClient) -> None:
        self.llm_client = llm_client

    def plan(self, request: JobCreateRequest) -> PlanningResult:
        try:
            generated = self.llm_client.generate_model(self._prompt(request), PlanningResult)
            return self._normalize_plan(generated, request)
        except Exception:
            return self._fallback(request)

    def _prompt(self, request: JobCreateRequest) -> str:
        return f"""
Please plan an Agent-Pilot workflow for the following request.
Return JSON matching exactly this schema:

{{
  "goal": "string",
  "success_criteria": ["string"],
  "clarification_questions": ["string"],
  "suggested_skills": ["string"],
  "steps": [
    {{
      "id": "string",
      "name": "string",
      "description": "string",
      "skills": ["string"],
      "status": "pending",
      "output_summary": ""
    }}
  ]
}}

Rules:
- Use concise Chinese.
- The workflow must follow this backbone:
  IM / 飞书入口 -> 自然语言指令 -> Agent Harness -> 任务拆解/规划 -> PPT/文档生成 -> 多端状态同步 -> 报告或 Slide 交付
- Suggested skills should be chosen from:
  lark-im, lark-doc, lark-slides, lark-drive, lark-event, lark-whiteboard, lark-wiki
- Keep step ids stable and machine-friendly.

Request source: {request.source.value}
Preferred output: {request.preferred_output.value}
Instruction:
{request.instruction}

Chat content:
{request.chat_text or request.voice_text or "(empty)"}
""".strip()

    def _fallback(self, request: JobCreateRequest) -> PlanningResult:
        output_label = {
            DeliveryMode.report: "报告",
            DeliveryMode.slides: "Slide",
            DeliveryMode.both: "报告与 Slide",
        }[request.preferred_output]
        result = PlanningResult(
            goal=f"将 IM 讨论转成可交付的{output_label}，并保持多端可追踪状态。",
            success_criteria=[
                "用户能从自然语言入口发起任务",
                "Agent 给出可执行计划并持续更新状态",
                "最终产出文档、演示稿或两者组合",
                "桌面端与移动端看到一致的任务状态",
            ],
            clarification_questions=[],
            suggested_skills=[
                "lark-im",
                "lark-doc",
                "lark-slides",
                "lark-event",
                "lark-drive",
            ],
            steps=[
                PlanStep(
                    id=phase["id"],
                    name=phase["name"],
                    description=phase["description"],
                    skills=list(phase["skills"]),
                )
                for phase in CANONICAL_PHASES
            ],
        )
        return self._normalize_plan(result, request)

    def _normalize_plan(self, plan: PlanningResult, request: JobCreateRequest) -> PlanningResult:
        normalized_steps: list[PlanStep] = []
        source_steps = list(plan.steps)

        for index, phase in enumerate(CANONICAL_PHASES):
            matched = self._match_phase_step(phase, source_steps, index)
            description = matched.description.strip() if matched and matched.description.strip() else phase["description"]
            skills = list(dict.fromkeys((matched.skills if matched and matched.skills else []) + list(phase["skills"])))
            normalized_steps.append(
                PlanStep(
                    id=phase["id"],
                    name=phase["name"],
                    description=description,
                    skills=skills,
                )
            )

        suggested_skills = list(dict.fromkeys(plan.suggested_skills or []))
        for phase in CANONICAL_PHASES:
            for skill in phase["skills"]:
                if skill not in suggested_skills:
                    suggested_skills.append(skill)

        goal = plan.goal.strip() if plan.goal.strip() else self._fallback_goal(request)
        return PlanningResult(
            goal=goal,
            success_criteria=plan.success_criteria,
            clarification_questions=plan.clarification_questions,
            suggested_skills=suggested_skills,
            steps=normalized_steps,
        )

    def _match_phase_step(self, phase: dict[str, object], steps: list[PlanStep], index: int) -> PlanStep | None:
        phase_id = str(phase["id"]).lower()
        keywords = [str(item).lower() for item in phase["keywords"]]
        phase_skills = {str(item) for item in phase["skills"]}

        for step in steps:
            step_blob = " ".join([step.id, step.name, step.description, " ".join(step.skills)]).lower()
            if step.id.lower() == phase_id:
                return step
            if any(keyword in step_blob for keyword in keywords):
                return step
            if phase_skills.intersection(step.skills):
                return step

        if index < len(steps):
            return steps[index]
        return None

    def _fallback_goal(self, request: JobCreateRequest) -> str:
        output_label = {
            DeliveryMode.report: "报告",
            DeliveryMode.slides: "Slide",
            DeliveryMode.both: "报告与 Slide",
        }[request.preferred_output]
        return f"根据用户指令生成{output_label}，并保持多端状态同步。"

    def infer_scenarios(self, request: JobCreateRequest, plan: PlanningResult) -> list[ScenarioId]:
        instruction = f"{request.instruction} {request.chat_text}".lower()
        selected: list[ScenarioId] = [ScenarioId.intake, ScenarioId.plan]

        doc_keywords = ["文档", "doc", "报告", "纪要", "总结"]
        slide_keywords = ["slide", "slides", "ppt", "演示", "汇报"]
        sync_keywords = ["同步", "多端", "移动端", "桌面端", "状态"]

        wants_doc = request.preferred_output in {DeliveryMode.report, DeliveryMode.both} or any(
            key in instruction for key in doc_keywords
        )
        wants_slides = request.preferred_output in {DeliveryMode.slides, DeliveryMode.both} or any(
            key in instruction for key in slide_keywords
        )
        wants_sync = any(key in instruction for key in sync_keywords)

        if wants_doc:
            selected.append(ScenarioId.document)
        if wants_slides:
            selected.append(ScenarioId.slides)
        if wants_sync:
            selected.append(ScenarioId.sync)

        has_delivery_intent = any(
            key in instruction for key in ["交付", "输出", "发给", "提交", "归档", "链接"]
        )
        if wants_doc or wants_slides or has_delivery_intent:
            selected.append(ScenarioId.delivery)

        # Plan may explicitly mention sync-oriented skills.
        plan_skills = {item for item in (plan.suggested_skills or [])}
        if "lark-event" in plan_skills and ScenarioId.sync not in selected:
            selected.append(ScenarioId.sync)

        return list(dict.fromkeys(selected))

    def plan_repair(
        self,
        previous_request: JobCreateRequest,
        current_job: JobState,
        proposed_plan: PlanningResult,
    ) -> TaskRepairDecision:
        try:
            generated = self.llm_client.generate_model(
                self._repair_prompt(previous_request, current_job, proposed_plan),
                TaskRepairDecision,
            )
            return self._normalize_repair_decision(generated, current_job, proposed_plan)
        except Exception:
            return self._fallback_repair(previous_request, current_job, proposed_plan)

    def _repair_prompt(
        self,
        previous_request: JobCreateRequest,
        current_job: JobState,
        proposed_plan: PlanningResult,
    ) -> str:
        completed_steps = [step.id for step in current_job.steps if step.status == "completed"]
        current_steps = [step.id for step in current_job.steps]
        current_artifacts = [artifact.kind for artifact in current_job.artifacts if artifact.status == "active"]
        return f"""
Please decide how to repair an existing Agent-Pilot task after the task input was edited.
Return JSON matching exactly this schema:

{{
  "change_level": "minor | partial_replan | full_replan",
  "summary": "string",
  "reasoning": ["string"],
  "keep_steps": ["string"],
  "rerun_steps": ["string"],
  "add_steps": ["string"],
  "drop_steps": ["string"],
  "invalidate_artifact_kinds": ["string"],
  "updated_success_criteria": ["string"]
}}

Rules:
- Use concise Chinese.
- Prefer minimum-cost repair.
- Only use canonical steps from: intake, plan, document, slides, sync, delivery.
- If document changes, slides and delivery are usually affected.
- If task goal/output changes materially, use full_replan.
- If only wording/supplement changes and current outputs can be updated incrementally, use partial_replan or minor.

Previous instruction:
{previous_request.instruction}

Previous supplement:
{previous_request.supplement}

New instruction:
{current_job.request.instruction}

New supplement:
{current_job.request.supplement}

Current steps:
{current_steps}

Completed steps:
{completed_steps}

Current active artifacts:
{current_artifacts}

New inferred scenarios:
{[item.value for item in current_job.scenario_ids] or [item.value for item in self.infer_scenarios(current_job.request, proposed_plan)]}
""".strip()

    def _normalize_repair_decision(
        self,
        decision: TaskRepairDecision,
        current_job: JobState,
        proposed_plan: PlanningResult,
    ) -> TaskRepairDecision:
        valid_steps = {phase["id"] for phase in CANONICAL_PHASES}
        valid_artifacts = {"report_markdown", "slides_preview", "pptx", "manifest", "feishu_doc", "feishu_slides"}
        keep_steps = [step for step in decision.keep_steps if step in valid_steps]
        rerun_steps = [step for step in decision.rerun_steps if step in valid_steps]
        add_steps = [step for step in decision.add_steps if step in valid_steps]
        drop_steps = [step for step in decision.drop_steps if step in valid_steps]
        invalid_artifacts = [kind for kind in decision.invalidate_artifact_kinds if kind in valid_artifacts]

        if not rerun_steps and decision.change_level != RepairChangeLevel.minor:
            fallback = self._fallback_repair(current_job.request, current_job, proposed_plan)
            rerun_steps = fallback.rerun_steps
            if not invalid_artifacts:
                invalid_artifacts = fallback.invalidate_artifact_kinds
            if not keep_steps:
                keep_steps = fallback.keep_steps
            if not decision.summary:
                decision.summary = fallback.summary
            if decision.change_level == RepairChangeLevel.minor and fallback.change_level != RepairChangeLevel.minor:
                decision.change_level = fallback.change_level

        rerun_steps = self._expand_rerun_steps(rerun_steps)
        keep_steps = [step for step in keep_steps if step not in rerun_steps and step not in drop_steps]
        if not keep_steps:
            keep_steps = [
                step.id for step in current_job.steps if step.id not in rerun_steps and step.id not in drop_steps
            ]
        return TaskRepairDecision(
            change_level=decision.change_level,
            summary=decision.summary or "任务输入已更新，Agent 将按最小影响范围修正任务。",
            reasoning=decision.reasoning,
            keep_steps=list(dict.fromkeys(keep_steps)),
            rerun_steps=list(dict.fromkeys(rerun_steps)),
            add_steps=list(dict.fromkeys(add_steps)),
            drop_steps=list(dict.fromkeys(drop_steps)),
            invalidate_artifact_kinds=list(dict.fromkeys(invalid_artifacts)),
            updated_success_criteria=decision.updated_success_criteria or current_job.success_criteria or proposed_plan.success_criteria,
        )

    def _fallback_repair(
        self,
        previous_request: JobCreateRequest,
        current_job: JobState,
        proposed_plan: PlanningResult,
    ) -> TaskRepairDecision:
        previous_text = f"{previous_request.instruction}\n{previous_request.supplement}\n{previous_request.chat_text}".strip()
        current_text = f"{current_job.request.instruction}\n{current_job.request.supplement}\n{current_job.request.chat_text}".strip()
        if previous_text == current_text:
            return TaskRepairDecision(
                change_level=RepairChangeLevel.minor,
                summary="任务输入未发生实质变化，保留现有执行结果。",
                keep_steps=[step.id for step in current_job.steps],
                rerun_steps=[],
                invalidate_artifact_kinds=[],
                updated_success_criteria=current_job.success_criteria or proposed_plan.success_criteria,
            )

        previous_output = previous_request.preferred_output
        current_output = current_job.request.preferred_output
        if previous_output != current_output:
            return TaskRepairDecision(
                change_level=RepairChangeLevel.full_replan,
                summary="交付模式发生变化，需要从规划开始重新生成文档与交付物。",
                rerun_steps=["plan", "document", "slides", "delivery"],
                invalidate_artifact_kinds=["report_markdown", "slides_preview", "pptx", "manifest", "feishu_doc", "feishu_slides"],
                updated_success_criteria=proposed_plan.success_criteria,
            )

        instruction_delta = previous_request.instruction.strip() != current_job.request.instruction.strip()
        if instruction_delta:
            return TaskRepairDecision(
                change_level=RepairChangeLevel.partial_replan,
                summary="任务说明已更新，需要重新规划并刷新文档、演示稿与交付物。",
                rerun_steps=["plan", "document", "slides", "delivery"],
                invalidate_artifact_kinds=["report_markdown", "slides_preview", "pptx", "manifest", "feishu_doc", "feishu_slides"],
                updated_success_criteria=proposed_plan.success_criteria,
            )

        return TaskRepairDecision(
            change_level=RepairChangeLevel.partial_replan,
            summary="上下文或补充内容已更新，保留入口步骤，重跑文档、演示稿和交付。",
            keep_steps=["intake", "plan", "sync"],
            rerun_steps=["document", "slides", "delivery"],
            invalidate_artifact_kinds=["report_markdown", "slides_preview", "pptx", "manifest", "feishu_doc", "feishu_slides"],
            updated_success_criteria=current_job.success_criteria or proposed_plan.success_criteria,
        )

    @staticmethod
    def _expand_rerun_steps(rerun_steps: list[str]) -> list[str]:
        expanded = list(rerun_steps)
        if "plan" in expanded:
            expanded.extend(["document", "slides", "delivery"])
        if "document" in expanded:
            expanded.extend(["slides", "delivery"])
        if "slides" in expanded:
            expanded.append("delivery")
        return list(dict.fromkeys(expanded))
