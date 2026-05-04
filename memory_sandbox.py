import os
import logging
from mem0 import Memory
from openai import OpenAI
from dotenv import load_dotenv

# 禁用过于冗长的 httpx 日志
logging.getLogger("httpx").setLevel(logging.WARNING)

# 加载环境变量
load_dotenv()

def main():
    print("===========================================")
    print("🐨 欢迎来到 KoalAgent (考拉特工) 记忆沙盒 (基于 Mem0 & 豆包)")
    print("输入 'quit' 或 'exit' 退出程序。")
    print("===========================================\n")

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    model_name = os.getenv("DOUBAO_MODEL")

    if not api_key or not model_name or "your_" in api_key:
        print("❌ 错误：请先在 .env 文件中配置好 OPENAI_API_KEY 和 DOUBAO_MODEL。")
        return

    # 1. 配置 Mem0
    # 使用豆包模型进行记忆提取，使用本地 HuggingFace BGE 模型进行中文记忆编码
    config = {
        "llm": {
            "provider": "openai",
            "config": {
                "model": model_name,
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
        print("⏳ 正在初始化记忆模块 (初次运行会自动下载 BGE 向量模型，请耐心等待)...")
        m = Memory.from_config(config)
        print("✅ 记忆模块初始化成功！")
    except Exception as e:
        print(f"❌ 记忆模块初始化失败: {e}")
        return

    # 初始化豆包大模型客户端（用于对话生成）
    client = OpenAI(
        api_key=api_key,
        base_url=base_url
    )

    user_id = "user_001" # 模拟固定用户

    while True:
        try:
            user_input = input("\n👨 你: ")
            if user_input.lower() in ['quit', 'exit', '退出']:
                print("👋 再见！")
                break
            
            if not user_input.strip():
                continue

            # 2. 将用户的输入存入 Mem0 记忆库
            print("  [Agent 正在思考并提取关键记忆...]")
            # add 会自动识别输入中是否有值得记忆的信息并保存
            m.add(user_input, user_id=user_id)

            # 3. 检索与当前对话相关的历史记忆
            relevant_memories = m.search(query=user_input, filters={'user_id': user_id})
            
            memory_str = ""
            if relevant_memories:
                print("\n  🧠 [回忆]: 我想起了关于你的这些事 ->")
                
                # 兼容 mem0 不同版本返回的数据结构
                mem_list = relevant_memories
                if hasattr(relevant_memories, 'results'):
                    mem_list = relevant_memories.results
                elif isinstance(relevant_memories, dict) and 'results' in relevant_memories:
                    mem_list = relevant_memories['results']
                elif isinstance(relevant_memories, dict):
                    mem_list = [relevant_memories]
                    
                for i, mem in enumerate(mem_list):
                    mem_text = str(mem)
                    if isinstance(mem, dict) and 'memory' in mem:
                        mem_text = mem['memory']
                    elif hasattr(mem, 'memory'):
                        mem_text = mem.memory
                    
                    print(f"      - {mem_text}")
                    memory_str += f"- {mem_text}\n"
            else:
                print("\n  🧠 [回忆]: (没有找到相关的历史记忆)")

            # 4. 构建包含记忆的 Prompt 并向豆包请求对话回复
            system_prompt = "你是一个贴心的中文私人助理。请使用原生中文，自然且得体地回答。"
            if memory_str:
                system_prompt += f"\n\n以下是关于用户的记忆信息，请在对话中自然地结合这些信息：\n{memory_str}"

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]

            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.7
            )

            agent_reply = response.choices[0].message.content
            print(f"\n🤖 Agent: {agent_reply}")

        except KeyboardInterrupt:
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 发生错误: {e}")

if __name__ == "__main__":
    main()
