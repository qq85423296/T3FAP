# 通用 Webhook 通知自动化

## 作用
监听任务和系统事件，通过 HTTP Webhook 将结构化消息推送到第三方系统，便于快速对接外部平台。

## 支持事件
- task.completed
- task.failed

## 配置项
- url
- method
- enabled_events

## 说明
- 首版仅支持文本和结构化 JSON 通知。
- 首版默认监听 `task.completed` 和 `task.failed`。
- 后续可扩展签名校验、模板映射和重试策略。
