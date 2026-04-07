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
    ResourceItem,
    ResourceLinks,
    ResourceListPage,
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


class TencentCatalogPlugin(BasePlugin, CatalogProvider):
    plugin_id = "catalog.tencent"
    plugin_name = "腾讯视频探索"
    plugin_version = "0.1.0"

    def __init__(self) -> None:
        self._detail_cache: dict[str, ResourceItem] = {}

    def health(self, ctx: dict[str, Any]) -> HealthReport:
        return HealthReport(status="ok", message="Tencent catalog plugin is ready.")

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


plugin = TencentCatalogPlugin()
