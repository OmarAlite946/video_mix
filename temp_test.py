#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
临时测试脚本 - 测试帮助系统
"""

import sys
import os
from pathlib import Path

# 确保可以导入src目录下的模块
src_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(src_dir))

try:
    from PyQt5.QtWidgets import QApplication
    from src.ui.main_window import MainWindow
    
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装所有依赖: pip install -r requirements.txt")
    sys.exit(1)

def main():
    """程序主入口"""
    app = QApplication(sys.argv)
    app.setApplicationName("视频混剪工具")
    app.setOrganizationName("VideoMixTool")
    
    # 初始化主窗口
    window = MainWindow()
    window.show()
    
    # 执行应用
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main()) 