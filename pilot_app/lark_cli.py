from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .models import LarkConnectionStatus


class LarkCLIClient:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.cli_path = self._detect_cli_path()

    @property
    def installed(self) -> bool:
        return bool(self.cli_path)

    def status(self) -> LarkConnectionStatus:
        doc_sync_enabled = _env_flag("LARK_DOC_SYNC_ENABLED", True)
        slides_sync_enabled = _env_flag("LARK_SLIDES_SYNC_ENABLED", False)
        drive_upload_enabled = _env_flag("LARK_DRIVE_UPLOAD_ENABLED", False)

        if not self.cli_path:
            return LarkConnectionStatus(
                installed=False,
                configured=False,
                user_linked=False,
                authenticated=False,
                doc_sync_enabled=doc_sync_enabled,
                slides_sync_enabled=slides_sync_enabled,
                drive_upload_enabled=drive_upload_enabled,
                mode="offline",
                summary="lark-cli not installed.",
                next_step="Install or point LARK_CLI_PATH to the official lark-cli binary.",
            )

        config = self._run_json(["config", "show"])
        auth = self._run_json(["auth", "status"])
        doctor = self._run_json(["doctor", "--offline"])

        configured = "appId" in config and "error" not in config
        linked_user = ""
        users_field = str(config.get("users", "")).strip()
        if users_field and users_field != "(no logged-in users)":
            linked_user = users_field
        user_linked = bool(linked_user)

        auth_note = str(auth.get("note", "")).strip()
        active_identity = str(auth.get("identity", "")).strip()
        authenticated = bool(
            auth.get("verified") is True
            or auth.get("tokenStatus") == "valid"
            or (active_identity == "user" and "no token" not in auth_note.lower())
        )

        mode = "cli_installed"
        summary = "lark-cli is installed but not configured."
        next_step = "Run lark-cli config init --new to create or bind a Feishu/Lark app."
        note = auth_note

        if configured and not user_linked:
            mode = "cli_configured"
            summary = "lark-cli is configured, but no Feishu/Lark user is linked yet."
            next_step = "Bot-identity delivery can already be attempted. Run lark-cli auth login --recommend if you also want user-identity commands."
        elif configured and user_linked and not authenticated:
            mode = "cli_user_linked"
            summary = "lark-cli is configured and a user is linked, but this runtime is not holding a valid user token."
            next_step = "Bot-identity Docs/Slides/Drive calls can still work if app scopes are enabled. Use the host shell for user-identity commands in restricted runtimes."
        elif configured and authenticated:
            mode = "online"
            summary = "lark-cli is installed, configured, and authenticated."
            next_step = "You can start invoking real Lark domains such as docs, slides, drive, and im."

        granted_scopes = set(str(auth.get("scope", "")).split())
        scope_hints: list[str] = []
        if slides_sync_enabled and "slides:presentation:create" not in granted_scopes:
            scope_hints.append("Slides sync requires scope: slides:presentation:create")
        if drive_upload_enabled and "drive:file:upload" not in granted_scopes:
            scope_hints.append("Drive upload requires scope: drive:file:upload")

        return LarkConnectionStatus(
            installed=True,
            configured=configured,
            user_linked=user_linked,
            authenticated=authenticated,
            doc_sync_enabled=doc_sync_enabled,
            slides_sync_enabled=slides_sync_enabled,
            drive_upload_enabled=drive_upload_enabled,
            cli_path=self.cli_path,
            mode=mode,
            summary=summary,
            next_step=next_step,
            active_identity=active_identity,
            linked_user=linked_user,
            note=note,
            scope_hints=scope_hints,
            config=config,
            auth=auth,
            doctor=doctor,
        )

    def search_user(self, query: str) -> dict[str, Any]:
        return self._run_json(
            ["contact", "+search-user", "--query", query, "--format", "json", "--as", "user"]
        )

    def list_chat_messages(
        self,
        chat_id: str = "",
        user_id: str = "",
        message_limit: int = 20,
        identity: str = "user",
    ) -> dict[str, Any]:
        args = [
            "im",
            "+chat-messages-list",
            "--as",
            identity,
            "--format",
            "json",
            "--page-size",
            str(max(1, min(message_limit, 50))),
            "--sort",
            "asc",
        ]
        if chat_id:
            args.extend(["--chat-id", chat_id])
        elif user_id:
            args.extend(["--user-id", user_id])
        else:
            return {"ok": False, "error": {"message": "chat_id or user_id is required."}}
        return self._run_json(args, timeout=60)

    def build_chat_transcript(
        self,
        chat_id: str = "",
        user_id: str = "",
        message_limit: int = 20,
    ) -> dict[str, Any]:
        result = self.list_chat_messages(chat_id=chat_id, user_id=user_id, message_limit=message_limit)
        if not result.get("ok"):
            return result

        messages = _extract_message_items(result)
        transcript_lines: list[str] = []
        for item in messages[:message_limit]:
            sender = (
                item.get("sender_name")
                or item.get("senderName")
                or item.get("name")
                or item.get("sender_open_id")
                or item.get("senderOpenId")
                or "未知成员"
            )
            text = _extract_message_text(item)
            if text:
                transcript_lines.append(f"{sender}：{text}")

        result["message_count"] = len(transcript_lines)
        result["chat_text"] = "\n".join(transcript_lines)
        result["source_label"] = chat_id or user_id
        return result

    def send_message(
        self,
        *,
        chat_id: str = "",
        user_id: str = "",
        text: str = "",
        markdown: str = "",
        identity: str = "bot",
    ) -> dict[str, Any]:
        args = [
            "im",
            "+messages-send",
            "--as",
            identity,
        ]
        if chat_id:
            args.extend(["--chat-id", chat_id])
        elif user_id:
            args.extend(["--user-id", user_id])
        else:
            return {"ok": False, "error": {"message": "chat_id or user_id is required."}}

        if markdown:
            args.extend(["--markdown", markdown])
        elif text:
            args.extend(["--text", text])
        else:
            return {"ok": False, "error": {"message": "text or markdown is required."}}
        return self._run_json(args, timeout=60)

    def create_doc_from_markdown(
        self,
        markdown_path: Path,
        title: str,
        folder_token: str = "",
    ) -> dict[str, Any]:
        return self.create_doc_from_text(
            markdown_text=markdown_path.read_text(encoding="utf-8"),
            title=title,
            folder_token=folder_token,
        )

    def create_doc_from_text(
        self,
        markdown_text: str,
        title: str,
        folder_token: str = "",
    ) -> dict[str, Any]:
        args = [
            "docs",
            "+create",
            "--as",
            "bot",
            "--title",
            title,
            "--markdown",
            "-",
        ]
        if folder_token:
            args.extend(["--folder-token", folder_token])
        return self._run_json(args, timeout=60, input_text=markdown_text)

    def create_slides_from_outline(
        self,
        title: str,
        slides: list[dict[str, Any]],
    ) -> dict[str, Any]:
        slide_xml = [
            self._build_slide_xml(
                slide.get("title", f"Slide {index}"),
                slide.get("bullets", []),
            )
            for index, slide in enumerate(slides[:10], start=1)
        ]
        return self._run_json(
            [
                "slides",
                "+create",
                "--as",
                "bot",
                "--title",
                title,
                "--slides",
                json.dumps(slide_xml, ensure_ascii=False),
            ],
            timeout=60,
        )

    def upload_file(
        self,
        file_path: Path,
        folder_token: str = "",
        name: str = "",
    ) -> dict[str, Any]:
        staging_dir = self.base_dir / ".lark-upload-cache"
        staging_dir.mkdir(parents=True, exist_ok=True)
        staged_name = name or file_path.name
        staged_path = staging_dir / staged_name
        shutil.copy2(file_path, staged_path)

        relative_name = f".\\{staged_path.name}"
        args = [
            "drive",
            "+upload",
            "--as",
            "bot",
            "--file",
            relative_name,
        ]
        if folder_token:
            args.extend(["--folder-token", folder_token])
        if name:
            args.extend(["--name", name])
        return self._run_json(args, timeout=90, cwd=staging_dir)

    @staticmethod
    def error_message(result: dict[str, Any]) -> str:
        error = result.get("error", {})
        if isinstance(error, dict):
            for key in ("message", "msg", "details", "detail"):
                value = error.get(key)
                if value:
                    return str(value)
        for key in ("note", "raw"):
            value = result.get(key)
            if value:
                return str(value)
        return "Unknown lark-cli error."

    @staticmethod
    def missing_scope(result: dict[str, Any]) -> str:
        text = json.dumps(result, ensure_ascii=False)
        match = re.search(r"([a-z]+:[a-z0-9:_-]+)", text)
        return match.group(1) if match else ""

    @staticmethod
    def first_url(result: dict[str, Any]) -> str:
        found = _find_first_url(result)
        return found or ""

    def _detect_cli_path(self) -> str:
        env_path = os.getenv("LARK_CLI_PATH")
        if env_path and Path(env_path).exists():
            return env_path

        workspace_cli = self.base_dir / "tools" / "lark-cli" / "lark-cli.exe"
        if workspace_cli.exists():
            return str(workspace_cli)

        global_cli = shutil.which("lark-cli")
        return global_cli or ""

    def _run_json(
        self,
        args: list[str],
        timeout: int = 20,
        input_text: str = "",
        cwd: Path | None = None,
    ) -> dict[str, Any]:
        if not self.cli_path:
            return {}

        result = subprocess.run(
            [self.cli_path, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            input=input_text,
            timeout=timeout,
            check=False,
            cwd=str(cwd or self.base_dir),
        )
        payload = result.stdout.strip() or result.stderr.strip()
        if not payload:
            return {"ok": result.returncode == 0}

        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return {
                "ok": result.returncode == 0,
                "raw": payload,
            }

    @staticmethod
    def _build_slide_xml(title: str, bullets: list[str]) -> str:
        bullet_nodes = "".join(
            f"<li>{_xml_escape(str(bullet))}</li>"
            for bullet in bullets[:5]
            if str(bullet).strip()
        )
        if not bullet_nodes:
            bullet_nodes = "<li>待补充要点</li>"
        return (
            "<slide>"
            f"<h1>{_xml_escape(title)}</h1>"
            f"<ul>{bullet_nodes}</ul>"
            "</slide>"
        )


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _find_first_url(payload: Any) -> str:
    if isinstance(payload, str):
        if payload.startswith("http://") or payload.startswith("https://"):
            return payload
        return ""
    if isinstance(payload, dict):
        for value in payload.values():
            found = _find_first_url(value)
            if found:
                return found
        return ""
    if isinstance(payload, list):
        for item in payload:
            found = _find_first_url(item)
            if found:
                return found
    return ""


def _extract_message_items(result: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [
        result.get("data"),
        result.get("items"),
        result,
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            for key in ("items", "messages", "data"):
                value = candidate.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return []


def _extract_message_text(item: dict[str, Any]) -> str:
    direct_keys = [
        "text",
        "body",
        "plain_text",
        "plainText",
        "content_text",
        "contentText",
    ]
    for key in direct_keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    content = item.get("content")
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return content.strip()
        return _extract_message_text(parsed if isinstance(parsed, dict) else {"content": parsed})

    if isinstance(content, dict):
        if "text" in content and isinstance(content["text"], str):
            return content["text"].strip()
        if "content" in content and isinstance(content["content"], str):
            return content["content"].strip()
        if "title" in content and isinstance(content["title"], str):
            return content["title"].strip()

    if "content" in item and isinstance(item["content"], list):
        flattened: list[str] = []
        for row in item["content"]:
            if isinstance(row, list):
                for cell in row:
                    if isinstance(cell, dict):
                        value = cell.get("text") or cell.get("content") or cell.get("title")
                        if isinstance(value, str) and value.strip():
                            flattened.append(value.strip())
        if flattened:
            return " ".join(flattened)
    return ""
