#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
短视频批量混剪工具 - 主程序入口
"""

import sys
import os
import traceback
import argparse
from pathlib import Path

# 确保可以导入src目录下的模块
src_dir = Path(__file__).resolve().parent / 'src'
sys.path.insert(0, str(src_dir))

def configure_ffmpeg():
    """配置FFmpeg路径"""
    print("=== FFmpeg配置工具 ===")
    print("此工具帮助您设置FFmpeg路径，无需管理员权限")
    print()
    
    # 获取FFmpeg路径
    ffmpeg_path = input("请输入您的FFmpeg可执行文件完整路径 (例如: C:\\FFmpeg\\bin\\ffmpeg.exe): ")
    ffmpeg_path = ffmpeg_path.strip()
    
    if not ffmpeg_path:
        print("错误: 路径不能为空！")
        return False
    
    # 检查路径是否存在
    if not os.path.exists(ffmpeg_path):
        print(f"警告: 路径不存在 - {ffmpeg_path}")
        confirm = input("是否仍然保存此路径? (y/n): ")
        if confirm.lower() != 'y':
            print("已取消设置")
            return False
    
    # 保存路径到配置文件
    try:
        with open("ffmpeg_path.txt", "w") as f:
            f.write(ffmpeg_path)
        print("FFmpeg路径已成功保存！")
        print(f"保存位置: {os.path.abspath('ffmpeg_path.txt')}")
        print("\n现在您可以不需要管理员权限也能使用软件的视频合成功能了！")
        return True
    except Exception as e:
        print(f"保存路径时出错: {str(e)}")
        return False

def handle_exception(exc_type, exc_value, exc_traceback):
    """全局异常处理"""
    if issubclass(exc_type, KeyboardInterrupt):
        # 正常退出
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    # 记录未捕获的异常
    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(f"发生未捕获的异常:\n{error_msg}")
    # 这里可以添加错误日志记录或弹窗提示

# 设置全局异常处理
sys.excepthook = handle_exception

def main():
    """程序主入口"""
    parser = argparse.ArgumentParser(description="短视频批量混剪工具")
    parser.add_argument("--config-ffmpeg", action="store_true", help="配置FFmpeg路径后退出")
    args = parser.parse_args()
    
    # 如果指定了配置FFmpeg，则运行配置工具后退出
    if args.config_ffmpeg:
        success = configure_ffmpeg()
        return 0 if success else 1
    
    try:
        from PyQt5.QtWidgets import QApplication
        from ui.main_window import MainWindow
        from utils.logger import setup_logger
        from hardware.system_analyzer import SystemAnalyzer
    except ImportError as e:
        print(f"导入错误: {e}")
        print("请确保已安装所有依赖: pip install -r requirements.txt")
        sys.exit(1)
    
    app = QApplication(sys.argv)
    app.setApplicationName("视频混剪工具")
    app.setOrganizationName("VideoMixTool")
    
    # 设置日志
    setup_logger()
    
    # 检测系统硬件
    analyzer = SystemAnalyzer()
    system_info = analyzer.analyze()
    print("系统信息:")
    for key, value in system_info.items():
        print(f"  {key}: {value}")
    
    # 创建并显示主窗口
    window = MainWindow()
    window.show()
    
    # 执行应用
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main()) 