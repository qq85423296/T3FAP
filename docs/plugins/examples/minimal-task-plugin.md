# 最小 task 插件示例

这份示例适合快速创建一个最小任务插件，用来打通“任务模板 -> 校验 -> 执行”主链路。

## 目录结构

```text
plugins/
  task.demo/
    plugin.json
    backend/
      plugin.py
```

## `plugin.json`

```json
{
  "id": "task.demo",
  "name": "演示任务插件",
  "version": "0.1.0",
  "category": "task",
  "description": "最小 task 插件示例",
  "core_version": ">=1.0.0 <2.0.0",
  "contract_version": "1.0",
  "capabilities": [
    "task.template",
    "task.executor",
    "task.from_resource"
  ],
  "backend": {
    "entry": "backend.plugin:plugin"
  },
  "permissions": [
    "task.dispatch"
  ],
  "dependencies": [],
  "config_schema": [],
  "ui": {
    "menus": [],
    "settings_sections": [],
    "task_templates": [
      "demo_task"
    ]
  }
}
```

## `backend/plugin.py`

```python
from __future__ import annotations

from typing import Any

from core.sdk import (
    BasePlugin,
    OperationResult,
    TaskExecutionResult,
    TaskTemplate,
    TaskTypeProvider,
)


class DemoTaskPlugin(BasePlugin, TaskTypeProvider):
    plugin_id = "task.demo"
    plugin_name = "演示任务插件"
    plugin_version = "0.1.0"

    def get_template(self) -> TaskTemplate:
        return TaskTemplate(
            type_key="demo_task",
            template_key="demo_task",
            plugin_id=self.plugin_id,
            title="演示任务",
            allow_manual_creation=True,
            supported_inputs=["manual", "resource"],
            form_schema=[
                {
                    "key": "message",
                    "label": "输出消息",
                    "type": "string",
                    "required": False,
                    "default": "hello from demo task",
                }
            ],
            default_config={"message": "hello from demo task"},
            output_types=["demo.result"],
        )

    def validate_config(self, config: dict[str, Any]) -> OperationResult:
        return OperationResult(success=True, message="config is valid")

    def create_from_resource(self, resource: dict[str, Any]) -> dict[str, Any]:
        title = str(resource.get("title") or "演示任务").strip()
        return {
            "title": f"处理资源：{title}",
            "input_type": "resource",
            "input_payload": {"resource": resource},
            "config": {"message": f"from resource: {title}"},
        }

    def dry_run(self, config: dict[str, Any]) -> OperationResult:
        return OperationResult(success=True, message="dry run ok", data={"config": config})

    def execute(self, execution_context: dict[str, Any]) -> TaskExecutionResult:
        config = execution_context.get("config") or {}
        message = str(config.get("message") or "hello from demo task").strip()
        return TaskExecutionResult(
            success=True,
            status="success",
            summary=message,
            artifacts=[{"type": "text", "value": message}],
            logs=[f"demo task executed: {message}"],
        )


plugin = DemoTaskPlugin()
```

## 开发建议

- 第一版先把 `get_template()` 和 `execute()` 跑通
- `create_from_resource()` 建议尽早实现，因为很多平台动作会依赖它
- 如果任务执行时间长，记得把关键日志写进 `logs`
