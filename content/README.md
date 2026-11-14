# 公开公告与更新日志

本目录是 T3FAP 用户端的公开静态内容源，不包含密钥、用户数据或后台接口。

## 发布地址

GitHub Pages 发布后，用户端优先读取：

- 更新日志：`https://qq85423296.github.io/T3FAP/changelog.json`
- 公告清单：`https://qq85423296.github.io/T3FAP/announcements/index.json`
- 公告正文：`https://qq85423296.github.io/T3FAP/announcements/<文件名>`

Pages 不可用或尚未开启时，用户端自动回退到：

- `https://raw.githubusercontent.com/qq85423296/T3FAP/main/content/`

用户端每 5 分钟、重新联网时以及打开对应页面时检查更新。成功读取后写入浏览器本地存储；远程读取失败时展示最近一次缓存。公告的已读、同意和不再提示记录仍只保存在用户本机。

同一轮公告同步固定使用同一来源；如果清单或任一公告读取失败，会整体切换下一来源，避免混合 Pages 与 Raw 的不同版本。浏览器禁止本地存储或空间不足时仍展示新内容，但会明确提示本次未能保存。

## 首次开启 GitHub Pages

1. 将本目录、`tools/validate_public_content.py` 和 `.github/workflows/public-content-pages.yml` 推送到 `main`。
2. 打开仓库 **Settings → Pages**。
3. 在 **Build and deployment → Source** 中选择 **GitHub Actions**。
4. 在 **Actions** 中运行 `Publish public content to GitHub Pages`，或再次推送本目录内容。
5. 工作流成功后，访问 `https://qq85423296.github.io/T3FAP/changelog.json` 验证发布结果。

GitHub 官方说明：<https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site>

## 更新日志维护规则

只编辑 `changelog.json`。文件根节点：

- `schema_version`：固定为数字 `1`。
- `updated_at`：本次文件修改时间，使用带时区的 ISO 8601 时间。
- `items`：版本记录数组，最多 200 条，建议新版本放在前面。

每条版本记录：

| 字段 | 必填 | 规则 |
| --- | --- | --- |
| `id` | 是 | 全局唯一且稳定，不因修正文案而改变 |
| `title` | 是 | 建议包含版本号，例如 `T3FAP v2.8 更新` |
| `content` | 是 | 纯文本，每行一条更新内容 |
| `status` | 是 | `published` 正常展示；`offline` 作为历史下线展示；`draft` 不展示 |
| `published_at` | 是 | 发布时间，带时区的 ISO 8601 时间 |
| `updated_at` | 是 | 内容修改时间，带时区的 ISO 8601 时间 |
| `created_at` | 否 | 创建时间 |
| `action_label` | 否 | 操作按钮文字；为空时不显示按钮 |
| `action_url` | 否 | 仅允许完整的 HTTPS 地址 |
| `action_target` | 否 | `blank` 新窗口打开，`self` 当前窗口打开；默认 `blank` |

`content` 通过行首前缀分组：

- `新增：` → 新增
- `修复：` → 修复
- `优化：` → 优化
- 其他行 → 说明

示例：

```json
{
  "id": "v2.8-example",
  "title": "T3FAP v2.8 更新",
  "content": "新增：示例功能\n修复：示例问题\n优化：示例体验",
  "status": "published",
  "published_at": "2026-11-15T01:00:00+08:00",
  "updated_at": "2026-11-15T01:00:00+08:00",
  "action_label": null,
  "action_url": null,
  "action_target": "blank"
}
```

## 公告维护规则

每条公告使用一个独立 JSON 文件，文件名只能包含英文字母、数字、点、下划线和连字符，必须以 `.json` 结尾。

发布公告：

1. 在 `announcements/` 新建公告 JSON 文件。
2. 在 `announcements/index.json` 的 `items` 中增加 `{ "file": "文件名.json" }`。
3. 更新公告文件和清单的 `updated_at`。
4. 本地运行 `python tools/validate_public_content.py`，通过后推送。

公告字段：

| 字段 | 必填 | 规则 |
| --- | --- | --- |
| `id` | 是 | 所有公告中唯一且稳定 |
| `title` | 是 | 公告标题 |
| `content` | 是 | 纯文本公告正文，不支持 HTML |
| `type` | 是 | `notice` 普通公告、`update` 更新提醒、`important` 重要通知 |
| `status` | 是 | 只有 `published` 在公告中心展示；`draft`、`offline` 不展示 |
| `show_popup` | 否 | 是否自动弹窗，默认 `false` |
| `show_every_visit` | 否 | 是否每次应用访问都提示，默认 `false`；定时同步不会反复弹出旧公告 |
| `require_agreement` | 否 | 是否必须同意，默认 `false`，仅用于必要公告 |
| `allow_skip_next_prompt` | 否 | 是否允许“下次不再提示”，默认 `false` |
| `show_badge` | 否 | 未读时是否显示角标，默认 `false` |
| `action_label` | 否 | 操作按钮文字 |
| `action_url` | 否 | 仅允许完整的 HTTPS 地址 |
| `action_target` | 否 | `blank` 或 `self`，默认 `blank` |
| `published_at` | 否 | 发布时间，带时区的 ISO 8601 时间 |
| `expired_at` | 否 | 预留字段；需要下线时请把 `status` 改为 `offline` |
| `created_at` | 否 | 创建时间 |
| `updated_at` | 是 | 内容版本时间；修改公告后必须更新，用于重新识别未读版本 |

不要修改已发布公告的 `id`。修正内容时只更新 `updated_at`，这样客户端能识别为新版本；如果只是修正错字且不希望重新提醒，可保留原 `updated_at`。

应用内置的免责声明不由此目录管理，即使首次离线启动也会保留。

## 发布前校验

在公开仓库根目录运行：

```bash
python tools/validate_public_content.py
```

校验内容包括 JSON 语法、必填字段、唯一 ID、清单文件名、时间格式、布尔字段以及 HTTPS 操作链接。GitHub Actions 发布前也会执行同一校验，校验失败不会部署。
