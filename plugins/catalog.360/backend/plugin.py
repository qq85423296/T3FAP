from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import unquote

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
from core.services.resource_http import fetch_json, fetch_text

KAN360_RANK_URL = "https://api.web.360kan.com/v1/rank"
KAN360_SEARCH_URL = "https://api.so.360kan.com/index"
KAN360_CATEGORIES = {
    "movie": 2,
    "tv": 3,
    "variety": 4,
    "anime": 5,
}
OFFICIAL_PLATFORM_MAP = {
    "qq": ("tencent", "Tencent Video"),
    "tencent": ("tencent", "Tencent Video"),
    "qiyi": ("iqiyi", "iQIYI"),
    "iqiyi": ("iqiyi", "iQIYI"),
    "youku": ("youku", "Youku"),
    "imgo": ("mango", "Mango TV"),
    "mango": ("mango", "Mango TV"),
    "mgtv": ("mango", "Mango TV"),
}
DETAIL_PLATFORM_PATTERNS = {
    "tencent": re.compile(r"https?://[^\s\"'<>]*v\.qq\.com[^\s\"'<>]*", re.IGNORECASE),
    "iqiyi": re.compile(r"https?://[^\s\"'<>]*iqiyi\.com[^\s\"'<>]*", re.IGNORECASE),
    "youku": re.compile(r"https?://[^\s\"'<>]*youku\.com[^\s\"'<>]*", re.IGNORECASE),
    "mango": re.compile(r"https?://[^\s\"'<>]*mgtv\.com[^\s\"'<>]*", re.IGNORECASE),
}
MEDIA_TYPE_LABELS = {
    "movie": "Movie",
    "tv": "TV",
    "variety": "Variety",
    "anime": "Anime",
}
MEDIA_TYPE_FILTERS = [
    ResourceFilterOption(value="movie", label="电影"),
    ResourceFilterOption(value="tv", label="电视剧"),
    ResourceFilterOption(value="variety", label="综艺"),
    ResourceFilterOption(value="anime", label="动漫"),
]


class Kan360CatalogPlugin(BasePlugin, CatalogProvider):
    plugin_id = "catalog.360"
    plugin_name = "360 Rank"
    plugin_version = "0.1.0"

    def __init__(self) -> None:
        self._detail_cache: dict[str, ResourceItem] = {}
        self._official_links_cache: dict[str, list[OfficialLink]] = {}

    def health(self, ctx: dict[str, Any]) -> HealthReport:
        return HealthReport(status="ok", message="360 catalog plugin is ready.")

    def query(self, filters: dict[str, Any], cursor: str | None, limit: int) -> ResourceQueryResponse:
        media_type = str(filters.get("media_type") or "movie").strip()
        if media_type not in KAN360_CATEGORIES:
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
            ResourceSection(key="movie", title="Movie", media_type="movie"),
            ResourceSection(key="tv", title="TV", media_type="tv"),
            ResourceSection(key="variety", title="Variety", media_type="variety"),
            ResourceSection(key="anime", title="Anime", media_type="anime"),
        ]

    def list_items(self, section: str, query: dict[str, Any]) -> ResourceListPage:
        media_type = section if section in KAN360_CATEGORIES else str(query.get("media_type") or "movie")
        page = max(int(query.get("page", 1) or 1), 1)
        page_size = max(min(int(query.get("page_size", 12) or 12), 50), 1)
        payload = fetch_json(
            KAN360_RANK_URL,
            params={"cat": KAN360_CATEGORIES.get(media_type, KAN360_CATEGORIES["movie"])},
            headers={"Referer": "https://www.360kan.com/"},
        )
        raw_items = payload.get("data", []) if isinstance(payload, dict) else []
        start_index = max(page - 1, 0) * page_size
        sliced_items = raw_items[start_index : start_index + page_size]
        items = [
            self._map_item(item, media_type, ranking=start_index + index + 1)
            for index, item in enumerate(sliced_items)
            if isinstance(item, dict)
        ]
        return ResourceListPage(
            items=items,
            page=page,
            page_size=page_size,
            total=len(raw_items),
            has_more=start_index + len(items) < len(raw_items),
        )

    def get_detail(self, resource_ref: dict[str, Any]) -> ResourceItem:
        raw_id = str(resource_ref.get("id", ""))
        cached = self._detail_cache.get(raw_id)
        if cached is not None:
            return cached
        return ResourceItem(
            id=raw_id,
            source_plugin_id=self.plugin_id,
            source_type="catalog",
            source_name="360",
            title=raw_id,
            subtitle="360 Detail",
            detail_url=raw_id if raw_id.startswith("http") else "",
            target_type="official",
            links=ResourceLinks(
                official=[
                    OfficialLink(platform="360", label="360 Detail", url=raw_id, kind="detail")
                ]
                if raw_id.startswith("http")
                else [],
            ),
            capabilities=ResourceCapabilities(
                searchable=True,
                official_searchable=False,
                share_searchable=True,
            ),
        )

    def _map_item(self, item: dict[str, Any], media_type: str, *, ranking: int) -> ResourceItem:
        detail_url = str(item.get("url", "")).strip()
        raw_id = str(item.get("id") or item.get("ent_id") or detail_url or item.get("title", "")).strip()
        title = str(item.get("title", "")).strip() or raw_id
        year = self._extract_year(item.get("pubdate"))
        official_links = self._search_official_links(title=title, year=year, detail_url=detail_url)
        categories = item.get("moviecat", [])
        category_tags = categories if isinstance(categories, list) else []
        score = str(item.get("doubanscore", "")).strip()
        tags = ["360 Rank", *[str(entry).strip() for entry in category_tags if str(entry).strip()][:2]]
        if score:
            tags.append(f"Score {score}")
        if item.get("vip"):
            tags.append("VIP")

        result = ResourceItem(
            id=raw_id,
            source_plugin_id=self.plugin_id,
            source_type="catalog",
            source_name="360",
            title=title,
            subtitle=self._build_subtitle(media_type, item),
            cover_url=str(item.get("cover", "")).strip(),
            media_type=media_type,  # type: ignore[arg-type]
            year=year,
            tags=tags,
            detail_url=detail_url,
            target_type="official",
            links=ResourceLinks(official=official_links),
            capabilities=ResourceCapabilities(
                searchable=True,
                official_searchable=bool(official_links),
                share_searchable=True,
                downloadable=bool(official_links),
                strmable=bool(official_links),
            ),
            actions=self._build_task_actions(),
            meta={
                "score": score,
                "hot_score": str(item.get("pv", "")).replace(",", "").strip(),
                "ranking": ranking,
                "description": str(item.get("description", "")).strip(),
                "upinfo": str(item.get("upinfo", "")).strip(),
                "vip": bool(item.get("vip", False)),
                "official_platforms": [link.platform for link in official_links],
                "api_fields": sorted(item.keys()),
            },
        )
        self._detail_cache[result.id] = result
        return result

    @staticmethod
    def _extract_year(pubdate: Any) -> int | None:
        if not pubdate:
            return None
        text = str(pubdate).strip()
        if len(text) >= 4 and text[:4].isdigit():
            return int(text[:4])
        return None

    @staticmethod
    def _build_subtitle(media_type: str, item: dict[str, Any]) -> str:
        year = str(item.get("pubdate", "")).strip()[:4]
        return " / ".join(part for part in [year, MEDIA_TYPE_LABELS.get(media_type, media_type), "360 Rank"] if part)

    def _search_official_links(self, *, title: str, year: int | None, detail_url: str) -> list[OfficialLink]:
        cache_key = f"{title}|{year or ''}|{detail_url}"
        cached = self._official_links_cache.get(cache_key)
        if cached is not None:
            return cached

        links: list[OfficialLink] = []
        try:
            payload = fetch_json(
                KAN360_SEARCH_URL,
                params={
                    "force_v": 1,
                    "kw": title,
                    "from": "",
                    "pageno": 1,
                    "v_ap": 1,
                    "tab": "all",
                },
                headers={"Referer": "https://www.so.com/"},
            )
            raw_items = self._coerce_long_data_rows((payload.get("data") or {}).get("longData")) if isinstance(payload, dict) else []
            candidate = self._pick_candidate(raw_items, title=title, year=year)
            links = self._extract_official_links(candidate)
        except Exception:
            links = []

        if detail_url:
            try:
                links = self._merge_official_links(links, self._extract_detail_page_links(detail_url))
            except Exception:
                pass

        self._official_links_cache[cache_key] = links
        return links

    def _pick_candidate(self, raw_items: list[dict[str, Any]], *, title: str, year: int | None) -> dict[str, Any] | None:
        best_item: dict[str, Any] | None = None
        best_score = -1
        normalized_title = self._normalize_title(title)

        for item in raw_items:
            if not isinstance(item, dict):
                continue
            official_links = self._extract_official_links(item)
            if not official_links:
                continue

            candidate_title = str(item.get("titleTxt") or item.get("title") or "").strip()
            normalized_candidate = self._normalize_title(candidate_title)
            score = 0
            if normalized_candidate == normalized_title and normalized_title:
                score += 100
            elif normalized_title and normalized_title in normalized_candidate:
                score += 80
            elif normalized_candidate and normalized_candidate in normalized_title:
                score += 70

            candidate_year = self._extract_year(item.get("year"))
            if year and candidate_year and year == candidate_year:
                score += 8

            score += len(official_links)
            if score > best_score:
                best_item = item
                best_score = score

        return best_item

    @staticmethod
    def _coerce_long_data_rows(raw_long_data: Any) -> list[dict[str, Any]]:
        if isinstance(raw_long_data, list):
            return [item for item in raw_long_data if isinstance(item, dict)]
        if isinstance(raw_long_data, dict):
            rows = raw_long_data.get("rows")
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
        return []

    def _extract_official_links(self, item: dict[str, Any] | None) -> list[OfficialLink]:
        if not isinstance(item, dict):
            return []

        playlinks = item.get("playlinks")
        if not isinstance(playlinks, dict):
            return []

        links: list[OfficialLink] = []
        seen_urls: set[str] = set()
        for platform_key, raw_link in playlinks.items():
            platform_info = OFFICIAL_PLATFORM_MAP.get(str(platform_key).strip().lower())
            if platform_info is None:
                continue

            normalized_url = self._coerce_playlink_url(raw_link)
            if not normalized_url or normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)

            platform_id, platform_label = platform_info
            links.append(
                OfficialLink(
                    platform=platform_id,
                    label=f"{platform_label} Official",
                    url=normalized_url,
                    kind="play",
                )
            )
        return links

    def _extract_detail_page_links(self, detail_url: str) -> list[OfficialLink]:
        if not detail_url.startswith("http"):
            return []

        payload = html.unescape(unquote(fetch_text(detail_url, headers={"Referer": "https://www.360kan.com/"})))
        links: list[OfficialLink] = []
        seen_urls: set[str] = set()
        for platform_id, pattern in DETAIL_PLATFORM_PATTERNS.items():
            for match in pattern.findall(payload):
                normalized_url = self._sanitize_detail_url(match)
                if not normalized_url or normalized_url in seen_urls:
                    continue
                seen_urls.add(normalized_url)
                platform_label = self._platform_label(platform_id)
                links.append(
                    OfficialLink(
                        platform=platform_id,
                        label=f"{platform_label} Official",
                        url=normalized_url,
                        kind="play",
                    )
                )
        return links

    @staticmethod
    def _sanitize_detail_url(value: str) -> str:
        text = value.strip().strip("\"'<>")
        text = text.replace("\\/", "/")
        for suffix in ("&quot;", "&amp;", "\\u0026"):
            if suffix in text:
                text = text.split(suffix, 1)[0]
        return text if text.startswith("http") else ""

    @staticmethod
    def _coerce_playlink_url(raw_link: Any) -> str:
        value = raw_link
        if isinstance(value, list):
            value = value[0] if value else ""
        if isinstance(value, dict):
            value = value.get("url") or value.get("link") or ""
        text = str(value or "").strip()
        return text if text.startswith("http") else ""

    @staticmethod
    def _normalize_title(value: str) -> str:
        return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fa5]+", "", value).lower()

    @staticmethod
    def _merge_official_links(*groups: list[OfficialLink]) -> list[OfficialLink]:
        merged: list[OfficialLink] = []
        seen_urls: set[str] = set()
        for group in groups:
            for link in group:
                if link.url in seen_urls:
                    continue
                seen_urls.add(link.url)
                merged.append(link)
        return merged

    @staticmethod
    def _platform_label(platform_id: str) -> str:
        labels = {
            "tencent": "Tencent Video",
            "iqiyi": "iQIYI",
            "youku": "Youku",
            "mango": "Mango TV",
        }
        return labels.get(platform_id, platform_id)

    @staticmethod
    def _build_task_actions() -> list[ResourceAction]:
        return [
            ResourceAction(
                key="task.video_download.create",
                label="影视下载",
                type="task",
                style="primary",
                target_plugin_id="task.video_download",
                payload={"template_key": "video_download"},
            ),
            ResourceAction(
                key="task.strm.create",
                label="生成STRM",
                type="task",
                target_plugin_id="task.strm",
                payload={"template_key": "strm_generate"},
            ),
        ]

    @staticmethod
    def _page_from_cursor(cursor: str | None) -> int:
        try:
            if not cursor:
                return 1
            return max(int(str(cursor).strip()), 1)
        except (TypeError, ValueError):
            return 1


plugin = Kan360CatalogPlugin()
