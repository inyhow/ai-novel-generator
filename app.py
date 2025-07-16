from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
from pathlib import Path
from utils.model_fetcher import get_llama_model, fetch_free_models
from utils.openrouter_api import generate_content
import re
import logging
import config

# 配置日志
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT,
    filename=config.LOG_DIR / 'app.log',
    filemode='a'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 设置模板目录
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

class GenerateRequest(BaseModel):
    prompt: str
    chapter_id: int = None
    mode: str = "generate"
    model: str = None
    genre: str = None

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

def extract_title_and_chapters(content: str) -> tuple:
    """
    改进的章节提取函数，支持多种格式
    """
    # 尝试从内容中提取标题
    title_match = re.search(r"[《【「](.*?)[》】」]", content)
    title = title_match.group(1) if title_match else "无标题"
    
    # 分割章节
    chapters = []
    
    # 更强大的章节匹配模式，支持多种格式
    chapter_patterns = [
        r'第[一二三四五六七八九十百千万\d]+章[^\n]*',  # 第一章 标题
        r'第[一二三四五六七八九十百千万\d]+节[^\n]*',  # 第一节 标题
        r'Chapter\s*\d+[^\n]*',                      # Chapter 1 标题
        r'\d+\.\s*[^\n]*',                          # 1. 标题
        r'[一二三四五六七八九十]+、[^\n]*'              # 一、标题
    ]
    
    # 合并所有模式
    combined_pattern = '|'.join(f'({pattern})' for pattern in chapter_patterns)
    chapter_regex = re.compile(combined_pattern, re.IGNORECASE | re.MULTILINE)
    
    # 查找所有章节标题的位置
    matches = list(chapter_regex.finditer(content))
    
    if matches:
        for i, match in enumerate(matches):
            chapter_title = match.group().strip()
            
            # 获取章节内容的开始和结束位置
            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            
            # 提取章节内容
            chapter_content = content[start_pos:end_pos].strip()
            
            # 清理内容，移除多余的空行
            chapter_content = re.sub(r'\n\s*\n\s*\n', '\n\n', chapter_content)
            
            if chapter_content:
                chapters.append({
                    "title": chapter_title,
                    "content": chapter_content
                })
    
    # 如果没有找到章节，尝试按段落分割
    if not chapters:
        # 按双换行符分割段落
        paragraphs = re.split(r'\n\s*\n', content.strip())
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        # 如果有多个段落，尝试创建章节
        if len(paragraphs) > 1:
            for i, paragraph in enumerate(paragraphs[:10], 1):  # 最多10章
                if len(paragraph) > 50:  # 只有足够长的段落才作为章节
                    chapters.append({
                        "title": f"第{['一','二','三','四','五','六','七','八','九','十'][i-1]}章",
                        "content": paragraph
                    })
        else:
            # 如果只有一个段落，作为单章节
            chapters.append({
                "title": "第一章",
                "content": content.strip()
            })
    
    # 确保至少有一个章节
    if not chapters and content.strip():
        chapters.append({
            "title": "第一章",
            "content": content.strip()
        })
    
    return title, chapters

@app.get("/models")
async def get_models():
    """获取可用的模型列表"""
    try:
        models = fetch_free_models()
        return {"success": True, "models": models}
    except Exception as e:
        logging.error(f"获取模型列表失败: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "获取模型列表失败"}
        )

@app.post("/generate")
async def generate(request: GenerateRequest):
    try:
        # 输入验证
        if not request.prompt or len(request.prompt.strip()) < config.MIN_PROMPT_LENGTH:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": f"提示词太短，请至少输入{config.MIN_PROMPT_LENGTH}个字符"}
            )
        
        if len(request.prompt) > config.MAX_PROMPT_LENGTH:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": f"提示词太长，请控制在{config.MAX_PROMPT_LENGTH}字符以内"}
            )
        
        # 记录请求
        logging.info(f"收到生成请求: 模式={request.mode}, 提示词长度={len(request.prompt)}, 模型={request.model or 'default'}, 风格={request.genre or 'default'}")
        
        # 强制使用 deepseek-chat-v3-0324 模型
        model_dict = {
            'id': 'deepseek/deepseek-chat-v3-0324:free',
            'name': 'deepseek-chat-v3-0324',
            'description': '强大的免费大型语言模型，适合生成创意内容和小说',
            'context_length': 4096
        }
        
        # 根据小说风格定制提示词
        genre_prompts = {
            "英雄史诗": "英雄主义，冒险旅程，战斗，魔法，史诗般的场景和壮丽的景观",
            "现代都市": "当代城市生活，职场关系，爱情故事，社会问题，现代人的挑战",
            "科幻太空": "未来科技，太空旅行，外星生命，人工智能，科学突破，未来社会",
            "奇幻冒险": "魔法世界，神秘生物，冒险旅程，古老预言，神秘力量",
            "悬疑推理": "谜题，犯罪，调查，心理分析，线索和证据，惊人的转折",
            "青春校园": "青少年生活，校园关系，成长经历，友情与爱情，自我发现"
        }
        
        genre_prompt = ""
        if request.genre and request.genre in genre_prompts:
            genre_prompt = f"风格要素包括：{genre_prompts[request.genre]}。"
        
        if request.mode == "expand":
            prompt = f"""请扩写以下章节内容，要求：
            1. 保持原有的故事情节和人物设定
            2. 添加更多细节描写、场景描写和人物对话
            3. 扩充内容至原文的2-3倍
            4. 使故事更加生动有趣
            5. 保持文风一致性
            {genre_prompt}
            
            原文内容：
            {request.prompt}
            
            请直接输出扩写后的内容，不要包含任何额外说明。
            """
        else:
            prompt = f"""请创作一个小说，严格遵循以下要求：
            1. 根据以下提示生成内容：{request.prompt}
            2. {genre_prompt}
            3. 必须生成一个吸引人的标题（使用《》括起来）
            4. 严格生成10个章节，不多不少
            5. 每个章节必须以"第X章 章节标题"开始（例如：第一章 初入仙门）
            6. 章节标题必须富有创意且各不相同，避免使用类似的词语
            7. 每章标题需要反映该章节的主要内容
            8. 每章节的内容要独立完整，建议300-500字
            9. 确保情节连贯，展现故事发展脉络
            
            请确保完整输出10个章节，每个章节都要有具体内容。
            """
        
        content = await generate_content(model_dict, prompt)
        
        if not content:
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "生成内容失败，请重试"}
            )
            
        title, chapters = extract_title_and_chapters(content)
        
        if not chapters:
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "无法解析生成的内容，请重试"}
            )
        
        # 记录成功响应
        logging.info(f"成功生成内容: 标题='{title}', 章节数={len(chapters)}")
            
        return {
            "success": True,
            "title": title,
            "chapters": chapters
        }
        
    except Exception as e:
        logging.error(f"生成内容时发生错误: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"生成内容时发生错误: {str(e)}"}
        )

if __name__ == "__main__":
    import uvicorn
    
    # 启动服务器
    uvicorn.run(app, host=config.APP_HOST, port=config.APP_PORT)
