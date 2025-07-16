#!/usr/bin/env python3
"""
简化的构建脚本
"""
import os
import sys
import shutil
from pathlib import Path

def main():
    print("🔨 构建AI小说生成器...")
    
    # 安装PyInstaller
    print("📦 安装构建工具...")
    os.system("pip install pyinstaller")
    
    # 简单构建命令
    cmd = [
        "pyinstaller",
        "--onefile",
        "--name", "AI小说生成器",
        "--add-data", "templates;templates",
        "--add-data", "static;static", 
        "--clean",
        "app.py"
    ]
    
    print("🚀 开始构建...")
    result = os.system(" ".join(cmd))
    
    if result == 0:
        print("✅ 构建成功！")
        print("📁 可执行文件位置: dist/AI小说生成器.exe")
    else:
        print("❌ 构建失败")

if __name__ == "__main__":
    main()