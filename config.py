"""
应用配置文件
"""
import os
from pathlib import Path

# 应用设置
APP_HOST = "0.0.0.0"
APP_PORT = 8000
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# API设置
MAX_TOKENS = 4000
TEMPERATURE = 0.7
TOP_P = 0.9
REQUEST_TIMEOUT = 60
MAX_RETRIES = 3

# 输入验证
MIN_PROMPT_LENGTH = 10
MAX_PROMPT_LENGTH = 2000

# 缓存设置
CACHE_ENABLED = True
CACHE_DIR = Path("cache")

# 日志设置
LOG_DIR = Path("logs")
LOG_LEVEL = "INFO"
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# 确保目录存在
LOG_DIR.mkdir(exist_ok=True)
if CACHE_ENABLED:
    CACHE_DIR.mkdir(exist_ok=True)