# 最小 drive 插件示例

网盘插件接口比资源插件和任务插件更宽，这份示例的目标不是“一次写完所有真实能力”，而是给出一个可以快速起步的最小骨架。

## 目录结构

```text
plugins/
  drive.demo/
    plugin.json
    backend/
      plugin.py
```

## `plugin.json`

```json
{
  "id": "drive.demo",
  "name": "演示网盘插件",
  "version": "0.1.0",
  "category": "drive",
  "description": "最小 drive 插件示例",
  "core_version": ">=1.0.0 <2.0.0",
  "contract_version": "1.0",
  "capabilities": [
    "drive.account",
    "drive.fs",
    "drive.share",
    "drive.download"
  ],
  "backend": {
    "entry": "backend.plugin:plugin"
  },
  "permissions": [
    "network"
  ],
  "dependencies": [],
  "config_schema": [],
  "ui": {
    "menus": [],
    "settings_sections": [],
    "task_templates": []
  }
}
```

## `backend/plugin.py`

```python
from __future__ import annotations

from typing import Any

from core.sdk import BasePlugin, HealthReport


class DemoDrivePlugin(BasePlugin):
    plugin_id = "drive.demo"
    plugin_name = "演示网盘插件"
    plugin_version = "0.1.0"

    def health(self, ctx: dict[str, Any]) -> HealthReport:
        return HealthReport(status="ok", message="demo drive plugin is ready")

    def get_contract(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "cloud_type": "demo",
            "display_name": "演示网盘",
            "account_mode": "user",
            "capabilities": ["drive.account", "drive.fs", "drive.share", "drive.download"],
            "account_form_schema": [
                {
                    "key": "token",
                    "label": "访问令牌",
                    "type": "string",
                    "required": True,
                    "default": "",
                    "description": "演示账号令牌",
                    "secret": True,
                }
            ],
            "supported_auth_types": ["token"],
            "supported_actions": {
                "account": ["test", "refresh"],
                "fs": ["list", "get_item"],
                "share": ["parse", "save"],
                "file": ["download_link"],
            },
            "share_url_patterns": ["https://demo.example.com/s/"],
        }

    def get_account_form_schema(self) -> list[dict[str, Any]]:
        return self.get_contract()["account_form_schema"]

    def test_account(self, payload: dict[str, Any]) -> dict[str, Any]:
        token = str(payload.get("token") or "").strip()
        return {
            "success": bool(token),
            "message": "ok" if token else "token is required",
        }

    def create_account_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"token": str(payload.get("token") or "").strip()}

    def get_account_info(self, account_ref: dict[str, Any]) -> dict[str, Any]:
        return {
            "account_id": str(account_ref.get("account_id") or "demo-account"),
            "plugin_id": self.plugin_id,
            "cloud_type": "demo",
            "display_name": "演示账号",
            "status": "ok",
            "supported_actions": ["list", "parse_share", "save_share"],
        }

    def refresh_account(self, account_ref: dict[str, Any]) -> dict[str, Any]:
        return self.get_account_info(account_ref)

    def start_scan_login(self) -> dict[str, Any]:
        return {"success": False, "message": "scan login is not supported in demo plugin"}

    def get_scan_status(self, scan_id: str) -> dict[str, Any]:
        return {"success": False, "message": "scan login is not supported in demo plugin"}

    def cancel_scan_login(self, scan_id: str) -> dict[str, Any]:
        return {"success": False, "message": "scan login is not supported in demo plugin"}

    def list_files(self, account_ref: dict[str, Any], parent_id: str, page: int, page_size: int) -> dict[str, Any]:
        return {
            "items": [
                {
                    "id": "demo-folder",
                    "name": "演示目录",
                    "type": "folder",
                    "parent_id": parent_id,
                }
            ],
            "total": 1,
            "parent_id": parent_id,
            "path_nodes": [],
        }

    def get_item(self, account_ref: dict[str, Any], item_id: str) -> dict[str, Any]:
        return {
            "id": item_id,
            "name": "演示文件",
            "type": "file",
            "parent_id": "0",
        }

    def list_folders(self, account_ref: dict[str, Any], parent_id: str) -> dict[str, Any]:
        return self.list_files(account_ref, parent_id, 1, 100)

    def resolve_path(self, account_ref: dict[str, Any], item_id: str) -> dict[str, Any]:
        return {
            "items": [],
            "total": 0,
            "parent_id": item_id,
            "path_nodes": [{"id": item_id, "name": "演示路径"}],
        }

    def mkdir(self, account_ref: dict[str, Any], parent_id: str, name: str) -> dict[str, Any]:
        return {"success": True, "item_id": "new-folder", "name": name}

    def rename(self, account_ref: dict[str, Any], item_id: str, new_name: str) -> dict[str, Any]:
        return {"success": True, "item_id": item_id, "name": new_name}

    def delete(self, account_ref: dict[str, Any], item_ids: list[str]) -> dict[str, Any]:
        return {"success": True, "deleted_count": len(item_ids)}

    def create_share(self, account_ref: dict[str, Any], item_ids: list[str], options: dict[str, Any]) -> dict[str, Any]:
        return {"success": False, "message": "create_share is not implemented in demo plugin"}

    def parse_share(self, account_ref: dict[str, Any], share_ref: dict[str, Any]) -> dict[str, Any]:
        share_url = str(share_ref.get("share_url") or "").strip()
        return {
            "share_id": "demo-share",
            "share_name": "演示分享",
            "share_url": share_url,
            "normalized_url": share_url,
            "can_save": True,
            "root_id": "0",
        }

    def browse_share(self, account_ref: dict[str, Any], share_ref: dict[str, Any], parent_id: str | None = None) -> dict[str, Any]:
        return {
            "items": [
                {
                    "id": "share-file-001",
                    "name": "演示分享文件.mp4",
                    "type": "file",
                    "parent_id": parent_id or "0",
                }
            ],
            "total": 1,
            "parent_id": parent_id or "0",
            "path_nodes": [],
        }

    def save_share(
        self,
        account_ref: dict[str, Any],
        share_ref: dict[str, Any],
        target_parent_id: str,
        selected_items: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "success": True,
            "message": "share saved",
            "saved_count": len(selected_items or []),
            "target_parent_id": target_parent_id,
        }

    def get_download_link(self, account_ref: dict[str, Any], item_id: str) -> dict[str, Any]:
        return {
            "item_id": item_id,
            "url": f"https://demo.example.com/download/{item_id}",
            "headers": {},
        }

    def get_supported_actions(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "account": ["test", "refresh"],
            "fs": ["list", "get_item", "mkdir", "rename", "delete"],
            "share": ["parse", "browse", "save"],
            "file": ["download_link"],
        }


plugin = DemoDrivePlugin()
```

## 开发建议

- 第一版优先保证 `test_account()`、`list_files()`、`parse_share()`、`save_share()` 四条链路
- 不支持的能力不要省略方法，直接返回明确失败信息
- 真正接第三方网盘前，先把返回结构用 mock 跑通
