#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
修复 Python 路径问题的脚本
"""

import os
import sys
from pathlib import Path

def fix_python_path():
    """修复 Python 路径"""
    # 获取当前目录
    current_dir = Path.cwd()
    
    # 添加 src 目录到 Python 路径
    src_dir = current_dir / "src"
    if src_dir.exists():
        sys.path.insert(0, str(src_dir))
        print(f"已添加 {src_dir} 到 Python 路径")
    
    # 安装必要的依赖
    try:
        import pip
        pip.main(["install", "moviepy"])
        print("已安装 moviepy")
    except Exception as e:
        print(f"安装 moviepy 时出错: {e}")

if __name__ == "__main__":
    fix_python_path() 