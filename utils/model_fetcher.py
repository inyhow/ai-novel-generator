from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_DEFAULT_MODEL = "openrouter/free"


def _openrouter_models() -> list[dict]:
    return [
        {
            "uid": f"openrouter::{OPENROUTER_DEFAULT_MODEL}",
            "provider": "openrouter",
            "id": OPENROUTER_DEFAULT_MODEL,
            "name": "openrouter/free",
            "description": "Free model on OpenRouter",
            "context_length": 4096,
        }
    ]


def _newapi_models() -> list[dict]:
    base_url = (os.getenv("NEWAPI_BASE_URL") or "").strip()
    model_list = (os.getenv("NEWAPI_MODELS") or os.getenv("NEWAPI_MODEL") or "").strip()
    if not base_url or not model_list:
        return []

    models = []
    for raw in model_list.split(","):
        model_id = raw.strip()
        if not model_id:
            continue
        models.append(
            {
                "uid": f"newapi::{model_id}",
                "provider": "newapi",
                "id": model_id,
                "name": f"{model_id} (NewAPI)",
                "description": "Model from NewAPI-compatible endpoint",
                "api_base": base_url,
            }
        )
    return models


def _google_models() -> list[dict]:
    model_list = (os.getenv("GOOGLE_MODELS") or os.getenv("GOOGLE_MODEL") or "").strip()
    if not model_list:
        return []
    models = []
    for raw in model_list.split(","):
        model_id = raw.strip()
        if not model_id:
            continue
        models.append(
            {
                "uid": f"google::{model_id}",
                "provider": "google",
                "id": model_id,
                "name": f"{model_id} (Google)",
                "description": "Official Google Generative Language API model",
            }
        )
    return models


def _anthropic_models() -> list[dict]:
    model_list = (os.getenv("ANTHROPIC_MODELS") or os.getenv("ANTHROPIC_MODEL") or "").strip()
    if not model_list:
        return []
    models = []
    for raw in model_list.split(","):
        model_id = raw.strip()
        if not model_id:
            continue
        models.append(
            {
                "uid": f"anthropic::{model_id}",
                "provider": "anthropic",
                "id": model_id,
                "name": f"{model_id} (Anthropic)",
                "description": "Official Anthropic Messages API model",
            }
        )
    return models


def fetch_free_models() -> list[dict]:
    """Return selectable models from OpenRouter/NewAPI/Google/Anthropic."""
    return _openrouter_models() + _newapi_models() + _google_models() + _anthropic_models()


def resolve_model(model_uid: str | None) -> dict:
    models = fetch_free_models()
    if model_uid:
        for model in models:
            if model.get("uid") == model_uid:
                return model
    return models[0]


def get_llama_model() -> dict:
    """Backward-compatible default model getter."""
    return resolve_model(None)
