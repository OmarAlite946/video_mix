#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
帮助系统测试脚本
"""

import sys
import os
from pathlib import Path

# 确保可以导入src目录下的模块
src_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(src_dir))

try:
    from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout
    from src.utils.help_system import HelpSystem
    
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装所有依赖: pip install -r requirements.txt")
    sys.exit(1)

class TestHelpWidget(QWidget):
    """测试帮助系统的小部件"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("帮助系统测试")
        self.setGeometry(100, 100, 400, 300)
        self.initUI()
    
    def initUI(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 创建测试按钮
        btn_main_features = QPushButton("测试主要功能帮助")
        btn_main_features.clicked.connect(lambda: HelpSystem.show_help_dialog("main_features"))
        layout.addWidget(btn_main_features)
        
        btn_performance_tips = QPushButton("测试性能优化提示")
        btn_performance_tips.clicked.connect(lambda: HelpSystem.show_help_dialog("performance_tips"))
        layout.addWidget(btn_performance_tips)
        
        btn_bitrate = QPushButton("测试比特率帮助")
        btn_bitrate.clicked.connect(lambda: HelpSystem.show_help_dialog("bitrate"))
        layout.addWidget(btn_bitrate)
        
        btn_gpu = QPushButton("测试GPU加速帮助")
        btn_gpu.clicked.connect(lambda: HelpSystem.show_help_dialog("gpu_accel"))
        layout.addWidget(btn_gpu)
        
        btn_not_exist = QPushButton("测试不存在的帮助内容")
        btn_not_exist.clicked.connect(lambda: HelpSystem.show_help_dialog("not_exist"))
        layout.addWidget(btn_not_exist)
        
        self.setLayout(layout)

def main():
    """主函数"""
    app = QApplication(sys.argv)
    widget = TestHelpWidget()
    widget.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 