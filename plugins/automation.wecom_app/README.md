# 企业微信应用消息通知自动化

## 作用
监听任务和系统事件，通过企业微信应用消息向指定成员、部门或标签发送通知，适用于更精细的企业内消息触达。

## 支持事件
- task.completed
- task.failed

## 配置项
- corp_id
- corp_secret
- agent_id

## 说明
- 首版仅支持文本通知。
- 首版默认监听 `task.completed` 和 `task.failed`。
- 后续可扩展图文消息、成员覆盖策略和更丰富的消息模板能力。
