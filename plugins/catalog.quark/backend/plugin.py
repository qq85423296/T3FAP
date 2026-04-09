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
    ShareLink,
)
from core.services.resource_http import fetch_json

QUARK_RANKING_URL = "https://biz.quark.cn/api/trending/ranking/getYingshiRanking"
QUARK_CHANNELS = {
    "movie": "电影",
    "tv": "电视剧",
    "variety": "综艺",
    "anime": "动漫",
}
MEDIA_TYPE_FILTERS = [
    ResourceFilterOption(value="movie", label="电影"),
    ResourceFilterOption(value="tv", label="电视剧"),
    ResourceFilterOption(value="variety", label="综艺"),
    ResourceFilterOption(value="anime", label="动漫"),
]


class QuarkCatalogPlugin(BasePlugin, CatalogProvider):
    plugin_id = "catalog.quark"
    plugin_name = "夸克热榜"
    plugin_version = "0.2.0"

    def __init__(self) -> None:
        self._detail_cache: dict[str, ResourceItem] = {}

    def health(self, ctx: dict[str, Any]) -> HealthReport:
        return HealthReport(status="ok", message="Quark catalog plugin is ready.")

    def query(self, filters: dict[str, Any], cursor: str | None, limit: int) -> ResourceQueryResponse:
        media_type = str(filters.get("media_type") or "movie").strip()
        if media_type not in QUARK_CHANNELS:
            media_type = "movie"
        page = self._page_from_cursor(cursor)
        page_result = self.list_items(media_type, {"media_type": media_type, "page": page, "page_size": limit})
        return ResourceQueryResponse(
            filter_groups=[
                ResourceFilterGroup(
                    key="media_type",
                    label="类型",
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
            ResourceSection(key="movie", title="电影", media_type="movie"),
            ResourceSection(key="tv", title="电视剧", media_type="tv"),
            ResourceSection(key="variety", title="综艺", media_type="variety"),
            ResourceSection(key="anime", title="动漫", media_type="anime"),
        ]

    def list_items(self, section: str, query: dict[str, Any]) -> ResourceListPage:
        media_type = section if section in QUARK_CHANNELS else str(query.get("media_type") or "movie")
        page = max(int(query.get("page", 1) or 1), 1)
        page_size = max(min(int(query.get("page_size", 12) or 12), 50), 1)

        payload = fetch_json(
            QUARK_RANKING_URL,
            params={"channel": QUARK_CHANNELS.get(media_type, QUARK_CHANNELS["movie"])},
            headers={
                "Referer": "https://www.quark.cn/",
                "Origin": "https://www.quark.cn",
            },
        )
        raw_items = self._extract_items(payload)
        mapped = [
            self._map_item(item, media_type, ranking=index + 1)
            for index, item in enumerate(raw_items[:page_size])
        ]
        return ResourceListPage(
            items=mapped,
            page=page,
            page_size=page_size,
            total=len(raw_items),
            has_more=len(raw_items) > page_size,
        )

    def get_detail(self, resource_ref: dict[str, Any]) -> ResourceItem:
        raw_id = str(resource_ref.get("id", ""))
        cached = self._detail_cache.get(raw_id)
        if cached is not None:
            return cached
        detail_url = f"https://www.quark.cn/search?q={quote(raw_id)}" if raw_id else ""
        return ResourceItem(
            id=raw_id,
            source_plugin_id=self.plugin_id,
            source_type="catalog",
            source_name="夸克",
            title=raw_id,
            subtitle="夸克热榜",
            detail_url=detail_url,
            target_type="official",
            links=ResourceLinks(
                official=[OfficialLink(platform="quark", label="夸克搜索", url=detail_url)] if detail_url else [],
            ),
            capabilities=ResourceCapabilities(
                searchable=True,
                official_searchable=False,
                share_searchable=True,
            ),
        )

    def _map_item(self, item: dict[str, Any], media_type: str, *, ranking: int) -> ResourceItem:
        title = str(item.get("title", "")).strip()
        detail_url = self._pick_value(item, "jump_url", "url", "link", "page_url")
        if not detail_url:
            detail_url = f"https://www.quark.cn/search?q={quote(title)}" if title else ""

        share_links = []
        if "pan.quark.cn/" in detail_url:
            share_links.append(
                ShareLink(
                    drive_type="quark",
                    label="夸克分享",
                    url=detail_url,
                )
            )

        official_links = []
        if detail_url and not share_links:
            official_links.append(
                OfficialLink(
                    platform="quark",
                    label="夸克搜索",
                    url=detail_url,
                    kind="detail",
                )
            )

        score = self._pick_value(item, "score_avg", "score")
        raw_id = self._pick_value(item, "id", "item_id", "video_id", "show_id") or detail_url or title
        tags = ["夸克热榜"]
        if score:
            tags.append(f"评分 {score}")

        result = ResourceItem(
            id=str(raw_id),
            source_plugin_id=self.plugin_id,
            source_type="catalog",
            source_name="夸克",
            title=title or str(raw_id),
            subtitle=self._build_subtitle(media_type, item),
            cover_url=self._pick_value(item, "src", "cover"),
            media_type=media_type,  # type: ignore[arg-type]
            year=self._to_int(item.get("year")),
            tags=tags,
            detail_url=detail_url,
            target_type="share" if share_links else "official",
            links=ResourceLinks(official=official_links, share=share_links),
            capabilities=ResourceCapabilities(
                searchable=True,
                official_searchable=False,
                share_searchable=True,
                transferable=bool(share_links),
            ),
            meta={
                "score": score,
                "hot_score": self._pick_value(item, "hot_score", "pv"),
                "ranking": ranking,
                "description": self._pick_value(item, "desc", "description"),
                "actors": self._split_csv(item.get("actors")),
                "area": self._pick_value(item, "area"),
                "api_fields": sorted(item.keys()),
            },
        )
        self._detail_cache[result.id] = result
        return result

    @staticmethod
    def _extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        candidates = [
            data.get("hits", {}).get("hit", {}).get("item", []),
            data.get("hits", {}).get("items", []),
            data.get("items", []),
            data.get("list", []),
        ]
        for candidate in candidates:
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []

    @staticmethod
    def _pick_value(item: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = item.get(key)
            if value not in (None, ""):
                return str(value).strip()
        return ""

    @staticmethod
    def _split_csv(value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [part.strip() for part in str(value).split(",") if part.strip()]

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            if value in ("", None):
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _build_subtitle(media_type: str, item: dict[str, Any]) -> str:
        labels = {
            "movie": "电影",
            "tv": "电视剧",
            "variety": "综艺",
            "anime": "动漫",
        }
        year = str(item.get("year", "")).strip()
        return " / ".join(part for part in [year, labels.get(media_type, media_type), "夸克热榜"] if part)

    @staticmethod
    def _page_from_cursor(cursor: str | None) -> int:
        try:
            if not cursor:
                return 1
            return max(int(str(cursor).strip()), 1)
        except (TypeError, ValueError):
            return 1


plugin = QuarkCatalogPlugin()
