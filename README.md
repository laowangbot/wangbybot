# 纯净版Telegram机器人

一个简单的Telegram机器人，用于测试和部署。

## 功能

- `/start` - 启动命令
- `/ping` - 响应测试
- `/status` - 状态查询
- 处理普通文本消息

## 部署

1. 在Render中创建新的Web Service
2. 连接GitHub仓库
3. 设置环境变量：
   - `API_ID`
   - `API_HASH`
   - `BOT_TOKEN`
4. 启动命令：`python clean_bot.py`

## 环境变量

- `API_ID`: Telegram API ID
- `API_HASH`: Telegram API Hash
- `BOT_TOKEN`: 机器人Token
