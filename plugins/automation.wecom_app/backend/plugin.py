from __future__ import annotations

from typing import Any

from core.sdk import AutomationProvider, BasePlugin, OperationResult

DEFAULT_EVENTS = ["task.completed", "task.failed"]


class WecomAppAutomationPlugin(BasePlugin, AutomationProvider):
    plugin_id = "automation.wecom_app"
    plugin_name = "企业微信应用消息通知自动化"
    plugin_version = "1.0.0"

    def __init__(self) -> None:
        self._runtime_config: dict[str, Any] = {}

    def set_runtime_config(self, config: dict[str, Any]) -> None:
        self._runtime_config = self._normalize_runtime_config(config)

    def validate_runtime_config(self, config: dict[str, Any]) -> OperationResult:
        normalized = self._normalize_runtime_config(config)
        errors: list[str] = []
        for key in ("corp_id", "corp_secret", "agent_id"):
            if not str(normalized.get(key) or "").strip():
                errors.append(f"缺少必填配置：{key}")
        if errors:
            return OperationResult(success=False, message="插件配置校验失败。", errors=errors)
        return OperationResult(success=True, message="插件配置校验通过。", data=normalized)

    def health(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "ok",
            "message": "企业微信应用消息通知插件运行正常。",
            "details": {
                "configured": self._is_configured(),
                "subscribed_events": self.subscribed_events(),
            },
        }

    def subscribed_events(self) -> list[str]:
        raw = str(self._runtime_config.get("enabled_events") or ",".join(DEFAULT_EVENTS))
        values = [item.strip() for item in raw.split(",") if item.strip()]
        return values or list(DEFAULT_EVENTS)

    def handle(self, event: dict[str, Any]) -> dict[str, Any]:
        event_type = str(event.get("event_type") or "unknown")
        title, content = self._build_message(event)
        return OperationResult(
            success=True,
            message=f"{self.plugin_name} 已处理事件：{event_type}",
            data={
                "event_type": event_type,
                "title": title,
                "content": content,
                "configured": self._is_configured(),
            },
        ).model_dump(mode="json")

    def _is_configured(self) -> bool:
        required = ("corp_id", "corp_secret", "agent_id")
        return all(bool(str(self._runtime_config.get(key) or "").strip()) for key in required)

    @staticmethod
    def _normalize_runtime_config(config: dict[str, Any] | None) -> dict[str, Any]:
        return dict(config or {})

    @staticmethod
    def _build_message(event: dict[str, Any]) -> tuple[str, str]:
        event_type = str(event.get("event_type") or "unknown")
        payload = dict(event.get("payload") or {})
        task_name = str(
            payload.get("task_name")
            or payload.get("title")
            or event.get("task_id")
            or "未命名任务"
        )
        summary = str(payload.get("summary") or "").strip()
        error_message = str(
            payload.get("error_message")
            or payload.get("error")
            or summary
            or "未知错误"
        ).strip()

        if event_type == "task.completed":
            content = f"{task_name} 已执行完成。"
            if summary:
                content = f"{content} {summary}"
            return "[任务完成]", content

        if event_type == "task.failed":
            return "[任务失败]", f"{task_name} 执行失败：{error_message}"

        if summary:
            return "[系统通知]", f"{task_name}：{summary}"
        return "[系统通知]", f"{task_name} 触发事件：{event_type}"


plugin = WecomAppAutomationPlugin()
