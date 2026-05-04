from __future__ import annotations

import os

from .lark_cli import LarkCLIClient
from .models import SkillDefinition


class LarkSkillRegistry:
    def __init__(self, cli_client: LarkCLIClient) -> None:
        self.cli_client = cli_client
        self.cli_available = cli_client.installed
        status = cli_client.status()
        self.execution_mode = os.getenv("LARK_SKILL_EXECUTION_MODE", "simulated")
        if status.mode == "online":
            self.execution_mode = "cli_live"
        elif status.configured:
            self.execution_mode = "cli_bot_ready"
        elif status.mode in {"cli_installed", "cli_configured"}:
            self.execution_mode = "cli_ready"
        self._skills = [
            SkillDefinition(
                name="lark-im",
                title="IM Intake",
                category="messaging",
                description="Read or route IM entry messages into the Agent workflow.",
                available=self.cli_available,
                execution_mode=self.execution_mode,
            ),
            SkillDefinition(
                name="lark-doc",
                title="Document Drafting",
                category="document",
                description="Create or update structured Docs from the generated brief.",
                available=self.cli_available,
                execution_mode=self.execution_mode,
            ),
            SkillDefinition(
                name="lark-slides",
                title="Slide Delivery",
                category="slides",
                description="Create and manage presentation content for final delivery.",
                available=self.cli_available,
                execution_mode=self.execution_mode,
            ),
            SkillDefinition(
                name="lark-drive",
                title="Drive Delivery",
                category="drive",
                description="Upload artifacts, manage sharing, and support archive delivery.",
                available=self.cli_available,
                execution_mode=self.execution_mode,
            ),
            SkillDefinition(
                name="lark-event",
                title="Realtime Sync",
                category="sync",
                description="Push status updates and event streams to multiple devices.",
                available=self.cli_available,
                execution_mode=self.execution_mode,
            ),
            SkillDefinition(
                name="lark-whiteboard",
                title="Canvas Support",
                category="canvas",
                description="Prepare future whiteboard or free-canvas operations.",
                available=self.cli_available,
                execution_mode=self.execution_mode,
            ),
            SkillDefinition(
                name="lark-wiki",
                title="Knowledge Retrieval",
                category="knowledge",
                description="Search project context or reference documents for grounding.",
                available=self.cli_available,
                execution_mode=self.execution_mode,
            ),
        ]

    def list_skills(self) -> list[SkillDefinition]:
        return [skill.model_copy(deep=True) for skill in self._skills]

    def phase_summary(self, skills: list[str]) -> str:
        if not skills:
            return "No external skill attached."
        mode = self.execution_mode if self.cli_available else "simulated"
        return f"{mode}: " + ", ".join(skills)
