# 🤖 AI小说生成器

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

一个基于OpenRouter API的智能小说生成器，支持多种AI模型，具备章节扩写、内容格式化等高级功能。

## ✨ 功能特点

- 🎯 **智能生成** - 使用免费AI模型生成完整的多章节小说
- 📝 **章节扩写** - 一键扩写任意章节，丰富故事内容
- 🎨 **内容格式化** - 自动格式化文本，支持段落分离、对话突出
- 💾 **智能缓存** - 缓存API响应，提高效率并节省调用次数
- 🔄 **错误重试** - 自动重试机制，提高服务稳定性
- 🌐 **现代界面** - 基于Tailwind CSS的美观响应式界面
- ⚡ **实时更新** - 生成过程实时显示，用户体验流畅

## 🚀 快速开始

### 方法一：下载可执行程序（推荐）

1. 前往 [Releases](../../releases) 页面
2. 下载最新版本的可执行文件
3. 解压并运行 `AI小说生成器.exe`
4. 在浏览器中访问 `http://localhost:8000`

### 方法二：从源码运行

#### 环境要求
- Python 3.8+
- pip

#### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/your-username/ai-novel-generator.git
cd ai-novel-generator
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置API密钥**
创建 `.env` 文件：
```bash
OPENROUTER_API_KEY=your_api_key_here
```

> 💡 获取API密钥：访问 [OpenRouter](https://openrouter.ai/) 注册并获取免费API密钥

4. **启动应用**
```bash
python app.py
# 或者使用
python start_server.py
```

5. **访问应用**
在浏览器中打开：`http://localhost:8000`

## 📖 使用指南

### 生成小说
1. 在左侧面板填写背景故事和特色亮点
2. 选择小说类型（如：玄幻、都市、科幻等）
3. 点击"生成结构"按钮
4. 等待AI生成完整的多章节小说

### 扩写章节
1. 在生成的小说中，点击任意章节右上角的"扩写"按钮
2. AI会自动扩写该章节，增加更多细节和对话
3. 扩写完成后内容会自动更新并格式化

### 管理章节
- **删除章节**：点击章节右上角的删除按钮
- **查看字数**：每个章节显示实时字数统计

## 🏗️ 项目结构

```
ai-novel-generator/
├── 📁 cache/              # API响应缓存
├── 📁 logs/               # 应用日志
├── 📁 static/             # 静态资源
├── 📁 templates/          # HTML模板
├── 📁 utils/              # 工具模块
│   ├── cache.py           # 缓存管理
│   ├── model_fetcher.py   # 模型获取
│   └── openrouter_api.py  # API调用
├── 📄 app.py              # 主应用
├── 📄 config.py           # 配置文件
├── 📄 requirements.txt    # 依赖列表
├── 📄 start_server.py     # 启动脚本
└── 📄 README.md           # 项目说明
```

## 🔧 配置选项

在 `config.py` 中可以调整以下设置：

- `MAX_TOKENS`: API最大令牌数（默认：4000）
- `TEMPERATURE`: 生成温度（默认：0.7）
- `MAX_RETRIES`: 重试次数（默认：3）
- `CACHE_ENABLED`: 是否启用缓存（默认：True）

## 🧪 测试

项目包含多个测试脚本：

```bash
# 测试API连接
python test_api.py

# 测试章节提取
python test_chapter_extraction.py

# 测试扩写功能
python test_expand_feature.py

# 测试完整流程
python test_full_generation.py
```

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

## 📝 更新日志

### v1.0.0 (2024-12-XX)
- ✨ 初始版本发布
- 🎯 支持多章节小说生成
- 📝 章节扩写功能
- 🎨 内容格式化
- 💾 智能缓存系统

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## ⚠️ 注意事项

- 需要有效的OpenRouter API密钥
- 建议使用免费模型以控制成本
- 生成时间取决于网络状况和模型响应速度
- 请遵守OpenRouter的使用条款

## 🆘 常见问题

**Q: 如何获取OpenRouter API密钥？**
A: 访问 [OpenRouter官网](https://openrouter.ai/) 注册账户并在控制台获取API密钥。

**Q: 生成失败怎么办？**
A: 检查网络连接和API密钥，应用会自动重试失败的请求。

**Q: 可以使用付费模型吗？**
A: 可以，但需要确保账户有足够余额，建议先使用免费模型测试。

---

⭐ 如果这个项目对你有帮助，请给个Star支持一下！
