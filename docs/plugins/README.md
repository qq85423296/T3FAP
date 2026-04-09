# T3FAP 插件开发总览

这份文档面向准备为 T3FAP / T3MT 运行时开发第三方插件的开发者。当前公开仓库主要承载市场插件示例，但下面这套规范覆盖整个插件体系，而不只限于资源插件。

## 这套文档覆盖哪些插件类型

| 插件类型 | 常见 ID 前缀 | 主要协议 / 关键方法 | 典型用途 |
| --- | --- | --- | --- |
| 基础插件 | `sample.base` | `BasePlugin` 生命周期 | 集成、扩展、占位 |
| 资源目录插件 | `catalog.xxx` | `CatalogProvider.query()` / `get_detail()` | 资源浏览页、资源列表 |
| 资源搜索插件 | `search.xxx` | `SearchProvider.query()` | 关键字搜索、网盘搜索 |
| 任务插件 | `task.xxx` | `TaskTypeProvider` | 转存、下载、STRM、定时任务 |
| 网盘插件 | `drive.xxx` | `DriveProvider` | 账号、文件系统、分享、保存 |
| 解析插件 | `parser.xxx` | `ParserProvider` | VIP 解析、第三方播放解析 |
| 下载插件 | `download.xxx` | `DownloadProvider` | HTTP 文件下载、媒体下载 |
| 自动化插件 | `automation.xxx` | `AutomationProvider` | 事件通知、Webhook、机器人 |
| 助手插件 | `assistant.xxx` | `AssistantProvider` | 企业微信、命令网关、聊天入口 |
| 媒体插件 | `media.xxx` | `MediaSourceProvider` | 官方站点媒体解析、播放源刷新 |

## 仓库目录约定

一个最小插件通常长这样：

```text
plugins/
  category.name/
    plugin.json
    backend/
      plugin.py
    frontend/
      index.ts
    README.md
```

说明：

- `plugin.json` 是插件清单，必须有
- `backend/plugin.py` 是后端入口，必须有
- `frontend/index.ts` 是前端扩展入口，可选
- `README.md` 建议提供，方便后续维护、安装和审计

## 先看哪份文档

- 想先知道整体规则，请看 [rules.md](./rules.md)
- 想直接照抄一个最小资源插件，请看 [minimal-catalog-plugin.md](./examples/minimal-catalog-plugin.md)
- 想开发任务插件，请看 [minimal-task-plugin.md](./examples/minimal-task-plugin.md)
- 想开发网盘插件，请看 [minimal-drive-plugin.md](./examples/minimal-drive-plugin.md)

## 开发一个第三方插件的推荐流程

1. 先确定插件类型、目标运行时版本和插件 ID。
2. 创建 `plugins/category.name/` 目录。
3. 编写 `plugin.json`，先把清单校准。
4. 编写 `backend/plugin.py`，并导出全局变量 `plugin`。
5. 先用 mock 数据把协议跑通，再接真实接口。
6. 至少做一次语法检查和最小烟测。
7. 补 README 或接入说明，再提交到仓库。

## 最重要的三个原则

1. 先对齐协议，再对接真实业务。
2. 返回稳定结构，不要把上游原始结构直接泄漏给平台页面。
3. 插件出错时要返回可识别的失败信息，而不是静默失败。

## 当前仓库里的现成参考

目前这个公开仓库里已经有多份可直接参考的目录型市场插件：

- `plugins/catalog.tencent`
- `plugins/catalog.bilibili`
- `plugins/catalog.mango`
- `plugins/catalog.cctv`
- `plugins/catalog.migu`
- `plugins/catalog.bangumi_daily`
- `plugins/catalog.iqiyi`
- `plugins/catalog.youku`

如果你准备做第三方资源来源插件，直接参考这些实现会最快。

## 你真正需要先做什么

如果你是第一次接入，推荐顺序如下：

1. 先看 [rules.md](./rules.md) 里的 `plugin.json` 规则和类型速查。
2. 再照着 [minimal-catalog-plugin.md](./examples/minimal-catalog-plugin.md) 做一个最小可运行版本。
3. 等最小版本能被平台识别后，再补真实接口、筛选项、动作和缓存。
