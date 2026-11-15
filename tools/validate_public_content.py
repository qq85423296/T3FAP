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
HELP_SLUG_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]*")
HELP_SECTION_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
HELP_IMAGE_PATTERN = re.compile(r"assets/[A-Za-z0-9][A-Za-z0-9/_-]*\.(?:png|jpe?g|webp)")
DEFAULT_HELP_ROOT = Path(__file__).resolve().parents[1] / "content" / "help"
HELP_INTERNAL_LINK_PATTERN = re.compile(
    r"/guide(?:/[a-z0-9][a-z0-9-]*)?(?:#[A-Za-z0-9][A-Za-z0-9_-]*)?"
)
HELP_TONES = {"info", "success", "warning", "error"}
HELP_CODE_LANGUAGES = {"json", "javascript", "shell", "text"}
HELP_CODE_VARIANTS = {"example", "success", "error"}
HELP_ACTION_VARIANTS = {"primary", "secondary", "ghost"}
HELP_BLOCK_TYPES = {
    "hero",
    "paragraph",
    "bullet-list",
    "callout",
    "code",
    "param-table",
    "card-grid",
    "meta-grid",
    "step-list",
    "faq-list",
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


def validate_optional_text(
    record: dict[str, Any],
    key: str,
    label: str,
    problems: list[str],
) -> None:
    if key in record and not isinstance(record[key], str):
        problems.append(f"{label}: {key} 必须是字符串")


def require_help_array(
    record: dict[str, Any],
    key: str,
    label: str,
    problems: list[str],
    *,
    required: bool = True,
    allow_empty: bool = False,
) -> list[Any] | None:
    if key not in record:
        if required:
            problems.append(f"{label}: {key} 必须是数组")
        return None
    value = record[key]
    if not isinstance(value, list):
        problems.append(f"{label}: {key} 必须是数组")
        return None
    if not value and not allow_empty:
        problems.append(f"{label}: {key} 不能为空数组")
    return value


def validate_help_string_array(
    record: dict[str, Any],
    key: str,
    label: str,
    problems: list[str],
    *,
    required: bool = False,
    allow_empty: bool = True,
) -> None:
    values = require_help_array(
        record,
        key,
        label,
        problems,
        required=required,
        allow_empty=allow_empty,
    )
    if values is None:
        return
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{label} {key}[{index}]: 必须是非空字符串")


def validate_help_boolean(
    record: dict[str, Any],
    key: str,
    label: str,
    problems: list[str],
    *,
    required: bool = False,
) -> None:
    if key not in record:
        if required:
            problems.append(f"{label}: {key} 必须是布尔值")
        return
    if not isinstance(record[key], bool):
        problems.append(f"{label}: {key} 必须是布尔值")


def validate_help_link(
    record: dict[str, Any],
    key: str,
    label: str,
    problems: list[str],
    *,
    required: bool = False,
) -> None:
    if key not in record:
        if required:
            problems.append(f"{label}: {key} 必须是有效的帮助链接")
        return
    value = record[key]
    if not isinstance(value, str) or not value.strip():
        problems.append(f"{label}: {key} 必须是非空链接字符串")
        return
    target = value.strip()
    if HELP_INTERNAL_LINK_PATTERN.fullmatch(target):
        return
    try:
        parsed = urlparse(target)
        is_https_url = (
            parsed.scheme == "https"
            and bool(parsed.netloc)
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )
        # 访问 port 可顺便拒绝非数字或超出范围的端口。
        _ = parsed.port
    except ValueError:
        is_https_url = False
    if not is_https_url:
        problems.append(
            f"{label}: {key} 仅允许 /guide、/guide/<slug>（可带 #section）"
            "或不含用户名密码的完整 HTTPS 地址"
        )


def validate_help_action(value: Any, label: str, problems: list[str]) -> None:
    action = require_mapping(value, label, problems)
    if action is None:
        return
    require_text(action, "label", label, problems)
    validate_help_link(action, "to", label, problems, required=True)
    if "variant" in action and (
        not isinstance(action["variant"], str) or action["variant"] not in HELP_ACTION_VARIANTS
    ):
        problems.append(f"{label}: variant 必须是 primary、secondary 或 ghost")
    validate_help_boolean(action, "external", label, problems)


def validate_help_param_rows(
    rows: list[Any],
    label: str,
    problems: list[str],
    *,
    depth: int,
) -> None:
    for index, value in enumerate(rows):
        row_label = f"{label}[{index}]"
        row = require_mapping(value, row_label, problems)
        if row is None:
            continue
        for key in ("name", "type", "defaultValue", "description", "example"):
            require_text(row, key, row_label, problems)
        validate_help_boolean(row, "required", row_label, problems, required=True)
        if "children" not in row:
            continue
        if depth >= 3:
            problems.append(f"{row_label}: children 会使参数行超过最多 3 层的限制")
            continue
        children = require_help_array(row, "children", row_label, problems)
        if children is not None:
            validate_help_param_rows(
                children,
                f"{row_label} children",
                problems,
                depth=depth + 1,
            )


def validate_help_block(
    value: Any,
    label: str,
    problems: list[str],
    help_root: Path = DEFAULT_HELP_ROOT,
) -> None:
    block = require_mapping(value, label, problems)
    if block is None:
        return
    block_type = block.get("type")
    if not isinstance(block_type, str) or block_type not in HELP_BLOCK_TYPES:
        problems.append(f"{label}: 未知块类型 {block_type!r}")
        return

    if block_type == "hero":
        require_text(block, "title", label, problems)
        require_text(block, "subtitle", label, problems)
        actions = require_help_array(block, "actions", label, problems, required=False)
        if actions is not None:
            for index, action in enumerate(actions):
                validate_help_action(action, f"{label} actions[{index}]", problems)
        validate_help_string_array(block, "badges", label, problems, allow_empty=False)
        return

    if block_type == "paragraph":
        require_text(block, "text", label, problems)
        return

    if block_type == "bullet-list":
        validate_help_string_array(
            block,
            "items",
            label,
            problems,
            required=True,
            allow_empty=False,
        )
        return

    if block_type == "callout":
        if not isinstance(block.get("tone"), str) or block["tone"] not in HELP_TONES:
            problems.append(f"{label}: tone 必须是 info、success、warning 或 error")
        require_text(block, "title", label, problems)
        require_text(block, "text", label, problems)
        return

    if block_type == "code":
        if (
            not isinstance(block.get("language"), str)
            or block["language"] not in HELP_CODE_LANGUAGES
        ):
            problems.append(f"{label}: language 必须是 json、javascript、shell 或 text")
        validate_optional_text(block, "title", label, problems)
        validate_optional_text(block, "description", label, problems)
        require_text(block, "code", label, problems)
        if "variant" in block and (
            not isinstance(block["variant"], str) or block["variant"] not in HELP_CODE_VARIANTS
        ):
            problems.append(f"{label}: variant 必须是 example、success 或 error")
        validate_help_boolean(block, "collapsible", label, problems)
        validate_help_boolean(block, "defaultWrapped", label, problems)
        return

    if block_type == "param-table":
        validate_optional_text(block, "title", label, problems)
        validate_optional_text(block, "description", label, problems)
        rows = require_help_array(block, "rows", label, problems)
        if rows is not None:
            validate_help_param_rows(rows, f"{label} rows", problems, depth=1)
        return

    if block_type == "card-grid":
        if "columns" in block and block["columns"] not in (2, 3, 4):
            problems.append(f"{label}: columns 只能是 2、3 或 4")
        items = require_help_array(block, "items", label, problems)
        if items is not None:
            for index, value in enumerate(items):
                item_label = f"{label} items[{index}]"
                item = require_mapping(value, item_label, problems)
                if item is None:
                    continue
                require_text(item, "title", item_label, problems)
                require_text(item, "description", item_label, problems)
                validate_optional_text(item, "icon", item_label, problems)
                validate_help_link(item, "to", item_label, problems)
                validate_optional_text(item, "actionLabel", item_label, problems)
                validate_help_string_array(item, "notes", item_label, problems)
        return

    if block_type == "meta-grid":
        items = require_help_array(block, "items", label, problems)
        if items is not None:
            for index, value in enumerate(items):
                item_label = f"{label} items[{index}]"
                item = require_mapping(value, item_label, problems)
                if item is None:
                    continue
                require_text(item, "label", item_label, problems)
                require_text(item, "value", item_label, problems)
                validate_help_link(item, "to", item_label, problems)
                validate_help_boolean(item, "external", item_label, problems)
        return

    if block_type == "step-list":
        items = require_help_array(block, "items", label, problems)
        if items is not None:
            for index, value in enumerate(items):
                item_label = f"{label} items[{index}]"
                item = require_mapping(value, item_label, problems)
                if item is None:
                    continue
                require_text(item, "title", item_label, problems)
                require_text(item, "description", item_label, problems)
                validate_help_string_array(
                    item,
                    "details",
                    item_label,
                    problems,
                    required=True,
                    allow_empty=True,
                )
                validate_optional_text(item, "imageLabel", item_label, problems)
                if "screenshot" in item:
                    screenshot_label = f"{item_label} screenshot"
                    screenshot = require_mapping(item["screenshot"], screenshot_label, problems)
                    if screenshot is not None:
                        src = require_text(screenshot, "src", screenshot_label, problems)
                        require_text(screenshot, "alt", screenshot_label, problems)
                        require_text(screenshot, "caption", screenshot_label, problems)
                        if src and not HELP_IMAGE_PATTERN.fullmatch(src):
                            problems.append(
                                f"{screenshot_label}: src 仅允许 assets/ 下的 PNG、JPEG 或 WebP 图片"
                            )
                        elif src and not (help_root / src).is_file():
                            problems.append(f"{screenshot_label}: 图片文件 {src!r} 不存在")
                        for dimension in ("width", "height"):
                            value = screenshot.get(dimension)
                            if type(value) is not int or not 1 <= value <= 5000:
                                problems.append(
                                    f"{screenshot_label}: {dimension} 必须是 1 到 5000 的整数"
                                )
                if "tip" in item:
                    tip = require_mapping(item["tip"], f"{item_label} tip", problems)
                    if tip is not None:
                        if not isinstance(tip.get("tone"), str) or tip["tone"] not in HELP_TONES:
                            problems.append(
                                f"{item_label} tip: tone 必须是 info、success、warning 或 error"
                            )
                        require_text(tip, "title", f"{item_label} tip", problems)
                        require_text(tip, "text", f"{item_label} tip", problems)
        return

    items = require_help_array(block, "items", label, problems)
    if items is not None:
        for index, value in enumerate(items):
            item_label = f"{label} items[{index}]"
            item = require_mapping(value, item_label, problems)
            if item is None:
                continue
            require_text(item, "question", item_label, problems)
            require_text(item, "answer", item_label, problems)
            validate_help_string_array(item, "steps", item_label, problems)
            if "tone" in item and (
                not isinstance(item["tone"], str) or item["tone"] not in HELP_TONES
            ):
                problems.append(f"{item_label}: tone 必须是 info、success、warning 或 error")
            validate_help_string_array(item, "keywords", item_label, problems)


def validate_help_section(
    value: Any,
    label: str,
    section_ids: set[str],
    problems: list[str],
    help_root: Path = DEFAULT_HELP_ROOT,
) -> None:
    section = require_mapping(value, label, problems)
    if section is None:
        return
    section_id = require_text(section, "id", label, problems)
    if section_id and not HELP_SECTION_ID_PATTERN.fullmatch(section_id):
        problems.append(f"{label}: id 只能包含字母、数字、下划线和连字符，且必须以字母或数字开头")
    if section_id in section_ids:
        problems.append(f"{label}: section id {section_id!r} 在文档内重复")
    section_ids.add(section_id)
    require_text(section, "title", label, problems)
    validate_optional_text(section, "description", label, problems)
    validate_optional_text(section, "key", label, problems)
    if section.get("level") not in (2, 3):
        problems.append(f"{label}: level 只能是 2 或 3")
    blocks = require_help_array(section, "blocks", label, problems)
    if blocks is None:
        return
    if len(blocks) > 60:
        problems.append(f"{label}: blocks 最多 60 项")
    for index, block in enumerate(blocks):
        validate_help_block(block, f"{label} blocks[{index}]", problems, help_root=help_root)


def validate_help_document(document: dict[str, Any], path: Path, problems: list[str]) -> int:
    schema_version = document.get("schema_version")
    if type(schema_version) is not int or schema_version != 1:
        problems.append(f"{path}: schema_version 必须为 1")
    validate_time(document, "updated_at", str(path), problems, required=True)

    items = document.get("items")
    if not isinstance(items, list):
        problems.append(f"{path}: items 必须是数组")
        return 0
    if not 1 <= len(items) <= 32:
        problems.append(f"{path}: items 必须包含 1 到 32 个文档")

    ids: set[str] = set()
    slugs: set[str] = set()
    home_count = 0
    for index, value in enumerate(items):
        label = f"{path} items[{index}]"
        item = require_mapping(value, label, problems)
        if item is None:
            continue
        item_id = require_text(item, "id", label, problems)
        for key in ("navTitle", "title", "subtitle", "group"):
            require_text(item, key, label, problems)
        validate_optional_text(item, "description", label, problems)
        validate_optional_text(item, "icon", label, problems)
        if item_id in ids:
            problems.append(f"{label}: id {item_id!r} 重复")
        ids.add(item_id)

        slug = item.get("slug")
        if not isinstance(slug, str):
            problems.append(f"{label}: slug 必须是字符串，仅首页允许空字符串")
        else:
            if not slug:
                home_count += 1
            elif not HELP_SLUG_PATTERN.fullmatch(slug):
                problems.append(f"{label}: 非首页 slug 只能匹配 ^[a-z0-9][a-z0-9-]*$")
            if slug in slugs:
                problems.append(f"{label}: slug {slug!r} 重复")
            slugs.add(slug)

        validate_help_string_array(item, "searchTags", label, problems)
        sections = require_help_array(item, "sections", label, problems)
        if sections is not None:
            if len(sections) > 50:
                problems.append(f"{label}: sections 最多 50 项")
            section_ids: set[str] = set()
            for section_index, section in enumerate(sections):
                validate_help_section(
                    section,
                    f"{label} sections[{section_index}]",
                    section_ids,
                    problems,
                    help_root=path.parent,
                )

    if home_count != 1:
        problems.append(f"{path}: 全库必须恰好有一个 slug 为空字符串的首页文档（当前 {home_count} 个）")
    return len(items)


def validate_help(content_root: Path, problems: list[str]) -> int:
    path = content_root / "help" / "index.json"
    document = require_mapping(load_json(path, problems), str(path), problems)
    if document is None:
        return 0
    return validate_help_document(document, path, problems)


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
    help_count = validate_help(content_root, problems)

    if problems:
        print("Public content validation failed:")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print(
        f"Public content validation passed: {changelog_count} changelog items, "
        f"{announcement_count} announcements, {help_count} help documents."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
