from __future__ import annotations

from typing import Any

from core.sdk import AssistantCommand, AssistantProvider, BasePlugin, OperationResult


class WecomAssistantBotPlugin(BasePlugin, AssistantProvider):
    plugin_id = "assistant.wecom_bot"
    plugin_name = "企业微信助手机器人"
    plugin_version = "1.0.0"

    def __init__(self) -> None:
        self._runtime_config: dict[str, Any] = {}

    def set_runtime_config(self, config: dict[str, Any]) -> None:
        self._runtime_config = self._normalize_runtime_config(config)

    def validate_runtime_config(self, config: dict[str, Any]) -> OperationResult:
        normalized = self._normalize_runtime_config(config)
        errors: list[str] = []
        for key in ("corp_id", "agent_id", "callback_token", "encoding_aes_key"):
            if not str(normalized.get(key) or "").strip():
                errors.append(f"缺少必填配置：{key}")
        if errors:
            return OperationResult(success=False, message="插件配置校验失败。", errors=errors)
        return OperationResult(success=True, message="插件配置校验通过。", data=normalized)

    def health(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "ok",
            "message": "企业微信助手机器人插件运行正常。",
            "details": {
                "configured": self._is_configured(),
                "command_count": len(self.commands()),
            },
        }

    def commands(self) -> list[AssistantCommand] | list[dict[str, Any]]:
        prefix = str(self._runtime_config.get("command_prefix") or "/").strip() or "/"
        return [
            AssistantCommand(
                command=f"{prefix}task-status",
                title="查询任务状态",
                description="查询指定任务的最新执行状态。",
            ),
            AssistantCommand(
                command=f"{prefix}task-run",
                title="执行任务",
                description="触发一次指定任务执行。",
            ),
            AssistantCommand(
                command=f"{prefix}task-disable",
                title="停用任务",
                description="停用指定任务。",
            ),
        ]

    def handle(self, command_request: dict[str, Any]) -> dict[str, Any]:
        command = str(command_request.get("command") or "").strip()
        return OperationResult(
            success=True,
            message="企业微信助手消息已接收。",
            data={
                "command": command,
                "configured": self._is_configured(),
            },
        ).model_dump(mode="json")

    def _is_configured(self) -> bool:
        required = ("corp_id", "agent_id", "callback_token", "encoding_aes_key")
        return all(bool(str(self._runtime_config.get(key) or "").strip()) for key in required)

    @staticmethod
    def _normalize_runtime_config(config: dict[str, Any] | None) -> dict[str, Any]:
        return dict(config or {})


plugin = WecomAssistantBotPlugin()
