#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FFmpeg配置工具
帮助设置FFmpeg路径，无需管理员权限
"""

import os
import sys
from pathlib import Path

def main():
    print("=== FFmpeg配置工具 ===")
    print("此工具帮助您设置FFmpeg路径，无需管理员权限")
    print()
    
    # 获取FFmpeg路径
    ffmpeg_path = input("请输入您的FFmpeg可执行文件完整路径 (例如: C:\\FFmpeg\\bin\\ffmpeg.exe): ")
    ffmpeg_path = ffmpeg_path.strip()
    
    if not ffmpeg_path:
        print("错误: 路径不能为空！")
        return
    
    # 检查路径是否存在
    if not os.path.exists(ffmpeg_path):
        print(f"警告: 路径不存在 - {ffmpeg_path}")
        confirm = input("是否仍然保存此路径? (y/n): ")
        if confirm.lower() != 'y':
            print("已取消设置")
            return
    
    # 保存路径到配置文件
    try:
        with open("ffmpeg_path.txt", "w") as f:
            f.write(ffmpeg_path)
        print("FFmpeg路径已成功保存！")
        print(f"保存位置: {os.path.abspath('ffmpeg_path.txt')}")
        print("\n现在您可以不需要管理员权限也能使用软件的视频合成功能了！")
    except Exception as e:
        print(f"保存路径时出错: {str(e)}")

if __name__ == "__main__":
    main()
    input("\n按任意键退出...") 