# 邮件通知自动化

## 作用
监听任务和系统事件，通过 SMTP 发送邮件通知，适用于告警、日报、失败汇总和结果回执。

## 支持事件
- task.completed
- task.failed

## 配置项
- smtp_host
- username
- to_list

## 说明
- 首版仅支持文本通知。
- 首版默认监听 `task.completed` 和 `task.failed`。
- 后续可扩展更多事件类型和 HTML 邮件模板能力。
