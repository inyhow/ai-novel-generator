import hashlib
import json
import os
from pathlib import Path
from typing import Optional

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

def get_cache_key(prompt: str, model_id: str) -> str:
    """Generate a cache key from prompt and model"""
    content = f"{prompt}:{model_id}"
    return hashlib.md5(content.encode()).hexdigest()

def get_cached_response(prompt: str, model_id: str) -> Optional[str]:
    """Get cached response if it exists"""
    try:
        cache_key = get_cache_key(prompt, model_id)
        cache_file = CACHE_DIR / f"{cache_key}.json"
        
        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('content')
    except Exception:
        pass
    return None

def cache_response(prompt: str, model_id: str, content: str) -> None:
    """Cache the response"""
    try:
        cache_key = get_cache_key(prompt, model_id)
        cache_file = CACHE_DIR / f"{cache_key}.json"
        
        data = {
            'prompt': prompt[:100],  # Store first 100 chars for reference
            'model_id': model_id,
            'content': content
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # Fail silently if caching fails