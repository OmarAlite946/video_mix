#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
修复批处理模板的参数记忆功能和排队处理勾选模板功能
"""

import os
import sys
import time
import logging
import shutil
from pathlib import Path
import subprocess

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def fix_user_settings():
    """修复UserSettings类初始化问题"""
    try:
        # 获取当前脚本所在目录
        current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        
        # 用户设置文件路径
        user_settings_path = current_dir / "src" / "utils" / "user_settings.py"
        
        if not user_settings_path.exists():
            logger.error(f"找不到用户设置文件: {user_settings_path}")
            return False
        
        # 读取文件内容
        with open(user_settings_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 创建备份
        backup_path = current_dir / "backup" / f"user_settings_{int(time.time())}.py.bak"
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        shutil.copy2(user_settings_path, backup_path)
        logger.info(f"已创建备份: {backup_path}")
        
        # 查找并修复初始化问题
        if "self.settings: Dict[str, Any] = {}" in content:
            # 修改为使用默认设置的副本
            fixed_content = content.replace(
                "self.settings: Dict[str, Any] = {}", 
                "# 初始化为默认设置的副本，而不是空字典\n        self.settings = DEFAULT_SETTINGS.copy()"
            )
            
            # 写入修复后的内容
            with open(user_settings_path, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            
            logger.info("成功修复UserSettings类初始化问题")
            return True
        elif "self.settings = DEFAULT_SETTINGS.copy()" in content:
            logger.info("UserSettings类已经正确初始化，不需要修复")
            return True
        else:
            logger.warning("无法找到需要修复的代码段，可能文件已被修改")
            return False
    except Exception as e:
        logger.error(f"修复UserSettings时出错: {e}")
        return False

def check_template_state():
    """检查模板状态类是否正确"""
    try:
        # 获取当前脚本所在目录
        current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        
        # 模板状态文件路径
        template_state_path = current_dir / "src" / "utils" / "template_state.py"
        
        if not template_state_path.exists():
            logger.error(f"找不到模板状态文件: {template_state_path}")
            return False
        
        # 检查文件内容
        with open(template_state_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键方法是否存在
        essential_methods = [
            "save_template_tabs", 
            "load_template_tabs"
        ]
        
        all_methods_exist = True
        for method in essential_methods:
            if method not in content:
                logger.error(f"模板状态类缺少关键方法: {method}")
                all_methods_exist = False
        
        return all_methods_exist
    except Exception as e:
        logger.error(f"检查模板状态类时出错: {e}")
        return False

def check_batch_window():
    """检查批处理窗口类是否正确"""
    try:
        # 获取当前脚本所在目录
        current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        
        # 批处理窗口文件路径
        batch_window_path = current_dir / "src" / "ui" / "batch_window.py"
        
        if not batch_window_path.exists():
            logger.error(f"找不到批处理窗口文件: {batch_window_path}")
            return False
        
        # 检查文件内容
        with open(batch_window_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键方法是否存在
        essential_methods = [
            "_save_template_state", 
            "_load_saved_templates",
            "_add_template_from_info"
        ]
        
        all_methods_exist = True
        for method in essential_methods:
            if method not in content:
                logger.error(f"批处理窗口类缺少关键方法: {method}")
                all_methods_exist = False
        
        return all_methods_exist
    except Exception as e:
        logger.error(f"检查批处理窗口类时出错: {e}")
        return False

def clear_settings_cache():
    """清理设置缓存文件，强制从头创建新的设置文件"""
    try:
        # 获取用户主目录下的设置目录
        settings_dir = Path.home() / "VideoMixTool"
        
        if not settings_dir.exists():
            logger.info(f"设置目录不存在，不需要清理: {settings_dir}")
            return True
        
        # 备份原有设置
        backup_dir = settings_dir / f"backup_{int(time.time())}"
        backup_dir.mkdir(exist_ok=True)
        
        # 复制所有设置文件到备份目录
        for settings_file in settings_dir.glob("*.json"):
            if settings_file.is_file():
                dest_file = backup_dir / settings_file.name
                shutil.copy2(settings_file, dest_file)
                logger.info(f"已备份设置文件: {settings_file.name}")
        
        # 可选：清理特定的设置文件
        template_state_file = settings_dir / "template_state.json"
        if template_state_file.exists():
            os.rename(template_state_file, template_state_file.with_suffix(".json.bak"))
            logger.info(f"已重命名模板状态文件: {template_state_file}")
        
        logger.info("设置缓存清理完成")
        return True
    except Exception as e:
        logger.error(f"清理设置缓存时出错: {e}")
        return False

def start_application():
    """启动应用程序"""
    try:
        # 获取当前脚本所在目录
        current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        
        # 主程序路径
        main_path = current_dir / "main.py"
        
        if not main_path.exists():
            logger.error(f"找不到主程序: {main_path}")
            return False
        
        logger.info("即将启动程序...")
        
        # 使用Popen启动程序，不等待完成
        subprocess.Popen([sys.executable, str(main_path)])
        
        logger.info("程序已启动，本修复脚本将退出")
        return True
    except Exception as e:
        logger.error(f"启动程序时出错: {e}")
        return False

if __name__ == "__main__":
    print("===== 开始修复批处理模板的参数记忆功能和排队处理勾选模板功能 =====")
    
    # 检查批处理窗口类
    print("\n检查批处理窗口类...")
    if check_batch_window():
        print("✓ 批处理窗口类检查通过")
    else:
        print("✗ 批处理窗口类检查失败，功能可能无法正常工作")
    
    # 检查模板状态类
    print("\n检查模板状态类...")
    if check_template_state():
        print("✓ 模板状态类检查通过")
    else:
        print("✗ 模板状态类检查失败，可能无法保存模板状态")
    
    # 修复UserSettings类
    print("\n修复用户设置类...")
    if fix_user_settings():
        print("✓ 用户设置类修复成功")
    else:
        print("✗ 用户设置类修复失败")
    
    # 清理设置缓存
    print("\n清理设置缓存...")
    if clear_settings_cache():
        print("✓ 设置缓存清理成功")
    else:
        print("✗ 设置缓存清理失败")
    
    # 启动应用程序
    print("\n修复完成，是否立即启动程序？")
    choice = input("请输入 y/n (默认y): ").strip().lower()
    if choice != 'n':
        if start_application():
            print("✓ 程序已启动，请检查功能是否正常")
        else:
            print("✗ 程序启动失败，请手动启动main.py")
    
    print("\n=== 修复过程完成 ===")
    time.sleep(3)  # 暂停几秒，方便用户查看结果 