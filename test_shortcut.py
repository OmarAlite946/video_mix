#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试快捷方式解析
"""

import os
import sys
import logging

# 配置基本日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ShortcutTest")

# Win32COM用于解析快捷方式
def resolve_shortcut(shortcut_path):
    """解析Windows快捷方式(.lnk文件)，返回其目标路径"""
    if not os.path.exists(shortcut_path) or not str(shortcut_path).lower().endswith('.lnk'):
        return None
        
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(shortcut_path))
        target_path = shortcut.Targetpath
        
        # 检查目标路径是否存在并且是目录
        if target_path and os.path.exists(target_path) and os.path.isdir(target_path):
            logger.info(f"解析快捷方式成功: {shortcut_path} -> {target_path}")
            return target_path
        else:
            logger.warning(f"快捷方式目标不存在或不是目录: {shortcut_path} -> {target_path}")
            return None
    except Exception as e:
        logger.warning(f"解析快捷方式失败 {shortcut_path}: {str(e)}")
        return None

def test_shortcut_resolution(shortcut_path):
    """测试解析快捷方式"""
    print(f"测试解析快捷方式: {shortcut_path}")
    target = resolve_shortcut(shortcut_path)
    if target:
        print(f"成功解析到目标: {target}")
        print(f"目标是目录: {os.path.isdir(target)}")
    else:
        print(f"解析失败或目标不是目录")
    return target

def check_folder_structure(folder_path):
    """检查文件夹结构"""
    print(f"\n检查文件夹结构: {folder_path}")
    
    if not os.path.exists(folder_path):
        print("文件夹不存在")
        return False
    
    if not os.path.isdir(folder_path):
        print("不是目录")
        return False
    
    video_dir = os.path.join(folder_path, "视频")
    audio_dir = os.path.join(folder_path, "配音")
    
    has_video = os.path.isdir(video_dir)
    has_audio = os.path.isdir(audio_dir)
    
    print(f"包含视频文件夹: {has_video}")
    print(f"包含配音文件夹: {has_audio}")
    
    return has_video or has_audio

def scan_directory(directory):
    """扫描目录"""
    print(f"\n扫描目录: {directory}")
    
    # 计数器
    total_items = 0
    folder_count = 0
    shortcut_count = 0
    valid_shortcut_count = 0
    invalid_shortcut_count = 0
    
    for item in os.listdir(directory):
        total_items += 1
        item_path = os.path.join(directory, item)
        print(f"\n检查项目: {item}")
        
        actual_path = item_path
        is_shortcut = False
        
        # 检查是否是快捷方式
        if item.lower().endswith('.lnk'):
            print(f"检测到可能的快捷方式: {item_path}")
            try:
                import win32com.client
                shell = win32com.client.Dispatch("WScript.Shell")
                shortcut = shell.CreateShortCut(str(item_path))
                target = shortcut.Targetpath
                print(f"  快捷方式信息:")
                print(f"  - 目标路径: {target}")
                print(f"  - 目标存在: {os.path.exists(target)}")
                print(f"  - 目标是目录: {os.path.isdir(target)}")
                
                shortcut_count += 1
                
                if os.path.exists(target) and os.path.isdir(target):
                    actual_path = target
                    is_shortcut = True
                    valid_shortcut_count += 1
                    print(f"确认为有效快捷方式，目标: {actual_path}")
                else:
                    invalid_shortcut_count += 1
                    print(f"快捷方式目标无效")
                    continue
            except Exception as e:
                invalid_shortcut_count += 1
                print(f"解析快捷方式时出错: {str(e)}")
                continue
        elif os.path.isdir(item_path):
            folder_count += 1
            print(f"确认为普通文件夹")
        else:
            print(f"既不是文件夹也不是快捷方式，跳过")
            continue
        
        # 检查是否是目录
        if not os.path.isdir(actual_path):
            print(f"不是目录，跳过")
            continue
        
        # 检查目录结构
        check_folder_structure(actual_path)
    
    # 打印统计信息
    print(f"\n目录扫描统计:")
    print(f"- 总项目数: {total_items}")
    print(f"- 普通文件夹数: {folder_count}")
    print(f"- 快捷方式数: {shortcut_count}")
    print(f"- 有效快捷方式数: {valid_shortcut_count}")
    print(f"- 无效快捷方式数: {invalid_shortcut_count}")

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("请提供要扫描的目录路径")
        return
    
    directory = sys.argv[1]
    print(f"开始扫描目录: {directory}")
    
    # 检查目录是否存在
    if not os.path.exists(directory):
        print(f"目录不存在: {directory}")
        return
    
    # 检查是否是目录
    if not os.path.isdir(directory):
        # 检查是否是快捷方式
        if directory.lower().endswith('.lnk'):
            target = test_shortcut_resolution(directory)
            if target:
                check_folder_structure(target)
        else:
            print(f"不是目录: {directory}")
        return
    
    # 扫描目录
    scan_directory(directory)

if __name__ == "__main__":
    main() 