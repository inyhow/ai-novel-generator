import asyncio
import logging
import re
import time
import uuid
from datetime import datetime
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from dotenv import load_dotenv

import config
from utils.model_fetcher import fetch_free_models, resolve_model
from utils.novel_workflow import (
    build_expand_prompt,
    build_continue_prompt,
    build_generate_prompt,
    build_inspiration_prompt,
    build_pad_prompt,
    build_rewrite_prompt,
    get_default_workflow_questions,
)
from utils.openrouter_api import check_model_connection, generate_content
from utils.fanqie_publisher import publish_chapter_via_cdp, probe_cdp_endpoint
from utils.content_quality import audit_chapters, clean_chapter_content, ensure_unique_titles

# Ensure .env is loaded from project root regardless of process cwd.
load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT,
    filename=config.LOG_DIR / "app.log",
    filemode="a",
)
logger = logging.getLogger(__name__)

app = FastAPI(title=config.APP_NAME)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    chapter_id: int | None = None
    mode: str = "generate"
    model: str | None = None
    genre: str | None = None
    workflow_answers: dict | None = None
    style_prompt: str | None = None
    custom_prompt: str | None = None
    chapter_min_words: int | None = None
    chapter_max_words: int | None = None
    analysis_notes: str | None = None
    role_cards: list | None = None
    org_cards: list | None = None
    profession_system: dict | None = None
    foreshadows: list | None = None
    custom_model: dict | None = None
    existing_chapters: list | None = None
    novel_title: str | None = None
    style_strength: str | None = None


class FanqiePublishRequest(BaseModel):
    cdp_url: str
    create_url: str
    chapter_title: str
    chapter_content: str
    selectors: dict | None = None
    dry_run: bool = False
    auto_publish: bool = True
    timeout_ms: int = 45000


class FanqieScheduleRequest(BaseModel):
    cdp_url: str
    create_url: str
    chapter_title: str
    chapter_content: str
    run_at_epoch: int | None = None
    max_retries: int = 2
    retry_delay_sec: int = 120
    selectors: dict | None = None
    timeout_ms: int = 45000


class FanqieCdpProbeRequest(BaseModel):
    cdp_url: str
    timeout_ms: int = 8000


class InMemoryRateLimiter:
    def __init__(self, limit_per_minute: int):
        self.limit_per_minute = limit_per_minute
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.time()
        bucket = self._hits[key]
        window_start = now - 60
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= self.limit_per_minute:
            return False
        bucket.append(now)
        return True


rate_limiter = InMemoryRateLimiter(config.RATE_LIMIT_PER_MINUTE)
generate_semaphore = asyncio.Semaphore(config.MAX_GENERATE_CONCURRENCY)
PUBLISH_TASKS: list[dict] = []
DASHBOARD_STATS = {
    "generated_calls": 0,
    "generated_chapters": 0,
    "published_attempts": 0,
    "published_success": 0,
}
PUBLISH_QUEUE: list[dict] = []


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _api_key_ok(request: Request) -> bool:
    if not config.SERVICE_API_KEY:
        return True
    key = request.headers.get("x-api-key", "").strip()
    return key == config.SERVICE_API_KEY


def extract_title_and_chapters(content: str) -> tuple[str, list[dict]]:
    title_match = re.search(r"《([^》]+)》", content)
    title = title_match.group(1) if title_match else "未命名小说"

    chapter_pattern = re.compile(r"(?m)^(第\s*[一二三四五六七八九十百千万\d]+\s*[章节卷]\s*[^\n]*)")
    matches = list(chapter_pattern.finditer(content))

    chapters = []
    if matches:
        for idx, m in enumerate(matches):
            start = m.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
            body = content[start:end].strip()
            if body:
                chapters.append({"title": m.group(1).strip(), "content": body})

    if not chapters:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content.strip()) if p.strip()]
        if len(paragraphs) >= 2:
            for i, p in enumerate(paragraphs[:10], 1):
                chapters.append({"title": f"第{i}章", "content": p})
        elif content.strip():
            chapters.append({"title": "第1章", "content": content.strip()})

    return title, chapters


def _net_word_count(text: str) -> int:
    # Count net characters excluding whitespace/punctuation/symbols.
    return len(re.sub(r"[\s\W_]+", "", text or "", flags=re.UNICODE))


def _extract_single_continue_chapter(content: str, next_idx: int) -> dict:
    text = (content or "").strip()
    if not text:
        return {"title": f"第{next_idx}章", "content": ""}

    # Prefer explicit chapter heading.
    m = re.search(rf"(?m)^\s*第\s*{next_idx}\s*[章节卷]\s*[^\n]*", text)
    if m:
        title = m.group(0).strip()
        body = text[m.end():].strip()
        return {"title": title or f"第{next_idx}章", "content": body}

    # Fallback: use first line as title only if it looks like a chapter heading.
    first_line, _, rest = text.partition("\n")
    if re.search(r"^\s*第\s*[一二三四五六七八九十百千万\d]+\s*[章节卷]", first_line):
        return {"title": first_line.strip(), "content": rest.strip()}

    # Hard fallback: force correct next-chapter title and keep full body.
    return {"title": f"第{next_idx}章", "content": text}


def _looks_like_outline(chapters: list[dict], min_words: int) -> bool:
    if not chapters:
        return False
    threshold = max(120, int(min_words * 0.25))
    short = 0
    for ch in chapters:
        wc = _net_word_count((ch or {}).get("content", ""))
        if wc < threshold:
            short += 1
    # If most chapters are very short, treat as outline/summary output.
    return len(chapters) >= 4 and short >= max(3, int(len(chapters) * 0.7))


async def _auto_expand_short_chapter(
    model_dict: dict,
    chapter: dict,
    *,
    genre: str | None,
    style_strength: str | None,
    chapter_min_words: int,
    max_rounds: int = 2,
) -> dict:
    cur = {"title": chapter.get("title", "章节"), "content": chapter.get("content", "")}
    target_floor = max(300, int(chapter_min_words * 0.8))
    for _ in range(max_rounds):
        if _net_word_count(cur.get("content", "")) >= target_floor:
            return cur
        expand_input = f"{cur.get('title','章节')}\n\n{cur.get('content','')}"
        expand_prompt = build_expand_prompt(chapter_text=expand_input, genre=genre, style_strength=style_strength)
        expanded = await asyncio.wait_for(
            generate_content(model_dict, expand_prompt),
            timeout=config.REQUEST_TIMEOUT + 10,
        )
        if not expanded:
            return cur
        _, parsed = extract_title_and_chapters(expanded)
        if parsed:
            nxt = parsed[0]
            cur = {"title": nxt.get("title") or cur["title"], "content": clean_chapter_content(nxt.get("content", ""))}
        else:
            cur = {"title": cur["title"], "content": clean_chapter_content(expanded)}
    return cur


async def _execute_publish_job(job: dict) -> dict:
    DASHBOARD_STATS["published_attempts"] += 1
    result = await publish_chapter_via_cdp(
        cdp_url=job["cdp_url"],
        chapter_title=job["chapter_title"],
        chapter_content=job["chapter_content"],
        create_url=job["create_url"],
        selectors=job.get("selectors"),
        dry_run=False,
        auto_publish=True,
        timeout_ms=job.get("timeout_ms", 45000),
    )
    task = {
        "task_id": str(uuid.uuid4()),
        "created_at": datetime.utcnow().isoformat() + "Z",
        "status": "success" if result.success else "failed",
        "title": job["chapter_title"][:60],
        "detail": result.detail,
        "url": result.url,
        "screenshot": result.screenshot,
        "dry_run": False,
    }
    PUBLISH_TASKS.append(task)
    if result.success:
        DASHBOARD_STATS["published_success"] += 1
    return task


async def _publish_queue_worker():
    while True:
        now = int(time.time())
        for job in PUBLISH_QUEUE:
            if job["status"] not in {"queued", "retry_wait"}:
                continue
            if job.get("next_run_at", 0) > now:
                continue
            job["status"] = "running"
            try:
                task = await _execute_publish_job(job)
                if task["status"] == "success":
                    job["status"] = "success"
                    job["last_detail"] = task["detail"]
                else:
                    raise RuntimeError(task.get("detail") or "publish failed")
            except Exception as exc:
                job["attempts"] += 1
                job["last_detail"] = str(exc)
                if job["attempts"] > job["max_retries"]:
                    job["status"] = "failed"
                else:
                    job["status"] = "retry_wait"
                    job["next_run_at"] = int(time.time()) + job["retry_delay_sec"]
        await asyncio.sleep(2)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.time()
    try:
        response = await call_next(request)
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        logger.exception("Unhandled base error rid=%s path=%s: %s", request_id, request.url.path, exc)
        err_text = str(exc).strip() or repr(exc) or exc.__class__.__name__
        response = JSONResponse(status_code=500, content={"success": False, "error": f"internal_error: {err_text}"})
    if response is None:
        logger.error("Null response rid=%s path=%s", request_id, request.url.path)
        response = JSONResponse(status_code=500, content={"success": False, "error": "null_response"})
    response.headers["x-request-id"] = request_id
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["x-frame-options"] = "DENY"
    response.headers["referrer-policy"] = "strict-origin-when-cross-origin"
    elapsed_ms = int((time.time() - start) * 1000)
    logger.info("%s %s -> %s (%sms) rid=%s", request.method, request.url.path, response.status_code, elapsed_ms, request_id)
    return response


@app.on_event("startup")
async def _startup():
    asyncio.create_task(_publish_queue_worker())


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/healthz")
async def healthz():
    return {"success": True, "status": "ok", "env": config.APP_ENV}


@app.get("/readyz")
async def readyz():
    try:
        _ = fetch_free_models()
        return {"success": True, "status": "ready"}
    except Exception as exc:
        logger.exception("Readiness check failed: %s", exc)
        return JSONResponse(status_code=503, content={"success": False, "status": "not_ready", "error": str(exc)})


@app.get("/models")
async def get_models(request: Request):
    if not _api_key_ok(request):
        return JSONResponse(status_code=401, content={"success": False, "error": "unauthorized"})
    try:
        return {"success": True, "models": fetch_free_models()}
    except Exception as exc:
        logger.exception("Failed to fetch models: %s", exc)
        return JSONResponse(status_code=500, content={"success": False, "error": "获取模型列表失败"})


@app.get("/runtime/status")
async def runtime_status(request: Request):
    if not _api_key_ok(request):
        return JSONResponse(status_code=401, content={"success": False, "error": "unauthorized"})
    return {
        "success": True,
        "openrouter_configured": bool((__import__("os").getenv("OPENROUTER_API_KEY") or "").strip()),
        "newapi_configured": bool((__import__("os").getenv("NEWAPI_API_KEY") or "").strip()),
        "newapi_base_configured": bool((__import__("os").getenv("NEWAPI_BASE_URL") or "").strip()),
        "google_configured": bool((__import__("os").getenv("GOOGLE_API_KEY") or "").strip()),
        "anthropic_configured": bool((__import__("os").getenv("ANTHROPIC_API_KEY") or "").strip()),
    }


@app.get("/dashboard/summary")
async def dashboard_summary(request: Request):
    if not _api_key_ok(request):
        return JSONResponse(status_code=401, content={"success": False, "error": "unauthorized"})
    recent = sorted(PUBLISH_TASKS, key=lambda x: x["created_at"], reverse=True)[:10]
    queue_recent = sorted(PUBLISH_QUEUE, key=lambda x: x["created_at"], reverse=True)[:20]
    return {"success": True, "stats": DASHBOARD_STATS, "recent_publish_tasks": recent, "publish_queue": queue_recent}


@app.get("/workflow/questions")
async def workflow_questions():
    return {"success": True, "questions": get_default_workflow_questions()}


@app.get("/models/health")
async def model_health(request: Request):
    if not _api_key_ok(request):
        return JSONResponse(status_code=401, content={"success": False, "error": "unauthorized"})

    ip = _client_ip(request)
    if not rate_limiter.allow(f"health:{ip}"):
        return JSONResponse(status_code=429, content={"success": False, "error": "rate limit exceeded"})

    try:
        models = fetch_free_models()
        results = []
        for model in models:
            try:
                ok, detail = await asyncio.wait_for(check_model_connection(model), timeout=config.MODEL_HEALTH_TIMEOUT)
            except Exception as inner:
                ok, detail = False, str(inner)
            results.append({"uid": model.get("uid"), "provider": model.get("provider"), "id": model.get("id"), "ok": ok, "detail": detail})
        return {"success": True, "results": results}
    except Exception as exc:
        logger.exception("Model health check failed: %s", exc)
        return JSONResponse(status_code=500, content={"success": False, "error": f"模型检查失败: {exc}"})


@app.post("/publish/fanqie")
async def publish_fanqie(request: Request, body: FanqiePublishRequest):
    if not _api_key_ok(request):
        return JSONResponse(status_code=401, content={"success": False, "error": "unauthorized"})
    ip = _client_ip(request)
    if not rate_limiter.allow(f"publish:{ip}"):
        return JSONResponse(status_code=429, content={"success": False, "error": "rate limit exceeded"})

    DASHBOARD_STATS["published_attempts"] += 1
    task = {
        "task_id": str(uuid.uuid4()),
        "created_at": datetime.utcnow().isoformat() + "Z",
        "status": "running",
        "title": body.chapter_title[:60],
        "dry_run": body.dry_run,
    }
    PUBLISH_TASKS.append(task)
    try:
        result = await publish_chapter_via_cdp(
            cdp_url=body.cdp_url,
            chapter_title=body.chapter_title,
            chapter_content=body.chapter_content,
            create_url=body.create_url,
            selectors=body.selectors,
            dry_run=body.dry_run,
            auto_publish=body.auto_publish,
            timeout_ms=body.timeout_ms,
        )
        task["status"] = "success" if result.success else "failed"
        task["detail"] = result.detail
        task["url"] = result.url
        task["screenshot"] = result.screenshot
        if result.success:
            DASHBOARD_STATS["published_success"] += 1
        return {"success": result.success, "task": task}
    except Exception as exc:
        task["status"] = "failed"
        task["detail"] = str(exc)
        return JSONResponse(status_code=500, content={"success": False, "error": f"发布失败: {exc}", "task": task})


@app.post("/publish/fanqie/schedule")
async def publish_fanqie_schedule(request: Request, body: FanqieScheduleRequest):
    if not _api_key_ok(request):
        return JSONResponse(status_code=401, content={"success": False, "error": "unauthorized"})
    ip = _client_ip(request)
    if not rate_limiter.allow(f"publish_sched:{ip}"):
        return JSONResponse(status_code=429, content={"success": False, "error": "rate limit exceeded"})

    now = int(time.time())
    run_at = body.run_at_epoch if body.run_at_epoch and body.run_at_epoch > now else now
    job = {
        "job_id": str(uuid.uuid4()),
        "created_at": datetime.utcnow().isoformat() + "Z",
        "cdp_url": body.cdp_url,
        "create_url": body.create_url,
        "chapter_title": body.chapter_title,
        "chapter_content": body.chapter_content,
        "selectors": body.selectors,
        "timeout_ms": body.timeout_ms,
        "status": "queued",
        "attempts": 0,
        "max_retries": max(0, body.max_retries),
        "retry_delay_sec": max(10, body.retry_delay_sec),
        "next_run_at": run_at,
        "last_detail": "",
    }
    PUBLISH_QUEUE.append(job)
    return {"success": True, "job": job}


@app.get("/publish/fanqie/queue")
async def publish_fanqie_queue(request: Request):
    if not _api_key_ok(request):
        return JSONResponse(status_code=401, content={"success": False, "error": "unauthorized"})
    return {"success": True, "queue": sorted(PUBLISH_QUEUE, key=lambda x: x["created_at"], reverse=True)}


@app.post("/publish/fanqie/probe")
async def publish_fanqie_probe(request: Request, body: FanqieCdpProbeRequest):
    if not _api_key_ok(request):
        return JSONResponse(status_code=401, content={"success": False, "error": "unauthorized"})
    ip = _client_ip(request)
    if not rate_limiter.allow(f"publish_probe:{ip}"):
        return JSONResponse(status_code=429, content={"success": False, "error": "rate limit exceeded"})
    try:
        result = await probe_cdp_endpoint(cdp_url=body.cdp_url, timeout_ms=body.timeout_ms)
        return {
            "success": result.success,
            "detail": result.detail,
            "websocket_endpoint": result.websocket_endpoint,
            "pages": result.pages or [],
        }
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "error": f"CDP检测失败: {exc}"})


@app.post("/generate")
async def generate(request: Request, body: GenerateRequest):
    if not _api_key_ok(request):
        return JSONResponse(status_code=401, content={"success": False, "error": "unauthorized"})

    ip = _client_ip(request)
    if not rate_limiter.allow(f"gen:{ip}"):
        return JSONResponse(status_code=429, content={"success": False, "error": "rate limit exceeded"})

    prompt_text = (body.prompt or "").strip()
    if len(prompt_text) < config.MIN_PROMPT_LENGTH:
        return JSONResponse(status_code=400, content={"success": False, "error": f"提示词太短，至少 {config.MIN_PROMPT_LENGTH} 字"})
    if len(prompt_text) > config.MAX_PROMPT_LENGTH:
        return JSONResponse(status_code=400, content={"success": False, "error": f"提示词太长，请控制在 {config.MAX_PROMPT_LENGTH} 字以内"})

    try:
        if body.custom_model:
            provider = (body.custom_model.get("provider") or "").strip()
            model_id = (body.custom_model.get("id") or "").strip()
            if provider not in {"openrouter", "newapi", "google", "anthropic"} or not model_id:
                return JSONResponse(status_code=400, content={"success": False, "error": "自定义模型参数无效"})
            model_dict = {
                "provider": provider,
                "id": model_id,
                "api_base": (body.custom_model.get("api_base") or "").strip(),
                "uid": f"custom::{provider}::{model_id}",
            }
        else:
            model_dict = resolve_model(body.model)
        if body.mode == "expand":
            llm_prompt = build_expand_prompt(chapter_text=prompt_text, genre=body.genre, style_strength=body.style_strength)
        elif body.mode == "pad":
            lines = prompt_text.splitlines()
            chapter_title = lines[0].strip() if lines else "章节"
            chapter_body = "\n".join(lines[1:]).strip() if len(lines) > 1 else prompt_text
            llm_prompt = build_pad_prompt(
                chapter_title=chapter_title,
                chapter_content=chapter_body,
                target_min_words=body.chapter_min_words or 3000,
                target_max_words=body.chapter_max_words or 5000,
                genre=body.genre,
                style_prompt=body.style_prompt,
                style_strength=body.style_strength,
            )
        elif body.mode == "continue":
            existing = body.existing_chapters or []
            next_idx = len(existing) + 1 if existing else 1
            existing_text = "\n\n".join(
                [f"{c.get('title','')}\\n{c.get('content','')}" for c in existing if isinstance(c, dict)]
            )
            llm_prompt = build_continue_prompt(
                novel_title=body.novel_title or "未命名小说",
                existing_chapters_text=existing_text[-20000:],
                next_chapter_index=next_idx,
                genre=body.genre,
                style_prompt=body.style_prompt,
                chapter_min_words=body.chapter_min_words,
                chapter_max_words=body.chapter_max_words,
                style_strength=body.style_strength,
            )
        elif body.mode == "inspiration":
            llm_prompt = build_inspiration_prompt(
                topic=prompt_text,
                genre=body.genre,
                style_prompt=body.style_prompt,
                style_strength=body.style_strength,
            )
        elif body.mode == "rewrite":
            llm_prompt = build_rewrite_prompt(
                source_text=prompt_text,
                analysis_notes=(body.analysis_notes or "请提升节奏与可读性"),
                genre=body.genre,
                style_prompt=body.style_prompt,
                style_strength=body.style_strength,
            )
        else:
            llm_prompt = build_generate_prompt(
                user_prompt=prompt_text,
                genre=body.genre,
                workflow_answers=body.workflow_answers,
                style_prompt=body.style_prompt,
                custom_prompt=body.custom_prompt,
                chapter_min_words=body.chapter_min_words,
                chapter_max_words=body.chapter_max_words,
                role_cards=body.role_cards,
                org_cards=body.org_cards,
                profession_system=body.profession_system,
                foreshadows=body.foreshadows,
                style_strength=body.style_strength,
            )

        async with generate_semaphore:
            content = await asyncio.wait_for(generate_content(model_dict, llm_prompt), timeout=config.REQUEST_TIMEOUT + 10)

        if not content:
            return JSONResponse(
                status_code=502,
                content={
                    "success": False,
                    "error": f"上游模型未返回有效内容 provider={model_dict.get('provider')} model={model_dict.get('id')}，请切换模型后重试",
                },
            )

        if body.mode == "inspiration":
            return {"success": True, "title": "灵感模式结果", "chapters": [{"title": "灵感清单", "content": content}]}

        if body.mode == "continue":
            existing = body.existing_chapters or []
            next_idx = len(existing) + 1 if existing else 1
            one = _extract_single_continue_chapter(content, next_idx)
            one = {"title": one["title"], "content": clean_chapter_content(one.get("content", ""))}
            min_words = int(body.chapter_min_words or 3000)
            # Too short continue outputs usually indicate provider formatting drift; fail fast instead of polluting chapter list.
            if _net_word_count(one["content"]) < max(200, int(min_words * 0.25)):
                return JSONResponse(status_code=500, content={"success": False, "error": "续写结果过短或格式异常，请重试或切换模型"})
            chapters = [one]
            title = body.novel_title or "未命名小说"
        else:
            title, chapters = extract_title_and_chapters(content)
            if not chapters:
                return JSONResponse(status_code=500, content={"success": False, "error": "内容解析失败"})

        chapters = ensure_unique_titles(chapters)
        chapters = [{"title": c["title"], "content": clean_chapter_content(c.get("content", ""))} for c in chapters]

        # Guard against "outline-only" responses (many chapters but each only one sentence).
        if body.mode == "generate":
            min_words = int(body.chapter_min_words or 3000)
            if _looks_like_outline(chapters, min_words):
                fallback_prompt = build_continue_prompt(
                    novel_title=title or "未命名小说",
                    existing_chapters_text="",
                    next_chapter_index=1,
                    genre=body.genre,
                    style_prompt=body.style_prompt,
                    chapter_min_words=body.chapter_min_words,
                    chapter_max_words=body.chapter_max_words,
                    style_strength=body.style_strength,
                )
                fallback_content = await asyncio.wait_for(
                    generate_content(model_dict, fallback_prompt),
                    timeout=config.REQUEST_TIMEOUT + 10,
                )
                if fallback_content:
                    one = _extract_single_continue_chapter(fallback_content, 1)
                    one = {"title": one["title"], "content": clean_chapter_content(one.get("content", ""))}
                    if _net_word_count(one["content"]) >= max(200, int(min_words * 0.25)):
                        chapters = [one]
                    else:
                        return JSONResponse(
                            status_code=422,
                            content={"success": False, "error": "模型输出为章节摘要，未达到正文长度。请切换更大上下文模型，或先生成少量章节再批量续写。"},
                        )
                else:
                    return JSONResponse(
                        status_code=422,
                        content={"success": False, "error": "模型输出为章节摘要，未达到正文长度。请切换更大上下文模型，或先生成少量章节再批量续写。"},
                    )

        # Auto-expand short chapters to reduce one-line outputs.
        min_words = int(body.chapter_min_words or 3000)
        normalized = []
        for ch in chapters:
            ch2 = await _auto_expand_short_chapter(
                model_dict,
                ch,
                genre=body.genre,
                style_strength=body.style_strength,
                chapter_min_words=min_words,
                max_rounds=2,
            )
            normalized.append({"title": ch2.get("title", ch.get("title", "章节")), "content": clean_chapter_content(ch2.get("content", ""))})
        chapters = normalized

        # Final guard: if still too short, return explicit error instead of weak content.
        too_short = [c for c in chapters if _net_word_count(c.get("content", "")) < max(300, int(min_words * 0.5))]
        if too_short and body.mode in {"generate", "continue", "expand"}:
            return JSONResponse(
                status_code=422,
                content={"success": False, "error": "模型多次生成仍偏短。建议换模型/提高上下文容量后重试。"},
            )

        quality_report = audit_chapters(chapters)

        DASHBOARD_STATS["generated_calls"] += 1
        DASHBOARD_STATS["generated_chapters"] += len(chapters)

        return {"success": True, "title": title, "chapters": chapters, "quality_report": quality_report}
    except asyncio.TimeoutError:
        return JSONResponse(status_code=504, content={"success": False, "error": "上游模型响应超时"})
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"success": False, "error": f"上游模型错误: {exc}"})
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        logger.exception("Generation error: %s", exc)
        err_text = str(exc).strip() or repr(exc) or exc.__class__.__name__
        return JSONResponse(status_code=500, content={"success": False, "error": f"生成异常: {err_text}"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config.APP_HOST, port=config.APP_PORT)

