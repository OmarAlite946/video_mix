#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
恢复带有记忆功能和批量处理功能的文件
"""

import os
import sys
import shutil
from pathlib import Path
import glob
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def restore_latest_backup():
    """恢复最新的备份文件"""
    try:
        # 获取当前脚本所在目录
        current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        parent_dir = current_dir.parent
        
        # 查找最新的备份文件
        backup_files = list(current_dir.glob("batch_window_*.py"))
        if not backup_files:
            logger.error("没有找到备份文件")
            return False
        
        # 按修改时间排序，获取最新的备份文件
        latest_backup = sorted(backup_files, key=os.path.getmtime)[-1]
        logger.info(f"找到最新备份文件: {latest_backup}")
        
        # 目标文件路径
        target_file = parent_dir / "src" / "ui" / "batch_window.py"
        
        # 备份当前文件
        if target_file.exists():
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            current_backup = parent_dir / "backup" / f"batch_window_{timestamp}.py.bak"
            os.makedirs(os.path.dirname(current_backup), exist_ok=True)
            shutil.copy2(target_file, current_backup)
            logger.info(f"已备份当前文件到: {current_backup}")
        
        # 复制备份文件到目标位置
        shutil.copy2(latest_backup, target_file)
        logger.info(f"已恢复文件到: {target_file}")
        
        return True
    except Exception as e:
        logger.error(f"恢复备份时出错: {e}")
        return False

if __name__ == "__main__":
    import time
    
    print("开始恢复带有记忆功能和批量处理功能的文件...")
    if restore_latest_backup():
        print("恢复成功！现在您可以启动程序并使用记忆功能和批量处理功能了。")
    else:
        print("恢复失败，请检查日志获取更多信息。")
    
    time.sleep(3)  # 等待3秒，让用户看到结果
