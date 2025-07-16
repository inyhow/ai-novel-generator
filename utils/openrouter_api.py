import os
import aiohttp
import logging
import json
import asyncio
from dotenv import load_dotenv
from pathlib import Path
from .cache import get_cached_response, cache_response

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 加载环境变量 - 确保从正确的路径加载
dotenv_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path)

async def generate_content(model: dict, prompt: str) -> str:
    """
    使用 OpenRouter API 生成内容
    """
    # 检查缓存
    cached_content = get_cached_response(prompt, model["id"])
    if cached_content:
        logger.info("使用缓存的响应")
        return cached_content
    
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.error("未找到 OPENROUTER_API_KEY 环境变量，请检查 .env 文件")
        raise ValueError(f"未找到 OPENROUTER_API_KEY 环境变量，已尝试从 {dotenv_path} 加载")

    # 调试输出API密钥的前几个字符，用于确认是否正确加载
    logger.debug(f"API密钥前10个字符: {api_key[:10]}...")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Novel Generator",
        "Content-Type": "application/json"
    }

    data = {
        "model": model["id"],
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4000,
        "temperature": 0.7,
        "top_p": 0.9,
        "stream": False
    }

    logger.info(f"开始调用 OpenRouter API，模型：{model['id']}")
    logger.debug(f"请求数据: {data}")

    # 重试逻辑
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=60
                ) as response:
                    response_text = await response.text()
                    logger.debug(f"API响应状态码: {response.status}")
                    logger.debug(f"API响应内容: {response_text[:200]}")

                    if response.status != 200:
                        if attempt < max_retries - 1:
                            logger.warning(f"API调用失败 (尝试 {attempt + 1}/{max_retries})，状态码: {response.status}")
                            await asyncio.sleep(2 ** attempt)  # 指数退避
                            continue
                        else:
                            error_msg = f"API调用失败，状态码: {response.status}, 响应: {response_text}"
                            logger.error(error_msg)
                            return None

                    try:
                        response_json = await response.json()
                        if not response_json.get('choices'):
                            logger.error(f"API响应缺少choices字段: {response_json}")
                            return None
                            
                        content = response_json['choices'][0]['message']['content']
                        logger.info("成功获取API响应")
                        
                        # 缓存响应
                        cache_response(prompt, model["id"], content.strip())
                        
                        return content.strip()
                    except (KeyError, json.JSONDecodeError) as e:
                        if attempt < max_retries - 1:
                            logger.warning(f"解析API响应失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            logger.error(f"解析API响应失败: {str(e)}")
                            return None

        except aiohttp.ClientError as e:
            if attempt < max_retries - 1:
                logger.warning(f"API请求失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                await asyncio.sleep(2 ** attempt)
                continue
            else:
                logger.error(f"API请求失败: {str(e)}")
                return None
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"生成内容时发生错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                await asyncio.sleep(2 ** attempt)
                continue
            else:
                logger.error(f"生成内容时发生未知错误: {str(e)}")
                return None
    
    return None
