# 钉钉机器人通知自动化

## 作用
监听任务和系统事件，通过钉钉群机器人发送通知消息，适用于团队协作群内的告警提醒和状态同步。

## 支持事件
- task.completed
- task.failed

## 配置项
- webhook_url
- secret
- enabled_events

## 说明
- 首版仅支持文本通知。
- 首版默认监听 `task.completed` 和 `task.failed`。
- 后续可扩展 Markdown 消息、卡片消息和更细粒度提醒策略。
