#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
简化版FFmpeg解压配置脚本
"""

import os
import sys
import zipfile
import shutil
from pathlib import Path

def main():
    print("===== FFmpeg解压配置工具 =====")
    
    # 设置路径
    ffmpeg_dir = Path("ffmpeg_compat")
    zip_path = ffmpeg_dir / "ffmpeg.zip"
    
    # 检查zip文件是否存在
    if not zip_path.exists():
        print(f"错误: 未找到 {zip_path}")
        return False
    
    print(f"找到FFmpeg压缩包: {zip_path}")
    
    # 解压文件
    try:
        print("正在解压文件...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # 获取顶级目录
            contents = zip_ref.namelist()
            top_dirs = set()
            for item in contents:
                parts = item.split('/')
                if len(parts) > 1:
                    top_dirs.add(parts[0])
            
            # 解压所有文件
            zip_ref.extractall(ffmpeg_dir)
            
            # 找到bin目录
            bin_found = False
            for top_dir in top_dirs:
                bin_dir = ffmpeg_dir / top_dir / "bin"
                if bin_dir.exists():
                    print(f"找到bin目录: {bin_dir}")
                    bin_found = True
                    
                    # 移动bin目录中的文件到ffmpeg_compat目录
                    for file in bin_dir.glob("*"):
                        dest_file = ffmpeg_dir / file.name
                        print(f"移动: {file} -> {dest_file}")
                        if dest_file.exists():
                            os.remove(dest_file)
                        shutil.move(str(file), str(dest_file))
                    
                    break
            
            if not bin_found:
                print("未找到bin目录，请手动查找ffmpeg.exe并移动到ffmpeg_compat目录")
        
        # 检查ffmpeg.exe是否已存在
        ffmpeg_exe = ffmpeg_dir / "ffmpeg.exe"
        if ffmpeg_exe.exists():
            print(f"FFmpeg解压成功: {ffmpeg_exe}")
            
            # 配置ffmpeg_path.txt
            with open("ffmpeg_path.txt", "w") as f:
                f.write(str(ffmpeg_exe))
            print(f"FFmpeg路径已配置: {ffmpeg_exe}")
            
            # 提示用户下一步操作
            print("\n===== 配置完成 =====")
            print("请运行以下命令测试GPU加速:")
            print("python test_gpu.py")
            
            return True
        else:
            print("未找到ffmpeg.exe，请手动查找并移动到ffmpeg_compat目录")
            return False
    
    except Exception as e:
        print(f"解压过程中出错: {e}")
        return False

if __name__ == "__main__":
    main() 