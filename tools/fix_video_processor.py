#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
视频处理器修复工具 - 专门修复缩进问题
"""

import os
import shutil
import re

def fix_video_processor_indentation():
    """修复视频处理器代码中的缩进问题"""
    video_processor_path = os.path.join("src", "core", "video_processor.py")
    
    if not os.path.exists(video_processor_path):
        print(f"错误: 找不到文件 {video_processor_path}")
        return False
    
    # 备份原始文件
    backup_path = f"{video_processor_path}.orig"
    try:
        shutil.copy2(video_processor_path, backup_path)
        print(f"已创建原始备份: {backup_path}")
    except Exception as e:
        print(f"创建备份时出错: {str(e)}")
        return False
    
    # 读取文件内容
    try:
        with open(video_processor_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        try:
            with open(video_processor_path, "r", encoding="gbk") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"读取文件时出错: {str(e)}")
            return False
    
    # 找到问题区域 - 查找包含"根据配音时长裁剪视频"和"subclip"的行
    clip_duration_start = -1
    for i, line in enumerate(lines):
        if "根据配音时长裁剪视频" in line:
            clip_duration_start = i
            break
    
    if clip_duration_start == -1:
        print("找不到裁剪视频相关代码段")
        return False
    
    # 查找问题区域结束位置 - 查找下一个函数定义或方法
    clip_duration_end = -1
    for i in range(clip_duration_start, len(lines)):
        if re.match(r'^\s*def\s+', lines[i]):
            clip_duration_end = i
            break
    
    if clip_duration_end == -1:
        clip_duration_end = len(lines)  # 如果找不到结束位置，假设它一直持续到文件末尾
    
    # 修复区域内的try语句块缩进问题
    fixed_lines = []
    in_try_block = False
    indent_level = 0
    
    for i in range(len(lines)):
        line = lines[i]
        
        # 如果在关注的区域内
        if clip_duration_start <= i < clip_duration_end:
            # 检测是否开始了try块
            if "try:" in line:
                in_try_block = True
                indent_level = len(line) - len(line.lstrip())
                # 保存原始行，不修改
                fixed_lines.append(line)
                continue
            
            # 如果在try块内部，确保缩进正确
            if in_try_block:
                stripped_line = line.lstrip()
                
                # 如果遇到except，结束try块
                if "except" in line:
                    in_try_block = False
                    # 保存原始行，不修改
                    fixed_lines.append(line)
                    continue
                
                # 空行不需要额外缩进
                if not stripped_line.strip():
                    fixed_lines.append(line)
                    continue
                
                # 检查缩进级别，修复缩进
                current_indent = len(line) - len(stripped_line)
                if current_indent <= indent_level:
                    # 如果缩进不足，修正缩进
                    correct_indent = indent_level + 4  # 增加一级缩进（4个空格）
                    fixed_line = " " * correct_indent + stripped_line
                    fixed_lines.append(fixed_line)
                    print(f"修复行 {i+1}: 增加缩进")
                else:
                    # 缩进正确，保持不变
                    fixed_lines.append(line)
            else:
                # 不在try块内部，保持不变
                fixed_lines.append(line)
        else:
            # 不在目标区域内，保持不变
            fixed_lines.append(line)
    
    # 写入修复后的内容
    try:
        with open(video_processor_path, "w", encoding="utf-8") as f:
            f.writelines(fixed_lines)
        print(f"文件已修复: {video_processor_path}")
        return True
    except Exception as e:
        print(f"写入文件时出错: {str(e)}")
        try:
            # 恢复备份
            shutil.copy2(backup_path, video_processor_path)
            print(f"已恢复原始备份: {video_processor_path}")
        except:
            pass
        return False

def fix_specific_indentation():
    """直接修复已知的特定缩进问题"""
    video_processor_path = os.path.join("src", "core", "video_processor.py")
    
    if not os.path.exists(video_processor_path):
        print(f"错误: 找不到文件 {video_processor_path}")
        return False
    
    # 备份原始文件
    backup_path = f"{video_processor_path}.orig2"
    try:
        shutil.copy2(video_processor_path, backup_path)
        print(f"已创建原始备份: {backup_path}")
    except Exception as e:
        print(f"创建备份时出错: {str(e)}")
        return False
    
    # 读取文件内容
    try:
        with open(video_processor_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(video_processor_path, "r", encoding="gbk") as f:
                content = f.read()
        except Exception as e:
            print(f"读取文件时出错: {str(e)}")
            return False
    
    # 查找并修复特定代码片段
    # 定位关键部分: 视频裁剪的try-except块
    pattern = re.compile(r'(if video_duration > clip_duration:\s+start_time = 0\s+# 从视频开头开始截取\s+try:)(\s+)(video_clip = video_clip\.subclip\(start_time, start_time \+ clip_duration\))')
    
    if pattern.search(content):
        # 修复缩进问题
        fixed_content = pattern.sub(r'\1\n                                \3', content)
        print("找到并修复了缩进问题")
        
        # 写入修复后的内容
        try:
            with open(video_processor_path, "w", encoding="utf-8") as f:
                f.write(fixed_content)
            print(f"文件已修复: {video_processor_path}")
            return True
        except Exception as e:
            print(f"写入文件时出错: {str(e)}")
            try:
                # 恢复备份
                shutil.copy2(backup_path, video_processor_path)
                print(f"已恢复原始备份: {video_processor_path}")
            except:
                pass
            return False
    else:
        print("未找到需要修复的特定代码段")
        return False

def fix_manually():
    """手动替换指定行来修复问题"""
    video_processor_path = os.path.join("src", "core", "video_processor.py")
    
    if not os.path.exists(video_processor_path):
        print(f"错误: 找不到文件 {video_processor_path}")
        return False
    
    # 备份原始文件
    backup_path = f"{video_processor_path}.manual_fix_bak"
    try:
        shutil.copy2(video_processor_path, backup_path)
        print(f"已创建原始备份: {backup_path}")
    except Exception as e:
        print(f"创建备份时出错: {str(e)}")
        return False
    
    # 读取文件内容
    try:
        with open(video_processor_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        try:
            with open(video_processor_path, "r", encoding="gbk") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"读取文件时出错: {str(e)}")
            return False
    
    # 定义修复后的代码片段
    fixed_code_segment = """                        # 如果视频比配音长，则从视频开头开始截取，而不是从中间
                        if video_duration > clip_duration:
                            start_time = 0  # 从视频开头开始截取
                            try:
                                video_clip = video_clip.subclip(start_time, start_time + clip_duration)
                                if video_clip.duration < 0.5:  # 如果裁剪后视频太短
                                    logger.warning(f"裁剪后视频时长过短: {video_clip.duration:.2f}秒，使用原始视频")
                                    video_clip = VideoFileClip(video_file)  # 重新加载原始视频
                            except Exception as e:
                                logger.error(f"裁剪视频时出错: {str(e)}，使用原始视频")
                                video_clip = VideoFileClip(video_file)  # 使用原始视频
"""
    
    # 查找关键行的索引位置
    start_idx = -1
    end_idx = -1
    
    for i, line in enumerate(lines):
        if "# 如果视频比配音长，则从视频开头开始截取，而不是从中间" in line:
            start_idx = i
        if start_idx != -1 and "视频时长过短" in line and end_idx == -1:
            # 继续搜索几行直到找到包含"使用原始视频"的行
            for j in range(i, min(i+10, len(lines))):
                if "使用原始视频" in lines[j]:
                    end_idx = j + 1
                    break
    
    if start_idx == -1 or end_idx == -1:
        print("未找到需要替换的代码段")
        return False
    
    # 替换代码段
    lines[start_idx:end_idx+1] = fixed_code_segment.splitlines(True)
    
    # 写入修复后的内容
    try:
        with open(video_processor_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"文件已手动修复: {video_processor_path}")
        return True
    except Exception as e:
        print(f"写入文件时出错: {str(e)}")
        try:
            # 恢复备份
            shutil.copy2(backup_path, video_processor_path)
            print(f"已恢复原始备份: {video_processor_path}")
        except:
            pass
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("视频处理器缩进问题修复工具")
    print("=" * 60)
    
    # 尝试通用方法修复
    if not fix_video_processor_indentation():
        print("\n通用方法修复失败，尝试针对特定问题的修复...")
        
        # 尝试修复特定问题
        if not fix_specific_indentation():
            print("\n特定问题修复失败，尝试手动替换方法...")
            
            # 尝试手动替换方法
            if fix_manually():
                print("\n成功使用手动替换方法修复了问题！")
            else:
                print("\n所有修复方法均失败，请手动检查文件。")
        else:
            print("\n成功使用特定问题修复方法！")
    else:
        print("\n成功使用通用方法修复了问题！")
    
    print("\n建议重启程序并测试视频合成功能。")
    print("=" * 60)
    
    input("\n按回车键退出...") 