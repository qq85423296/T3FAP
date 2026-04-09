# 飞书机器人通知自动化

## 作用
监听任务和系统事件，通过飞书群机器人发送通知消息，适用于团队群内的运行播报和异常提醒。

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
- 后续可扩展富文本卡片、模板渲染和更细的事件筛选能力。
