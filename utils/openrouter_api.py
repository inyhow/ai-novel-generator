import asyncio
import json
import logging
import os
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

import config
from .cache import cache_response, get_cached_response

logger = logging.getLogger(__name__)
load_dotenv(Path(__file__).parent.parent / ".env")


def _build_endpoint(provider: str, model: dict) -> tuple[str, dict]:
    if provider == "newapi":
        api_base = (model.get("api_base") or os.getenv("NEWAPI_BASE_URL") or "").strip()
        api_key = (os.getenv("NEWAPI_API_KEY") or "").strip()
        if not api_base:
            raise ValueError("NEWAPI_BASE_URL is not set")
        if not api_key:
            raise ValueError("NEWAPI_API_KEY is not set")

        endpoint = f"{api_base.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        return endpoint, headers

    if provider == "google":
        api_base = (model.get("api_base") or os.getenv("GOOGLE_API_BASE") or "https://generativelanguage.googleapis.com/v1beta").strip()
        api_key = (os.getenv("GOOGLE_API_KEY") or "").strip()
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is not set")
        model_id = model.get("id", "").strip()
        if not model_id:
            raise ValueError("google model id is empty")
        endpoint = f"{api_base.rstrip('/')}/models/{model_id}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        return endpoint, headers

    if provider == "anthropic":
        api_base = (model.get("api_base") or os.getenv("ANTHROPIC_API_BASE") or "https://api.anthropic.com/v1").strip()
        api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        endpoint = f"{api_base.rstrip('/')}/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        return endpoint, headers

    api_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is not set")
    endpoint = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "AI Novel Generator",
        "Content-Type": "application/json",
    }
    return endpoint, headers


async def check_model_connection(model: dict) -> tuple[bool, str]:
    """Lightweight connectivity check for a model endpoint."""
    provider = model.get("provider", "openrouter")
    model_id = model["id"]
    endpoint, headers = _build_endpoint(provider, model)
    if provider == "google":
        payload = {
            "contents": [{"role": "user", "parts": [{"text": "ping"}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 16},
        }
    elif provider == "anthropic":
        payload = {
            "model": model_id,
            "max_tokens": 16,
            "temperature": 0,
            "messages": [{"role": "user", "content": "ping"}],
        }
    else:
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 8,
            "temperature": 0,
            "stream": False,
        }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=min(20, config.REQUEST_TIMEOUT),
            ) as resp:
                text = await resp.text()
                if resp.status != 200:
                    return False, f"HTTP {resp.status}: {text[:120]}"
                data = await resp.json()
                if provider == "google":
                    candidates = data.get("candidates") or []
                    if not candidates:
                        return False, "No candidates in response"
                elif provider == "anthropic":
                    blocks = data.get("content") or []
                    if not blocks:
                        return False, "No content blocks in response"
                else:
                    choices = data.get("choices") or []
                    if not choices:
                        return False, "No choices in response"
                return True, "ok"
    except Exception as exc:
        return False, str(exc)


async def generate_content(model: dict, prompt: str) -> str | None:
    provider = model.get("provider", "openrouter")
    model_id = model["id"]
    cache_model_id = f"{provider}:{model_id}:{model.get('api_base', '')}"

    cached = get_cached_response(prompt, cache_model_id)
    if cached:
        logger.info("Using cached response")
        return cached

    endpoint, headers = _build_endpoint(provider, model)
    if provider == "google":
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": config.TEMPERATURE,
                "topP": config.TOP_P,
                "maxOutputTokens": config.MAX_TOKENS,
            },
        }
    elif provider == "anthropic":
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": config.TEMPERATURE,
            "max_tokens": config.MAX_TOKENS,
        }
    else:
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": config.MAX_TOKENS,
            "temperature": config.TEMPERATURE,
            "top_p": config.TOP_P,
            "stream": False,
        }

    last_error = ""
    for attempt in range(config.MAX_RETRIES):
        try:
            req_payload = dict(payload)
            # On retries, lower output budget to improve completion stability on some providers.
            if attempt > 0:
                if provider == "google":
                    gc = dict(req_payload.get("generationConfig") or {})
                    gc["maxOutputTokens"] = max(512, int(config.MAX_TOKENS / (attempt + 1)))
                    req_payload["generationConfig"] = gc
                elif provider == "anthropic":
                    req_payload["max_tokens"] = max(512, int(config.MAX_TOKENS / (attempt + 1)))
                else:
                    req_payload["max_tokens"] = max(512, int(config.MAX_TOKENS / (attempt + 1)))
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    headers=headers,
                    json=req_payload,
                    timeout=config.REQUEST_TIMEOUT,
                ) as resp:
                    text = await resp.text()
                    if resp.status != 200:
                        last_error = f"HTTP {resp.status}: {text[:300]}"
                        if attempt < config.MAX_RETRIES - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        logger.error("LLM API error %s: %s", resp.status, text)
                        raise RuntimeError(last_error)

                    data = await resp.json()
                    if provider == "google":
                        candidates = data.get("candidates") or []
                        if not candidates:
                            logger.error("Invalid Google API response: %s", json.dumps(data)[:300])
                            return None
                        parts = (((candidates[0] or {}).get("content") or {}).get("parts") or [])
                        content = "\n".join([str((p or {}).get("text", "")).strip() for p in parts if (p or {}).get("text")]).strip()
                    elif provider == "anthropic":
                        blocks = data.get("content") or []
                        texts = [str((b or {}).get("text", "")).strip() for b in blocks if (b or {}).get("type") == "text"]
                        content = "\n".join([t for t in texts if t]).strip()
                    else:
                        choices = data.get("choices") or []
                        if not choices:
                            logger.error("Invalid API response: %s", json.dumps(data)[:300])
                            return None
                        content = choices[0]["message"]["content"].strip()
                    if not content:
                        finish_reason = ""
                        if provider not in {"google", "anthropic"}:
                            choices = data.get("choices") or []
                            finish_reason = str((choices[0] or {}).get("finish_reason", "")) if choices else ""
                        last_error = f"empty_content provider={provider} finish_reason={finish_reason}".strip()
                        logger.error("Empty content from provider=%s: %s", provider, json.dumps(data)[:300])
                        if attempt < config.MAX_RETRIES - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        raise RuntimeError(last_error)
                    cache_response(prompt, cache_model_id, content)
                    return content
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            last_error = f"{exc.__class__.__name__}: {exc}"
            if attempt < config.MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            logger.error("Request failed: %s", exc)
            raise RuntimeError(last_error)
        except Exception as exc:
            last_error = f"{exc.__class__.__name__}: {exc}"
            logger.exception("Unexpected generation error: %s", exc)
            if attempt < config.MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            raise RuntimeError(last_error)

    raise RuntimeError(last_error or "upstream_generation_failed")
