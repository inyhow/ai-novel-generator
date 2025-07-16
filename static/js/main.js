let isGenerating = false;
let currentNovel = null;
let activeChapterId = null;

// 页面加载完成后的初始化
document.addEventListener('DOMContentLoaded', () => {
    // 加载模型列表
    loadModels();
    
    // 添加事件监听器
    setupEventListeners();
});

async function loadModels() {
    try {
        const response = await fetch('/models');
        const data = await response.json();
        
        if (data.success && data.models) {
            const modelSelect = document.getElementById('model-select');
            modelSelect.innerHTML = ''; // 清空现有选项
            
            // 添加模型选项
            data.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.id || model.name;
                option.textContent = model.name || model.id;
                modelSelect.appendChild(option);
            });
        } else {
            console.error('获取模型列表失败:', data.error);
            const modelSelect = document.getElementById('model-select');
            modelSelect.innerHTML = '<option value="">加载模型失败</option>';
        }
    } catch (error) {
        console.error('获取模型列表出错:', error);
        const modelSelect = document.getElementById('model-select');
        modelSelect.innerHTML = '<option value="">加载模型失败</option>';
    }
}

function setupEventListeners() {
    // 生成按钮点击事件
    const generateButton = document.getElementById('generate-btn');
    if (generateButton) {
        generateButton.addEventListener('click', debounce(generateContent, 500));
    }
    
    // 示例提示点击事件
    const promptExamples = document.querySelectorAll('.prompt-examples li');
    promptExamples.forEach(example => {
        example.addEventListener('click', () => {
            document.getElementById('prompt').value = example.textContent.trim();
        });
    });
}

async function generateContent() {
    if (isGenerating) {
        alert('正在生成中，请稍候...');
        return;
    }

    const prompt = document.getElementById('prompt').value.trim();
    if (!prompt) {
        alert('请输入提示词');
        return;
    }

    const mode = document.querySelector('input[name="mode"]:checked').value;
    const modelId = document.getElementById('model-select').value;
    const genreSelect = document.getElementById('genre-select');
    const genre = genreSelect ? genreSelect.value : null;
    
    const loadingElement = document.getElementById('loading');
    const resultElement = document.getElementById('result');
    const chapterListElement = document.querySelector('.chapter-list');

    try {
        isGenerating = true;
        loadingElement.style.display = 'block';
        resultElement.innerHTML = '';
        chapterListElement.innerHTML = '';

        const response = await fetch('/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                prompt: prompt,
                mode: mode,
                model: modelId,
                genre: genre
            })
        });

        const data = await response.json();

        if (data.success) {
            // 保存小说数据
            currentNovel = {
                title: data.title,
                chapters: data.chapters
            };
            
            // 更新小说标题
            document.getElementById('novel-title').textContent = data.title;
            
            // 生成章节列表
            renderChapterList(data.chapters);
            
            // 默认显示第一章
            if (data.chapters.length > 0) {
                showChapter(0);
            }
        } else {
            throw new Error(data.error || '生成失败');
        }
    } catch (error) {
        console.error('Error:', error);
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error';
        errorDiv.textContent = `生成失败: ${error.message}`;
        resultElement.appendChild(errorDiv);
    } finally {
        isGenerating = false;
        loadingElement.style.display = 'none';
    }
}

function renderChapterList(chapters) {
    const chapterListElement = document.querySelector('.chapter-list');
    chapterListElement.innerHTML = '';
    
    chapters.forEach((chapter, index) => {
        // 计算字数
        const wordCount = countChineseWords(chapter.content);
        
        const chapterItem = document.createElement('div');
        chapterItem.className = 'chapter-item';
        chapterItem.dataset.index = index;
        
        chapterItem.innerHTML = `
            <div class="chapter-title">${chapter.title}</div>
            <div class="chapter-word-count">${wordCount}字</div>
            <div class="chapter-status">
                <div class="status-indicator success"></div>
            </div>
        `;
        
        chapterItem.addEventListener('click', () => {
            // 移除其他章节的active状态
            document.querySelectorAll('.chapter-item').forEach(item => {
                item.classList.remove('active');
            });
            
            // 给当前章节添加active状态
            chapterItem.classList.add('active');
            
            // 显示章节内容
            showChapter(index);
        });
        
        chapterListElement.appendChild(chapterItem);
    });
}

function showChapter(index) {
    if (!currentNovel || !currentNovel.chapters[index]) {
        return;
    }
    
    activeChapterId = index;
    const chapter = currentNovel.chapters[index];
    const resultElement = document.getElementById('result');
    
    resultElement.innerHTML = '';
    
    // 添加章节标题
    const titleElement = document.createElement('h3');
    titleElement.textContent = chapter.title;
    resultElement.appendChild(titleElement);
    
    // 添加章节内容
    const contentElement = document.createElement('div');
    contentElement.textContent = chapter.content;
    resultElement.appendChild(contentElement);
    
    // 标记章节为活跃状态
    document.querySelectorAll('.chapter-item').forEach((item, idx) => {
        if (idx === index) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
}

// 统计中文字数的函数
function countChineseWords(text) {
    // 移除空格和标点符号
    const cleanText = text.replace(/[\s\p{P}]/gu, '');
    return cleanText.length;
}

// 防抖函数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
} 