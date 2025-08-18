# CSByBot - Telegram 消息搬运机器人

## 🚀 最新版本 v2.1.0 - 性能优化重大更新

### ✨ 新功能
- **批量消息处理机制**: 支持每批10条消息并发处理
- **智能连接池管理**: 提升连接复用效率
- **智能FloodWait处理策略**: 自动优化等待时间

### ⚡ 性能优化
- **进度更新频率优化**: 从0.3秒调整到1秒，减少70%更新开销
- **批量处理优化**: 实现消息批量处理，显著提升大量消息搬运效率
- **连接复用优化**: 避免频繁建立Telegram连接，提升连接稳定性
- **异常处理优化**: 统一FloodWait最大等待时间为60秒，减少异常处理开销

### 📈 性能提升数据
- 响应速度提升: 减少70%进度更新开销
- 处理效率: 批量处理机制大幅提升消息处理速度
- 连接稳定性: 连接池管理确保更稳定的API调用
- 异常处理: 智能等待策略减少因限制导致的延迟

## 🔧 技术架构

### 核心组件
- `csmain.py` - 主程序入口
- `new_cloning_engine.py` - 优化的克隆引擎
- `optimization_manager.py` - 性能优化管理器
- `optimized_listener.py` - 优化的监听器

### 性能特性
- 智能连接池管理
- 批量消息处理
- 优化的异常处理
- 智能FloodWait策略

## 📦 安装部署

### 环境要求
- Python 3.8+
- Telegram Bot Token
- 必要的Python依赖包

### 快速开始
```bash
# 克隆仓库
git clone https://github.com/laowangbot/wangbybot.git
cd wangbybot

# 安装依赖
pip install -r requirements.txt

# 配置机器人
# 编辑 config.py 文件

# 运行机器人
python csmain.py
```

## 📚 文档

详细的部署和使用说明请参考项目文档。

## 🤝 贡献

欢迎提交Issue和Pull Request来改进项目。

## 📄 许可证

本项目采用MIT许可证。

---

**版本**: v2.1.0  
**更新日期**: 2024年12月  
**主要更新**: 性能优化重大更新，包含批量处理、连接池管理和智能异常处理
