import os
import json
import logging
from datetime import datetime
from threading import Thread

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from mem0 import Memory
from openai import OpenAI

import lark_oapi as lark
from lark_oapi.api.im.v1 import *

# 禁用冗余日志
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("lark_oapi").setLevel(logging.WARNING)

load_dotenv()

class KoalAgent:
    def __init__(self):
        print("===========================================")
        print("🐨 正在唤醒 KoalAgent (考拉特工) 飞书双向引擎...")
        print("===========================================\n")
        
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
        self.model_name = os.getenv("DOUBAO_MODEL")
        self.feishu_app_id = os.getenv("FEISHU_APP_ID")
        self.feishu_app_secret = os.getenv("FEISHU_APP_SECRET")
        
        if not all([self.api_key, self.model_name, self.feishu_app_id, self.feishu_app_secret]):
            print("❌ 错误：请在 .env 文件中配置好 API_KEY、模型ID，以及 FEISHU_APP_ID 和 FEISHU_APP_SECRET。")
            exit(1)

        # 1. 配置并初始化 Mem0
        config = {
            "llm": {
                "provider": "openai",
                "config": {
                    "model": self.model_name,
                    "api_key": self.api_key,
                    "openai_base_url": self.base_url,
                    "max_tokens": 1500,
                }
            },
            "embedder": {
                "provider": "huggingface",
                "config": {
                    "model": "BAAI/bge-small-zh-v1.5"
                }
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "feishu_memories",
                    "embedding_model_dims": 512
                }
            }
        }
        self.m = Memory.from_config(config)
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        
        # 初始化飞书 Open API 客户端 (用于发送消息)
        self.lark_client = lark.Client.builder() \
            .app_id(self.feishu_app_id) \
            .app_secret(self.feishu_app_secret) \
            .log_level(lark.LogLevel.WARNING) \
            .build()
            
        # 用于记录谁和机器人聊过天（心跳会给他们发消息）
        self.active_users = set()
        
        # 调度器，这里用 BackgroundScheduler，以免阻塞主线程的 WebSocket
        self.scheduler = BackgroundScheduler()

        # 注册工具
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_latest_tech_news",
                    "description": "获取 Hacker News 上最热门的 3 条技术新闻",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "获取城市天气",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": ["city"]
                    }
                }
            }
        ]

    # --- 工具函数 ---
    def get_latest_tech_news(self):
        try:
            url = "https://hacker-news.firebaseio.com/v0/topstories.json"
            response = requests.get(url, timeout=5)
            story_ids = response.json()[:3]
            stories = []
            for sid in story_ids:
                data = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=5).json()
                stories.append(f"- {data.get('title')} ({data.get('url', '')})")
            return "Top News:\n" + "\n".join(stories)
        except Exception as e:
            return f"新闻获取失败: {e}"

    def get_weather(self, city):
        try:
            return requests.get(f"https://wttr.in/{city}?format=3", timeout=5).text.strip()
        except Exception as e:
            return f"天气获取失败: {e}"
    # ----------------

    def fetch_user_memories(self, user_id):
        try:
            if hasattr(self.m, 'get_all'):
                all_memories = self.m.get_all(user_id=user_id)
            else:
                all_memories = self.m.search("我的全部信息", filters={"user_id": user_id})
                
            mem_list = all_memories.results if hasattr(all_memories, 'results') else (all_memories['results'] if isinstance(all_memories, dict) and 'results' in all_memories else (all_memories if isinstance(all_memories, list) else [all_memories]))
            
            mem_strings = []
            for mem in mem_list:
                if isinstance(mem, dict) and 'memory' in mem:
                    mem_strings.append(mem['memory'])
                elif hasattr(mem, 'memory'):
                    mem_strings.append(mem.memory)
                else:
                    mem_strings.append(str(mem))
            return list(set(mem_strings))
        except Exception as e:
            return []

    def call_llm_with_tools(self, messages):
        """通用的大模型带工具的请求封装"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=self.tools,
                temperature=0.7
            )
            message = response.choices[0].message
            
            if message.tool_calls:
                print("  [Agent 触发本地工具调用]")
                messages.append(message)
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)
                    
                    if function_name == "get_latest_tech_news":
                        result = self.get_latest_tech_news()
                    elif function_name == "get_weather":
                        result = self.get_weather(arguments.get("city", "Beijing"))
                    else:
                        result = "工具不存在"
                        
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(result)
                    })
                
                # 第二轮请求
                second_response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=0.7
                )
                return second_response.choices[0].message.content.strip()
            else:
                return message.content.strip()
        except Exception as e:
            return f"抱歉，我脑子短路了: {e}"

    def send_feishu_message(self, receive_id, content):
        """向飞书发送消息"""
        request: CreateMessageRequest = CreateMessageRequest.builder() \
            .receive_id_type("open_id") \
            .request_body(CreateMessageRequestBody.builder()
                .receive_id(receive_id)
                .msg_type("text")
                .content(json.dumps({"text": content}))
                .build()) \
            .build()

        response = self.lark_client.im.v1.message.create(request)
        if not response.success():
            print(f"❌ 飞书消息发送失败: {response.code}, {response.msg}")

    # ================= 飞书事件回调 =================
    def on_message_receive(self, data: P2ImMessageReceiveV1) -> None:
        try:
            msg = data.event.message
            sender = data.event.sender
            open_id = sender.sender_id.open_id
            
            # 记录活跃用户
            self.active_users.add(open_id)

            if msg.message_type != "text":
                self.send_feishu_message(open_id, "暂时只支持文本消息哦~")
                return

            text = json.loads(msg.content)["text"]
            print(f"\n💬 收到来自飞书的消息: {text}")

            # 1. 存入记忆
            self.m.add(text, user_id=open_id)

            # 2. 提取画像
            memories = self.fetch_user_memories(open_id)
            memory_str = "\n".join([f"- {m}" for m in memories])

            system_prompt = f"你是一个在飞书中运行的私人助理。\n[用户的长期记忆]：\n{memory_str}\n\n请自然地回答用户的问题，并结合上面提取的记忆。"
            
            # 3. 交给大模型
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ]
            
            reply = self.call_llm_with_tools(messages)
            
            # 4. 回复飞书
            self.send_feishu_message(open_id, reply)
            print(f"🤖 已回复飞书: {reply}")

        except Exception as e:
            print(f"❌ 处理飞书消息异常: {e}")

    # ================= 心跳机制 =================
    def tick(self):
        if not self.active_users:
            return
            
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{now}] 🫀 心跳触发，准备给 {len(self.active_users)} 个活跃用户发送关怀...")

        for open_id in self.active_users:
            memories = self.fetch_user_memories(open_id)
            memory_str = "\n".join([f"- {m}" for m in memories])

            system_prompt = f"""你是一个飞书私人助理。
[当前时间]：{now}
[用户的长期记忆]：\n{memory_str}

这是一次定期的主动心跳。你需要主动找用户聊天（可以是问候、或者是调用工具去获取他们可能感兴趣的新闻/天气并分享）。
语气要自然得体。"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "（后台心跳唤醒：请主动对我说句话）"}
            ]
            
            reply = self.call_llm_with_tools(messages)
            self.send_feishu_message(open_id, reply)

    def run(self):
        # 启动心跳 (目前设定 120 秒一次，以免过于频繁发消息)
        self.scheduler.add_job(self.tick, 'interval', seconds=120)
        self.scheduler.start()
        print("✅ 后台心跳调度器已启动 (间隔: 120秒)。")

        # 构造飞书长连接监听器
        event_handler = lark.EventDispatcherHandler.builder("", "") \
            .register_p2_im_message_receive_v1(self.on_message_receive) \
            .build()
            
        cli = lark.ws.Client(
            self.feishu_app_id, 
            self.feishu_app_secret, 
            event_handler=event_handler,
            log_level=lark.LogLevel.WARNING
        )
        
        print("🎧 开始监听飞书 WebSocket 长连接 (按 Ctrl+C 退出)...")
        cli.start()

if __name__ == "__main__":
    agent = KoalAgent()
    agent.run()
