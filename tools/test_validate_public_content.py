from __future__ import annotations

import copy
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Callable


TOOLS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_ROOT.parent
CONTENT_ROOT = REPO_ROOT / "content"
HELP_PATH = CONTENT_ROOT / "help" / "index.json"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

import validate_public_content as validator  # noqa: E402


class PublicContentValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.real_help = json.loads(HELP_PATH.read_text(encoding="utf-8"))

    def setUp(self) -> None:
        self.document = copy.deepcopy(self.real_help)

    def validate_document(
        self, document: dict[str, Any] | None = None
    ) -> tuple[int, list[str]]:
        problems: list[str] = []
        count = validator.validate_help_document(
            self.document if document is None else document,
            HELP_PATH,
            problems,
        )
        return count, problems

    def assert_rejected(
        self,
        mutate: Callable[[dict[str, Any]], None],
        expected_message: str,
    ) -> None:
        mutate(self.document)
        _, problems = self.validate_document()
        self.assertTrue(problems, "修改后的帮助文档应校验失败")
        messages = "\n".join(problems)
        self.assertIn(expected_message, messages)
        self.assertIn(str(HELP_PATH), messages)

    def test_real_help_index_passes_and_main_prints_help_count(self) -> None:
        problems: list[str] = []
        count = validator.validate_help(CONTENT_ROOT, problems)
        self.assertEqual([], problems)
        self.assertEqual(len(self.real_help["items"]), count)

        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = validator.main()
        self.assertEqual(0, exit_code)
        self.assertRegex(
            output.getvalue().strip(),
            rf"Public content validation passed: \d+ changelog items, "
            rf"\d+ announcements, {count} help documents\.",
        )

    def test_existing_changelog_and_announcements_still_pass(self) -> None:
        problems: list[str] = []
        changelog_count = validator.validate_changelog(CONTENT_ROOT, problems)
        announcement_count = validator.validate_announcements(CONTENT_ROOT, problems)
        self.assertEqual([], problems)
        self.assertGreater(changelog_count, 0)
        self.assertGreater(announcement_count, 0)

    def test_unknown_block_is_rejected(self) -> None:
        self.assert_rejected(
            lambda document: document["items"][0]["sections"][0]["blocks"][0].update(
                type="mystery-block"
            ),
            "未知块类型",
        )

    def test_duplicate_slug_is_rejected(self) -> None:
        self.assert_rejected(
            lambda document: document["items"][1].update(
                slug=document["items"][2]["slug"]
            ),
            "slug 'install' 重复",
        )

    def test_missing_home_is_rejected(self) -> None:
        self.assert_rejected(
            lambda document: document["items"][0].update(slug="home"),
            "当前 0 个",
        )

    def test_multiple_homes_are_rejected(self) -> None:
        self.assert_rejected(
            lambda document: document["items"][1].update(slug=""),
            "当前 2 个",
        )

    def test_javascript_link_is_rejected(self) -> None:
        self.assert_rejected(
            lambda document: document["items"][0]["sections"][0]["blocks"][0][
                "actions"
            ][0].update(to="javascript:alert(1)"),
            "to 仅允许 /guide",
        )

    def test_invalid_or_naive_updated_at_is_rejected(self) -> None:
        for value in ("not-a-time", "2026-11-15T03:00:00"):
            with self.subTest(value=value):
                self.assert_rejected(
                    lambda document, invalid=value: document.update(updated_at=invalid),
                    "updated_at",
                )

    def test_non_boolean_code_option_is_rejected(self) -> None:
        def mutate(document: dict[str, Any]) -> None:
            code_block = next(
                block
                for item in document["items"]
                for section in item["sections"]
                for block in section["blocks"]
                if block["type"] == "code"
            )
            code_block["defaultWrapped"] = "true"

        self.assert_rejected(mutate, "defaultWrapped 必须是布尔值")

    def test_numbers_cannot_replace_text(self) -> None:
        self.assert_rejected(
            lambda document: document["items"][0].update(title=123),
            "title 必须是非空字符串",
        )

    def test_all_block_types_and_optional_fields_are_accepted(self) -> None:
        def param_row(name: str, children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            row: dict[str, Any] = {
                "name": name,
                "type": "string",
                "required": False,
                "defaultValue": "-",
                "description": "参数说明",
                "example": "example",
            }
            if children is not None:
                row["children"] = children
            return row

        blocks = [
            {
                "type": "hero",
                "title": "标题",
                "subtitle": "副标题",
                "actions": [
                    {
                        "label": "内部链接",
                        "to": "/guide/install#prepare-install",
                        "variant": "primary",
                        "external": True,
                    },
                    {
                        "label": "外部链接",
                        "to": "https://example.com/docs?q=1#part",
                        "variant": "ghost",
                        "external": False,
                    },
                ],
                "badges": ["标签"],
            },
            {"type": "paragraph", "text": "正文"},
            {"type": "bullet-list", "items": ["第一项"]},
            {"type": "callout", "tone": "info", "title": "提示", "text": "内容"},
            {
                "type": "code",
                "language": "json",
                "title": "示例",
                "description": "说明",
                "code": "{}",
                "variant": "example",
                "collapsible": True,
                "defaultWrapped": False,
            },
            {
                "type": "param-table",
                "title": "参数",
                "description": "参数表",
                "rows": [param_row("parent", [param_row("child", [param_row("leaf")])])],
            },
            {
                "type": "card-grid",
                "columns": 2,
                "items": [
                    {
                        "title": "卡片",
                        "description": "卡片说明",
                        "icon": "book",
                        "to": "/guide",
                        "actionLabel": "查看",
                        "notes": ["备注"],
                    }
                ],
            },
            {
                "type": "meta-grid",
                "items": [
                    {
                        "label": "名称",
                        "value": "值",
                        "to": "https://example.com",
                        "external": False,
                    }
                ],
            },
            {
                "type": "step-list",
                "items": [
                    {
                        "title": "步骤",
                        "description": "步骤说明",
                        "details": [],
                        "imageLabel": "截图",
                        "tip": {"tone": "success", "title": "完成", "text": "已完成"},
                    }
                ],
            },
            {
                "type": "faq-list",
                "items": [
                    {
                        "question": "问题",
                        "answer": "答案",
                        "steps": ["第一步"],
                        "tone": "warning",
                        "keywords": ["关键词"],
                    }
                ],
            },
        ]
        self.document["items"][0]["sections"][0]["blocks"] = blocks
        _, problems = self.validate_document()
        self.assertEqual([], problems)

    def test_link_rules(self) -> None:
        action = self.document["items"][0]["sections"][0]["blocks"][0]["actions"][0]
        accepted = (
            "/guide",
            "/guide#welcome",
            "/guide/install",
            "/guide/install#prepare-install",
            "https://example.com/path?q=1#part",
        )
        for target in accepted:
            with self.subTest(target=target, accepted=True):
                action["to"] = target
                _, problems = self.validate_document()
                self.assertEqual([], problems)

        rejected = (
            "javascript:alert(1)",
            "data:text/html,hello",
            "//example.com/path",
            "/api/health",
            "http://example.com",
            "https://user:password@example.com",
            "/guide/Invalid",
            "/guide/install?query=1",
        )
        for target in rejected:
            with self.subTest(target=target, accepted=False):
                action["to"] = target
                _, problems = self.validate_document()
                self.assertTrue(any("to 仅允许" in problem for problem in problems))

    def test_required_arrays_cannot_be_empty(self) -> None:
        cases = (
            ({"type": "hero", "title": "标题", "subtitle": "副标题", "actions": []}, "actions"),
            ({"type": "hero", "title": "标题", "subtitle": "副标题", "badges": []}, "badges"),
            ({"type": "bullet-list", "items": []}, "items"),
            ({"type": "param-table", "rows": []}, "rows"),
            ({"type": "card-grid", "items": []}, "items"),
            ({"type": "meta-grid", "items": []}, "items"),
            ({"type": "step-list", "items": []}, "items"),
            ({"type": "faq-list", "items": []}, "items"),
        )
        for block, key in cases:
            with self.subTest(block=block["type"], key=key):
                problems: list[str] = []
                validator.validate_help_block(block, str(HELP_PATH), problems)
                self.assertIn(f"{key} 不能为空数组", "\n".join(problems))

    def test_param_rows_have_at_most_three_levels(self) -> None:
        def row(children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            value: dict[str, Any] = {
                "name": "name",
                "type": "string",
                "required": True,
                "defaultValue": "-",
                "description": "说明",
                "example": "示例",
            }
            if children is not None:
                value["children"] = children
            return value

        block = {"type": "param-table", "rows": [row([row([row([row()])])])]}
        problems: list[str] = []
        validator.validate_help_block(block, str(HELP_PATH), problems)
        self.assertIn("最多 3 层", "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
