# 🐨 KoalAgent (考拉特工) 

[![Built by BitKoala Lab](https://img.shields.io/badge/Built%20by-BitKoala%20Lab-blue.svg)](https://github.com/BitkoalaLab)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**[English](#english-version) | [中文说明](#中文说明)**

---

## 中文说明

**KoalAgent** 是由**比特考拉实验室 (BitKoala Lab)** 孵化的一个原生开源、具备长期记忆与自主心跳机制的个人专属 AI 智能体 (Agent)。

区别于传统的“一问一答”式死板聊天机器人，KoalAgent 旨在成为一个“有生命力”的实体。它能够记住你的个人偏好、利用本地环境主动获取外部世界的数据，并在不需要你触发的情况下，在后台主动产生思考并向你发送关怀。它深度集成了飞书 (Feishu/Lark) 的长连接 WebSocket，让你能够随时随地在手机上与它互动。

### ✨ 核心特性 (Features)
- 🧠 **原生中文长期记忆 (Persistent Memory)**：底层采用 `Mem0` 结合本地化的 `BAAI/bge-small-zh-v1.5` 模型。它能精准提取你的身份画像、喜好与聊天历史，并在每次对话中潜移默化地运用这些记忆。
- 🫀 **自主心跳引擎 (Proactive Heartbeat)**：基于 `APScheduler` 构建的后台守护进程。即使你不发消息，它也会根据设定的时间间隔主动苏醒，结合你的画像与当前系统时间，进行发散性思考。
- 🛠️ **实体抓手 (Tool Calling)**：原生支持函数调用。遇到自己不懂的事情，它能自己决定调用本地 Python 工具（如获取实时天气、爬取 Hacker News 最热资讯），获取真实数据后再与你沟通。
- 💬 **零内网穿透的双向通讯**：深度接入飞书 (Feishu) Open API 的 WebSocket 模式。无需公网服务器，无需配置繁琐的 Webhook，只需在本地运行即可实现完美的手机端双向对话推送。

### 🚀 快速上手 (Quick Start)

**1. 克隆与安装依赖**
```bash
git clone https://github.com/your-username/KoalAgent.git
cd KoalAgent
pip install -r requirements.txt
```

**2. 配置环境变量**
复制项目根目录的配置模板并新建一个 `.env` 文件：
```env
# 大模型配置 (默认使用火山引擎豆包)
OPENAI_API_KEY=your_doubao_api_key
OPENAI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL=your_endpoint_id

# 飞书机器人配置 (前往飞书开发者后台获取)
FEISHU_APP_ID=cli_xxxxxx
FEISHU_APP_SECRET=xxxxxx
```

**3. 运行你的考拉特工**
```bash
# 启动飞书版双向全能 Agent
python feishu_agent.py

# 或是仅在终端测试记忆沙盒
python memory_sandbox.py
```

### 🗺️ 演进路线图 (Roadmap)
- [x] Phase 0: 长期记忆提取与检索
- [x] Phase 0.5: 引入 Tool Calling 与飞书通讯
- [ ] **Phase 1: Code Interpreter (代码解释器)** - 赋予 Agent 在沙盒中自己写 Python 爬虫并执行的终极自由度。
- [ ] **Phase 2: Computer Use (系统控制)** - 引入 Playwright 实现网页自动化控制。

---

## English Version

**KoalAgent** is an open-source, proactive personal AI Agent with persistent memory, hatched by **BitKoala Lab**.

Unlike traditional "request-response" chatbots, KoalAgent is designed to be a "living" entity. It remembers your personal preferences, actively fetches data from the external world using local tools, and autonomously generates thoughts to check in on you without any prompt. It deeply integrates with Feishu (Lark) via WebSocket, allowing you to interact with it anytime, anywhere on your mobile device.

### ✨ Key Features
- 🧠 **Native Persistent Memory**: Powered by `Mem0` and the localized `BAAI/bge-small-zh-v1.5` embedding model. It accurately extracts your user persona, preferences, and chat history, subtly applying these memories to every conversation.
- 🫀 **Proactive Heartbeat Engine**: A background daemon built on `APScheduler`. Even if you don't message it, it wakes up at set intervals, considers your persona and the current time, and initiates a conversation.
- 🛠️ **Tool Calling**: Native support for function calling. When facing tasks beyond its LLM knowledge, it decides to execute local Python tools (e.g., fetching real-time weather, scraping top Hacker News stories) before replying to you.
- 💬 **Zero-Config Two-Way Communication**: Deeply integrates with Feishu's Open API WebSocket mode. No public IP or complicated Webhooks required—just run it locally for seamless two-way chat on your phone.

### 🚀 Quick Start

**1. Clone & Install**
```bash
git clone https://github.com/your-username/KoalAgent.git
cd KoalAgent
pip install -r requirements.txt
```

**2. Environment Setup**
Create a `.env` file in the root directory:
```env
# LLM Config (Default: Volcengine Doubao)
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL=your_endpoint_id

# Feishu / Lark Bot Config
FEISHU_APP_ID=cli_xxxxxx
FEISHU_APP_SECRET=xxxxxx
```

**3. Run Your Agent**
```bash
# Start the full-featured Feishu Agent
python feishu_agent.py

# Or test the memory sandbox in the terminal
python memory_sandbox.py
```

### 🗺️ Roadmap
- [x] Phase 0: Persistent Memory Extraction & Retrieval
- [x] Phase 0.5: Tool Calling & Feishu Integration
- [ ] **Phase 1: Code Interpreter** - Granting the Agent the ultimate freedom to write and execute its own Python scripts in a sandbox.
- [ ] **Phase 2: Computer Use** - Introducing Playwright for web automation and GUI control.

---
*Created with ❤️ by BitKoala Lab.*
