#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
备份带有记忆功能和批量处理功能的文件
"""

import os
import sys
import shutil
from pathlib import Path
import time
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def create_backup():
    """创建备份文件"""
    try:
        # 获取当前脚本所在目录
        current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        
        # 创建备份目录
        backup_dir = current_dir / "memory_backup"
        backup_dir.mkdir(exist_ok=True)
        
        # 备份batch_window.py文件
        src_file = current_dir / "src" / "ui" / "batch_window.py"
        if not src_file.exists():
            logger.error(f"源文件不存在: {src_file}")
            return False
        
        # 创建带时间戳的备份文件名
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"batch_window_{timestamp}.py"
        
        # 复制文件
        shutil.copy2(src_file, backup_file)
        logger.info(f"已备份文件到: {backup_file}")
        
        # 创建恢复脚本
        restore_script = backup_dir / "restore_memory_functions.py"
        with open(restore_script, 'w', encoding='utf-8') as f:
            f.write("""#!/usr/bin/env python
# -*- coding: utf-8 -*-

\"\"\"
恢复带有记忆功能和批量处理功能的文件
\"\"\"

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
    \"\"\"恢复最新的备份文件\"\"\"
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
""")
        logger.info(f"已创建恢复脚本: {restore_script}")
        
        # 创建说明文件
        readme_file = backup_dir / "README.txt"
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write("""# 批处理记忆功能和排队处理勾选模板备份

本备份包含了以下功能：

1. 批处理模板的参数记忆功能（每个模板的信息都单独记忆，下次打开时保持上次的参数信息）
2. 排队处理勾选模板功能（允许随机勾选模板并正常计算运行）

## 如何恢复功能

如果将来您的软件更新后这些功能丢失了，可以运行 `restore_memory_functions.py` 脚本恢复这些功能。

## 备份文件说明

- `batch_window_*.py`: 包含记忆功能和批量处理功能的代码文件备份
- `restore_memory_functions.py`: 用于恢复功能的脚本

注意：恢复脚本会自动找到最新的备份文件进行恢复。
""")
        logger.info(f"已创建说明文件: {readme_file}")
        
        return True
    except Exception as e:
        logger.error(f"创建备份时出错: {e}")
        return False

if __name__ == "__main__":
    print("开始备份带有记忆功能和批量处理功能的文件...")
    if create_backup():
        print("备份成功！文件已保存到 memory_backup 目录。")
        print("如果将来软件更新后功能丢失，可运行 memory_backup/restore_memory_functions.py 恢复。")
    else:
        print("备份失败，请检查日志获取更多信息。")
    
    # 等待用户阅读结果
    input("按回车键退出...") 