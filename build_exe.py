#!/usr/bin/env python3
"""
构建可执行文件的脚本
"""
import os
import sys
import shutil
from pathlib import Path

def build_executable():
    """构建可执行文件"""
    
    print("🔨 开始构建AI小说生成器可执行文件...")
    
    # 检查PyInstaller是否安装
    try:
        import PyInstaller
    except ImportError:
        print("❌ PyInstaller未安装，正在安装...")
        os.system("pip install pyinstaller")
    
    # 构建命令
    build_cmd = [
        "pyinstaller",
        "--onefile",                    # 打包成单个文件
        "--windowed",                   # 无控制台窗口
        "--name", "AI小说生成器",        # 可执行文件名
        "--add-data", "templates;templates",  # 包含模板文件
        "--add-data", "static;static",        # 包含静态文件
        "--add-data", ".env.example;.",       # 包含环境变量示例
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "uvicorn.lifespan.off",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--clean",                      # 清理临时文件
        "app.py"
    ]
    
    print("📦 执行构建命令...")
    result = os.system(" ".join(build_cmd))
    
    if result == 0:
        print("✅ 构建成功！")
        
        # 创建发布目录
        release_dir = Path("release")
        if release_dir.exists():
            shutil.rmtree(release_dir)
        release_dir.mkdir()
        
        # 复制文件到发布目录
        print("📁 准备发布文件...")
        
        # 复制可执行文件
        exe_file = Path("dist/AI小说生成器.exe")
        if exe_file.exists():
            shutil.copy2(exe_file, release_dir)
        
        # 复制必要文件
        files_to_copy = [
            "README.md",
            "LICENSE", 
            ".env.example"
        ]
        
        for file in files_to_copy:
            if Path(file).exists():
                shutil.copy2(file, release_dir)
        
        # 创建使用说明
        usage_file = release_dir / "使用说明.txt"
        with open(usage_file, 'w', encoding='utf-8') as f:
            f.write("""AI小说生成器 - 使用说明

1. 首次使用：
   - 将 .env.example 重命名为 .env
   - 编辑 .env 文件，填入你的OpenRouter API密钥
   - API密钥获取地址：https://openrouter.ai/

2. 启动程序：
   - 双击 "AI小说生成器.exe" 启动程序
   - 程序启动后会自动打开浏览器
   - 如果没有自动打开，请手动访问：http://localhost:8000

3. 使用功能：
   - 填写背景故事和特色亮点
   - 点击"生成结构"生成小说
   - 点击章节右上角"扩写"按钮扩写内容
   - 点击删除按钮可删除不需要的章节

4. 注意事项：
   - 确保网络连接正常
   - 首次使用可能需要较长时间加载
   - 如遇问题请查看README.md文件

技术支持：https://github.com/your-username/ai-novel-generator
""")
        
        print(f"🎉 发布文件已准备完成！")
        print(f"📂 发布目录：{release_dir.absolute()}")
        print(f"📦 可执行文件：{release_dir / 'AI小说生成器.exe'}")
        
    else:
        print("❌ 构建失败！")
        return False
    
    return True

if __name__ == "__main__":
    success = build_executable()
    if success:
        print("\n🚀 构建完成！你现在可以：")
        print("1. 测试 release/AI小说生成器.exe")
        print("2. 将 release 文件夹打包上传到GitHub Releases")
    else:
        print("\n💥 构建失败，请检查错误信息")
        sys.exit(1)