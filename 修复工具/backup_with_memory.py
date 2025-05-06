#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
批量处理模板记忆功能备份工具

此脚本用于备份当前的批量处理模板记忆功能配置文件，
包括模板状态、用户设置和相关配置文件。
"""

import os
import sys
import time
import logging
import shutil
from pathlib import Path
import json

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('BackupTool')

def create_backup_folder():
    """创建备份文件夹"""
    timestamp = int(time.time())
    user_home = Path.home() / "VideoMixTool"
    backup_dir = Path("backup") / f"backup_{timestamp}"
    
    if not backup_dir.exists():
        backup_dir.mkdir(parents=True)
        logger.info(f"创建备份文件夹：{backup_dir}")
    
    return backup_dir

def backup_settings_files():
    """备份设置文件"""
    backup_dir = create_backup_folder()
    user_home = Path.home() / "VideoMixTool"
    
    if not user_home.exists():
        logger.warning(f"未找到用户设置目录：{user_home}")
        return backup_dir
    
    # 备份所有设置文件
    for file in user_home.glob("*.json"):
        dest_file = backup_dir / file.name
        try:
            shutil.copy2(file, dest_file)
            logger.info(f"已备份设置文件：{file.name}")
        except Exception as e:
            logger.error(f"备份文件 {file.name} 失败：{str(e)}")
    
    # 备份模板状态文件
    template_state_file = user_home / "template_state.json"
    if template_state_file.exists():
        dest_file = backup_dir / "template_state.json"
        try:
            shutil.copy2(template_state_file, dest_file)
            logger.info(f"已备份模板状态文件：template_state.json")
        except Exception as e:
            logger.error(f"备份模板状态文件失败：{str(e)}")
    
    return backup_dir

def backup_source_files():
    """备份源代码文件"""
    backup_dir = Path("backup") / "source_files"
    if not backup_dir.exists():
        backup_dir.mkdir(parents=True)
    
    # 备份关键源文件
    src_files = [
        "src/utils/user_settings.py",
        "src/utils/template_state.py",
        "src/ui/batch_window.py"
    ]
    
    for file_path in src_files:
        if os.path.exists(file_path):
            dest_file = backup_dir / Path(file_path).name
            try:
                shutil.copy2(file_path, dest_file)
                logger.info(f"已备份源文件：{file_path}")
            except Exception as e:
                logger.error(f"备份源文件 {file_path} 失败：{str(e)}")

def main():
    """主函数"""
    print("="*50)
    print("  批量处理模板记忆功能备份工具  ")
    print("="*50)
    
    logger.info("开始备份...")
    
    # 备份用户设置
    backup_dir = backup_settings_files()
    
    # 备份源文件
    backup_source_files()
    
    logger.info(f"备份完成！文件保存在：{backup_dir}")
    print("\n备份已完成！")
    print(f"文件保存在：{backup_dir}")
    print("="*50)

if __name__ == "__main__":
    main() 