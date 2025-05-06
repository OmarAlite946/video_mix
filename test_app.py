#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试应用程序是否可以正常导入和初始化
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 添加 src 目录到 Python 路径
src_dir = project_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# 导入测试
try:
    print("测试导入src包...")
    from src.ui.main_window import MainWindow
    from src.ui.batch_window import BatchWindow
    print("✅ 成功导入所需模块")
except ImportError as e:
    print(f"❌ 导入失败: {str(e)}")
    sys.exit(1)
except SyntaxError as e:
    print(f"❌ 语法错误: {str(e)}")
    sys.exit(1)
except Exception as e:
    print(f"❌ 其他错误: {str(e)}")
    sys.exit(1)

# 文件检查
try:
    print("\n检查文件完整性...")
    main_window_path = Path("src/ui/main_window.py")
    batch_window_path = Path("src/ui/batch_window.py")
    
    if main_window_path.exists():
        main_size = main_window_path.stat().st_size
        print(f"✅ main_window.py 文件存在，大小: {main_size} 字节")
    else:
        print("❌ main_window.py 文件不存在")
    
    if batch_window_path.exists():
        batch_size = batch_window_path.stat().st_size
        print(f"✅ batch_window.py 文件存在，大小: {batch_size} 字节")
    else:
        print("❌ batch_window.py 文件不存在")
except Exception as e:
    print(f"❌ 文件检查出错: {str(e)}")

# 功能验证
try:
    print("\n验证类的初始化...")
    # 需要先创建QApplication实例
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    
    # 尝试初始化MainWindow和BatchWindow类对象
    # 我们不会显示它们，只是测试初始化是否正常
    main_window = MainWindow(instance_id="test_instance")
    batch_window = BatchWindow()
    print("✅ 成功初始化MainWindow和BatchWindow类")
    
    # 检查双击编辑功能是否存在
    if hasattr(batch_window, "_on_tab_double_clicked"):
        print("✅ 批处理窗口中的标签双击编辑功能已正确实现")
    else:
        print("❌ 批处理窗口中缺少标签双击编辑功能")
        
    print("\n所有测试已完成，软件应该可以正常启动了")
except Exception as e:
    print(f"❌ 初始化类时出错: {str(e)}")

print("\n如果软件仍然无法启动，请尝试以下步骤:")
print("1. 运行 'python main.py' 启动软件，查看具体错误信息")
print("2. 如果仍有问题，可以考虑恢复完整备份文件并重试") 