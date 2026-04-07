from __future__ import annotations

import re
from typing import Any

from core.sdk import (
    BasePlugin,
    CatalogProvider,
    HealthReport,
    OfficialLink,
    ResourceCapabilities,
    ResourceItem,
    ResourceLinks,
    ResourceListPage,
    ResourceSection,
)
from core.services.resource_http import fetch_json

BILIBILI_LIST_URL = "https://api.bilibili.com/pgc/season/index/result"
BILIBILI_HEADERS = {
    "Referer": "https://www.bilibili.com/",
}
BILIBILI_SECTIONS = {
    "tv": {"title": "电视剧", "type": "1", "st": "5", "season_type": "5"},
    "movie": {"title": "电影", "type": "1", "st": "2", "season_type": "2"},
    "documentary": {"title": "纪录片", "type": "1", "st": "3", "season_type": "3"},
    "anime": {"title": "番剧", "type": "1", "st": "1", "season_type": "1"},
    "variety": {"title": "综艺", "type": "1", "st": "7", "season_type": "7"},
}
MEDIA_TYPE_LABELS = {
    "movie": "电影",
    "tv": "电视剧",
    "variety": "综艺",
    "documentary": "纪录片",
    "anime": "番剧",
}


class BilibiliCatalogPlugin(BasePlugin, CatalogProvider):
    plugin_id = "catalog.bilibili"
    plugin_name = "哔哩哔哩探索"
    plugin_version = "0.1.0"

    def __init__(self) -> None:
        self._detail_cache: dict[str, ResourceItem] = {}

    def health(self, ctx: dict[str, Any]) -> HealthReport:
        return HealthReport(status="ok", message="Bilibili catalog plugin is ready.")

    def list_sections(self) -> list[ResourceSection]:
        return [
            ResourceSection(key=key, title=value["title"], media_type=key)
            for key, value in BILIBILI_SECTIONS.items()
        ]

    def list_items(self, section: str, query: dict[str, Any]) -> ResourceListPage:
        media_type = section if section in BILIBILI_SECTIONS else str(query.get("media_type") or "tv")
        page = max(int(query.get("page", 1) or 1), 1)
        page_size = max(min(int(query.get("page_size", 12) or 12), 50), 1)
        section_meta = BILIBILI_SECTIONS.get(media_type, BILIBILI_SECTIONS["tv"])

        payload = fetch_json(
            BILIBILI_LIST_URL,
            params={
                "type": section_meta["type"],
                "st": section_meta["st"],
                "season_type": section_meta["season_type"],
                "page": page,
                "pagesize": page_size,
            },
            headers=BILIBILI_HEADERS,
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
            has_more=bool(data.get("has_next")) or (page * page_size < total),
        )

    def get_detail(self, resource_ref: dict[str, Any]) -> ResourceItem:
        raw_id = str(resource_ref.get("id", ""))
        cached = self._detail_cache.get(raw_id)
        if cached is not None:
            return cached

        detail_url = f"https://www.bilibili.com/bangumi/media/md{raw_id}" if raw_id.isdigit() else ""

        return ResourceItem(
            id=raw_id,
            source_plugin_id=self.plugin_id,
            source_type="catalog",
            source_name="哔哩哔哩",
            title=raw_id,
            subtitle="哔哩哔哩详情",
            detail_url=detail_url,
            target_type="official",
            links=ResourceLinks(
                official=[OfficialLink(platform="bilibili", label="哔哩哔哩详情", url=detail_url, kind="detail")]
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
        raw_id = str(item.get("media_id") or item.get("season_id") or item.get("title") or "").strip()
        title = str(item.get("title") or raw_id).strip()
        detail_url = self._normalize_url(item.get("link"))
        score = str(item.get("score") or "").strip()
        subtitle = self._pick_value(item, "subTitle", "index_show", "badge")
        year = self._parse_year(item.get("index_show"))

        tags = ["哔哩哔哩"]
        badge = str(item.get("badge") or "").strip()
        if badge:
            tags.append(badge)
        if score:
            tags.append(f"评分 {score}")

        result = ResourceItem(
            id=raw_id,
            canonical_id=f"bilibili:{raw_id}" if raw_id else "",
            source_plugin_id=self.plugin_id,
            source_type="catalog",
            source_name="哔哩哔哩",
            title=title,
            subtitle=self._build_subtitle(media_type, subtitle=subtitle),
            cover_url=self._normalize_url(item.get("cover")),
            media_type=media_type,  # type: ignore[arg-type]
            year=year,
            tags=tags,
            detail_url=detail_url,
            target_type="official",
            links=ResourceLinks(
                official=[
                    OfficialLink(
                        platform="bilibili",
                        label="哔哩哔哩详情",
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
            ),
            meta={
                "ranking": ranking,
                "score": score,
                "season_id": str(item.get("season_id") or "").strip(),
                "season_status": str(item.get("season_status") or "").strip(),
                "index_show": str(item.get("index_show") or "").strip(),
                "badge": badge,
                "api_fields": sorted(item.keys()),
            },
        )
        self._detail_cache[result.id] = result
        return result

    @staticmethod
    def _normalize_url(value: Any) -> str:
        text = str(value or "").strip()
        if text.startswith("//"):
            return f"https:{text}"
        if text.startswith("http://"):
            return f"https://{text[7:]}"
        return text

    @staticmethod
    def _pick_value(item: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = str(item.get(key) or "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def _parse_year(value: Any) -> int | None:
        matched = re.search(r"(19|20)\d{2}", str(value or ""))
        return int(matched.group(0)) if matched else None

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            if value in ("", None):
                return None
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _build_subtitle(media_type: str, *, subtitle: str) -> str:
        return " / ".join(
            part
            for part in [
                MEDIA_TYPE_LABELS.get(media_type, media_type),
                subtitle,
            ]
            if part
        )


plugin = BilibiliCatalogPlugin()
