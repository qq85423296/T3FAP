from __future__ import annotations

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

IQIYI_TAG_URL = "https://mesh.if.iqiyi.com/portal/lw/videolib/tag"
IQIYI_DATA_URL = "https://mesh.if.iqiyi.com/portal/lw/videolib/data"
IQIYI_LEGACY_URL = "https://pcw-api.iqiyi.com/search/recommended/recommend/list"
IQIYI_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.iqiyi.com",
    "Referer": "https://www.iqiyi.com/",
    "User-Agent": "Mozilla/5.0",
}
IQIYI_SECTIONS = {
    "movie": {"title": "电影", "channel_id": "1", "legacy_sort": "7"},
    "tv": {"title": "电视剧", "channel_id": "2", "legacy_sort": "4"},
    "variety": {"title": "综艺", "channel_id": "6", "legacy_sort": "1"},
    "anime": {"title": "动漫", "channel_id": "4", "legacy_sort": "4"},
    "documentary": {"title": "纪录片", "channel_id": "15", "legacy_sort": "4"},
}
IQIYI_MEDIA_LABELS = {
    "movie": "电影",
    "tv": "电视剧",
    "variety": "综艺",
    "anime": "动漫",
    "documentary": "纪录片",
}
IQIYI_FILTERS = [
    ResourceFilterOption(value="movie", label="Movie"),
    ResourceFilterOption(value="tv", label="TV"),
    ResourceFilterOption(value="variety", label="Variety"),
    ResourceFilterOption(value="anime", label="Anime"),
    ResourceFilterOption(value="documentary", label="Documentary"),
]


class IqiyiCatalogPlugin(BasePlugin, CatalogProvider):
    plugin_id = "catalog.iqiyi"
    plugin_name = "爱奇艺探索"
    plugin_version = "0.1.0"

    def __init__(self) -> None:
        self._detail_cache: dict[str, ResourceItem] = {}

    def health(self, ctx: dict[str, Any]) -> HealthReport:
        return HealthReport(status="ok", message="Iqiyi catalog plugin is ready.")

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
                    options=IQIYI_FILTERS,
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
            for key, value in IQIYI_SECTIONS.items()
        ]

    def list_items(self, section: str, query: dict[str, Any]) -> ResourceListPage:
        media_type = self._normalize_media_type(section or query.get("media_type"))
        page = max(int(query.get("page", 1) or 1), 1)
        page_size = max(min(int(query.get("page_size", 12) or 12), 60), 1)
        payload = self._fetch_page(media_type, page, page_size)
        raw_items, total = self._extract_items(payload, media_type)
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
            source_name="爱奇艺",
            title=raw_id,
            subtitle="爱奇艺资源目录",
            detail_url=detail_url,
            target_type="official",
            links=ResourceLinks(
                official=[OfficialLink(platform="iqiyi", label="爱奇艺详情", url=detail_url, kind="detail")]
                if detail_url
                else [],
            ),
            capabilities=ResourceCapabilities(
                searchable=True,
                official_searchable=bool(detail_url),
                share_searchable=True,
            ),
        )

    def _fetch_page(self, media_type: str, page: int, page_size: int) -> dict[str, Any]:
        section_meta = IQIYI_SECTIONS[media_type]
        try:
            tag_payload = fetch_json(
                IQIYI_TAG_URL,
                params={
                    "channel_id": section_meta["channel_id"],
                    "tagAdd": "",
                    "selected_tag_name": "",
                    "version": "14.024.24728",
                    "device": "e263d61bb4dced863193e41b024025b2",
                    "uid": "",
                },
                headers=IQIYI_HEADERS,
            )
            session = self._extract_session(tag_payload)
            params = {
                "uid": "",
                "passport_id": "",
                "ret_num": max(page_size, 30),
                "pcv": "14.024.24728",
                "version": "14.024.24728",
                "device_id": "e263d61bb4dced863193e41b024025b2",
                "channel_id": section_meta["channel_id"],
                "page_id": page,
                "os": "10.0",
                "conduit_id": "",
                "vip": 0,
                "auth": "",
                "recent_selected_tag": "全部",
            }
            if session:
                params["session"] = session
            return fetch_json(IQIYI_DATA_URL, params=params, headers=IQIYI_HEADERS)
        except Exception:
            return fetch_json(
                IQIYI_LEGACY_URL,
                params={
                    "channel_id": section_meta["channel_id"],
                    "data_type": "1",
                    "mode": section_meta["legacy_sort"],
                    "page_id": page,
                    "ret_num": max(page_size, 30),
                    "is_purchase": "0",
                },
                headers=IQIYI_HEADERS,
            )

    def _extract_items(self, payload: dict[str, Any], media_type: str) -> tuple[list[dict[str, Any]], int]:
        channel_id = IQIYI_SECTIONS[media_type]["channel_id"]
        items = self._parse_video_items(payload, channel_id)
        total = self._extract_total(payload) or len(items)
        return items, total

    def _parse_video_items(self, payload: dict[str, Any], channel_id: str) -> list[dict[str, Any]]:
        videos: list[dict[str, Any]] = []
        dedupe: set[tuple[str, str]] = set()
        for item in self._collect_candidate_items(payload):
            normalized = self._normalize_video_item(item, channel_id)
            if not normalized:
                continue
            dedupe_key = (normalized["video_id"], normalized["title"])
            if dedupe_key in dedupe:
                continue
            dedupe.add(dedupe_key)
            videos.append(normalized)
        return videos

    def _map_item(self, item: dict[str, Any], media_type: str, *, ranking: int) -> ResourceItem:
        raw_id = str(item.get("video_id") or item.get("title") or "").strip()
        title = str(item.get("title") or raw_id).strip()
        detail_url = str(item.get("play_url") or "").strip() or self._build_search_url(title)
        cover_url = self._normalize_url(item.get("cover"))
        subtitle = str(item.get("subtitle") or "").strip()
        year = self._to_int(item.get("year"))
        score = str(item.get("score") or "").strip()

        tags = ["爱奇艺"]
        if score:
            tags.append(f"评分 {score}")
        item_type = str(item.get("type") or "").strip()
        if item_type:
            tags.append(item_type)

        result = ResourceItem(
            id=raw_id,
            canonical_id=f"iqiyi:{raw_id}" if raw_id else "",
            source_plugin_id=self.plugin_id,
            source_type="catalog",
            source_name="爱奇艺",
            title=title,
            subtitle=self._build_subtitle(media_type, year=year, subtitle=subtitle),
            cover_url=cover_url,
            media_type=media_type,  # type: ignore[arg-type]
            year=year,
            tags=tags,
            detail_url=detail_url,
            target_type="official",
            links=ResourceLinks(
                official=[
                    OfficialLink(
                        platform="iqiyi",
                        label="爱奇艺详情",
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
                "video_id": raw_id,
                "api_fields": sorted(item.keys()),
            },
        )
        self._detail_cache[result.id] = result
        return result

    @staticmethod
    def _normalize_media_type(value: Any) -> str:
        media_type = str(value or "tv").strip()
        if media_type not in IQIYI_SECTIONS:
            return "tv"
        return media_type

    @staticmethod
    def _extract_session(payload: dict[str, Any]) -> str:
        for path in (
            ("data", "session"),
            ("data", "session_id"),
            ("session",),
            ("session_id",),
            ("data", "next", "session"),
        ):
            current: Any = payload
            for key in path:
                if not isinstance(current, dict) or key not in current:
                    current = None
                    break
                current = current[key]
            if current not in (None, ""):
                return str(current)
        return ""

    @staticmethod
    def _extract_total(payload: dict[str, Any]) -> int:
        for path in (
            ("data", "total"),
            ("data", "count"),
            ("total",),
            ("count",),
        ):
            current: Any = payload
            for key in path:
                if not isinstance(current, dict) or key not in current:
                    current = None
                    break
                current = current[key]
            total = IqiyiCatalogPlugin._to_int(current)
            if total:
                return total
        return 0

    @staticmethod
    def _collect_candidate_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for path in (
            ("data", "list"),
            ("data", "videos"),
            ("data", "video_list"),
            ("data", "cards"),
            ("list",),
            ("videos",),
            ("cards",),
        ):
            current: Any = payload
            for key in path:
                if not isinstance(current, dict) or key not in current:
                    current = None
                    break
                current = current[key]
            if isinstance(current, list):
                candidates.extend(entry for entry in current if isinstance(entry, dict))
        if candidates:
            return candidates

        queue: list[Any] = [payload]
        visited: set[int] = set()
        while queue:
            node = queue.pop(0)
            if not isinstance(node, (dict, list)):
                continue
            node_id = id(node)
            if node_id in visited:
                continue
            visited.add(node_id)
            if isinstance(node, list):
                if node and all(isinstance(entry, dict) for entry in node):
                    return [entry for entry in node if isinstance(entry, dict)]
                queue.extend(node)
            else:
                queue.extend(node.values())
        return []

    @staticmethod
    def _normalize_video_item(item: dict[str, Any], channel_id: str) -> dict[str, Any] | None:
        item_channel_id = str(
            item.get("channelId") or item.get("channel_id") or item.get("channelid") or ""
        ).strip()
        if item_channel_id and item_channel_id != channel_id:
            return None

        video_id = str(
            item.get("albumId")
            or item.get("album_id")
            or item.get("qipuId")
            or item.get("qipu_id")
            or item.get("id")
            or ""
        ).strip()
        title = str(
            item.get("name")
            or item.get("title")
            or item.get("albumName")
            or item.get("showName")
            or ""
        ).strip()
        if not video_id or not title:
            return None

        return {
            "video_id": video_id,
            "title": title,
            "cover": item.get("imageUrl")
            or item.get("image_url")
            or item.get("poster")
            or item.get("pic")
            or item.get("image")
            or "",
            "subtitle": item.get("subtitle")
            or item.get("subTitle")
            or item.get("desc")
            or item.get("description")
            or "",
            "type": item.get("videoType")
            or item.get("channelName")
            or item.get("type")
            or "",
            "score": item.get("score") or item.get("hotNum") or "",
            "year": item.get("year") or item.get("albumYear") or "",
            "play_url": item.get("playUrl")
            or item.get("pageUrl")
            or item.get("url")
            or item.get("jumpUrl")
            or "",
        }

    @staticmethod
    def _normalize_url(url: Any) -> str:
        text = str(url or "").strip()
        if text.startswith("//"):
            return f"https:{text}"
        if text.startswith("http://"):
            return f"https://{text[7:]}"
        return text

    @staticmethod
    def _build_search_url(keyword: str) -> str:
        text = str(keyword or "").strip()
        return f"https://so.iqiyi.com/so/q_{quote(text)}" if text else ""

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            if value in ("", None):
                return None
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _build_subtitle(media_type: str, *, year: int | None, subtitle: str) -> str:
        return " / ".join(
            part
            for part in [
                str(year) if year else "",
                IQIYI_MEDIA_LABELS.get(media_type, media_type),
                subtitle,
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


plugin = IqiyiCatalogPlugin()
