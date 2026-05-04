import os
import time
import json
import logging
import requests
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from mem0 import Memory
from openai import OpenAI
from dotenv import load_dotenv

# 禁用冗余日志
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

load_dotenv()

class HeartbeatAgent:
    def __init__(self):
        print("===========================================")
        print("🐨 正在唤醒 KoalAgent (考拉特工) 心跳引擎...")
        print("===========================================\n")
        
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
        self.model_name = os.getenv("DOUBAO_MODEL")
        
        if not api_key or not self.model_name or "your_" in api_key:
            print("❌ 错误：请先在 .env 文件中配置好 API_KEY 和 模型 ID。")
            exit(1)

        # 1. 配置并初始化 Mem0
        config = {
            "llm": {
                "provider": "openai",
                "config": {
                    "model": self.model_name,
                    "api_key": api_key,
                    "openai_base_url": base_url,
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
                    "collection_name": "sandbox_memories",
                    "embedding_model_dims": 512
                }
            }
        }
        
        try:
            self.m = Memory.from_config(config)
            print("✅ 长期记忆库连接成功！")
        except Exception as e:
            print(f"❌ 记忆库连接失败: {e}")
            exit(1)

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.user_id = "user_001"
        self.scheduler = BlockingScheduler()
        
        # 2. 注册可用的工具 (Tools Schema)
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_latest_tech_news",
                    "description": "获取当前 Hacker News 上最热门的 3 条技术新闻/开源项目",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "获取指定城市的实时天气情况",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "城市名称的拼音或英文，例如 'Beijing', 'Shanghai'"
                            }
                        },
                        "required": ["city"]
                    }
                }
            }
        ]

    # --- Python 工具函数实现 ---
    def get_latest_tech_news(self):
        try:
            url = "https://hacker-news.firebaseio.com/v0/topstories.json"
            response = requests.get(url, timeout=10)
            story_ids = response.json()[:3]
            
            stories = []
            for sid in story_ids:
                story_res = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=10)
                data = story_res.json()
                stories.append(f"- {data.get('title')} (url: {data.get('url', '无链接')})")
            return "Hacker News Top 3:\n" + "\n".join(stories)
        except Exception as e:
            return f"获取新闻失败: {e}"

    def get_weather(self, city):
        try:
            url = f"https://wttr.in/{city}?format=3"
            response = requests.get(url, timeout=10)
            return response.text.strip()
        except Exception as e:
            return f"获取天气失败: {e}"
    # --------------------------

    def fetch_all_memories(self):
        """获取该用户的所有记忆画像"""
        try:
            if hasattr(self.m, 'get_all'):
                all_memories = self.m.get_all(user_id=self.user_id)
            else:
                all_memories = self.m.search("我的全部信息", filters={"user_id": self.user_id})
                
            mem_list = all_memories
            if hasattr(all_memories, 'results'):
                mem_list = all_memories.results
            elif isinstance(all_memories, dict) and 'results' in all_memories:
                mem_list = all_memories['results']
            elif isinstance(all_memories, dict):
                mem_list = [all_memories]
                
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
            print(f"[Error fetching memory]: {e}")
            return []

    def tick(self):
        """带有 Tool Calling 的智能心跳循环"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{now}] 🫀 心跳触发... Agent 正在后台思考...")

        memories = self.fetch_all_memories()
        memory_str = "\n".join([f"- {m}" for m in memories]) if memories else "暂无记录。"

        system_prompt = f"""你是一个自主运行的私人助理 Agent。
[当前系统时间]：{now}
[用户的长期记忆]：
{memory_str}

你的任务：
这是一次定期的心跳触发，你需要主动发起一句友好的关怀或分享。
你有能力调用工具查询最新技术新闻或者天气。如果你觉得结合用户的记忆（比如TA是做前端的），有必要查询一些新闻来分享给TA，请大胆使用工具。
要求：
1. 语气一定要像一个贴心的人类朋友。
2. 如果调用了工具，请在回复中自然地结合查询到的数据。
3. 篇幅简短，不要像机器人。
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "（后台心跳唤醒：请决定是否调用工具，并开始你的分享）"}
        ]

        try:
            # === 第一轮：发送请求，携带可用工具 ===
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=self.tools,
                temperature=0.8
            )
            
            message = response.choices[0].message
            
            # 判断模型是否决定调用工具
            if message.tool_calls:
                print("  [思考结果: 决定使用外挂工具获取真实数据！]")
                messages.append(message) # 必须把模型的请求拼接到上下文
                
                # 遍历执行模型要求的所有工具
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)
                    print(f"    🛠️ 执行工具: {function_name} {arguments}")
                    
                    # 本地路由执行
                    if function_name == "get_latest_tech_news":
                        result = self.get_latest_tech_news()
                    elif function_name == "get_weather":
                        result = self.get_weather(arguments.get("city", "Beijing"))
                    else:
                        result = "未知的工具"
                        
                    print(f"    📥 获得数据: {result.replace(chr(10), ' | ')}") # 单行打印以免太长
                    
                    # 把工具执行的真实结果拼接到上下文
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(result)
                    })
                    
                # === 第二轮：带着外部数据，再次请求模型生成最终回复 ===
                print("  [Agent 正在整合真实数据写文案...]")
                second_response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=0.8
                )
                final_reply = second_response.choices[0].message.content.strip()
                print(f"🤖 Agent 主动发声: {final_reply}")
                
            else:
                # 模型觉得不需要调用工具，直接回复
                print("  [思考结果: 无需工具，直接回复]")
                final_reply = message.content.strip()
                print(f"🤖 Agent 主动发声: {final_reply}")

        except Exception as e:
            print(f"❌ 思考过程发生错误: {e}")

    def run(self):
        print("\n⏳ 正在启动心跳调度器 (间隔: 30秒)...")
        print("💡 提示: 接下来你不需要输入任何内容，静静观察终端里 Agent 是如何调用外部 API 抓取新闻的。\n")
        
        self.tick() # 立即执行一次
        self.scheduler.add_job(self.tick, 'interval', seconds=30)
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            print("\n👋 停止心跳，Agent 已休眠。")

if __name__ == "__main__":
    agent = HeartbeatAgent()
    agent.run()
