from typing import Dict, Optional

DEFAULT_WORKFLOW_QUESTIONS = [
    {
        "id": "genre",
        "question": "题材与风格是什么？",
        "hint": "如：玄幻升级流、都市悬疑、现实言情"
    },
    {
        "id": "protagonist",
        "question": "主角是谁？核心身份和欲望是什么？",
        "hint": "如：落魄调查记者，想洗清冤案"
    },
    {
        "id": "world_conflict",
        "question": "世界设定与主冲突是什么？",
        "hint": "如：近未来城市，AI监管与地下组织对抗"
    },
    {
        "id": "tone_pace",
        "question": "叙事语气和节奏偏好？",
        "hint": "如：冷峻克制、快节奏、反转密集"
    },
    {
        "id": "length_target",
        "question": "篇幅目标？",
        "hint": "章数范围（10-50章）与单章字数范围（3000-5000字）"
    }
]


def get_default_workflow_questions():
    return DEFAULT_WORKFLOW_QUESTIONS


def build_generate_prompt(
    user_prompt: str,
    genre: Optional[str] = None,
    workflow_answers: Optional[Dict[str, str]] = None,
    style_prompt: Optional[str] = None,
    custom_prompt: Optional[str] = None,
    chapter_min_words: Optional[int] = None,
    chapter_max_words: Optional[int] = None,
    role_cards: Optional[list] = None,
    org_cards: Optional[list] = None,
    profession_system: Optional[Dict[str, str]] = None,
    foreshadows: Optional[list] = None,
    style_strength: Optional[str] = None,
) -> str:
    workflow_answers = workflow_answers or {}

    style_block = ""
    if genre:
        style_block = f"\n- 补充风格：{genre}\n"

    qna_lines = []
    for item in DEFAULT_WORKFLOW_QUESTIONS:
        key = item["id"]
        answer = (workflow_answers.get(key) or "").strip()
        if answer:
            qna_lines.append(f"- {item['question']} {answer}")
    qna_block = "\n".join(qna_lines) if qna_lines else "- 未提供完整5问信息，请根据用户提示合理补全。"
    length_target_answer = (workflow_answers.get("length_target") or "").strip()
    chapter_rule = "默认先输出1-3章完整正文，并给出后续章节规划；若用户明确给出章数目标且模型容量允许，则按用户目标执行。"
    if length_target_answer:
        chapter_rule = f"按用户篇幅目标执行：{length_target_answer}。若模型容量不足，优先保证前1-3章为完整正文，其余给章节规划。"

    style_extra = f"- 自定义写作风格：{style_prompt}\n" if style_prompt else ""
    style_strength_line = f"- 风格锁定强度：{style_strength or 'medium'}\n"
    prompt_extra = f"- Prompt工坊附加要求：{custom_prompt}\n" if custom_prompt else ""
    min_words = chapter_min_words or 3000
    max_words = chapter_max_words or 5000
    role_cards = role_cards or []
    org_cards = org_cards or []
    foreshadows = foreshadows or []
    profession_system = profession_system or {}

    extra_context_lines = []
    if profession_system:
        extra_context_lines.append(f"- 职业/等级体系：{profession_system}")
    if role_cards:
        extra_context_lines.append(f"- 角色卡：{role_cards}")
    if org_cards:
        extra_context_lines.append(f"- 组织卡：{org_cards}")
    if foreshadows:
        extra_context_lines.append(f"- 伏笔清单：{foreshadows}")
    extra_context = "\n".join(extra_context_lines) if extra_context_lines else "- 无额外世界观结构数据"

    return f"""你是专业中文长篇小说创作助手。请严格执行以下工作流与输出规范。

【输入信息】
- 用户核心需求：{user_prompt}
{style_block}
{style_extra}{style_strength_line}{prompt_extra}
【5问确认结果】
{qna_block}
【扩展创作上下文】
{extra_context}

【创作流程】
1. 先构建总体大纲：世界观、主线冲突、角色弧线、阶段性目标。
2. 再生成章节内容，必须前后因果清晰，人物动机稳定。
3. 每章结尾设置悬念钩子，推动读者继续阅读。
4. 完成后做一次“去AI痕迹”润色：避免模板化句式、避免重复口头禅、减少机械总结句。
5. 结尾只保留剧情内钩子，不要出现“本章总结/作者点评/结局留下悬念”等元叙述句。

【硬性约束】
1. {chapter_rule}
2. 单章目标字数{min_words}-{max_words}字（若受输出长度限制，可先输出前几章并保证章结构完整）。
3. 文风自然流畅，避免生硬解释。
4. 每章需有章节标题，且标题风格统一但不重复。
5. 严禁输出创作说明、提示词解释或系统注释。

【输出格式】
- 标题：用《》包裹
- 故事简介：150-300字
- 章节正文：按“第X章 章节名”组织，优先保证前1-3章为完整正文
- 后续规划：当未输出全部目标章数时，补充“后续章节规划（第X章-第Y章）”的简要提纲
"""


def build_expand_prompt(chapter_text: str, genre: Optional[str] = None, style_strength: Optional[str] = None) -> str:
    style_line = f"风格参考：{genre}\n" if genre else ""
    strength_line = f"风格锁定强度：{style_strength or 'medium'}\n"
    return f"""请对下面章节进行深度扩写与润色。

要求：
1. 保留原有情节、人物关系和关键事件。
2. 扩写到原文约2-3倍，补充场景、动作、对话、心理细节。
3. 结尾补一个自然悬念钩子。
4. 进行去AI痕迹润色：避免重复句式、避免总结腔、语言更像真人小说作者。
5. 不要输出任何解释，直接输出扩写后的章节正文。

{style_line}{strength_line}原章节：
{chapter_text}
"""


def build_inspiration_prompt(
    topic: str,
    genre: Optional[str] = None,
    style_prompt: Optional[str] = None,
    style_strength: Optional[str] = None,
) -> str:
    return f"""你是网文编辑，请围绕用户给定主题生成创作灵感。

主题：{topic}
题材：{genre or "不限"}
风格偏好：{style_prompt or "不限"}
风格锁定强度：{style_strength or "medium"}

请输出：
1. 10个高概念故事点子（每个2-3句）
2. 3个可做长篇的主线方案（含冲突、成长、商业卖点）
3. 5个高点击标题方向
仅输出结果，不要解释。"""


def build_rewrite_prompt(
    source_text: str,
    analysis_notes: str,
    genre: Optional[str] = None,
    style_prompt: Optional[str] = None,
    style_strength: Optional[str] = None,
) -> str:
    return f"""请根据分析建议重写以下小说内容。

分析建议：
{analysis_notes}

风格要求：{style_prompt or "自然流畅"}；题材参考：{genre or "原文题材"}；风格锁定强度：{style_strength or "medium"}。

重写要求：
1. 保留核心剧情事实，不跑题。
2. 强化冲突与悬念，减少重复表达。
3. 语言更口语化、更有人味，去除AI模板腔。
4. 章节结构清晰，结尾给下一步钩子。

原文：
{source_text}
"""


def build_continue_prompt(
    novel_title: str,
    existing_chapters_text: str,
    next_chapter_index: int,
    genre: Optional[str] = None,
    style_prompt: Optional[str] = None,
    style_strength: Optional[str] = None,
    chapter_min_words: Optional[int] = None,
    chapter_max_words: Optional[int] = None,
) -> str:
    min_words = chapter_min_words or 3000
    max_words = chapter_max_words or 5000
    return f"""请基于已生成小说内容，继续创作下一章。

小说标题：{novel_title or "未命名小说"}
题材参考：{genre or "沿用前文"}
风格要求：{style_prompt or "沿用前文"}
风格锁定强度：{style_strength or "medium"}
目标章节：第{next_chapter_index}章

硬性要求：
1. 只输出“下一章”内容，不要重写前文。
2. 与现有剧情严格衔接，保持人物设定和世界观一致。
3. 字数目标{min_words}-{max_words}。
4. 章节结尾必须有悬念钩子。
5. 输出格式必须是：
第{next_chapter_index}章 章节标题
[章节正文]

现有章节摘要/正文：
{existing_chapters_text}
"""


def build_pad_prompt(
    chapter_title: str,
    chapter_content: str,
    target_min_words: int,
    target_max_words: int,
    genre: Optional[str] = None,
    style_prompt: Optional[str] = None,
    style_strength: Optional[str] = None,
) -> str:
    return f"""请在不改变原剧情事实的前提下，扩写当前章节至目标字数区间。

章节标题：{chapter_title}
题材参考：{genre or "沿用原文"}
风格要求：{style_prompt or "沿用原文"}
风格锁定强度：{style_strength or "medium"}
目标字数：{target_min_words}-{target_max_words}

要求：
1. 保留原有事件顺序与人物关系。
2. 通过场景细节、动作、对话、心理描写扩写，不要灌水。
3. 语言自然，去除AI模板感。
4. 结尾保留或增强悬念钩子。
5. 只输出扩写后的章节正文（包含章节标题）。

原章节：
{chapter_title}
{chapter_content}
"""
