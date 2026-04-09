# 按类型开发插件

这份文档补充 [rules.md](./rules.md) 的类型速查，按插件类型整理最常见的实现入口、返回结构、配置重点和开发建议。

## 1. 通用原则

- 先确定插件 `category`、`id`、运行时能力，再写 `plugin.json`。
- 后端入口统一导出全局变量 `plugin`。
- 配置读取优先走 `config_schema` + 运行时配置，不要把密钥硬编码进代码。
- 返回结构要稳定，优先返回平台统一协议对象，不直接泄漏上游原始响应。
- 请求外部接口时尽量在插件内做超时、默认值和错误兜底。

## 2. `catalog`

适合做资源目录、榜单、分类浏览。

最小入口：

- 实现 `BasePlugin, CatalogProvider`
- 至少提供 `query()` 和 `get_detail()`
- 如果支持资源中心分区展示，再实现 `list_sections()` / `list_items()`

重点：

- `ResourceItem` 里优先补齐 `title`、`cover_url`、`detail_url`、`links.official`
- 能力通常包含 `resource.catalog`
- 需要目录筛选时，使用 `ResourceFilterGroup`
- 如果图片可能被防盗链，优先走平台图片代理或插件内可控代理地址

参考实现：

- `plugins/catalog.tencent`
- `plugins/catalog.bilibili`
- `plugins/catalog.360`

## 3. `search`

适合做关键词搜索、网盘聚合搜索、二次联动搜索。

最小入口：

- 实现 `BasePlugin, SearchProvider`
- 主要方法是 `query(keyword, filters, cursor, limit, resource_context)`

重点：

- 搜索结果仍然建议复用 `ResourceQueryResponse` 和 `ResourceItem`
- 如果支持从资源详情页跳转二次搜索，注意使用 `resource_context`
- 官方搜索与网盘搜索可以共用协议，但要在 `target_type` 和 `links` 上区分清楚
- 搜索插件通常不需要 `get_detail()`

参考实现：

- `plugins/search.pansou`

## 4. `automation`

适合做通知、Webhook、事件响应、自动化动作。

最小入口：

- 实现 `BasePlugin, AutomationProvider`
- 主要方法是 `subscribed_events()` 和 `handle(event)`

重点：

- `subscribed_events()` 只返回你真正要监听的事件
- `handle()` 建议返回 `OperationResult`
- 配置项通常包含目标地址、鉴权令牌、启用事件列表、超时等
- 自动化插件要尽量避免抛未处理异常，失败时返回可识别信息

参考实现：

- `plugins/automation.email`
- `plugins/automation.webhook`
- `plugins/automation.feishu_bot`
- `plugins/automation.dingtalk_robot`
- `plugins/automation.wecom_app`

## 5. `assistant`

适合做聊天入口、命令网关、机器人对话入口。

最小入口：

- 实现 `BasePlugin, AssistantProvider`
- 典型方法包括 `commands()`、`handle_command()`、平台回调入口相关方法

重点：

- 先定义清楚命令集合，再决定如何接入聊天平台
- 助手插件更像“入口层”，不要把大量业务写死在对话逻辑里
- 返回结构尽量稳定，便于前端或 API 层转发
- 如果依赖外部平台回调，配置项里要明确回调密钥、签名方式和回调路径

参考实现：

- `plugins/assistant.wecom_bot`

## 6. `task`

适合做转存、下载、STRM、定时任务模板。

最小入口：

- 实现 `TaskTypeProvider`
- 至少提供任务模板、草稿生成和执行入口

重点：

- 明确区分“任务模板配置”和“任务实例输入”
- 任务插件要尽量输出结构化日志和阶段状态
- 如果支持从资源动作直接创建任务，补齐 `create_from_resource()`

参考实现：

- 查看 [minimal-task-plugin.md](./examples/minimal-task-plugin.md)

## 7. `drive`

适合做网盘账号、目录、分享链接解析、保存与校验。

最小入口：

- 实现 `DriveProvider`
- 常见方法包含账号信息、目录列举、分享解析、保存能力检测

重点：

- 分享链接解析和账号读写要分开
- 统一驱动 `drive_type`、分享链接协议和容量信息字段
- 如果插件涉及 cookie / token，务必使用 secret 配置项

参考实现：

- 查看 [minimal-drive-plugin.md](./examples/minimal-drive-plugin.md)

## 8. `parser`

适合做第三方播放解析、默认解析链路、网关解析。

最小入口：

- 实现 `ParserProvider`
- 常见方法是 `supports()` 和 `parse()`

重点：

- `supports()` 只负责判断，不做重请求
- `parse()` 返回统一 `ParseResult`
- 解析插件通常需要考虑优先级和默认链路协作

## 9. `download`

适合做 HTTP 下载、媒体下载、外部下载器适配。

最小入口：

- 实现 `DownloadProvider`
- 提供创建任务、启动、查询状态、取消等能力

重点：

- 明确区分下载任务状态与平台任务状态
- 对外部进程型下载器要做好超时和退出码处理

## 10. `media`

适合做官方站点媒体解析、剧集枚举、播放源刷新。

最小入口：

- 实现 `MediaSourceProvider`
- 常见方法是 `supports()`、`resolve_source()`、`refresh_source()`

重点：

- 媒体插件要优先返回统一的剧集/播放源快照
- 平台特有抓取逻辑尽量收敛到插件内部 helper
- 不要把 parser / task 逻辑重新耦合回 media 插件

## 11. 开发顺序建议

1. 先用最小字段跑通协议。
2. 再补筛选、动作、配置和缓存。
3. 最后再做更复杂的上游接口适配、代理和联动行为。

## 12. 发布前检查

- `plugin.json` 的 `id`、`category`、`backend.entry` 是否正确。
- 语法检查是否通过。
- 配置缺失时是否能返回清晰错误。
- 是否只声明了实际需要的权限。
- 远程接口失败时是否还能返回可恢复结果或明确 notice。
