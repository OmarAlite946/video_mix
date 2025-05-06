#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
恢复完整的原始文件并添加双击编辑功能
"""

import os
import shutil
import re

# 完全恢复原始文件
def restore_original_files():
    """从备份文件恢复原始文件"""
    main_window_file = 'src/ui/main_window.py'
    batch_window_file = 'src/ui/batch_window.py'
    
    main_window_bak = main_window_file + '.bak'
    batch_window_bak = batch_window_file + '.bak'
    
    restored = False
    
    # 恢复main_window.py
    if os.path.exists(main_window_bak):
        shutil.copy2(main_window_bak, main_window_file)
        print(f"已恢复 {main_window_file}")
        restored = True
    else:
        print(f"未找到 {main_window_bak} 备份文件")
    
    # 恢复batch_window.py
    if os.path.exists(batch_window_bak):
        shutil.copy2(batch_window_bak, batch_window_file)
        print(f"已恢复 {batch_window_file}")
        restored = True
    else:
        print(f"未找到 {batch_window_bak} 备份文件")
    
    return restored

# 添加双击编辑功能
def add_double_click_edit():
    """添加双击编辑标签功能到batch_window.py"""
    file_path = 'src/ui/batch_window.py'
    
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查功能是否已存在
    if 'def _on_tab_double_clicked' in content:
        print("双击编辑功能已存在")
        return True
    
    # 定位TabWidget初始化代码
    tab_widget_pattern = r'self\.tab_widget = QTabWidget\(\)\s+self\.tab_widget\.setTabsClosable\(True\)\s+self\.tab_widget\.tabCloseRequested\.connect\(self\._on_tab_close\)'
    tab_init_code = re.search(tab_widget_pattern, content)
    
    if not tab_init_code:
        print("无法在代码中找到TabWidget初始化部分")
        return False
    
    # 添加启用双击编辑的代码
    double_click_connection = '\n        # 启用双击编辑标签功能\n        self.tab_widget.tabBarDoubleClicked.connect(self._on_tab_double_clicked)'
    new_init_code = tab_init_code.group() + double_click_connection
    content = content.replace(tab_init_code.group(), new_init_code)
    
    # 定位新方法的添加位置（在_on_tab_close方法后面）
    on_tab_close_pattern = r'def _on_tab_close\(self, index\):.*?self\._save_template_state\(\)'
    on_tab_close_match = re.search(on_tab_close_pattern, content, re.DOTALL)
    
    if not on_tab_close_match:
        print("无法在代码中找到_on_tab_close方法")
        return False
    
    # 构建双击编辑方法代码
    double_click_method = '''
    
    def _on_tab_double_clicked(self, index):
        """处理标签页双击事件，允许用户编辑标签名称"""
        # 正在处理时不允许编辑标签名
        if self.is_processing:
            QMessageBox.warning(self, "警告", "批量处理过程中不能修改标签名")
            return
            
        # 获取当前标签名
        current_name = self.tab_widget.tabText(index)
        
        # 弹出输入对话框
        from PyQt5.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(
            self, 
            "修改模板名称", 
            "请输入新的模板名称:",
            text=current_name
        )
        
        # 如果用户确认修改且名称不为空
        if ok and new_name.strip():
            # 更新TabWidget上的标签名
            self.tab_widget.setTabText(index, new_name)
            
            # 更新内部存储的标签信息
            if 0 <= index < len(self.tabs):
                self.tabs[index]["name"] = new_name
                logger.info(f"模板名称已修改: '{current_name}' -> '{new_name}'")
                
                # 更新任务表格
                self._update_tasks_table()
                
                # 保存更新后的模板状态
                self._save_template_state()'''
    
    # 插入新方法
    insert_position = on_tab_close_match.end()
    content = content[:insert_position] + double_click_method + content[insert_position:]
    
    # 如果没有QInputDialog导入，添加导入
    import_pattern = r'from PyQt5\.QtWidgets import \(.*?QTabWidget.*?QMessageBox.*?\)'
    import_match = re.search(import_pattern, content, re.DOTALL)
    
    if import_match and 'QInputDialog' not in import_match.group():
        new_import = import_match.group().replace(')', ', QInputDialog)')
        content = content.replace(import_match.group(), new_import)
    
    # 备份原文件
    backup_file = file_path + '.double_click.bak'
    shutil.copy2(file_path, backup_file)
    print(f"已备份原文件到 {backup_file}")
    
    # 写入修改后的内容
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("已添加双击编辑功能")
    return True

if __name__ == '__main__':
    print("开始完整修复程序...")
    
    # 第一步：完全恢复原始文件
    if restore_original_files():
        print("文件已成功恢复")
    else:
        print("文件恢复失败")
        exit(1)
    
    # 第二步：添加双击编辑功能
    if add_double_click_edit():
        print("双击编辑功能已添加")
    else:
        print("添加双击编辑功能失败")
        exit(1)
    
    print("\n修复已完成！请尝试重新启动程序。") 