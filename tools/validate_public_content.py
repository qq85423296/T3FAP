from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


FILE_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.json")
STATUSES = {"draft", "published", "offline"}
ANNOUNCEMENT_TYPES = {"notice", "update", "important"}
ACTION_TARGETS = {"self", "blank"}
BOOLEAN_FIELDS = {
    "show_popup",
    "show_every_visit",
    "require_agreement",
    "allow_skip_next_prompt",
    "show_badge",
}


def load_json(path: Path, problems: list[str]) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        problems.append(f"{path}: 无法读取 JSON：{exc}")
        return None


def require_mapping(value: Any, label: str, problems: list[str]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        problems.append(f"{label}: 必须是 JSON 对象")
        return None
    return value


def require_text(record: dict[str, Any], key: str, label: str, problems: list[str]) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        problems.append(f"{label}: {key} 必须是非空字符串")
        return ""
    return value.strip()


def validate_time(
    record: dict[str, Any],
    key: str,
    label: str,
    problems: list[str],
    *,
    required: bool,
) -> None:
    value = record.get(key)
    if value is None and not required:
        return
    if not isinstance(value, str) or not value.strip():
        problems.append(f"{label}: {key} 必须是带时区的 ISO 8601 时间")
        return
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        problems.append(f"{label}: {key} 不是有效的 ISO 8601 时间")
        return
    if parsed.tzinfo is None:
        problems.append(f"{label}: {key} 必须包含时区")


def validate_action(record: dict[str, Any], label: str, problems: list[str]) -> None:
    action_url = record.get("action_url")
    if action_url is not None:
        if not isinstance(action_url, str) or not action_url.strip():
            problems.append(f"{label}: action_url 必须是 null 或完整 HTTPS 地址")
        else:
            parsed = urlparse(action_url.strip())
            if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
                problems.append(f"{label}: action_url 仅允许不含账号信息的完整 HTTPS 地址")
    action_target = record.get("action_target", "blank")
    if action_target not in ACTION_TARGETS:
        problems.append(f"{label}: action_target 必须是 self 或 blank")


def validate_changelog(content_root: Path, problems: list[str]) -> int:
    path = content_root / "changelog.json"
    document = require_mapping(load_json(path, problems), str(path), problems)
    if document is None:
        return 0
    if document.get("schema_version") != 1:
        problems.append(f"{path}: schema_version 必须为 1")
    validate_time(document, "updated_at", str(path), problems, required=True)

    items = document.get("items")
    if not isinstance(items, list):
        problems.append(f"{path}: items 必须是数组")
        return 0
    if len(items) > 200:
        problems.append(f"{path}: 更新日志最多 200 条")

    ids: set[str] = set()
    for index, value in enumerate(items):
        label = f"{path} items[{index}]"
        item = require_mapping(value, label, problems)
        if item is None:
            continue
        item_id = require_text(item, "id", label, problems)
        require_text(item, "title", label, problems)
        require_text(item, "content", label, problems)
        if item_id in ids:
            problems.append(f"{label}: id {item_id!r} 重复")
        ids.add(item_id)
        if item.get("status") not in STATUSES:
            problems.append(f"{label}: status 必须是 draft、published 或 offline")
        validate_time(item, "published_at", label, problems, required=True)
        validate_time(item, "updated_at", label, problems, required=True)
        validate_time(item, "created_at", label, problems, required=False)
        validate_action(item, label, problems)
    return len(items)


def validate_announcement(
    path: Path,
    value: Any,
    ids: set[str],
    problems: list[str],
) -> None:
    label = str(path)
    item = require_mapping(value, label, problems)
    if item is None:
        return
    item_id = require_text(item, "id", label, problems)
    require_text(item, "title", label, problems)
    require_text(item, "content", label, problems)
    if item_id in ids:
        problems.append(f"{label}: id {item_id!r} 重复")
    ids.add(item_id)
    if item.get("type") not in ANNOUNCEMENT_TYPES:
        problems.append(f"{label}: type 必须是 notice、update 或 important")
    if item.get("status") not in STATUSES:
        problems.append(f"{label}: status 必须是 draft、published 或 offline")
    for key in BOOLEAN_FIELDS:
        if key in item and not isinstance(item[key], bool):
            problems.append(f"{label}: {key} 必须是布尔值")
    for key in ("published_at", "expired_at", "created_at"):
        validate_time(item, key, label, problems, required=False)
    validate_time(item, "updated_at", label, problems, required=True)
    validate_action(item, label, problems)


def validate_announcements(content_root: Path, problems: list[str]) -> int:
    announcements_root = content_root / "announcements"
    index_path = announcements_root / "index.json"
    manifest = require_mapping(load_json(index_path, problems), str(index_path), problems)
    if manifest is None:
        return 0
    if manifest.get("schema_version") != 1:
        problems.append(f"{index_path}: schema_version 必须为 1")
    validate_time(manifest, "updated_at", str(index_path), problems, required=True)

    entries = manifest.get("items")
    if not isinstance(entries, list):
        problems.append(f"{index_path}: items 必须是数组")
        return 0
    if len(entries) > 100:
        problems.append(f"{index_path}: 公告最多 100 条")

    files: list[str] = []
    for index, value in enumerate(entries):
        label = f"{index_path} items[{index}]"
        entry = require_mapping(value, label, problems)
        if entry is None:
            continue
        file_name = require_text(entry, "file", label, problems)
        if not FILE_NAME_PATTERN.fullmatch(file_name) or file_name == "index.json":
            problems.append(f"{label}: file 文件名无效")
            continue
        files.append(file_name)
    if len(set(files)) != len(files):
        problems.append(f"{index_path}: 清单包含重复文件")

    ids: set[str] = set()
    for file_name in files:
        path = announcements_root / file_name
        if not path.is_file():
            problems.append(f"{index_path}: 清单文件 {file_name!r} 不存在")
            continue
        validate_announcement(path, load_json(path, problems), ids, problems)

    actual_files = {
        path.name
        for path in announcements_root.glob("*.json")
        if path.is_file() and path.name != "index.json"
    }
    for file_name in sorted(actual_files - set(files)):
        problems.append(f"{announcements_root / file_name}: 文件未加入 index.json")
    return len(files)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    content_root = repo_root / "content"
    problems: list[str] = []
    changelog_count = validate_changelog(content_root, problems)
    announcement_count = validate_announcements(content_root, problems)

    if problems:
        print("Public content validation failed:")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print(f"Public content validation passed: {changelog_count} changelog items, {announcement_count} announcements.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
