#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
恢复main_window.py文件
"""

import os
import shutil

def restore_main_window():
    original_file = 'src/ui/main_window.py'
    backup_file = original_file + '.bak'
    
    if os.path.exists(backup_file):
        # 覆盖受损文件
        shutil.copy2(backup_file, original_file)
        print(f"已成功从 {backup_file} 恢复到 {original_file}")
        return True
    else:
        print(f"备份文件 {backup_file} 不存在，无法恢复")
        return False

def fix_audio_settings():
    """修复重复的音频设置问题，但保持文件完整性"""
    file_path = 'src/ui/main_window.py'
    temp_file_path = 'src/ui/main_window.new.py'
    
    # 两个标记，用于定位重复区域
    first_volume_found = False
    skip_section = False
    
    with open(file_path, 'r', encoding='utf-8') as infile, \
         open(temp_file_path, 'w', encoding='utf-8') as outfile:
        
        for line in infile:
            # 检测第一个音量设置区域的开始
            if '# 音量设置' in line and not first_volume_found:
                first_volume_found = True
                skip_section = True
                # 添加替代注释
                outfile.write('        # 音频设置区域已经在下方实现\n')
                continue
            
            # 检测第一个区域的结束位置
            if skip_section and 'settings_layout.addRow(bgm_layout)' in line:
                skip_section = False
                continue
            
            # 跳过重复区域内的行
            if skip_section:
                continue
            
            # 写入其他所有行
            outfile.write(line)
    
    # 备份当前文件
    backup_file = file_path + '.fix.bak'
    shutil.copy2(file_path, backup_file)
    print(f"已备份当前文件到 {backup_file}")
    
    # 应用修复
    shutil.move(temp_file_path, file_path)
    print(f"已将修复后的内容写入 {file_path}")
    return True

if __name__ == '__main__':
    print("开始恢复文件...")
    restored = restore_main_window()
    
    if restored:
        print("原文件已恢复，现在修复音频设置问题...")
        fixed = fix_audio_settings()
        if fixed:
            print("修复完成，软件应该可以正常启动了")
        else:
            print("修复音频设置问题失败")
    else:
        print("无法恢复原文件，请手动检查") 