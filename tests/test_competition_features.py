from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from pilot_app.models import (
    AcceptanceStatus,
    JobCreateRequest,
    Platform,
    ScenarioId,
    SessionSource,
)
from pilot_app.server import app
from pilot_app.store import MySQLJobStore


class CompetitionFeatureTests(unittest.TestCase):
    def test_mysql_store_persists_job_sources_and_acceptance_after_reconnect(self) -> None:
        store = MySQLJobStore()
        job = store.create_job(
            JobCreateRequest(
                instruction="生成周会汇报",
                chat_text="张三：先整理需求",
                platform=Platform.mobile,
                session_sources=[
                    SessionSource(kind="chat", source_id="oc_1", label="产品群", transcript="产品群：需求 A"),
                    SessionSource(kind="user", source_id="ou_1", label="李四", transcript="李四：风险 B"),
                ],
                scenario_ids=[ScenarioId.intake, ScenarioId.plan, ScenarioId.document],
            )
        )
        store.set_acceptance(
            job.job_id,
            criteria=["覆盖 IM、Doc、PPT/自由画布", "桌面端和移动端可同步操作"],
            status=AcceptanceStatus.pending,
        )

        restored = MySQLJobStore().get_job(job.job_id)

        self.assertIn("产品群：需求 A", restored.request.chat_text)
        self.assertIn("李四：风险 B", restored.request.chat_text)
        self.assertEqual([source.label for source in restored.request.session_sources], ["产品群", "李四"])
        self.assertEqual(restored.scenario_ids, [ScenarioId.intake, ScenarioId.plan, ScenarioId.document])
        self.assertEqual(restored.acceptance.status, AcceptanceStatus.pending)

    def test_scenario_api_runs_selected_scene_without_recreating_job(self) -> None:
        client = TestClient(app)
        created = client.post(
            "/api/jobs",
            json={
                "instruction": "只生成文档草稿",
                "chat_text": "王五：把这段讨论整理成文档。",
                "scenario_ids": ["intake", "plan"],
                "auto_run": False,
            },
        )
        self.assertEqual(created.status_code, 200)
        job_id = created.json()["job_id"]

        response = client.post(
            f"/api/jobs/{job_id}/scenarios",
            json={"scenario_ids": ["document"], "device_id": "mobile-console", "platform": "mobile"},
        )

        self.assertEqual(response.status_code, 200)
        job = response.json()
        self.assertTrue(any(step["id"] == "document" and step["status"] == "completed" for step in job["steps"]))
        self.assertTrue(any(artifact["kind"] == "report_markdown" for artifact in job["artifacts"]))
        self.assertIn("confirm_acceptance", job["available_actions"])

    def test_acceptance_api_confirms_criteria_and_records_result(self) -> None:
        client = TestClient(app)
        created = client.post(
            "/api/jobs",
            json={
                "instruction": "完成 IM 到 PPT 的闭环",
                "chat_text": "赵六：需要有文档和演示稿。",
                "scenario_ids": ["intake", "plan", "document", "slides", "delivery"],
                "auto_run": False,
            },
        )
        job_id = created.json()["job_id"]

        response = client.post(
            f"/api/jobs/{job_id}/acceptance",
            json={"confirmed": True, "note": "验收标准已确认"},
        )

        self.assertEqual(response.status_code, 200)
        acceptance = response.json()["acceptance"]
        self.assertEqual(acceptance["status"], "confirmed")
        self.assertTrue(acceptance["criteria"])

    def test_bot_webhook_creates_manual_job_without_real_lark_callback_dependency(self) -> None:
        client = TestClient(app)

        response = client.post(
            "/api/bot/webhook",
            json={
                "event_id": "evt-demo",
                "instruction": "从机器人入口创建任务",
                "chat_id": "oc_demo",
                "text": "请整理这段 IM 并生成汇报材料。",
                "sender_id": "ou_demo",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("job_id", payload)
        self.assertEqual(payload["status"], "queued")
        self.assertEqual(payload["reply_mode"], "reserved")


if __name__ == "__main__":
    unittest.main()
