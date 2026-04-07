from __future__ import annotations

from datetime import datetime
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

BANGUMI_CALENDAR_URL = "https://api.bgm.tv/calendar"
BANGUMI_HEADERS = {
    "Referer": "https://api.bgm.tv/",
}
WEEKDAY_LABELS = {
    1: "星期一",
    2: "星期二",
    3: "星期三",
    4: "星期四",
    5: "星期五",
    6: "星期六",
    7: "星期日",
}


class BangumiDailyCatalogPlugin(BasePlugin, CatalogProvider):
    plugin_id = "catalog.bangumi_daily"
    plugin_name = "Bangumi每日放送探索"
    plugin_version = "0.1.0"

    def __init__(self) -> None:
        self._detail_cache: dict[str, ResourceItem] = {}

    def health(self, ctx: dict[str, Any]) -> HealthReport:
        return HealthReport(status="ok", message="Bangumi daily catalog plugin is ready.")

    def list_sections(self) -> list[ResourceSection]:
        return [
            ResourceSection(
                key="anime",
                title="每日放送",
                media_type="anime",
            )
        ]

    def list_items(self, section: str, query: dict[str, Any]) -> ResourceListPage:
        page = max(int(query.get("page", 1) or 1), 1)
        page_size = max(min(int(query.get("page_size", 12) or 12), 100), 1)
        today = datetime.now().isoweekday()

        payload = fetch_json(
            BANGUMI_CALENDAR_URL,
            headers=BANGUMI_HEADERS,
        )
        day_entries = [entry for entry in payload if isinstance(entry, dict)] if isinstance(payload, list) else []
        day_entries.sort(key=lambda entry: self._weekday_sort_key(self._weekday_id(entry), today))

        mapped_items: list[ResourceItem] = []
        for day_entry in day_entries:
            weekday_id = self._weekday_id(day_entry)
            weekday_name = self._weekday_name(weekday_id)
            for item in day_entry.get("items", []):
                if not isinstance(item, dict):
                    continue
                mapped_items.append(
                    self._map_item(
                        item,
                        weekday_id=weekday_id,
                        weekday_name=weekday_name,
                    )
                )

        start = (page - 1) * page_size
        sliced = mapped_items[start : start + page_size]
        return ResourceListPage(
            items=sliced,
            page=page,
            page_size=page_size,
            total=len(mapped_items),
            has_more=start + page_size < len(mapped_items),
            notice="Bangumi 每日放送按当前星期优先排序展示。",
        )

    def get_detail(self, resource_ref: dict[str, Any]) -> ResourceItem:
        raw_id = str(resource_ref.get("id", ""))
        cached = self._detail_cache.get(raw_id)
        if cached is not None:
            return cached

        detail_url = f"https://bgm.tv/subject/{raw_id}" if raw_id else ""
        return ResourceItem(
            id=raw_id,
            source_plugin_id=self.plugin_id,
            source_type="catalog",
            source_name="Bangumi",
            title=raw_id,
            subtitle="Bangumi 每日放送",
            detail_url=detail_url,
            target_type="official",
            links=ResourceLinks(
                official=[OfficialLink(platform="bangumi", label="Bangumi 条目", url=detail_url, kind="detail")]
                if detail_url
                else [],
            ),
            capabilities=ResourceCapabilities(
                searchable=True,
                official_searchable=bool(detail_url),
                share_searchable=True,
            ),
        )

    def _map_item(self, item: dict[str, Any], *, weekday_id: int, weekday_name: str) -> ResourceItem:
        raw_id = str(item.get("id") or item.get("url") or "").strip()
        title = str(item.get("name_cn") or item.get("name") or raw_id).strip()
        detail_url = self._normalize_url(item.get("url")) or f"https://bgm.tv/subject/{raw_id}"
        rating = item.get("rating") if isinstance(item.get("rating"), dict) else {}
        images = item.get("images") if isinstance(item.get("images"), dict) else {}
        score = self._to_float(rating.get("score"))
        air_date = str(item.get("air_date") or "").strip()
        tags = ["Bangumi", weekday_name]
        if score is not None:
            tags.append(f"评分 {score:g}")

        result = ResourceItem(
            id=raw_id,
            canonical_id=f"bangumi:{raw_id}" if raw_id else "",
            source_plugin_id=self.plugin_id,
            source_type="catalog",
            source_name="Bangumi",
            title=title,
            subtitle=" / ".join(part for part in [weekday_name, air_date] if part),
            cover_url=self._normalize_url(images.get("large") or images.get("common") or ""),
            media_type="anime",
            year=self._parse_year(air_date),
            tags=tags,
            detail_url=detail_url,
            target_type="official",
            links=ResourceLinks(
                official=[
                    OfficialLink(
                        platform="bangumi",
                        label="Bangumi 条目",
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
                "weekday_id": weekday_id,
                "weekday_name": weekday_name,
                "air_date": air_date,
                "score": score,
                "rank": self._to_int(item.get("rank")),
                "collection_doing": self._to_int((item.get("collection") or {}).get("doing")),
                "rating_total": self._to_int(rating.get("total")),
                "summary": str(item.get("summary") or "").strip(),
                "api_fields": sorted(item.keys()),
            },
        )
        self._detail_cache[result.id] = result
        return result

    @staticmethod
    def _weekday_id(entry: dict[str, Any]) -> int:
        weekday = entry.get("weekday") if isinstance(entry.get("weekday"), dict) else {}
        return BangumiDailyCatalogPlugin._to_int(weekday.get("id")) or 0

    @staticmethod
    def _weekday_name(weekday_id: int) -> str:
        return WEEKDAY_LABELS.get(weekday_id, "未知星期")

    @staticmethod
    def _weekday_sort_key(weekday_id: int, today: int) -> tuple[int, int]:
        if weekday_id == today:
            return (0, 0)
        if weekday_id > today:
            return (1, weekday_id)
        return (2, weekday_id)

    @staticmethod
    def _normalize_url(value: Any) -> str:
        text = str(value or "").strip()
        if text.startswith("http://"):
            return f"https://{text[7:]}"
        return text

    @staticmethod
    def _parse_year(value: Any) -> int | None:
        text = str(value or "").strip()
        if len(text) >= 4 and text[:4].isdigit():
            return int(text[:4])
        return None

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            if value in ("", None):
                return None
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        try:
            if value in ("", None):
                return None
            return float(str(value).strip())
        except (TypeError, ValueError):
            return None


plugin = BangumiDailyCatalogPlugin()
