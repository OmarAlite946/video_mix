#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
视频混剪工具 - 主程序入口
"""

import os
import sys
import argparse
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 添加 src 目录到 Python 路径
src_dir = project_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

def install_dependencies():
    """安装必要的依赖"""
    try:
        import pip
        print("正在安装必要的依赖...")
        pip.main(["install", "PyQt5==5.15.9", "moviepy==2.0.0.dev2", "opencv-python==4.8.1.78", "numpy==1.24.3", "scipy==1.11.3"])
        print("依赖安装完成")
    except Exception as e:
        print(f"安装依赖时出错: {e}")
        return False
    return True

def check_dependencies():
    """检查必要的依赖是否已安装"""
    try:
        from PyQt5.QtWidgets import QApplication
        from moviepy.editor import VideoFileClip
        import cv2
        import numpy
        return True
    except ImportError:
        return False

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='视频混剪工具')
    parser.add_argument('--batch-mode', action='store_true', help='启动批量处理模式')
    return parser.parse_args()

def main():
    """程序主入口"""
    try:
        # 解析命令行参数
        args = parse_arguments()
        
        # 检查并安装依赖
        if not check_dependencies():
            if not install_dependencies():
                print("无法安装必要的依赖，程序无法启动")
                return 1
            
            # 再次检查依赖
            if not check_dependencies():
                print("依赖安装可能未成功，但将尝试继续运行...")
        
        # 导入必要的组件
        from PyQt5.QtWidgets import QApplication
        
        # 创建应用程序
        app = QApplication(sys.argv)
        app.setApplicationName("视频混剪工具")
        app.setOrganizationName("VideoMixTool")
        
        # 根据参数启动不同的窗口
        if args.batch_mode:
            from src.ui.batch_window import BatchWindow
            print("正在启动批量处理模式...")
            window = BatchWindow()
        else:
            from src.ui.main_window import MainWindow
            window = MainWindow()
        
        window.show()
        
        # 运行应用程序
        return app.exec_()
        
    except Exception as e:
        print(f"程序启动时出错: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 