from __future__ import annotations

from typing import Any

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
from core.services.resource_http import fetch_json

MANGO_LIST_URL = "https://pianku.api.mgtv.com/rider/list/pcweb/v3"
MANGO_HEADERS = {
    "Referer": "https://www.mgtv.com/",
}
MANGO_SECTIONS = {
    "tv": {"title": "电视剧", "channelId": "2"},
    "movie": {"title": "电影", "channelId": "3"},
    "anime": {"title": "动漫", "channelId": "50"},
    "variety": {"title": "综艺", "channelId": "1"},
    "documentary": {"title": "纪录片", "channelId": "51"},
}
MEDIA_TYPE_LABELS = {
    "movie": "电影",
    "tv": "电视剧",
    "variety": "综艺",
    "documentary": "纪录片",
    "anime": "动漫",
}


class MangoCatalogPlugin(BasePlugin, CatalogProvider):
    plugin_id = "catalog.mango"
    plugin_name = "芒果TV探索"
    plugin_version = "0.1.0"

    def __init__(self) -> None:
        self._detail_cache: dict[str, ResourceItem] = {}

    def health(self, ctx: dict[str, Any]) -> HealthReport:
        return HealthReport(status="ok", message="Mango catalog plugin is ready.")

    def list_sections(self) -> list[ResourceSection]:
        return [
            ResourceSection(key=key, title=value["title"], media_type=key)
            for key, value in MANGO_SECTIONS.items()
        ]

    def list_items(self, section: str, query: dict[str, Any]) -> ResourceListPage:
        media_type = section if section in MANGO_SECTIONS else str(query.get("media_type") or "tv")
        page = max(int(query.get("page", 1) or 1), 1)
        page_size = max(min(int(query.get("page_size", 12) or 12), 80), 1)
        section_meta = MANGO_SECTIONS.get(media_type, MANGO_SECTIONS["tv"])

        payload = fetch_json(
            MANGO_LIST_URL,
            params={
                "allowedRC": "1",
                "platform": "pcweb",
                "channelId": section_meta["channelId"],
                "pn": page,
                "pc": page_size,
                "hudong": "1",
                "_support": "10000000",
            },
            headers=MANGO_HEADERS,
        )
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        raw_items = [item for item in data.get("hitDocs", []) if isinstance(item, dict)]
        total = self._to_int(data.get("totalHits")) or ((page - 1) * page_size + len(raw_items))
        items = [
            self._map_item(item, media_type, ranking=(page - 1) * page_size + index + 1)
            for index, item in enumerate(raw_items)
        ]
        return ResourceListPage(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            has_more=bool(data.get("hasMore")) or (page * page_size < total),
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
            source_name="芒果TV",
            title=raw_id,
            subtitle="芒果TV详情",
            detail_url="",
            target_type="official",
            capabilities=ResourceCapabilities(
                searchable=True,
                official_searchable=False,
                share_searchable=True,
                downloadable=True,
                strmable=True,
            ),
            actions=self._build_task_actions(),
        )

    def _map_item(self, item: dict[str, Any], media_type: str, *, ranking: int) -> ResourceItem:
        clip_id = str(item.get("clipId") or "").strip()
        play_part_id = str(item.get("playPartId") or "").strip()
        raw_id = clip_id or play_part_id or str(item.get("title") or "").strip()
        title = str(item.get("title") or raw_id).strip()
        detail_url = self._build_detail_url(clip_id, play_part_id)
        year = self._to_int(item.get("year"))
        score = self._clean_score(item.get("zhihuScore"))
        genres = [str(value).strip() for value in item.get("kind", []) if str(value).strip()] if isinstance(item.get("kind"), list) else []
        vip_tag = self._pick_nested_text(item, ("rightCorner", "text"))

        tags = ["芒果TV"]
        if score and score != "0.0":
            tags.append(f"评分 {score}")
        if vip_tag:
            tags.append(vip_tag)
        tags.extend(genres[:2])

        result = ResourceItem(
            id=raw_id,
            canonical_id=f"mango:{play_part_id or clip_id}" if (play_part_id or clip_id) else "",
            source_plugin_id=self.plugin_id,
            source_type="catalog",
            source_name="芒果TV",
            title=title,
            subtitle=self._build_subtitle(media_type, year=year, update_info=str(item.get("updateInfo") or "").strip()),
            cover_url=self._normalize_url(item.get("img")),
            media_type=media_type,  # type: ignore[arg-type]
            year=year,
            tags=tags,
            detail_url=detail_url,
            target_type="official",
            links=ResourceLinks(
                official=[
                    OfficialLink(
                        platform="mango",
                        label="芒果TV详情",
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
                "clip_id": clip_id,
                "play_part_id": play_part_id,
                "story": str(item.get("story") or "").strip(),
                "subtitle_text": str(item.get("subtitle") or "").strip(),
                "update_info": str(item.get("updateInfo") or "").strip(),
                "views": str(item.get("views") or "").strip(),
                "genres": genres,
                "api_fields": sorted(item.keys()),
            },
        )
        self._detail_cache[result.id] = result
        return result

    @staticmethod
    def _build_detail_url(clip_id: str, play_part_id: str) -> str:
        if clip_id and play_part_id:
            return f"https://www.mgtv.com/b/{clip_id}/{play_part_id}.html"
        if clip_id:
            return f"https://www.mgtv.com/b/{clip_id}/{clip_id}.html"
        return ""

    @staticmethod
    def _normalize_url(value: Any) -> str:
        text = str(value or "").strip()
        if text.startswith("http://"):
            return f"https://{text[7:]}"
        return text

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            if value in ("", None):
                return None
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _clean_score(value: Any) -> str:
        return str(value or "").strip()

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
    def _build_subtitle(media_type: str, *, year: int | None, update_info: str) -> str:
        return " / ".join(
            part
            for part in [
                str(year) if year else "",
                MEDIA_TYPE_LABELS.get(media_type, media_type),
                update_info,
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


plugin = MangoCatalogPlugin()
