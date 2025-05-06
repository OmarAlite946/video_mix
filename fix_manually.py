#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
手动修复视频处理器代码文件中的缩进问题
"""

import os
import shutil

def fix_manually():
    """直接替换出错代码段"""
    try:
        # 文件路径
        file_path = os.path.join("src", "core", "video_processor.py")
        
        # 备份原文件
        backup_path = f"{file_path}.manual_bak"
        shutil.copy2(file_path, backup_path)
        print(f"已创建备份: {backup_path}")
        
        # 读取文件内容
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 定位问题区域
        problem_code = """                        # 如果视频比配音长，则从视频开头开始截取，而不是从中间
                        if video_duration > clip_duration:
                            start_time = 0  # 从视频开头开始截取
                            try:
                            video_clip = video_clip.subclip(start_time, start_time + clip_duration)"""
        
        # 修复后的代码
        fixed_code = """                        # 如果视频比配音长，则从视频开头开始截取，而不是从中间
                        if video_duration > clip_duration:
                            start_time = 0  # 从视频开头开始截取
                            try:
                                video_clip = video_clip.subclip(start_time, start_time + clip_duration)"""
        
        # 替换代码
        if problem_code in content:
            content = content.replace(problem_code, fixed_code)
            print("找到并修复了问题代码")
        else:
            # 如果找不到完全匹配的代码，尝试更简单的匹配
            problem_pattern = "try:\n                            video_clip"
            fixed_pattern = "try:\n                                video_clip"
            
            if problem_pattern in content:
                content = content.replace(problem_pattern, fixed_pattern)
                print("使用模式匹配找到并修复了问题代码")
            else:
                print("找不到匹配的问题代码，尝试完全重写相关部分...")
                
                # 尝试完全重写相关部分
                complete_section = """                        # 如果视频比配音长，则从视频开头开始截取，而不是从中间
                        if video_duration > clip_duration:
                            start_time = 0  # 从视频开头开始截取
                            try:
                                video_clip = video_clip.subclip(start_time, start_time + clip_duration)
                                if video_clip.duration < 0.5:  # 如果裁剪后视频太短
                                    logger.warning(f"裁剪后视频时长过短: {video_clip.duration:.2f}秒，使用原始视频")
                                    video_clip = VideoFileClip(video_file)  # 重新加载原始视频
                            except Exception as e:
                                logger.error(f"裁剪视频时出错: {str(e)}，使用原始视频")
                                video_clip = VideoFileClip(video_file)  # 使用原始视频"""
                
                # 查找开始位置和结束位置
                start_marker = "# 如果视频比配音长，则从视频开头开始截取"
                end_marker = "使用原始视频"
                
                start_idx = content.find(start_marker)
                if start_idx >= 0:
                    # 找到 "使用原始视频" 附近的位置
                    search_area = content[start_idx:start_idx + 1000]  # 只在后面1000个字符内查找
                    end_idx = search_area.find(end_marker)
                    
                    if end_idx >= 0:
                        end_idx = start_idx + end_idx + len(end_marker)
                        
                        # 确保结束位置有效（找到下一个有效的缩进行）
                        next_line_idx = content.find("\n", end_idx)
                        if next_line_idx >= 0:
                            # 提取需要替换的整段代码
                            code_to_replace = content[start_idx:next_line_idx]
                            content = content.replace(code_to_replace, complete_section)
                            print("已完全重写相关代码部分")
                        else:
                            print("无法找到段落结束位置")
                            return False
                    else:
                        print("无法找到 '使用原始视频' 标记")
                        return False
                else:
                    print("无法找到 '如果视频比配音长' 标记")
                    return False
        
        # 写入修复后的内容
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"文件已修复: {file_path}")
        return True
    
    except Exception as e:
        print(f"修复过程出错: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("手动修复视频处理器代码文件")
    print("=" * 60)
    
    success = fix_manually()
    
    if success:
        print("\n修复成功！请重启程序并测试视频合成功能。")
    else:
        print("\n修复失败！请手动检查并修复文件。")
    
    print("=" * 60)
    
    input("\n按回车键退出...") 