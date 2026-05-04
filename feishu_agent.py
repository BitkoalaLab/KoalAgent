import os
import json
import logging
import sqlite3
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

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
            
        # 2. 初始化 SQLite 数据库进行状态持久化
        self.db_conn = sqlite3.connect("koalagent.db", check_same_thread=False)
        self.db_cursor = self.db_conn.cursor()
        self.db_cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_users (
                open_id TEXT PRIMARY KEY,
                last_chat_time DATETIME,
                last_heartbeat_time DATETIME
            )
        ''')
        self.db_conn.commit()
        
        # 短期对话缓存 (open_id -> [{"role": "user", "content": "..."}, ...])
        self.chat_history = {}
        
        # 线程池用于并发执行心跳任务
        self.executor = ThreadPoolExecutor(max_workers=5)
        
        # 调度器，以免阻塞主线程的 WebSocket
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

    # --- 状态持久化函数 ---
    def update_user_activity(self, open_id, is_chat=True):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.db_cursor.execute("SELECT * FROM active_users WHERE open_id = ?", (open_id,))
        if not self.db_cursor.fetchone():
            self.db_cursor.execute("INSERT INTO active_users (open_id, last_chat_time, last_heartbeat_time) VALUES (?, ?, ?)", 
                                   (open_id, now if is_chat else None, now if not is_chat else None))
        else:
            if is_chat:
                self.db_cursor.execute("UPDATE active_users SET last_chat_time = ? WHERE open_id = ?", (now, open_id))
            else:
                self.db_cursor.execute("UPDATE active_users SET last_heartbeat_time = ? WHERE open_id = ?", (now, open_id))
        self.db_conn.commit()

    def get_all_active_users(self):
        self.db_cursor.execute("SELECT open_id, last_chat_time, last_heartbeat_time FROM active_users")
        return self.db_cursor.fetchall()

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

    def fetch_user_memories(self, user_id, query="我的核心画像与偏好"):
        try:
            # Phase 1: 改用 search，限制 top 5，解决 token 膨胀问题
            results = self.m.search(query, user_id=user_id, limit=5)
            
            # 兼容不同 mem0 版本的返回结果格式
            mem_list = results.results if hasattr(results, 'results') else (results['results'] if isinstance(results, dict) and 'results' in results else (results if isinstance(results, list) else [results]))
            
            mem_strings = []
            for mem in mem_list:
                if isinstance(mem, dict) and 'memory' in mem:
                    mem_strings.append(mem['memory'])
                elif hasattr(mem, 'memory'):
                    mem_strings.append(mem.memory)
                elif isinstance(mem, str):
                    mem_strings.append(mem)
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
            
            # Phase 1: SQLite 持久化记录活跃时间
            self.update_user_activity(open_id, is_chat=True)

            if msg.message_type != "text":
                self.send_feishu_message(open_id, "暂时只支持文本消息哦~")
                return

            text = json.loads(msg.content)["text"]
            print(f"\n💬 收到飞书消息: {text}")

            # 1. 存入长期记忆
            self.m.add(text, user_id=open_id)

            # 2. 提取画像 (根据当前对话内容检索 top-k 相关记忆)
            memories = self.fetch_user_memories(open_id, query=text)
            memory_str = "\n".join([f"- {m}" for m in memories]) if memories else "暂无相关记忆"

            system_prompt = f"你是一个在飞书中运行的私人助理。\n[用户的长期记忆参考]：\n{memory_str}\n\n请自然地回答用户的问题，并结合上面提取的记忆。"
            
            # 3. 融合短期对话历史缓存 (滑动窗口)
            if open_id not in self.chat_history:
                self.chat_history[open_id] = []
                
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(self.chat_history[open_id])
            messages.append({"role": "user", "content": text})
            
            # 4. 交给大模型
            reply = self.call_llm_with_tools(messages)
            
            # 5. 回复飞书并更新短期记忆窗口
            self.send_feishu_message(open_id, reply)
            print(f"🤖 已回复: {reply}")
            
            self.chat_history[open_id].append({"role": "user", "content": text})
            self.chat_history[open_id].append({"role": "assistant", "content": reply})
            if len(self.chat_history[open_id]) > 10: # 保留最近 5 轮交互
                self.chat_history[open_id] = self.chat_history[open_id][-10:]

        except Exception as e:
            print(f"❌ 处理飞书消息异常: {e}")

    # ================= 心跳机制 =================
    def process_user_heartbeat(self, open_id, last_chat_time_str, last_heartbeat_time_str, now_dt):
        try:
            # 阈值 1: 聊天活跃期防打扰 (最近 5 分钟发过消息不触发心跳)
            if last_chat_time_str:
                last_chat = datetime.strptime(last_chat_time_str, "%Y-%m-%d %H:%M:%S")
                if (now_dt - last_chat).total_seconds() < 5 * 60:
                    print(f"  [静默拦截] 用户 {open_id} 最近5分钟处于活跃对话，不打扰。")
                    return

            # 阈值 2: 心跳冷却期防打扰 (两次心跳间隔必须大于 10 分钟)
            if last_heartbeat_time_str:
                last_hb = datetime.strptime(last_heartbeat_time_str, "%Y-%m-%d %H:%M:%S")
                if (now_dt - last_hb).total_seconds() < 10 * 60:
                    print(f"  [冷却拦截] 用户 {open_id} 距离上次心跳不足10分钟。")
                    return
            
            print(f"  -> 正在给用户 {open_id} 计算并发起心跳关怀...")

            # 心跳时使用通用画像检索
            memories = self.fetch_user_memories(open_id, query="用户的个人特征、作息与核心偏好")
            memory_str = "\n".join([f"- {m}" for m in memories]) if memories else "暂无画像"

            system_prompt = f"""你是一个飞书私人助理。
[当前时间]：{now_dt.strftime("%Y-%m-%d %H:%M:%S")}
[用户的核心画像参考]：\n{memory_str}

这是一次定期的主动心跳。你需要主动找用户聊天（可以是基于画像的简短问候，或者是调用工具去获取他们可能感兴趣的新闻/天气并分享）。
请保持自然得体，绝不要重复你以前说过的话。请控制字数，不要像机器人在汇报工作。"""
            
            messages = [{"role": "system", "content": system_prompt}]
            
            # 拼入短期历史让心跳显得更连贯
            if open_id in self.chat_history:
                messages.extend(self.chat_history[open_id][-4:]) 

            messages.append({"role": "user", "content": "（内部触发指令：现在是你的自主思考时间，请主动开启一个话题并给我发消息）"})
            
            reply = self.call_llm_with_tools(messages)
            
            # 保存到聊天历史，确保心跳发的内容用户能继续顺着聊
            if open_id not in self.chat_history:
                self.chat_history[open_id] = []
            self.chat_history[open_id].append({"role": "assistant", "content": reply})

            self.send_feishu_message(open_id, reply)
            # 记录这次心跳时间
            self.update_user_activity(open_id, is_chat=False)
            
        except Exception as e:
            print(f"❌ 心跳处理失败 {open_id}: {e}")

    def tick(self):
        now_dt = datetime.now()
        
        # 阈值 0: 夜间免打扰 (23点到8点不发心跳)
        if now_dt.hour >= 23 or now_dt.hour < 8:
            print(f"[{now_dt.strftime('%H:%M:%S')}] 夜间免打扰开启，挂起所有心跳。")
            return
            
        users = self.get_all_active_users()
        if not users:
            return
            
        print(f"\n[{now_dt.strftime('%Y-%m-%d %H:%M:%S')}] 🫀 调度器触发，开始并发检测 {len(users)} 个活跃用户是否需要心跳...")
        
        # Phase 1: 并发分发心跳任务
        for open_id, last_chat_time, last_heartbeat_time in users:
            self.executor.submit(self.process_user_heartbeat, open_id, last_chat_time, last_heartbeat_time, now_dt)

    def run(self):
        # 启动心跳 (目前设定 120 秒触发一次轮询检测，具体发不发由 process_user_heartbeat 里的阈值决定)
        self.scheduler.add_job(self.tick, 'interval', seconds=120)
        self.scheduler.start()
        print("✅ 后台心跳调度器已启动 (每120秒一轮检测)。")

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
