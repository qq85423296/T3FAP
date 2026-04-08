from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from core.sdk import (
    BasePlugin,
    CatalogProvider,
    HealthReport,
    OfficialLink,
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

CCTV_LIST_URL = "https://api.cntv.cn/newVideoset/getCboxVideoAlbumList"
CCTV_HEADERS = {
    "Referer": "https://app.cctv.com/",
}
CCTV_SECTIONS = {
    "movie": {"fc": "电影", "title": "电影"},
    "tv": {"fc": "电视剧", "title": "电视剧"},
    "anime": {"fc": "动画片", "title": "动画"},
    "documentary": {"fc": "纪录片", "title": "纪录片"},
}
MEDIA_TYPE_LABELS = {
    "movie": "电影",
    "tv": "电视剧",
    "anime": "动画",
    "documentary": "纪录片",
}
MEDIA_TYPE_FILTERS = [
    ResourceFilterOption(value="movie", label="Movie"),
    ResourceFilterOption(value="tv", label="TV"),
    ResourceFilterOption(value="anime", label="Anime"),
    ResourceFilterOption(value="documentary", label="Documentary"),
]


class CctvCatalogPlugin(BasePlugin, CatalogProvider):
    plugin_id = "catalog.cctv"
    plugin_name = "CCTV探索"
    plugin_version = "0.1.0"

    def __init__(self) -> None:
        self._detail_cache: dict[str, ResourceItem] = {}

    def health(self, ctx: dict[str, Any]) -> HealthReport:
        return HealthReport(status="ok", message="CCTV catalog plugin is ready.")

    def query(self, filters: dict[str, Any], cursor: str | None, limit: int) -> ResourceQueryResponse:
        media_type = str(filters.get("media_type") or "movie").strip()
        if media_type not in CCTV_SECTIONS:
            media_type = "movie"

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
                    options=MEDIA_TYPE_FILTERS,
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
            for key, value in CCTV_SECTIONS.items()
        ]

    def list_items(self, section: str, query: dict[str, Any]) -> ResourceListPage:
        media_type = section if section in CCTV_SECTIONS else str(query.get("media_type") or "movie")
        page = max(int(query.get("page", 1) or 1), 1)
        page_size = max(min(int(query.get("page_size", 12) or 12), 50), 1)
        section_meta = CCTV_SECTIONS.get(media_type, CCTV_SECTIONS["movie"])

        payload = fetch_json(
            CCTV_LIST_URL,
            params={
                "p": page,
                "n": page_size,
                "serviceId": "cbox",
                "sort": "desc",
                "fc": section_meta["fc"],
            },
            headers=CCTV_HEADERS,
        )
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        raw_items = [item for item in data.get("list", []) if isinstance(item, dict)]
        total = self._to_int(data.get("total")) or ((page - 1) * page_size + len(raw_items))
        items = [
            self._map_item(item, media_type, ranking=(page - 1) * page_size + index + 1)
            for index, item in enumerate(raw_items)
        ]
        return ResourceListPage(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            has_more=page * page_size < total,
        )

    def get_detail(self, resource_ref: dict[str, Any]) -> ResourceItem:
        raw_id = str(resource_ref.get("id", ""))
        cached = self._detail_cache.get(raw_id)
        if cached is not None:
            return cached

        detail_url = self._build_detail_url(raw_id)
        return ResourceItem(
            id=raw_id,
            source_plugin_id=self.plugin_id,
            source_type="catalog",
            source_name="CCTV",
            title=raw_id,
            subtitle="CCTV 资源目录",
            detail_url=detail_url,
            target_type="official",
            links=ResourceLinks(
                official=[OfficialLink(platform="cctv", label="CCTV 检索", url=detail_url, kind="detail")]
                if detail_url
                else [],
            ),
            capabilities=ResourceCapabilities(
                searchable=True,
                official_searchable=bool(detail_url),
                share_searchable=True,
            ),
        )

    def _map_item(self, item: dict[str, Any], media_type: str, *, ranking: int) -> ResourceItem:
        raw_id = str(item.get("id") or item.get("vsetid") or item.get("title") or "").strip()
        title = self._clean_title(item.get("title"))
        detail_url = self._build_detail_url(title or raw_id)
        sc = str(item.get("sc") or "").strip()
        channel = str(item.get("channel") or "").strip()
        tags = ["CCTV"]
        if sc:
            tags.append(sc)
        if channel:
            tags.append(channel)

        result = ResourceItem(
            id=raw_id,
            canonical_id=f"cctv:{raw_id}" if raw_id else "",
            source_plugin_id=self.plugin_id,
            source_type="catalog",
            source_name="CCTV",
            title=title or raw_id,
            subtitle=self._build_subtitle(media_type, sc=sc, channel=channel),
            cover_url=self._pick_value(item, "image", "image2", "image3"),
            media_type=media_type,  # type: ignore[arg-type]
            tags=tags,
            detail_url=detail_url,
            target_type="official",
            links=ResourceLinks(
                official=[
                    OfficialLink(
                        platform="cctv",
                        label="CCTV 检索",
                        url=detail_url,
                        kind="detail",
                    )
                ]
                if detail_url
                else [],
            ),
            capabilities=ResourceCapabilities(
                searchable=True,
                official_searchable=bool(detail_url),
                share_searchable=True,
            ),
            meta={
                "ranking": ranking,
                "fc": str(item.get("fc") or "").strip(),
                "sc": sc,
                "channel": channel,
                "vsetid": str(item.get("vsetid") or "").strip(),
                "vset_cs": str(item.get("vset_cs") or "").strip(),
                "api_fields": sorted(item.keys()),
            },
        )
        self._detail_cache[result.id] = result
        return result

    @staticmethod
    def _clean_title(value: Any) -> str:
        text = str(value or "").strip()
        return re.sub(r"[《》]", "", text)

    @staticmethod
    def _pick_value(item: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = str(item.get(key) or "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            if value in ("", None):
                return None
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _build_detail_url(keyword: str) -> str:
        cleaned = str(keyword or "").strip()
        return f"https://search.cctv.com/search.php?qtext={quote(cleaned)}" if cleaned else ""

    @staticmethod
    def _build_subtitle(media_type: str, *, sc: str, channel: str) -> str:
        return " / ".join(
            part
            for part in [
                MEDIA_TYPE_LABELS.get(media_type, media_type),
                sc,
                channel,
            ]
            if part
        )

    @staticmethod
    def _page_from_cursor(cursor: str | None) -> int:
        try:
            if not cursor:
                return 1
            return max(int(str(cursor).strip()), 1)
        except (TypeError, ValueError):
            return 1


plugin = CctvCatalogPlugin()
