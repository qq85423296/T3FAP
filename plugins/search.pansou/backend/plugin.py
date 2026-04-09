from __future__ import annotations

import html
import os
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

from core.sdk import (
    BasePlugin,
    HealthReport,
    OperationResult,
    ResourceCapabilities,
    ResourceFilterGroup,
    ResourceFilterOption,
    ResourceItem,
    ResourceLinks,
    ResourceListPage,
    ResourceQueryResponse,
    SearchProvider,
    ShareLink,
)
from core.services.resource_http import ResourceHttpError, fetch_json

PANSOU_ENV_URL = "T3MT_PANSOU_API_URL"
PANSOU_ENV_KEY = "T3MT_PANSOU_API_KEY"
PANSOU_CONFIG_URL = "api_url"
PANSOU_CONFIG_KEY = "api_key"
PANSOU_CONFIG_REQUIRED_NOTICE = "未配置盘搜插件，请先到插件中心配置盘搜地址。"
PANSOU_SEARCH_FAILED_NOTICE = "盘搜搜索暂时不可用，请检查盘搜插件配置后重试。"
TRANSFERABLE_DRIVES = {"quark", "cloud189"}
NOTE_SPLIT_RE = re.compile(r"(?:简介|介绍|描述)[:：]?", re.IGNORECASE)
HTTP_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
QUARK_PATH_RE = re.compile(r"/s/([A-Za-z0-9_-]+)", re.IGNORECASE)
CLOUD189_CODE_RE = re.compile(r"(?:/t/|/web/share/)([A-Za-z0-9]+)", re.IGNORECASE)
ALIYUN_SHARE_RE = re.compile(r"/s/([A-Za-z0-9_-]+)", re.IGNORECASE)
MEDIA_TYPE_FILTERS = [
    ResourceFilterOption(value="all", label="全部"),
    ResourceFilterOption(value="movie", label="电影"),
    ResourceFilterOption(value="tv", label="电视剧"),
    ResourceFilterOption(value="variety", label="综艺"),
    ResourceFilterOption(value="anime", label="动漫"),
    ResourceFilterOption(value="documentary", label="纪录片"),
]
DRIVE_LABELS = {
    "quark": "夸克网盘",
    "cloud189": "天翼云盘",
    "aliyun": "阿里云盘",
    "baidu": "百度网盘",
    "115": "115 网盘",
    "xunlei": "迅雷云盘",
}


class PansouSearchPlugin(BasePlugin, SearchProvider):
    plugin_id = "search.pansou"
    plugin_name = "盘搜聚合"
    plugin_version = "0.1.1"

    def __init__(self) -> None:
        self._runtime_config: dict[str, Any] = {}

    def set_runtime_config(self, config: dict[str, Any]) -> None:
        self._runtime_config = dict(config or {})

    def validate_config(self, config: dict[str, Any]) -> OperationResult:
        api_url = str(config.get(PANSOU_CONFIG_URL) or "").strip()
        if api_url or os.getenv(PANSOU_ENV_URL, "").strip():
            return OperationResult(success=True, message="Config validation passed.", data=config)
        return OperationResult(
            success=False,
            message="盘搜地址不能为空。",
            errors=[f"Provide '{PANSOU_CONFIG_URL}' or set {PANSOU_ENV_URL}."],
        )

    def health(self, ctx: dict[str, Any]) -> HealthReport:
        api_url, _api_key = self._resolve_api_credentials()
        if api_url:
            return HealthReport(status="ok", message="Pansou search plugin is ready.")
        return HealthReport(
            status="degraded",
            message="Pansou API URL is not configured. Please configure the plugin first.",
            details={"config_key": PANSOU_CONFIG_URL, "env_key": PANSOU_ENV_URL},
        )

    def query(
        self,
        keyword: str,
        filters: dict[str, Any],
        cursor: str | None,
        limit: int,
        resource_context: dict[str, Any] | None,
    ) -> ResourceQueryResponse:
        requested_media_type = str(filters.get("media_type") or "all").strip() or "all"
        selected_drive_type = str(filters.get("drive_type") or "all").strip() or "all"

        base_groups = [
            self._build_media_type_group(requested_media_type),
            self._build_drive_type_group([], selected_drive_type),
        ]
        if not keyword.strip():
            return ResourceQueryResponse(filter_groups=base_groups, items=[], next_cursor=None, total=0)

        api_url, api_key = self._resolve_api_credentials()
        if not api_url:
            return ResourceQueryResponse(
                filter_groups=base_groups,
                items=[],
                next_cursor=None,
                total=0,
                notice=PANSOU_CONFIG_REQUIRED_NOTICE,
            )

        try:
            items = self._search_remote(keyword, api_url=api_url, api_key=api_key)
        except ResourceHttpError:
            return ResourceQueryResponse(
                filter_groups=base_groups,
                items=[],
                next_cursor=None,
                total=0,
                notice=PANSOU_SEARCH_FAILED_NOTICE,
            )

        filtered_items = self._filter_media_type(items, requested_media_type, resource_context)
        filtered_items = self._filter_drive_type(filtered_items, selected_drive_type)
        offset = self._offset_from_cursor(cursor)
        batch_size = max(min(int(limit or 20), 50), 1)
        sliced = filtered_items[offset : offset + batch_size]

        return ResourceQueryResponse(
            filter_groups=[
                self._build_media_type_group(requested_media_type),
                self._build_drive_type_group(items, selected_drive_type),
            ],
            items=sliced,
            next_cursor=str(offset + batch_size) if offset + batch_size < len(filtered_items) else None,
            total=len(filtered_items),
        )

    def search(self, keyword: str, filters: dict[str, Any], page: int) -> ResourceListPage:
        page_size = max(min(int(filters.get("page_size", 20) or 20), 50), 1)
        if filters.get("target_type") == "official":
            return ResourceListPage(items=[], page=page, page_size=page_size)

        api_url, api_key = self._resolve_api_credentials()
        if not api_url:
            return ResourceListPage(
                items=[],
                page=page,
                page_size=page_size,
                total=0,
                has_more=False,
                notice=PANSOU_CONFIG_REQUIRED_NOTICE,
            )

        try:
            items = self._search_remote(keyword, api_url=api_url, api_key=api_key)
        except ResourceHttpError:
            return ResourceListPage(
                items=[],
                page=page,
                page_size=page_size,
                total=0,
                has_more=False,
                notice=PANSOU_SEARCH_FAILED_NOTICE,
            )

        requested_media_type = str(filters.get("media_type") or "all").strip()
        if requested_media_type and requested_media_type != "all":
            for item in items:
                if item.media_type == "unknown":
                    item.media_type = requested_media_type  # type: ignore[assignment]

        drive_types = {str(entry).strip() for entry in filters.get("drive_types", []) if str(entry).strip()}
        if drive_types:
            items = [
                item
                for item in items
                if any(link.drive_type in drive_types for link in item.links.share)
            ]

        start = max(page - 1, 0) * page_size
        sliced = items[start : start + page_size]
        return ResourceListPage(
            items=sliced,
            page=page,
            page_size=page_size,
            total=len(items),
            has_more=start + page_size < len(items),
        )

    def _resolve_api_credentials(self) -> tuple[str, str]:
        api_url = str(self._runtime_config.get(PANSOU_CONFIG_URL) or "").strip()
        api_key = str(self._runtime_config.get(PANSOU_CONFIG_KEY) or "").strip()
        if not api_url:
            api_url = os.getenv(PANSOU_ENV_URL, "").strip()
        if not api_key:
            api_key = os.getenv(PANSOU_ENV_KEY, "").strip()
        return api_url, api_key

    def _search_remote(
        self,
        keyword: str,
        *,
        api_url: str,
        api_key: str,
    ) -> list[ResourceItem]:
        if not api_url:
            raise ResourceHttpError("Pansou API URL is empty.")

        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        payload = fetch_json(
            f"{api_url.rstrip('/')}/api/search",
            params={"kw": keyword, "res": "merge", "src": "all"},
            headers=headers,
        )
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        merged_by_type = data.get("merged_by_type", {})
        items: list[ResourceItem] = []
        for platform, values in merged_by_type.items():
            if not isinstance(values, list):
                continue
            for index, raw_item in enumerate(values):
                if not isinstance(raw_item, dict):
                    continue
                mapped = self._map_item(raw_item, str(platform), index=index)
                if mapped is not None:
                    items.append(mapped)
        return self._dedupe(items)

    def _map_item(
        self,
        item: dict[str, Any],
        platform: str,
        *,
        index: int,
        response_source: str = "remote",
    ) -> ResourceItem | None:
        password = str(item.get("password", "")).strip()
        share_url = self._resolve_share_url(item, platform, password=password)
        if not share_url:
            return None

        drive_type = self._normalize_drive_type(platform)
        inferred_drive_type = self._infer_drive_type_from_url(share_url)
        if inferred_drive_type:
            drive_type = inferred_drive_type

        title, description = self._split_note(str(item.get("note", "")).strip())
        source = str(item.get("source", "")).strip()
        detail_url = self._resolve_detail_url(item, share_url)
        link = ShareLink(
            drive_type=drive_type,
            label=self._drive_label(drive_type),
            url=share_url,
            password=password,
        )
        tags = [self._drive_label(drive_type)]
        if source:
            tags.append(source)

        return ResourceItem(
            id=share_url or f"{drive_type}:{index}",
            source_plugin_id=self.plugin_id,
            source_type="search",
            source_name="盘搜",
            title=title or share_url or f"盘搜结果 {index + 1}",
            subtitle=" / ".join(part for part in [self._drive_label(drive_type), source] if part),
            cover_url=self._pick_cover(item),
            detail_url=detail_url,
            target_type="share",
            links=ResourceLinks(share=[link]),
            capabilities=ResourceCapabilities(
                searchable=True,
                official_searchable=False,
                share_searchable=False,
                transferable=drive_type in TRANSFERABLE_DRIVES,
            ),
            tags=tags,
            meta={
                "description": description,
                "source": source,
                "datetime": self._normalize_datetime(str(item.get("datetime", "")).strip()),
                "platform": platform,
                "response_source": response_source,
                "raw_url": str(item.get("url", "")).strip(),
                "api_fields": sorted(item.keys()),
            },
        )

    @staticmethod
    def _pick_cover(item: dict[str, Any]) -> str:
        images = item.get("images")
        if isinstance(images, list):
            for entry in images:
                value = str(entry).strip()
                if value:
                    return value
        return ""

    @staticmethod
    def _split_note(note: str) -> tuple[str, str]:
        if not note:
            return "", ""
        parts = NOTE_SPLIT_RE.split(note, maxsplit=1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
        return note.strip(), ""

    def _resolve_share_url(self, item: dict[str, Any], platform: str, *, password: str) -> str:
        drive_type = self._normalize_drive_type(platform)
        candidates = [
            item.get("share_url"),
            item.get("shareUrl"),
            item.get("accessUrl"),
            item.get("url"),
            item.get("link"),
            item.get("jump_url"),
            item.get("jumpUrl"),
        ]
        for candidate in candidates:
            normalized = self._normalize_share_url(str(candidate or "").strip(), drive_type, password=password)
            if normalized:
                return normalized

        for field in ("note", "description", "content", "title"):
            extracted = self._extract_share_url(str(item.get(field, "")).strip(), drive_type)
            normalized = self._normalize_share_url(extracted, drive_type, password=password)
            if normalized:
                return normalized
        return ""

    def _resolve_detail_url(self, item: dict[str, Any], share_url: str) -> str:
        for key in ("detail_url", "detailUrl", "page_url", "pageUrl"):
            value = str(item.get(key, "")).strip()
            if value and value != share_url and value.startswith("http"):
                return value
        return ""

    @staticmethod
    def _extract_share_url(text: str, drive_type: str) -> str:
        for match in HTTP_URL_RE.finditer(text):
            value = match.group(0).strip()
            if PansouSearchPlugin._normalize_share_url(value, drive_type, password=""):
                return value
        return ""

    @staticmethod
    def _normalize_share_url(url: str, drive_type: str, *, password: str) -> str:
        if not url:
            return ""

        normalized = html.unescape(unquote(url)).strip()
        normalized = normalized.replace("\\/", "/")
        if normalized.startswith("//"):
            normalized = f"https:{normalized}"
        elif normalized.startswith(("pan.quark.cn/", "cloud.189.cn/", "c.189.cn/", "www.alipan.com/", "www.aliyundrive.com/", "pan.baidu.com/", "115.com/", "pan.xunlei.com/")):
            normalized = f"https://{normalized}"
        if not normalized.startswith("http"):
            return ""

        parsed = urlparse(normalized)
        host = parsed.netloc.lower()

        if drive_type == "quark" or "pan.quark.cn" in host:
            match = QUARK_PATH_RE.search(parsed.path)
            if not match:
                return ""
            return f"https://pan.quark.cn/s/{match.group(1)}"

        if drive_type == "cloud189" or host.endswith("189.cn"):
            code = ""
            query_code = parse_qs(parsed.query).get("code", [])
            if query_code:
                code = str(query_code[0]).strip()
            if not code:
                path_match = CLOUD189_CODE_RE.search(parsed.path)
                if path_match:
                    code = path_match.group(1)
            if not code and parsed.fragment:
                fragment_match = CLOUD189_CODE_RE.search(parsed.fragment)
                if fragment_match:
                    code = fragment_match.group(1)
            if not code:
                return ""
            canonical = f"https://cloud.189.cn/web/share?code={quote(code, safe='')}"
            if password:
                canonical = f"{canonical}&pwd={quote(password, safe='')}"
            return canonical

        if drive_type == "aliyun" or "aliyundrive.com" in host or "alipan.com" in host:
            share_match = ALIYUN_SHARE_RE.search(parsed.path)
            if not share_match:
                return ""
            canonical_host = "www.alipan.com" if "alipan.com" in host else "www.aliyundrive.com"
            return f"https://{canonical_host}/s/{share_match.group(1)}"

        if drive_type == "baidu" or "pan.baidu.com" in host:
            return normalized
        if drive_type == "115" or "115.com" in host:
            return normalized
        if drive_type == "xunlei" or "xunlei.com" in host:
            return normalized
        return normalized

    @staticmethod
    def _normalize_datetime(value: str) -> str:
        if not value or value == "0001-01-01T00:00:00Z":
            return ""
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return value

    @staticmethod
    def _normalize_drive_type(value: str) -> str:
        mapping = {
            "tianyi": "cloud189",
            "189": "cloud189",
            "alipan": "aliyun",
        }
        return mapping.get(value.lower(), value.lower())

    @staticmethod
    def _infer_drive_type_from_url(value: str) -> str:
        host = urlparse(value).netloc.lower()
        if "pan.quark.cn" in host:
            return "quark"
        if host.endswith("189.cn"):
            return "cloud189"
        if "alipan.com" in host or "aliyundrive.com" in host:
            return "aliyun"
        if "pan.baidu.com" in host:
            return "baidu"
        if "115.com" in host:
            return "115"
        if "xunlei.com" in host:
            return "xunlei"
        return ""

    @staticmethod
    def _drive_label(value: str) -> str:
        labels = {
            "quark": "夸克网盘",
            "cloud189": "天翼云盘",
            "aliyun": "阿里云盘",
            "baidu": "百度网盘",
            "115": "115 网盘",
            "xunlei": "迅雷云盘",
        }
        return labels.get(value, value)

    @staticmethod
    def _dedupe(items: list[ResourceItem]) -> list[ResourceItem]:
        deduped: dict[str, ResourceItem] = {}
        for item in items:
            share_url = item.links.share[0].url if item.links.share else item.id
            deduped.setdefault(share_url, item)
        return list(deduped.values())

    def _build_media_type_group(self, selected: str) -> ResourceFilterGroup:
        normalized_selected = selected if any(option.value == selected for option in MEDIA_TYPE_FILTERS) else "all"
        return ResourceFilterGroup(
            key="media_type",
            label="类型",
            level=1,
            options=MEDIA_TYPE_FILTERS,
            selected=normalized_selected,
            hidden_when_empty=False,
        )

    def _build_drive_type_group(self, items: list[ResourceItem], selected: str) -> ResourceFilterGroup:
        counts: dict[str, int] = {}
        for item in items:
            if not item.links.share:
                continue
            drive_type = item.links.share[0].drive_type
            counts[drive_type] = counts.get(drive_type, 0) + 1

        ordered_drive_types = sorted(counts.keys(), key=lambda key: (-counts[key], DRIVE_LABELS.get(key, key)))
        options = [ResourceFilterOption(value="all", label="全部网盘", count=sum(counts.values()))]
        options.extend(
            ResourceFilterOption(
                value=drive_type,
                label=DRIVE_LABELS.get(drive_type, drive_type),
                count=counts[drive_type],
            )
            for drive_type in ordered_drive_types
        )
        normalized_selected = selected if any(option.value == selected for option in options) else "all"
        return ResourceFilterGroup(
            key="drive_type",
            label="网盘",
            level=2,
            options=options,
            selected=normalized_selected,
            hidden_when_empty=False,
        )

    @staticmethod
    def _offset_from_cursor(cursor: str | None) -> int:
        try:
            if not cursor:
                return 0
            return max(int(str(cursor).strip()), 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _filter_drive_type(items: list[ResourceItem], selected_drive_type: str) -> list[ResourceItem]:
        if selected_drive_type in ("", "all"):
            return items
        return [
            item
            for item in items
            if item.links.share and item.links.share[0].drive_type == selected_drive_type
        ]

    @staticmethod
    def _filter_media_type(
        items: list[ResourceItem],
        requested_media_type: str,
        resource_context: dict[str, Any] | None,
    ) -> list[ResourceItem]:
        if requested_media_type in ("", "all"):
            return items

        inferred_media_type = requested_media_type
        if inferred_media_type == "unknown" and isinstance(resource_context, dict):
            inferred_media_type = str(resource_context.get("media_type") or "unknown").strip() or "unknown"

        filtered: list[ResourceItem] = []
        for item in items:
            if item.media_type == requested_media_type:
                filtered.append(item)
                continue
            if item.media_type == "unknown":
                item.media_type = inferred_media_type  # type: ignore[assignment]
                filtered.append(item)
        return filtered


plugin = PansouSearchPlugin()
