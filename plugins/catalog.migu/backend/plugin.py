from __future__ import annotations

import re
from typing import Any

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

MIGU_LIST_URL = "https://jadeite.migu.cn/search/v3/category"
MIGU_HEADERS = {
    "Referer": "https://www.miguvideo.com/",
}
MIGU_SECTIONS = {
    "tv": {
        "title": "电视剧",
        "packId": "1002581,1003861,1003863,1003866,1002601,1004761,1004121,1004641,1005521,1005261",
        "contDisplayType": "1001",
    },
    "movie": {
        "title": "电影",
        "packId": "1002581,1002601,1003862,1003864,1003866,1004121,1003861,1004761,1004641",
        "contDisplayType": "1000",
        "mediaShape": "全片",
        "order": "2",
    },
    "variety": {
        "title": "综艺",
        "packId": "1002581,1002601",
        "contDisplayType": "1005",
        "mediaShape": "连载",
        "order": "2",
    },
    "documentary": {
        "title": "纪实",
        "packId": "1002581,1002601",
        "contDisplayType": "1002",
        "mediaShape": "连载",
        "order": "2",
    },
    "anime": {
        "title": "动漫",
        "packId": "1002581,1003861,1003863,1003866,1002601,1004761,1004121,1004641",
        "contDisplayType": "1007",
        "mediaShape": "连载",
    },
}
MEDIA_TYPE_LABELS = {
    "movie": "电影",
    "tv": "电视剧",
    "variety": "综艺",
    "documentary": "纪实",
    "anime": "动漫",
}
MEDIA_TYPE_FILTERS = [
    ResourceFilterOption(value="movie", label="Movie"),
    ResourceFilterOption(value="tv", label="TV"),
    ResourceFilterOption(value="variety", label="Variety"),
    ResourceFilterOption(value="documentary", label="Documentary"),
    ResourceFilterOption(value="anime", label="Anime"),
]


class MiguCatalogPlugin(BasePlugin, CatalogProvider):
    plugin_id = "catalog.migu"
    plugin_name = "咪咕视频探索"
    plugin_version = "0.1.0"

    def __init__(self) -> None:
        self._detail_cache: dict[str, ResourceItem] = {}

    def health(self, ctx: dict[str, Any]) -> HealthReport:
        return HealthReport(status="ok", message="Migu catalog plugin is ready.")

    def query(self, filters: dict[str, Any], cursor: str | None, limit: int) -> ResourceQueryResponse:
        media_type = str(filters.get("media_type") or "tv").strip()
        if media_type not in MIGU_SECTIONS:
            media_type = "tv"

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
            for key, value in MIGU_SECTIONS.items()
        ]

    def list_items(self, section: str, query: dict[str, Any]) -> ResourceListPage:
        media_type = section if section in MIGU_SECTIONS else str(query.get("media_type") or "tv")
        page = max(int(query.get("page", 1) or 1), 1)
        page_size = max(min(int(query.get("page_size", 12) or 12), 50), 1)
        section_meta = MIGU_SECTIONS.get(media_type, MIGU_SECTIONS["tv"])

        params = {
            "pageStart": page,
            "pageNum": page_size,
            "copyrightTerminal": 3,
            "packId": section_meta["packId"],
            "contDisplayType": section_meta["contDisplayType"],
        }
        if section_meta.get("mediaShape"):
            params["mediaShape"] = section_meta["mediaShape"]
        if section_meta.get("order"):
            params["order"] = section_meta["order"]

        payload = fetch_json(
            MIGU_LIST_URL,
            params=params,
            headers=MIGU_HEADERS,
        )
        body = payload.get("body", {}) if isinstance(payload, dict) else {}
        raw_items = [item for item in body.get("data", []) if isinstance(item, dict)]
        total = self._to_int(body.get("totalCount")) or ((page - 1) * page_size + len(raw_items))
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
            source_name="咪咕",
            title=raw_id,
            subtitle="咪咕视频详情",
            detail_url=detail_url,
            target_type="official",
            links=ResourceLinks(
                official=[OfficialLink(platform="migu", label="咪咕视频详情", url=detail_url, kind="detail")]
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
        raw_id = str(item.get("pID") or item.get("contentID") or item.get("name") or "").strip()
        title = str(item.get("name") or raw_id).strip()
        detail_url = self._build_detail_url(raw_id)
        score = self._clean_score(item.get("score"))
        year = self._parse_year(item.get("year") or item.get("publishTime"))
        cover_url = self._normalize_cover(item)
        area = str(item.get("mediaArea") or "").strip()
        content_style = str(item.get("contentStyle") or item.get("programSecClass") or "").strip()
        tip = self._pick_nested_text(item, ("tip", "msg"), ("storeTip", "msg"))

        tags = ["咪咕视频"]
        if score:
            tags.append(f"评分 {score}")
        if tip:
            tags.append(tip)
        if content_style:
            tags.extend(part for part in re.split(r"[\s/]+", content_style) if part.strip()[:12])

        result = ResourceItem(
            id=raw_id,
            canonical_id=f"migu:{raw_id}" if raw_id else "",
            source_plugin_id=self.plugin_id,
            source_type="catalog",
            source_name="咪咕",
            title=title,
            subtitle=self._build_subtitle(media_type, year=year, area=area),
            cover_url=cover_url,
            media_type=media_type,  # type: ignore[arg-type]
            year=year,
            tags=tags[:6],
            detail_url=detail_url,
            target_type="official",
            links=ResourceLinks(
                official=[
                    OfficialLink(
                        platform="migu",
                        label="咪咕视频详情",
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
                "score": score,
                "publish_time": str(item.get("publishTime") or "").strip(),
                "media_area": area,
                "director": str(item.get("director") or "").strip(),
                "actor": str(item.get("actor") or "").strip(),
                "content_style": content_style,
                "media_source_name": str(item.get("mediaSourceName") or "").strip(),
                "api_fields": sorted(item.keys()),
            },
        )
        self._detail_cache[result.id] = result
        return result

    @staticmethod
    def _build_detail_url(raw_id: str) -> str:
        cleaned = str(raw_id or "").strip()
        return f"https://www.miguvideo.com/p/detail/{cleaned}" if cleaned else ""

    @staticmethod
    def _normalize_cover(item: dict[str, Any]) -> str:
        for field in ("h5pics", "pics", "sharePics"):
            images = item.get(field)
            if not isinstance(images, dict):
                continue
            for key in ("highResolutionV", "lowResolutionV", "highResolutionH", "lowResolutionH"):
                value = str(images.get(key) or "").strip()
                if value:
                    return value.replace("http://wapx.cmvideo.cn:8080", "https://wapx.cmvideo.cn")
        return ""

    @staticmethod
    def _parse_year(value: Any) -> int | None:
        text = str(value or "").strip()
        matched = re.search(r"(19|20)\d{2}", text)
        return int(matched.group(0)) if matched else None

    @staticmethod
    def _clean_score(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            if value in ("", None):
                return None
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _pick_nested_text(item: dict[str, Any], *paths: tuple[str, str]) -> str:
        for first, second in paths:
            nested = item.get(first)
            if isinstance(nested, dict):
                value = str(nested.get(second) or "").strip()
                if value:
                    return value
        return ""

    @staticmethod
    def _build_subtitle(media_type: str, *, year: int | None, area: str) -> str:
        return " / ".join(
            part
            for part in [
                str(year) if year else "",
                MEDIA_TYPE_LABELS.get(media_type, media_type),
                area,
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


plugin = MiguCatalogPlugin()
