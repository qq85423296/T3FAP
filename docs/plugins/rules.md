# T3FAP 插件规范与规则

本文档用于统一第三方插件的目录结构、清单字段、返回契约和实现习惯，目标是让后续开发者能够快速接入而不破坏平台主流程。

## 1. 适用版本

- 目标运行时：当前 `t3mt-next / T3FAP` 插件体系
- 推荐清单版本：`contract_version = "1.0"`
- 推荐核心版本约束：`core_version = ">=1.0.0 <2.0.0"`

## 2. `plugin.json` 规则

### 2.1 必填字段

每个插件至少应该声明这些字段：

- `id`
- `name`
- `version`
- `category`
- `backend.entry`
- `core_version`
- `contract_version`
- `capabilities`
- `permissions`
- `dependencies`
- `ui`

如果是资源相关插件，还应声明：

- `resource.source_label`
- `resource.source_group`
- `resource.supported_media_types`
- `resource.target_types`
- `resource.priority`

### 2.2 命名规则

- `id` 必须使用 `category.name` 风格，例如 `catalog.tencent`
- `category` 应与插件真实类型一致
- 版本号建议使用语义化版本，例如 `0.1.0`
- `backend.entry` 推荐固定写法：`backend.plugin:plugin`

### 2.3 最小清单示例

```json
{
  "id": "catalog.demo",
  "name": "演示资源插件",
  "version": "0.1.0",
  "category": "catalog",
  "description": "最小第三方资源目录插件示例",
  "core_version": ">=1.0.0 <2.0.0",
  "contract_version": "1.0",
  "capabilities": ["resource.catalog"],
  "backend": {
    "entry": "backend.plugin:plugin"
  },
  "permissions": ["network"],
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

### 2.4 字段建议

- `permissions` 走最小权限原则，不要为了省事全部乱填
- `dependencies` 只写真正必需的插件
- `config_schema` 里所有敏感字段都应设置 `secret: true`
- `ui.task_templates` 只在任务插件真正对外暴露模板时填写

### 2.5 版本变更规则

- 任何会影响插件行为、返回结构、可见按钮、任务动作、配置项、依赖关系或对外文案的调整，都必须同步升级插件版本号。
- 升级版本时，`plugin.json` 中的 `version` 必须与后端插件对象的 `plugin_version` 保持一致。
- 提交前必须执行 `python tools/validate_plugin_versions.py`，确认没有版本缺失或版本不一致的问题。
- 完成调整后需要提交到 git，并推送到远程仓库，避免本地修复未发布。

## 3. 通用实现规则

### 3.1 入口规则

- 后端入口文件推荐放在 `backend/plugin.py`
- 必须导出全局变量 `plugin`
- 插件对象应暴露 `plugin_id`、`plugin_name`、`plugin_version`

### 3.2 生命周期规则

所有插件都建议至少具备这些基础能力：

- `install()`
- `enable()`
- `disable()`
- `health()`
- `register()`
- `uninstall()`

即使当前不需要，也建议继承 `BasePlugin`，保持行为一致。

### 3.3 错误处理规则

- 网络请求必须设置超时
- 上游失败时返回明确错误或降级结果
- 不要把半成品结构返回给平台
- 对资源类插件，建议把本次使用过的上游字段保存在 `meta.api_fields`

### 3.4 配置和敏感信息规则

- 不要把密钥、Cookie、Token 硬编码进代码
- 敏感配置放进 `config_schema`
- 能通过环境变量注入的配置，也要在 README 里写清楚

### 3.5 导入阶段规则

- 导入模块时不要立刻发网络请求
- 导入模块时不要依赖运行时上下文
- 缓存、连接池、客户端建议延迟初始化

## 4. 插件类型速查

如果你想按插件类型查看最小实现清单、常见能力和易错点，建议配合阅读 [types.md](./types.md)。

### 4.1 基础插件

适用于只需要生命周期、不需要专门 Provider 协议的扩展。

最低要求：

- 导出 `plugin`
- 实现 `health()`

### 4.2 资源目录插件 `catalog`

必须实现：

- `query(filters, cursor, limit)`
- `get_detail(resource_ref)`

推荐返回：

- `ResourceQueryResponse`
- `ResourceItem`

关键规则：

- `next_cursor` 必须是字符串或 `null`
- `filter_groups.selected` 必须存在于 `options` 中
- 页面只消费标准 `ResourceItem`，不要直接返回站点私有结构

### 4.3 资源搜索插件 `search`

必须实现：

- `query(keyword, filters, cursor, limit, resource_context)`

关键规则：

- 搜索结果同样必须返回标准 `ResourceItem`
- `resource_context` 要兼容“基于当前资源继续搜索”的场景
- 如果没有下一页，`next_cursor` 返回 `null`

### 4.4 任务插件 `task`

必须实现：

- `get_template()`
- `validate_config(config)`
- `create_from_resource(resource)`
- `dry_run(config)`
- `execute(execution_context)`

关键规则：

- `get_template()` 返回的 `type_key`、`template_key`、`supported_inputs` 要稳定
- `create_from_resource()` 要能把资源转成默认任务草稿
- `execute()` 应返回 `TaskExecutionResult`
- 任务插件如果对外展示模板，记得在 `ui.task_templates` 中登记

### 4.5 网盘插件 `drive`

`DriveProvider` 是最宽的一类接口，通常需要实现完整账号、文件系统、分享和下载链路。

常见方法分组：

- 账号相关：`get_contract()`、`get_account_form_schema()`、`test_account()`、`create_account_payload()`、`get_account_info()`、`refresh_account()`
- 扫码登录：`start_scan_login()`、`get_scan_status()`、`cancel_scan_login()`
- 文件系统：`list_files()`、`get_item()`、`list_folders()`、`resolve_path()`、`mkdir()`、`rename()`、`delete()`
- 分享相关：`create_share()`、`parse_share()`、`browse_share()`、`save_share()`
- 文件能力：`get_download_link()`、`get_supported_actions()`

关键规则：

- 即使第一版不支持某些动作，也应该返回明确的“不支持”结果
- `get_contract()` 里的 `supported_actions`、`share_url_patterns` 要真实可靠
- 网盘插件是高风险接口，必须重视超时、鉴权失效和重试边界

### 4.6 解析插件 `parser`

必须实现：

- `supports(target)`
- `parse(parse_request)`
- `health_score()`

关键规则：

- `parse()` 推荐返回 `ParseResult`
- 解析结果里应明确 `streams`、`access_mode`、`headers`
- 如果某目标不支持，`supports()` 要尽早返回 `False`

### 4.7 下载插件 `download`

必须实现：

- `supports(source)`
- `create_job(download_request)`
- `start(job)`
- `resume(job)`
- `cancel(job_id)`
- `progress(job_id)`

关键规则：

- `create_job()` 推荐返回 `DownloadJob`
- 进度接口要可重复查询
- 取消任务要幂等

### 4.8 自动化插件 `automation`

必须实现：

- `subscribed_events()`
- `handle(event)`

关键规则：

- `subscribed_events()` 只订阅你真的处理的事件
- `handle()` 中应保证幂等或可重试
- 外发通知类插件一定要限制超时

### 4.9 助手插件 `assistant`

必须实现：

- `commands()`
- `handle(command_request)`

关键规则：

- `commands()` 应返回稳定命令列表
- 命令参数结构要清晰
- 任何可触发平台动作的命令都要做权限控制

### 4.10 媒体插件 `media`

必须实现：

- `get_contract()`
- `supports(source)`
- `resolve_source(source_request)`
- `refresh_source(source_request)`

关键规则：

- 返回 `MediaSourceSnapshot` 时要包含稳定 `entries`
- `supports_refresh` 真实反映刷新能力
- 输入 schema 要能支撑前端表单生成

## 5. 资源插件的额外规则

### 5.1 `ResourceItem` 最重要的字段

这些字段必须稳定：

- `id`
- `source_plugin_id`
- `source_type`
- `source_name`
- `title`
- `media_type`
- `detail_url`
- `target_type`
- `links`
- `capabilities`

这些字段强烈推荐补齐：

- `canonical_id`
- `subtitle`
- `cover_url`
- `year`
- `tags`
- `actions`
- `meta.api_fields`
- `meta.ranking`
- `meta.score`

### 5.2 动作生成建议

资源插件动作建议与能力保持一致：

- 有详情页时可提供 `link.detail.open`
- 有分享链接时可提供 `link.share.open`
- 可转存时可提供 `task.transfer.create`
- 可下载时可提供 `task.video_download.create`
- 可生成 STRM 时可提供 `task.strm.create`

### 5.3 筛选组规则

- `filter_groups` 是有序数组
- `level` 从小到大表示展示顺序
- `selected` 必须存在于当前组选项里
- 不要返回平台无法理解的自由结构

## 6. 能力和权限建议

能力名没有唯一固定全集，但应尽量遵循现有命名风格。

常见示例：

- 资源目录：`resource.catalog`
- 资源搜索：`resource.search`
- 资源跳转：`resource.search.handoff`
- 任务模板：`task.template`
- 任务执行：`task.executor`
- 从资源创建任务：`task.from_resource`
- 网盘账号：`drive.account`
- 网盘文件系统：`drive.fs`
- 解析：`parser.resolve`
- 下载：`download.file`
- 自动化：`automation.event_handler`
- 助手：`assistant.command_gateway`
- 媒体：`media.source`

常见权限示例：

- `network`
- `task.dispatch`
- `secret.read`

原则只有一个：只声明你真正需要的权限。

## 7. 发布前自检清单

发布前建议逐项确认：

- `plugin.json` 的 `id` 使用了 `category.name`
- `backend.entry` 能正确导入到 `plugin`
- 语法检查通过
- 所有必需方法都已实现
- 网络请求都设置了超时
- 出错时会返回明确失败信息
- 敏感字段没有硬编码
- 资源插件已经返回标准 `ResourceItem`
- 任务插件已经返回稳定 `TaskTemplate`
- 网盘插件的 `supported_actions` 和真实能力一致
- README 或接入说明已补齐

## 8. 开发建议

如果你是第一次写第三方插件，推荐这样做：

1. 先从最小 mock 版本做起，不要一上来就连真实接口。
2. 先让平台能识别插件，再补细节字段。
3. 资源插件优先保证 `query()` 和 `get_detail()` 稳定。
4. 任务插件优先保证 `get_template()` 和 `execute()` 链路打通。
5. 网盘插件优先保证账号测试、文件列表和分享解析三条主链路。
