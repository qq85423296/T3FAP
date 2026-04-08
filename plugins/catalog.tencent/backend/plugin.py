from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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

TENCENT_LIST_URL = "https://pbaccess.video.qq.com/trpc.universal_backend_service.page_server_rpc.PageServer/GetPageData"
TENCENT_QUERY_PARAMS = {
    "video_appid": "1000005",
    "vplatform": "2",
    "vversion_name": "8.9.10",
    "new_mark_label_enabled": "1",
}
TENCENT_HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://v.qq.com/",
    "Origin": "https://v.qq.com",
}
TENCENT_SECTIONS = {
    "tv": {"title": "电视剧", "channel_id": "100113"},
    "movie": {"title": "电影", "channel_id": "100173"},
    "variety": {"title": "综艺", "channel_id": "100109"},
    "anime": {"title": "动漫", "channel_id": "100119"},
    "documentary": {"title": "纪录片", "channel_id": "100105"},
}
MEDIA_TYPE_LABELS = {
    "movie": "电影",
    "tv": "电视剧",
    "variety": "综艺",
    "documentary": "纪录片",
    "anime": "动漫",
}
TENCENT_PAGE_SIZE = 21
MEDIA_TYPE_FILTERS = [
    ResourceFilterOption(value="tv", label="TV"),
    ResourceFilterOption(value="movie", label="Movie"),
    ResourceFilterOption(value="variety", label="Variety"),
    ResourceFilterOption(value="anime", label="Anime"),
    ResourceFilterOption(value="documentary", label="Documentary"),
]
SORT_FILTERS = [
    ResourceFilterOption(value="hot_desc", label="Hot"),
    ResourceFilterOption(value="score_desc", label="Score"),
    ResourceFilterOption(value="year_desc", label="Newest"),
    ResourceFilterOption(value="year_asc", label="Oldest"),
    ResourceFilterOption(value="title_asc", label="Title"),
]
YEAR_FILTERS = [
    ResourceFilterOption(value="all", label="All"),
    ResourceFilterOption(value="2026", label="2026"),
    ResourceFilterOption(value="2025", label="2025"),
    ResourceFilterOption(value="2024", label="2024"),
    ResourceFilterOption(value="2023", label="2023"),
    ResourceFilterOption(value="2022", label="2022"),
    ResourceFilterOption(value="2021", label="2021"),
    ResourceFilterOption(value="2020", label="2020"),
    ResourceFilterOption(value="2019", label="2019"),
    ResourceFilterOption(value="2018", label="2018"),
    ResourceFilterOption(value="2017", label="2017"),
    ResourceFilterOption(value="2016", label="2016"),
    ResourceFilterOption(value="older", label="<=2015"),
]
FEE_FILTERS = [
    ResourceFilterOption(value="all", label="All"),
    ResourceFilterOption(value="free", label="Free"),
    ResourceFilterOption(value="vip", label="VIP"),
]


class TencentCatalogPlugin(BasePlugin, CatalogProvider):
    plugin_id = "catalog.tencent"
    plugin_name = "腾讯视频探索"
    plugin_version = "0.1.0"

    def __init__(self) -> None:
        self._detail_cache: dict[str, ResourceItem] = {}

    def health(self, ctx: dict[str, Any]) -> HealthReport:
        return HealthReport(status="ok", message="Tencent catalog plugin is ready.")

    def query(self, filters: dict[str, Any], cursor: str | None, limit: int) -> ResourceQueryResponse:
        media_type = str(filters.get("media_type") or "tv").strip()
        if media_type not in TENCENT_SECTIONS:
            media_type = "tv"

        page = self._page_from_cursor(cursor)
        payload = self._fetch_page(media_type, page)
        raw_items, raw_total = self._extract_items(payload)
        batch_limit = max(min(int(limit or TENCENT_PAGE_SIZE), TENCENT_PAGE_SIZE), 1)
        mapped_items = [
            self._map_item(item, media_type, ranking=(page - 1) * TENCENT_PAGE_SIZE + index + 1)
            for index, item in enumerate(raw_items)
        ]
        filtered_items = self._apply_local_filters(mapped_items, filters)[:batch_limit]

        local_filters_active = any(
            str(filters.get(key) or default) != default
            for key, default in (
                ("sort", "hot_desc"),
                ("year", "all"),
                ("fee", "all"),
            )
        )
        has_more = page * TENCENT_PAGE_SIZE < raw_total
        return ResourceQueryResponse(
            filter_groups=self._build_filter_groups(media_type, filters),
            items=filtered_items,
            next_cursor=str(page + 1) if has_more else None,
            total=None if local_filters_active else raw_total,
        )

    def list_sections(self) -> list[ResourceSection]:
        return [
            ResourceSection(key=key, title=value["title"], media_type=key)
            for key, value in TENCENT_SECTIONS.items()
        ]

    def list_items(self, section: str, query: dict[str, Any]) -> ResourceListPage:
        media_type = section if section in TENCENT_SECTIONS else str(query.get("media_type") or "tv")
        page = max(int(query.get("page", 1) or 1), 1)
        page_size = max(min(int(query.get("page_size", 12) or 12), 50), 1)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        first_api_page = start_index // TENCENT_PAGE_SIZE + 1
        last_api_page = max(first_api_page, (max(end_index - 1, 0) // TENCENT_PAGE_SIZE) + 1)

        collected_items: list[dict[str, Any]] = []
        total = 0
        for api_page in range(first_api_page, last_api_page + 1):
            payload = self._fetch_page(media_type, api_page)
            raw_items, page_total = self._extract_items(payload)
            if page_total:
                total = page_total
            collected_items.extend(raw_items)

        local_start = start_index - (first_api_page - 1) * TENCENT_PAGE_SIZE
        local_end = local_start + page_size
        sliced_items = collected_items[local_start:local_end]
        items = [
            self._map_item(item, media_type, ranking=start_index + index + 1)
            for index, item in enumerate(sliced_items)
        ]
        total = total or (start_index + len(items) + (1 if len(items) == page_size else 0))
        return ResourceListPage(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            has_more=end_index < total,
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
            source_name="腾讯视频",
            title=raw_id,
            subtitle="腾讯视频详情",
            detail_url=detail_url,
            target_type="official",
            links=ResourceLinks(
                official=[OfficialLink(platform="tencent", label="腾讯视频详情", url=detail_url, kind="detail")]
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
        section_meta = TENCENT_SECTIONS.get(media_type, TENCENT_SECTIONS["tv"])
        body = {
            "page_params": {
                "channel_id": section_meta["channel_id"],
                "page_type": "channel_operation",
                "page_id": "channel_list_second_page",
            },
            "page_context": {
                "data_src_647bd63b21ef4b64b50fe65201d89c6e_page": str(max(page - 1, 0)),
            },
        }
        request_url = f"{TENCENT_LIST_URL}?{urlencode(TENCENT_QUERY_PARAMS)}"
        request = Request(
            request_url,
            data=json.dumps(body).encode("utf-8"),
            headers=TENCENT_HEADERS,
            method="POST",
        )
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))

    @staticmethod
    def _extract_items(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
        module_groups = ((payload.get("data") or {}).get("module_list_datas")) or []
        items: list[dict[str, Any]] = []
        total = 0
        for module_group in module_groups:
            for module in module_group.get("module_datas", []) or []:
                if not isinstance(module, dict):
                    continue
                module_params = module.get("module_params") if isinstance(module.get("module_params"), dict) else {}
                total = total or TencentCatalogPlugin._to_int(module_params.get("total_video")) or 0
                raw_items = ((module.get("item_data_lists") or {}).get("item_datas")) or []
                if not isinstance(raw_items, list):
                    continue
                for entry in raw_items:
                    if not isinstance(entry, dict):
                        continue
                    if str(entry.get("item_type") or "").strip() != "2":
                        continue
                    item_params = entry.get("item_params")
                    if isinstance(item_params, dict):
                        items.append(item_params)
        return items, total

    def _map_item(self, item: dict[str, Any], media_type: str, *, ranking: int) -> ResourceItem:
        cid = str(item.get("cid") or "").strip()
        raw_id = cid or str(item.get("title") or "").strip()
        title = str(item.get("title") or item.get("series_name") or raw_id).strip()
        detail_url = self._build_detail_url(cid)
        score = self._extract_score(item)
        year = self._to_int(item.get("year"))
        area = str(item.get("area_name") or item.get("areaName") or item.get("gen_area_name") or "").strip()
        main_genre = str(item.get("main_genre") or item.get("third_title") or "").strip()
        vip_tag = "VIP" if "VIP" in json.dumps(item, ensure_ascii=False) else ""

        tags = ["腾讯视频"]
        if score:
            tags.append(f"评分 {score}")
        if vip_tag:
            tags.append(vip_tag)
        if main_genre:
            tags.append(main_genre)

        result = ResourceItem(
            id=raw_id,
            canonical_id=f"tencent:{cid}" if cid else "",
            source_plugin_id=self.plugin_id,
            source_type="catalog",
            source_name="腾讯视频",
            title=title,
            subtitle=self._build_subtitle(media_type, year=year, area=area),
            cover_url=self._normalize_cover(item.get("new_pic_vt") or item.get("new_pic_hz") or ""),
            media_type=media_type,  # type: ignore[arg-type]
            year=year,
            tags=tags,
            detail_url=detail_url,
            target_type="official",
            links=ResourceLinks(
                official=[
                    OfficialLink(
                        platform="tencent",
                        label="腾讯视频详情",
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
                "score": score,
                "cid": cid,
                "area": area,
                "main_genre": main_genre,
                "vip": bool(vip_tag),
                "publish_date": str(item.get("publish_date") or "").strip(),
                "leading_actor": self._normalize_bracket_text(item.get("leading_actor")),
                "sub_title": str(item.get("sub_title") or item.get("second_title") or "").strip(),
                "api_fields": sorted(item.keys()),
            },
        )
        self._detail_cache[result.id] = result
        return result

    @staticmethod
    def _build_detail_url(cid: str) -> str:
        cleaned = str(cid or "").strip()
        return f"https://v.qq.com/x/cover/{cleaned}.html" if cleaned else ""

    @staticmethod
    def _normalize_cover(value: Any) -> str:
        text = str(value or "").strip()
        if text.endswith("/350"):
            return text[:-4]
        return text

    @staticmethod
    def _normalize_bracket_text(value: Any) -> str:
        text = str(value or "").strip()
        return text.strip("[]")

    @staticmethod
    def _extract_score(item: dict[str, Any]) -> str:
        direct = str(item.get("score") or "").strip()
        if direct:
            return direct
        for key in ("latest_mark_label", "uni_imgtag", "imgtag_ver"):
            raw = item.get(key)
            text = json.dumps(raw, ensure_ascii=False) if isinstance(raw, dict) else str(raw or "")
            text_matches = re.findall(r'"text"\s*:\s*"(\d+(?:\.\d+)?)"', text)
            if text_matches:
                return text_matches[-1]
            float_matches = re.findall(r"(\d+\.\d+)", text)
            if float_matches:
                return float_matches[-1]
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

    def _build_filter_groups(self, media_type: str, filters: dict[str, Any]) -> list[ResourceFilterGroup]:
        return [
            ResourceFilterGroup(
                key="media_type",
                label="Type",
                level=1,
                options=MEDIA_TYPE_FILTERS,
                selected=media_type,
                hidden_when_empty=False,
            ),
            ResourceFilterGroup(
                key="sort",
                label="Sort",
                level=2,
                options=SORT_FILTERS,
                selected=self._normalize_filter_value(filters.get("sort"), "hot_desc", SORT_FILTERS),
                hidden_when_empty=False,
            ),
            ResourceFilterGroup(
                key="year",
                label="Year",
                level=3,
                options=YEAR_FILTERS,
                selected=self._normalize_filter_value(filters.get("year"), "all", YEAR_FILTERS),
                hidden_when_empty=False,
            ),
            ResourceFilterGroup(
                key="fee",
                label="Access",
                level=4,
                options=FEE_FILTERS,
                selected=self._normalize_filter_value(filters.get("fee"), "all", FEE_FILTERS),
                hidden_when_empty=False,
            ),
        ]

    def _apply_local_filters(self, items: list[ResourceItem], filters: dict[str, Any]) -> list[ResourceItem]:
        year = self._normalize_filter_value(filters.get("year"), "all", YEAR_FILTERS)
        fee = self._normalize_filter_value(filters.get("fee"), "all", FEE_FILTERS)
        sort_key = self._normalize_filter_value(filters.get("sort"), "hot_desc", SORT_FILTERS)

        filtered = items
        if year != "all":
            if year == "older":
                filtered = [item for item in filtered if item.year is not None and item.year <= 2015]
            else:
                filtered = [item for item in filtered if str(item.year or "") == year]

        if fee == "vip":
            filtered = [item for item in filtered if bool(item.meta.get("vip"))]
        elif fee == "free":
            filtered = [item for item in filtered if not bool(item.meta.get("vip"))]

        return self._sort_items(filtered, sort_key)

    @staticmethod
    def _sort_items(items: list[ResourceItem], sort_key: str) -> list[ResourceItem]:
        if sort_key == "score_desc":
            return sorted(items, key=lambda item: TencentCatalogPlugin._to_float(item.meta.get("score")), reverse=True)
        if sort_key == "year_desc":
            return sorted(items, key=lambda item: item.year or 0, reverse=True)
        if sort_key == "year_asc":
            return sorted(items, key=lambda item: item.year or 0)
        if sort_key == "title_asc":
            return sorted(items, key=lambda item: item.title or "")
        return sorted(items, key=lambda item: int(item.meta.get("ranking") or 0) or 10**9)

    @staticmethod
    def _normalize_filter_value(value: Any, fallback: str, options: list[ResourceFilterOption]) -> str:
        normalized = str(value or "").strip()
        if any(option.value == normalized for option in options):
            return normalized
        return fallback

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

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            if value in ("", None):
                return 0.0
            return float(str(value).strip())
        except (TypeError, ValueError):
            return 0.0


plugin = TencentCatalogPlugin()
