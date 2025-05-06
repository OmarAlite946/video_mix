#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
修复src/ui/main_window.py文件中的缩进问题
"""

import re

# 读取文件内容
file_path = "src/ui/main_window.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 修复on_compose_interrupted方法中的缩进问题
pattern1 = re.compile(r'def on_compose_interrupted\(self\):[^\n]*\n\s+"""[^"]*"""[^\n]*\n(\s+)# 更新界面状态')
content = pattern1.sub(r'def on_compose_interrupted(self):\n    """处理被中断时调用"""\n    # 更新界面状态', content)

# 修复其他缩进问题
content = re.sub(r'(\s+)# 显示消息\n(\s+)QMessageBox\.information', r'    # 显示消息\n    QMessageBox.information', content)

# 修复on_compose_completed方法中的缩进问题
content = re.sub(r'(\s+)# 显示完成消息\n(\s+)QMessageBox\.information', r'            # 显示完成消息\n            QMessageBox.information', content)

# 保存修复后的文件
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"已修复 {file_path} 中的缩进问题") 