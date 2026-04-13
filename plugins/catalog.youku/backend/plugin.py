from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote

from core.sdk import (
    BasePlugin,
    CatalogProvider,
    HealthReport,
    OfficialLink,
    ResourceAction,
    ResourceCapabilities,
    ResourceFilterGroup,
    ResourceFilterOption,
    ResourceItem,
    ResourceLinks,
    ResourceListPage,
    ResourceQueryResponse,
    ResourceSection,
)
from core.services.resource_http import fetch_json

YOUKU_LIST_URL = "https://www.youku.com/category/data"
YOUKU_HEADERS = {
    "Referer": "https://www.youku.com/",
    "User-Agent": "Mozilla/5.0",
}
YOUKU_SECTIONS = {
    "tv": {"title": "电视剧", "path": "EP636904", "category": "电视剧", "subIndex": 48, "spmC": "drawer3"},
    "movie": {"title": "电影", "path": "EP516623", "category": "电影", "subIndex": 48, "spmC": "drawer2"},
    "variety": {"title": "综艺", "path": "EP447978", "category": "综艺", "subIndex": 48, "spmC": "drawer2"},
    "anime": {"title": "动漫", "path": "EP118607", "category": "动漫", "subIndex": 47, "spmC": "drawer2"},
}
YOUKU_MEDIA_LABELS = {
    "movie": "电影",
    "tv": "电视剧",
    "variety": "综艺",
    "anime": "动漫",
}
YOUKU_FILTERS = [
    ResourceFilterOption(value="movie", label="Movie"),
    ResourceFilterOption(value="tv", label="TV"),
    ResourceFilterOption(value="variety", label="Variety"),
    ResourceFilterOption(value="anime", label="Anime"),
]


class YoukuCatalogPlugin(BasePlugin, CatalogProvider):
    plugin_id = "catalog.youku"
    plugin_name = "优酷探索"
    plugin_version = "0.1.9"

    def __init__(self) -> None:
        self._detail_cache: dict[str, ResourceItem] = {}

    def health(self, ctx: dict[str, Any]) -> HealthReport:
        return HealthReport(status="ok", message="Youku catalog plugin is ready.")

    def query(self, filters: dict[str, Any], cursor: str | None, limit: int) -> ResourceQueryResponse:
        media_type = self._normalize_media_type(filters.get("media_type"))
        page = self._page_from_cursor(cursor)
        page_result = self.list_items(
            media_type,
            {
                "media_type": media_type,
                "page": page,
                "page_size": limit,
            },
        )
        return ResourceQueryResponse(
            filter_groups=[
                ResourceFilterGroup(
                    key="media_type",
                    label="Type",
                    level=1,
                    options=YOUKU_FILTERS,
                    selected=media_type,
                )
            ],
            items=page_result.items,
            next_cursor=str(page + 1) if page_result.has_more else None,
            total=page_result.total,
            notice=page_result.notice,
        )

    def list_sections(self) -> list[ResourceSection]:
        return [
            ResourceSection(key=key, title=value["title"], media_type=key)
            for key, value in YOUKU_SECTIONS.items()
        ]

    def list_items(self, section: str, query: dict[str, Any]) -> ResourceListPage:
        media_type = self._normalize_media_type(section or query.get("media_type"))
        page = max(int(query.get("page", 1) or 1), 1)
        page_size = max(min(int(query.get("page_size", 12) or 12), 60), 1)

        payload = self._fetch_page(media_type, page)
        raw_items, total = self._extract_items(payload)
        items = [
            self._map_item(item, media_type, ranking=(page - 1) * page_size + index + 1)
            for index, item in enumerate(raw_items[:page_size])
        ]
        total = total or ((page - 1) * page_size + len(items))
        return ResourceListPage(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            has_more=page * page_size < total,
        )

    def get_detail(self, resource_ref: dict[str, Any]) -> ResourceItem:
        raw_id = str(resource_ref.get("id") or "").strip()
        cached = self._detail_cache.get(raw_id)
        if cached is not None:
            return cached

        detail_url = str(resource_ref.get("detail_url") or "").strip()
        if not detail_url and raw_id:
            detail_url = self._build_search_url(raw_id)

        return ResourceItem(
            id=raw_id,
            source_plugin_id=self.plugin_id,
            source_type="catalog",
            source_name="优酷",
            title=raw_id,
            subtitle="优酷资源目录",
            detail_url=detail_url,
            target_type="official",
            links=ResourceLinks(
                official=[OfficialLink(platform="youku", label="优酷详情", url=detail_url, kind="detail")]
                if detail_url
                else [],
            ),
            capabilities=ResourceCapabilities(
                searchable=True,
                official_searchable=bool(detail_url),
                share_searchable=True,
                downloadable=bool(detail_url),
                strmable=bool(detail_url),
            ),
            actions=self._build_task_actions(),
        )

    def _fetch_page(self, media_type: str, page: int) -> dict[str, Any]:
        section_meta = YOUKU_SECTIONS[media_type]
        session_data = {
            "subIndex": section_meta["subIndex"],
            "trackInfo": {"parentdrawerid": "34441"},
            "spmA": "a2h05",
            "level": 2,
            "spmC": section_meta["spmC"],
            "spmB": "8165803_SHAIXUAN_ALL",
            "index": 1,
            "pageName": "page_channelmain_SHAIXUAN_ALL",
            "scene": "search_component_paging",
            "scmB": "manual",
            "path": section_meta["path"],
            "scmA": "20140719",
            "scmC": "34441",
            "from": "SHAIXUAN",
            "id": 227939,
            "category": section_meta["category"],
        }
        params_data = {
            "type": section_meta["category"],
        }
        return fetch_json(
            YOUKU_LIST_URL,
            params={
                "session": json.dumps(session_data, separators=(",", ":"), ensure_ascii=False),
                "params": json.dumps(params_data, separators=(",", ":"), ensure_ascii=False),
                "pageNo": page,
            },
            headers=YOUKU_HEADERS,
        )

    @staticmethod
    def _extract_items(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
        filter_data = payload.get("data", {}).get("filterData", {}) if isinstance(payload, dict) else {}
        raw_items = [item for item in filter_data.get("listData", []) if isinstance(item, dict)]
        total = YoukuCatalogPlugin._to_int(filter_data.get("total")) or len(raw_items)
        return raw_items, total

    def _map_item(self, item: dict[str, Any], media_type: str, *, ranking: int) -> ResourceItem:
        detail_url = self._normalize_url(item.get("videoLink") or item.get("showLink") or item.get("link"))
        raw_id = self._extract_video_id(detail_url) or str(item.get("showId") or item.get("id") or item.get("title") or "").strip()
        title = str(item.get("title") or item.get("showTitle") or raw_id).strip()
        subtitle = str(item.get("subTitle") or item.get("summary") or "").strip()
        cover_url = self._normalize_url(item.get("img") or item.get("poster") or item.get("cover"))
        year = self._parse_year(item.get("updateNotice") or item.get("subTitle") or item.get("summary"))
        tags = ["优酷"]
        if subtitle:
            tags.append(subtitle)
        summary = str(item.get("summary") or "").strip()
        if summary and summary != subtitle:
            tags.append(summary)

        if not detail_url:
            detail_url = self._build_search_url(title)

        result = ResourceItem(
            id=raw_id,
            canonical_id=f"youku:{raw_id}" if raw_id else "",
            source_plugin_id=self.plugin_id,
            source_type="catalog",
            source_name="优酷",
            title=title,
            subtitle=self._build_subtitle(media_type, subtitle=subtitle),
            cover_url=cover_url,
            media_type=media_type,  # type: ignore[arg-type]
            year=year,
            tags=tags[:5],
            detail_url=detail_url,
            target_type="official",
            links=ResourceLinks(
                official=[
                    OfficialLink(
                        platform="youku",
                        label="优酷详情",
                        url=detail_url,
                        kind="play",
                    )
                ]
                if detail_url
                else [],
            ),
            capabilities=ResourceCapabilities(
                searchable=True,
                official_searchable=bool(detail_url),
                share_searchable=True,
                downloadable=bool(detail_url),
                strmable=bool(detail_url),
            ),
            actions=self._build_task_actions(),
            meta={
                "ranking": ranking,
                "summary": summary,
                "update_notice": str(item.get("updateNotice") or "").strip(),
                "api_fields": sorted(item.keys()),
            },
        )
        self._detail_cache[result.id] = result
        return result

    @staticmethod
    def _normalize_media_type(value: Any) -> str:
        media_type = str(value or "tv").strip()
        if media_type not in YOUKU_SECTIONS:
            return "tv"
        return media_type

    @staticmethod
    def _normalize_url(value: Any) -> str:
        text = str(value or "").strip()
        if text.startswith("//"):
            return f"https:{text}"
        if text.startswith("http://"):
            return f"https://{text[7:]}"
        return text

    @staticmethod
    def _extract_video_id(url: str) -> str:
        text = str(url or "").strip()
        for pattern in (r"/id_([^/.?]+)", r"[?&]vid=([^&]+)", r"[?&]video_id=([^&]+)"):
            matched = re.search(pattern, text)
            if matched:
                return matched.group(1)
        return ""

    @staticmethod
    def _build_search_url(keyword: str) -> str:
        text = str(keyword or "").strip()
        return f"https://so.youku.com/search_video/q_{quote(text)}" if text else ""

    @staticmethod
    def _parse_year(value: Any) -> int | None:
        matched = re.search(r"(19|20)\d{2}", str(value or ""))
        return int(matched.group(0)) if matched else None

    @staticmethod
    def _build_subtitle(media_type: str, *, subtitle: str) -> str:
        return " / ".join(
            part
            for part in [
                YOUKU_MEDIA_LABELS.get(media_type, media_type),
                subtitle,
            ]
            if part
        )

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            if value in ("", None):
                return None
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _page_from_cursor(cursor: str | None) -> int:
        try:
            if not cursor:
                return 1
            return max(int(str(cursor).strip()), 1)
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def _build_task_actions() -> list[ResourceAction]:
        return [
            ResourceAction(
                key="task.video_download.create",
                label="褰辫涓嬭浇",
                type="task",
                style="primary",
                target_plugin_id="task.video_download",
                payload={"template_key": "video_download"},
            ),
            ResourceAction(
                key="task.strm.create",
                label="鐢熸垚STRM",
                type="task",
                target_plugin_id="task.strm",
                payload={"template_key": "strm_generate"},
            ),
        ]


plugin = YoukuCatalogPlugin()
