from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SENSITIVE_PATH = Path('references') / 'sensitive_words.txt'
SENSITIVE_SUGGESTIONS = {
    "暴恐": "极端冲突",
    "极端组织": "极端团体",
    "毒品交易": "违禁交易",
    "仇恨言论": "攻击性言论",
    "未成年人色情": "未成年人不当内容",
    "血腥虐杀": "激烈冲突",
    "恐怖袭击": "重大袭击",
    "教唆自杀": "诱导伤害",
    "洗钱": "非法资金流转",
    "非法集资": "违规募资",
}


@dataclass
class ChapterAudit:
    title: str
    word_count_net: int
    sensitive_hits: list[str]
    sensitive_suggestions: list[dict]
    readability_score: int
    coherence_score: int
    hook_ok: bool
    hook_reason: str


def load_sensitive_words() -> list[str]:
    if not SENSITIVE_PATH.exists():
        return []
    words = []
    for line in SENSITIVE_PATH.read_text(encoding='utf-8').splitlines():
        x = line.strip()
        if x and not x.startswith('#'):
            words.append(x)
    return words


def count_net_words(text: str) -> int:
    # Keep Chinese chars, letters, digits; drop whitespace/punct/symbols.
    filtered = re.findall(r'[\u4e00-\u9fffA-Za-z0-9]', text or '')
    return len(filtered)


def detect_sensitive(text: str, words: list[str]) -> list[str]:
    hits = []
    for w in words:
        if w in text:
            hits.append(w)
    return hits


def readability_score(text: str) -> int:
    # Heuristic: reward punctuation rhythm and paragraphing, penalize overly long sentences.
    if not text.strip():
        return 0
    sentences = re.split(r'[。！？!?]', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    avg_len = sum(len(s) for s in sentences) / max(1, len(sentences))
    paras = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    score = 80
    if avg_len > 70:
        score -= 20
    elif avg_len > 50:
        score -= 10
    if len(paras) < 3:
        score -= 10
    if re.search(r'(然后|接着|随后|之后)\1{0,}', text):
        score -= 5
    return max(0, min(100, int(score)))


def coherence_score(current: str, prev: str | None) -> int:
    if not current.strip():
        return 0
    if not prev:
        return 85
    # weak heuristic based on recurring entities and overlap
    cur_tokens = set(re.findall(r'[\u4e00-\u9fff]{2,}', current))
    prev_tokens = set(re.findall(r'[\u4e00-\u9fff]{2,}', prev))
    overlap = len(cur_tokens & prev_tokens)
    if overlap >= 20:
        return 90
    if overlap >= 10:
        return 82
    if overlap >= 5:
        return 74
    return 62


def check_hook(text: str) -> tuple[bool, str]:
    tail = text.strip()[-120:]
    if not tail:
        return False, 'empty_tail'
    if re.search(r'(下章|下一章|未完待续|悬念|转折|真相|秘密|危机)', tail):
        return True, 'keyword_hook'
    if re.search(r'[？?！!…]$', tail):
        return True, 'punctuation_hook'
    return False, 'no_hook_signal'


def clean_chapter_content(text: str) -> str:
    """Remove common AI-meta ending lines that read like commentary instead of story."""
    s = (text or "").strip()
    if not s:
        return s

    # Remove explicit meta-summary endings.
    meta_tail_patterns = [
        r"(本章(到此|完|结束).{0,40})$",
        r"(以上(就是|为).{0,40})$",
        r"(结局留下悬念.{0,120})$",
        r"(暗示着.{0,120}转折点.{0,80})$",
        r"(为后续剧情(埋下|留下).{0,80})$",
    ]
    for p in meta_tail_patterns:
        s = re.sub(p, "", s, flags=re.IGNORECASE)

    # Trim dangling separators/newlines.
    s = re.sub(r"[\n\s]+$", "", s)
    return s


def ensure_unique_titles(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, int] = {}
    out = []
    for ch in chapters:
        title = (ch.get('title') or '').strip() or '未命名章节'
        n = seen.get(title, 0)
        seen[title] = n + 1
        if n > 0:
            title = f"{title}（续{n+1}）"
        out.append({'title': title, 'content': ch.get('content', '')})
    return out


def audit_chapters(chapters: list[dict[str, Any]]) -> dict[str, Any]:
    words = load_sensitive_words()
    audits: list[dict[str, Any]] = []
    total_sensitive = 0
    prev = None
    for ch in chapters:
        content = ch.get('content', '') or ''
        hits = detect_sensitive(content, words)
        sugg = [{"word": w, "replace_with": SENSITIVE_SUGGESTIONS.get(w, "合规替代表述")} for w in hits]
        total_sensitive += len(hits)
        hook_ok, hook_reason = check_hook(content)
        row = ChapterAudit(
            title=ch.get('title', ''),
            word_count_net=count_net_words(content),
            sensitive_hits=hits,
            sensitive_suggestions=sugg,
            readability_score=readability_score(content),
            coherence_score=coherence_score(content, prev),
            hook_ok=hook_ok,
            hook_reason=hook_reason,
        )
        audits.append(row.__dict__)
        prev = content

    avg_read = int(sum(x['readability_score'] for x in audits) / max(1, len(audits)))
    avg_coh = int(sum(x['coherence_score'] for x in audits) / max(1, len(audits)))
    hook_rate = round(sum(1 for x in audits if x['hook_ok']) / max(1, len(audits)), 2)
    return {
        'summary': {
            'chapter_count': len(audits),
            'avg_readability': avg_read,
            'avg_coherence': avg_coh,
            'hook_rate': hook_rate,
            'sensitive_hit_count': total_sensitive,
            'sensitive_word_count': len(words),
        },
        'chapters': audits,
    }
