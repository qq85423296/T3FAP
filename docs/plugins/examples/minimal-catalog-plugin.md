# 最小 catalog 插件示例

这份示例适合做第三方资源目录插件，也适合作为 `search` 插件的起点参考。

## 目录结构

```text
plugins/
  catalog.demo/
    plugin.json
    backend/
      plugin.py
```

## `plugin.json`

```json
{
  "id": "catalog.demo",
  "name": "演示资源目录",
  "version": "0.1.0",
  "category": "catalog",
  "description": "最小 catalog 插件示例",
  "core_version": ">=1.0.0 <2.0.0",
  "contract_version": "1.0",
  "capabilities": [
    "resource.catalog"
  ],
  "backend": {
    "entry": "backend.plugin:plugin"
  },
  "permissions": [
    "network"
  ],
  "dependencies": [],
  "config_schema": [],
  "resource": {
    "source_label": "演示来源",
    "source_group": "catalog",
    "supported_media_types": ["movie", "tv"],
    "target_types": ["official"],
    "priority": 50
  },
  "ui": {
    "menus": [],
    "settings_sections": [],
    "task_templates": []
  }
}
```

## `backend/plugin.py`

```python
from __future__ import annotations

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
    ResourceQueryResponse,
)


MEDIA_TYPE_FILTERS = [
    ResourceFilterOption(value="movie", label="电影"),
    ResourceFilterOption(value="tv", label="电视剧"),
]


class DemoCatalogPlugin(BasePlugin, CatalogProvider):
    plugin_id = "catalog.demo"
    plugin_name = "演示资源目录"
    plugin_version = "0.1.0"

    def __init__(self) -> None:
        self._cache: dict[str, ResourceItem] = {}

    def health(self, ctx: dict[str, Any]) -> HealthReport:
        return HealthReport(status="ok", message="demo catalog plugin is ready")

    def query(self, filters: dict[str, Any], cursor: str | None, limit: int) -> ResourceQueryResponse:
        media_type = str(filters.get("media_type") or "movie").strip()
        if media_type not in {"movie", "tv"}:
            media_type = "movie"

        item = ResourceItem(
            id="demo-001",
            canonical_id="demo:001",
            source_plugin_id=self.plugin_id,
            source_type="catalog",
            source_name="演示来源",
            title="演示影片",
            subtitle="最小 catalog 示例",
            cover_url="",
            media_type=media_type,
            year=2026,
            tags=["演示", "最小示例"],
            detail_url="https://example.com/detail/demo-001",
            target_type="official",
            links=ResourceLinks(
                official=[
                    OfficialLink(
                        platform="demo",
                        label="详情页",
                        url="https://example.com/detail/demo-001",
                        kind="detail",
                    )
                ]
            ),
            capabilities=ResourceCapabilities(
                searchable=True,
                official_searchable=True,
                share_searchable=False,
                downloadable=True,
                strmable=True,
            ),
            meta={
                "ranking": 1,
                "api_fields": ["title", "detail_url"],
            },
            actions=[],
        )
        self._cache[item.id] = item

        return ResourceQueryResponse(
            filter_groups=[
                ResourceFilterGroup(
                    key="media_type",
                    label="类型",
                    level=1,
                    options=MEDIA_TYPE_FILTERS,
                    selected=media_type,
                    hidden_when_empty=False,
                )
            ],
            items=[item],
            next_cursor=None,
            total=1,
            notice="这是一个最小 catalog 示例。",
        )

    def get_detail(self, resource_ref: dict[str, Any]) -> ResourceItem:
        resource_id = str(resource_ref.get("id") or "").strip()
        cached = self._cache.get(resource_id)
        if cached is not None:
            return cached

        return ResourceItem(
            id=resource_id or "demo-001",
            source_plugin_id=self.plugin_id,
            source_type="catalog",
            source_name="演示来源",
            title=resource_id or "演示影片",
            detail_url="https://example.com/detail/demo-001",
            target_type="official",
            links=ResourceLinks(
                official=[
                    OfficialLink(
                        platform="demo",
                        label="详情页",
                        url="https://example.com/detail/demo-001",
                        kind="detail",
                    )
                ]
            ),
            capabilities=ResourceCapabilities(
                searchable=True,
                official_searchable=True,
                share_searchable=False,
            ),
        )


plugin = DemoCatalogPlugin()
```

## 如果你要改成 `search` 插件

核心差异只有一个：把类改为 `BasePlugin, SearchProvider`，并把 `query()` 签名改成：

```python
def query(
    self,
    keyword: str,
    filters: dict[str, Any],
    cursor: str | None,
    limit: int,
    resource_context: dict[str, Any] | None,
) -> ResourceQueryResponse:
    ...
```

其它返回结构依然建议沿用 `ResourceQueryResponse` 和 `ResourceItem`。
