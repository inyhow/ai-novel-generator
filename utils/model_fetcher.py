import os
from dotenv import load_dotenv

load_dotenv()

def fetch_free_models():
    """获取可用的模型列表"""
    return [
        {
            'id': 'deepseek/deepseek-chat-v3-0324:free',
            'name': 'deepseek-chat-v3-0324',
            'description': '强大的免费大型语言模型，适合生成创意内容和小说',
            'context_length': 4096
        }
    ]

def get_llama_model():
    """获取默认的 deepseek-chat-v3-0324 模型"""
    return {
            'id': 'deepseek/deepseek-chat-v3-0324:free',
            'name': 'deepseek-chat-v3-0324',
            'description': '强大的免费大型语言模型，适合生成创意内容和小说',
            'context_length': 4096
    }
