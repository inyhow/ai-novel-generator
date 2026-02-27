from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright


@dataclass
class FanqiePublishResult:
    success: bool
    detail: str
    url: str = ""
    screenshot: str = ""


@dataclass
class FanqieCdpProbeResult:
    success: bool
    detail: str
    websocket_endpoint: str = ""
    pages: list[str] | None = None


def _pick_selector(selectors: dict[str, Any] | None, key: str, fallback: list[str]) -> list[str]:
    if not selectors:
        return fallback
    value = selectors.get(key)
    if not value:
        return fallback
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [x for x in value if isinstance(x, str) and x.strip()]
    return fallback


async def _first_visible(page, candidates: list[str]):
    for sel in candidates:
        locator = page.locator(sel).first
        try:
            if await locator.is_visible(timeout=1200):
                return locator, sel
        except Exception:
            continue
    return None, ""


async def publish_chapter_via_cdp(
    *,
    cdp_url: str,
    chapter_title: str,
    chapter_content: str,
    create_url: str,
    selectors: dict[str, Any] | None = None,
    dry_run: bool = False,
    auto_publish: bool = True,
    timeout_ms: int = 45000,
) -> FanqiePublishResult:
    title_selectors = _pick_selector(
        selectors,
        "title",
        [
            'input[placeholder*="标题"]',
            'textarea[placeholder*="标题"]',
            'input[type="text"]',
        ],
    )
    content_selectors = _pick_selector(
        selectors,
        "content",
        [
            'div[contenteditable="true"]',
            'textarea[placeholder*="正文"]',
            'textarea',
        ],
    )
    publish_selectors = _pick_selector(
        selectors,
        "publish",
        [
            'button:has-text("发布")',
            'button:has-text("保存并发布")',
            'button:has-text("确认发布")',
            'button:has-text("提交")',
        ],
    )

    screenshot_file = Path("logs") / f"fanqie_publish_{int(asyncio.get_event_loop().time())}.png"

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(cdp_url, timeout=timeout_ms)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto(create_url, wait_until="domcontentloaded", timeout=timeout_ms)

            if dry_run:
                await page.screenshot(path=str(screenshot_file), full_page=True)
                return FanqiePublishResult(True, "dry_run_ok", page.url, str(screenshot_file))

            title_locator, title_sel = await _first_visible(page, title_selectors)
            if not title_locator:
                return FanqiePublishResult(False, f"title_not_found: {title_selectors}", page.url)
            tag = await title_locator.evaluate("el => el.tagName.toLowerCase()")
            if tag in {"input", "textarea"}:
                await title_locator.fill(chapter_title)
            else:
                await title_locator.click()
                await page.keyboard.type(chapter_title)

            content_locator, content_sel = await _first_visible(page, content_selectors)
            if not content_locator:
                return FanqiePublishResult(False, f"content_not_found: {content_selectors}", page.url)
            ctag = await content_locator.evaluate("el => el.tagName.toLowerCase()")
            if ctag == "textarea":
                await content_locator.fill(chapter_content)
            else:
                await content_locator.click()
                await page.keyboard.press("Control+A")
                await page.keyboard.type(chapter_content)

            detail = f"filled(title={title_sel}, content={content_sel})"
            if auto_publish:
                publish_locator, publish_sel = await _first_visible(page, publish_selectors)
                if not publish_locator:
                    await page.screenshot(path=str(screenshot_file), full_page=True)
                    return FanqiePublishResult(False, f"publish_button_not_found: {publish_selectors}", page.url, str(screenshot_file))
                await publish_locator.click()
                detail += f", clicked({publish_sel})"

            await asyncio.sleep(1)
            await page.screenshot(path=str(screenshot_file), full_page=True)
            return FanqiePublishResult(True, detail, page.url, str(screenshot_file))
        finally:
            await page.close()


async def probe_cdp_endpoint(*, cdp_url: str, timeout_ms: int = 8000) -> FanqieCdpProbeResult:
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(cdp_url, timeout=timeout_ms)
        pages: list[str] = []
        for ctx in browser.contexts:
            for pg in ctx.pages:
                try:
                    pages.append(pg.url or "about:blank")
                except Exception:
                    pages.append("unknown")
        return FanqieCdpProbeResult(
            success=True,
            detail=f"cdp_connected contexts={len(browser.contexts)} pages={len(pages)}",
            websocket_endpoint=cdp_url,
            pages=pages[:20],
        )
