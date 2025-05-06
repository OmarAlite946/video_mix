#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
主窗口实现
"""

import os
import sys
import time
import json
import shutil
import subprocess
import threading
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple, Callable, Optional, Union

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
    QLabel, QPushButton, QLineEdit, QSpinBox, QDoubleSpinBox, 
    QProgressBar, QComboBox, QTabWidget, QGroupBox, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QCheckBox, QStatusBar, QAction, QMenu, QTextEdit, QDialog, QApplication, QStyle,
    QSplitter, QSizePolicy, QFrame, QDialogButtonBox, QTextBrowser
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QMetaObject, Q_ARG, Qt, QPoint, QRect
from PyQt5 import QtCore
from PyQt5.QtGui import QFont, QIcon, QPainter, QColor, QPen, QBrush, QMouseEvent

from src.utils.logger import get_logger
from src.utils.cache_config import CacheConfig
from src.hardware.system_analyzer import SystemAnalyzer
from src.hardware.gpu_config import GPUConfig
from src.utils.help_system import HelpSystem
from src.utils.file_utils import list_media_files, resolve_shortcut
from src.utils.user_settings import UserSettings  # 导入用户设置类

logger = get_logger()

# 添加自定义的可点击表格项类
class ExtractModeItem(QTableWidgetItem):
    """
    自定义表格项，用于显示和切换抽取模式
    """
    def __init__(self, text="", extract_mode="single_video", folder_path=""):
        super().__init__(text)
        self.extract_mode = extract_mode
        self.folder_path = folder_path
        self.status = "待处理"  # 可以是 "待处理", "处理中", "已完成", "错误", "已中止"
        
        # 从文本中提取状态信息
        if "处理中" in text:
            self.status = "处理中"
        elif "已完成" in text:
            self.status = "已完成"
        elif "错误" in text:
            self.status = "错误"
        elif "已中止" in text:
            self.status = "已中止"
        
        self._update_appearance()
    
    def _update_appearance(self):
        """更新表格项的外观以反映当前模式和状态"""
        mode_text = "多视频拼接" if self.extract_mode == "multi_video" else "单视频模式"
        
        # 根据状态设置显示文本
        if self.status == "处理中":
            self.setText(f"处理中 ({mode_text})")
            self.setForeground(QColor("#FF6600"))  # 橙色
            self.setToolTip(f"正在处理：{mode_text}")
        elif self.status in ["错误", "已中止"]:
            self.setText(f"{self.status} ({mode_text})")
            self.setForeground(QColor("#FF0000"))  # 红色
            self.setToolTip(f"状态：{self.status}\n当前模式：{mode_text}\n点击可切换模式")
        elif self.status == "已完成":
            self.setText(f"已完成 ({mode_text})")
            self.setForeground(QColor("#008800"))  # 绿色
            self.setToolTip(f"状态：已完成\n当前模式：{mode_text}\n点击可切换模式")
        else:  # 待处理
            # 更醒目的可点击指示
            if self.extract_mode == "multi_video":
                self.setText("▶ 多视频拼接 ◀ 点击切换")
                self.setForeground(QColor("#0000FF"))  # 蓝色
                self.setToolTip("当前模式：多视频拼接\n适用于：配音较长，视频较短时\n点击切换为单视频模式")
            else:
                self.setText("▶ 单视频模式 ◀ 点击切换")
                self.setForeground(QColor("#000000"))  # 黑色
                self.setToolTip("当前模式：单视频\n适用于：单段视频配音\n点击切换为多视频拼接模式")
    
    def set_status(self, status):
        """设置状态并更新外观"""
        self.status = status
        self._update_appearance()

class MainWindow(QMainWindow):
    """应用程序主窗口"""
    
    def __init__(self, parent=None, instance_id=None):
        super().__init__(parent)
        self.setWindowTitle("短视频批量混剪工具")
        self.resize(1200, 800)
        
        # 初始化状态变量
        self.processor = None
        self.processing_thread = None
        self.last_compose_count = 0  # 记录最后一次合成的视频数量
        
        # 初始化GPU配置
        self.gpu_config = GPUConfig()
        self.gpu_info = {}  # 存储GPU信息
        
        # 初始化缓存配置
        self.cache_config = CacheConfig()
        
        # 初始化用户设置 - 使用传入的instance_id
        self.user_settings = UserSettings(instance_id)
        
        # 初始化界面
        self._init_ui()
        
        # 创建菜单栏
        self._init_menubar()
        
        # 连接信号槽
        self._connect_signals()
        
        # 初始化状态栏
        self._init_statusbar()
        
        # 加载用户设置
        self._load_user_settings()
        
        # 检测GPU（软件启动时自动检测一次）
        self.detect_gpu()
    
    def _init_ui(self):
        """初始化UI界面"""
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 创建选项卡部件
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # 添加"合成任务"选项卡
        self.tab_compose = QWidget()
        self.tabs.addTab(self.tab_compose, "合成任务")
        
        # 创建"合成任务"选项卡的布局
        compose_layout = QHBoxLayout(self.tab_compose)
        compose_layout.setContentsMargins(3, 3, 3, 3)
        compose_layout.setSpacing(5)
        
        # =========================================
        # 左侧 - 材料列表区域 (占80%，原先是70%)
        # =========================================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(5)
        
        # 添加到主布局，设置宽度比例
        compose_layout.addWidget(left_widget, 80)  # 从70增加到80
        
        # 工具栏 - 更加紧凑的横向布局
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(5)
        
        # 合成控制区域（移到红框位置）
        compose_control_layout = QHBoxLayout()
        compose_control_layout.setContentsMargins(5, 5, 5, 5)
        compose_control_layout.setSpacing(10)
        
        # 文件夹名称和控制按钮水平排列
        folder_control_layout = QHBoxLayout()
        
        # 添加父文件夹名称标题显示（红框位置）
        self.parent_folder_title = QLabel("未选择文件夹")
        self.parent_folder_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.parent_folder_title.setStyleSheet("""
            font-size: 16px; 
            font-weight: bold; 
            color: #333333;
            padding-left: 8px;
        """)
        self.parent_folder_title.setMinimumHeight(40)
        
        # 合成按钮和状态
        self.btn_start_compose = QPushButton("开始合成")
        self.btn_start_compose.setMinimumWidth(100)
        self.btn_start_compose.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        self.btn_stop_compose = QPushButton("停止合成")
        self.btn_stop_compose.setMinimumWidth(100)
        self.btn_stop_compose.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        
        # 设置默认禁用停止按钮
        self.btn_stop_compose.setEnabled(False)
        
        # 进度条和状态文本
        progress_status_layout = QVBoxLayout()
        progress_status_layout.setContentsMargins(0, 0, 0, 0)
        progress_status_layout.setSpacing(2)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMinimumWidth(250)
        
        self.label_progress = QLabel("等待合成任务...")
        self.label_progress.setStyleSheet("color: #666666;")
        
        progress_status_layout.addWidget(self.progress_bar)
        progress_status_layout.addWidget(self.label_progress)
        
        # 添加文件夹名称到水平布局的左侧
        folder_control_layout.addWidget(self.parent_folder_title, 1)
        
        # 添加合成按钮和进度条到水平布局的右侧
        compose_buttons_layout = QHBoxLayout()
        compose_buttons_layout.addWidget(self.btn_start_compose)
        compose_buttons_layout.addWidget(self.btn_stop_compose)
        
        folder_control_layout.addLayout(compose_buttons_layout)
        folder_control_layout.addLayout(progress_status_layout)
        
        # 将整个合成控制区域添加到左侧布局
        left_layout.addLayout(folder_control_layout)
        
        # 创建分割器，允许用户调整素材列表的大小
        splitter = QSplitter(Qt.Vertical)
        left_layout.addWidget(splitter, 1)  # 让分割器占据剩余空间
        
        # 视频列表区域 - 添加到分割器
        list_group = QGroupBox("素材列表")
        list_layout = QVBoxLayout(list_group)
        
        # 创建视频列表表格
        self.video_table = QTableWidget()
        self.video_table.setColumnCount(6)
        self.video_table.setHorizontalHeaderLabels(["序号", "场景名称", "路径", "视频数量", "配音数量", "抽取模式"])
        self.video_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.video_table.verticalHeader().setVisible(False)
        self.video_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_table.setMinimumHeight(200)  # 设置最小高度
        
        # 设置表格允许右键菜单
        self.video_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.video_table.customContextMenuRequested.connect(self._show_folder_context_menu)
        
        # 连接表格点击事件
        self.video_table.cellClicked.connect(self._on_table_cell_clicked)
        
        list_layout.addWidget(self.video_table)
        
        # 素材操作按钮
        btn_layout = QHBoxLayout()
        list_layout.addLayout(btn_layout)
        
        self.btn_add_material = QPushButton("添加素材")
        self.btn_add_material.setVisible(False)  # 隐藏添加素材按钮
        self.btn_batch_import = QPushButton("批量导入")
        self.btn_refresh_material = QPushButton("刷新素材")
        self.btn_clear_material = QPushButton("清空素材")

        # 创建抽取模式数据存储字典
        self.folder_extract_modes = {}  # 用于存储每个文件夹的抽取模式，键为文件夹路径，值为抽取模式
        
        # 创建批量导入按钮和帮助按钮的布局
        batch_import_layout = QHBoxLayout()
        batch_import_layout.addWidget(self.btn_batch_import)
        HelpSystem.add_help_button(batch_import_layout, "batch_import")
        batch_import_layout.addStretch()
        
        btn_layout.addWidget(self.btn_add_material)
        btn_layout.addLayout(batch_import_layout)
        btn_layout.addWidget(self.btn_refresh_material)
        btn_layout.addWidget(self.btn_clear_material)
        
        # 将素材列表添加到分割器
        splitter.addWidget(list_group)
        
        # 合成设置区域
        settings_group = QGroupBox("合成设置")
        compose_layout.addWidget(settings_group)
        
        settings_layout = QFormLayout(settings_group)
        
        # 合成模式选择
        mode_layout = QHBoxLayout()
        self.combo_audio_mode = QComboBox()
        self.combo_audio_mode.addItems(["配音模式"])
        
        mode_layout.addWidget(QLabel("合成模式:"))
        mode_layout.addWidget(self.combo_audio_mode)
        mode_layout.addStretch()
        
        # 添加合成模式帮助按钮
        HelpSystem.add_help_button(mode_layout, "compose_mode")
        
        settings_layout.addRow(mode_layout)
        
        # 分辨率设置
        resolution_layout = QHBoxLayout()
        self.combo_resolution = QComboBox()
        self.combo_resolution.addItems(["竖屏 1080x1920", "横屏 1920x1080", "竖屏 720x1280", "横屏 1280x720"])
        
        resolution_layout.addWidget(QLabel("分辨率:"))
        resolution_layout.addWidget(self.combo_resolution)
        resolution_layout.addStretch()
        
        # 添加分辨率帮助按钮
        HelpSystem.add_help_button(resolution_layout, "resolution")
        
        settings_layout.addRow(resolution_layout)
        
        # 比特率设置
        bitrate_layout = QHBoxLayout()
        self.spin_bitrate = QSpinBox()
        self.spin_bitrate.setRange(1000, 20000)
        self.spin_bitrate.setValue(5000)
        self.spin_bitrate.setSuffix(" k")
        
        # 添加比特率范围说明标签
        bitrate_info_layout = QHBoxLayout()
        bitrate_info_label = QLabel("推荐值：抖音竖屏4000-8000k，横屏3000-6000k；720p(2000-4000k)，1080p(4000-8000k)，2K/1440p(8000-12000k)，4K/2160p(12000-15000k)")
        bitrate_info_label.setStyleSheet("color: #666666; font-size: 9pt;")
        bitrate_info_layout.addWidget(bitrate_info_label)
        bitrate_info_layout.addStretch()
        
        # 添加保持原画比特率选项
        self.chk_original_bitrate = QCheckBox("与原画一致")
        self.chk_original_bitrate.setChecked(False)  # 默认不选中
        self.chk_original_bitrate.toggled.connect(self._on_original_bitrate_toggled)
        
        # 确保比特率输入框初始是启用状态
        self.spin_bitrate.setEnabled(True)
        
        bitrate_layout.addWidget(QLabel("比特率:"))
        bitrate_layout.addWidget(self.spin_bitrate)
        bitrate_layout.addWidget(self.chk_original_bitrate)
        bitrate_layout.addStretch()
        
        # 添加比特率帮助按钮
        HelpSystem.add_help_button(bitrate_layout, "bitrate")
        
        # 添加"与原画一致"选项帮助按钮
        original_bitrate_layout = QHBoxLayout()
        original_bitrate_label = QLabel("与原画一致选项:")
        original_bitrate_label.setStyleSheet("color: #666666;")
        original_bitrate_layout.addWidget(original_bitrate_label)
        HelpSystem.add_help_button(original_bitrate_layout, "original_bitrate")
        original_bitrate_layout.addStretch()
        
        settings_layout.addRow(bitrate_layout)
        settings_layout.addRow(bitrate_info_layout)  # 添加比特率范围说明行
        settings_layout.addRow(original_bitrate_layout)  # 添加"与原画一致"帮助行
        
        # 转场效果设置
        transition_layout = QHBoxLayout()
        self.combo_transition = QComboBox()
        self.combo_transition.addItems([
            "不使用转场", "随机转场", "镜像翻转", "色相偏移", "光束扫描", 
            "像素化过渡", "轻微旋转缩放", "倒放闪回", "速度波动过渡", "分屏滑动"
        ])
        
        transition_layout.addWidget(QLabel("转场效果:"))
        transition_layout.addWidget(self.combo_transition)
        transition_layout.addStretch()
        
        # 添加转场效果帮助按钮
        HelpSystem.add_help_button(transition_layout, "transition")
        
        settings_layout.addRow(transition_layout)

        # GPU加速
        gpu_layout = QHBoxLayout()
        self.combo_gpu = QComboBox()
        self.combo_gpu.addItems(["自动检测", "Nvidia显卡", "AMD显卡", "Intel显卡", "CPU处理"])
        
        # 添加GPU检测按钮
        self.btn_detect_gpu = QPushButton("检测显卡")
        self.btn_detect_gpu.setToolTip("检测系统GPU并自动配置硬件加速")
        
        gpu_layout.addWidget(QLabel("显卡加速:"))
        gpu_layout.addWidget(self.combo_gpu)
        gpu_layout.addWidget(self.btn_detect_gpu)
        gpu_layout.addStretch()
        
        # 添加显卡加速帮助按钮
        HelpSystem.add_help_button(gpu_layout, "gpu_accel")
        
        settings_layout.addRow(gpu_layout)

        # 保存目录
        save_dir_layout = QHBoxLayout()
        self.edit_save_dir = QLineEdit()
        self.btn_browse_save_dir = QPushButton("选择")
        self.btn_open_save_dir = QPushButton("打开")
        
        save_dir_layout.addWidget(QLabel("保存目录:"))
        save_dir_layout.addWidget(self.edit_save_dir)
        save_dir_layout.addWidget(self.btn_browse_save_dir)
        save_dir_layout.addWidget(self.btn_open_save_dir)
        
        # 添加保存目录帮助按钮
        HelpSystem.add_help_button(save_dir_layout, "save_directory")
        
        settings_layout.addRow(save_dir_layout)
        
        # 添加编码模式选择
        encode_mode_layout = QHBoxLayout()
        self.combo_encode_mode = QComboBox()
        self.combo_encode_mode.addItems(["快速模式(不重编码)", "标准模式(重编码)"])
        self.combo_encode_mode.setCurrentIndex(0)  # 设置默认为快速模式(不重编码)
        
        encode_mode_layout.addWidget(QLabel("编码模式:"))
        encode_mode_layout.addWidget(self.combo_encode_mode)
        encode_mode_layout.addStretch()
        
        # 添加编码模式帮助按钮
        HelpSystem.add_help_button(encode_mode_layout, "encode_mode")
        
        settings_layout.addRow(encode_mode_layout)
        
        # 音频设置部分已移到下方的QGroupBox内
        
        
        # 添加水印设置
        watermark_group = QGroupBox("水印设置")
        watermark_layout = QVBoxLayout(watermark_group)
        
        # 创建一个水平布局，将所有水印设置平铺在一行
        watermark_controls_layout = QHBoxLayout()
        
        # 字体大小
        self.spin_watermark_size = QSpinBox()
        self.spin_watermark_size.setRange(10, 100)
        self.spin_watermark_size.setValue(24)
        self.spin_watermark_size.setSuffix(" px")
        size_layout = QVBoxLayout()
        size_layout.addWidget(QLabel("字体大小:"))
        size_layout.addWidget(self.spin_watermark_size)
        watermark_controls_layout.addLayout(size_layout)
        
        # 字体颜色
        self.combo_watermark_color = QComboBox()
        self.combo_watermark_color.addItems(["白色", "黑色", "红色", "绿色", "蓝色", "黄色"])
        self.watermark_color = "#FFFFFF"  # 默认白色
        color_layout = QVBoxLayout()
        color_layout.addWidget(QLabel("字体颜色:"))
        
        color_buttons_layout = QHBoxLayout()
        color_buttons_layout.addWidget(self.combo_watermark_color)
        
        self.btn_custom_color = QPushButton("自定义")
        self.btn_custom_color.setMaximumWidth(60)
        color_buttons_layout.addWidget(self.btn_custom_color)
        
        color_layout.addLayout(color_buttons_layout)
        watermark_controls_layout.addLayout(color_layout)
        
        # 水印位置
        self.combo_watermark_position = QComboBox()
        self.combo_watermark_position.addItems(["右上角", "左上角", "右下角", "左下角", "中心"])
        position_layout = QVBoxLayout()
        position_layout.addWidget(QLabel("水印位置:"))
        position_layout.addWidget(self.combo_watermark_position)
        watermark_controls_layout.addLayout(position_layout)
        
        # 位置微调
        adjust_layout = QVBoxLayout()
        adjust_layout.addWidget(QLabel("位置微调:"))
        
        adjust_spinners_layout = QHBoxLayout()
        
        # X轴微调
        self.spin_pos_x = QSpinBox()
        self.spin_pos_x.setRange(-100, 100)
        self.spin_pos_x.setValue(0)
        self.spin_pos_x.setSuffix(" px")
        self.spin_pos_x.setMaximumWidth(70)
        
        # Y轴微调
        self.spin_pos_y = QSpinBox()
        self.spin_pos_y.setRange(-100, 100)
        self.spin_pos_y.setValue(0)
        self.spin_pos_y.setSuffix(" px")
        self.spin_pos_y.setMaximumWidth(70)
        
        adjust_spinners_layout.addWidget(QLabel("X:"))
        adjust_spinners_layout.addWidget(self.spin_pos_x)
        adjust_spinners_layout.addWidget(QLabel("Y:"))
        adjust_spinners_layout.addWidget(self.spin_pos_y)
        
        adjust_layout.addLayout(adjust_spinners_layout)
        watermark_controls_layout.addLayout(adjust_layout)
        
        # 重置和预览按钮
        buttons_layout = QVBoxLayout()
        buttons_layout.addWidget(QLabel("操作:"))
        
        action_buttons_layout = QHBoxLayout()
        
        # 重置按钮
        self.reset_btn = QPushButton("重置位置")
        self.reset_btn.setToolTip("将水印位置重置到默认值")
        action_buttons_layout.addWidget(self.reset_btn)
        
        # 预览按钮
        self.btn_preview_watermark = QPushButton("预览效果")
        self.btn_preview_watermark.setIcon(QApplication.style().standardIcon(QStyle.SP_FileDialogContentsView))
        self.btn_preview_watermark.setToolTip("打开水印预览对话框，可视化调整水印位置")
        self.btn_preview_watermark.setStyleSheet("""
            QPushButton {
                background-color: #5C85D6;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #4A6FB8;
            }
        """)
        action_buttons_layout.addWidget(self.btn_preview_watermark)
        
        buttons_layout.addLayout(action_buttons_layout)
        watermark_controls_layout.addLayout(buttons_layout)
        
        # 启用水印选项
        enable_watermark_layout = QHBoxLayout()
        self.chk_enable_watermark = QCheckBox("启用时间戳水印")
        self.chk_enable_watermark.setChecked(False)
        enable_watermark_layout.addWidget(self.chk_enable_watermark)
        
        # 添加水印帮助按钮
        HelpSystem.add_help_button(enable_watermark_layout, "watermark")
        enable_watermark_layout.addStretch()
        watermark_layout.addLayout(enable_watermark_layout)
        
        watermark_layout.addLayout(watermark_controls_layout)
        
        # 水印自定义文字
        watermark_text_layout = QHBoxLayout()
        self.edit_watermark_prefix = QLineEdit()
        self.edit_watermark_prefix.setPlaceholderText("自定义文字（可选）")
        watermark_text_layout.addWidget(QLabel("自定义前缀:"))
        watermark_text_layout.addWidget(self.edit_watermark_prefix)
        watermark_layout.addLayout(watermark_text_layout)
        
        # 水印预览控件不直接创建，在需要时通过对话框显示
        self.watermark_preview = None
        
        # 添加水印设置到主设置布局
        settings_layout.addRow(watermark_group)
        
        # 缓存设置
        cache_group = QGroupBox("缓存设置")
        cache_dir_layout = QHBoxLayout()
        self.edit_cache_dir = QLineEdit()
        self.edit_cache_dir.setText(self.cache_config.get_cache_dir())
        self.btn_browse_cache_dir = QPushButton("选择")
        self.btn_open_cache_dir = QPushButton("打开")
        self.btn_clear_cache = QPushButton("清理缓存")
        
        cache_dir_layout.addWidget(QLabel("缓存目录:"))
        cache_dir_layout.addWidget(self.edit_cache_dir)
        cache_dir_layout.addWidget(self.btn_browse_cache_dir)
        cache_dir_layout.addWidget(self.btn_open_cache_dir)
        cache_dir_layout.addWidget(self.btn_clear_cache)
        
        # 添加缓存目录帮助按钮
        HelpSystem.add_help_button(cache_dir_layout, "cache_directory")
        
        settings_layout.addRow(cache_dir_layout)
        
        # 生成数量设置
        count_layout = QHBoxLayout()
        self.spin_generate_count = QSpinBox()
        self.spin_generate_count.setRange(1, 500)
        self.spin_generate_count.setValue(20)
        self.spin_generate_count.setSuffix(" 个")
        
        count_layout.addWidget(QLabel("生成数量:"))
        count_layout.addWidget(self.spin_generate_count)
        count_layout.addStretch()
        
        # 添加生成数量帮助按钮
        HelpSystem.add_help_button(count_layout, "generate_count")
        
        settings_layout.addRow(count_layout)
        
        # 音频部分
        audio_group = QGroupBox("音频设置")
        audio_layout = QVBoxLayout(audio_group)
        
        # 音量设置
        volume_layout = QHBoxLayout()
        self.spin_voice_volume = QDoubleSpinBox()
        self.spin_voice_volume.setRange(0, 5)
        self.spin_voice_volume.setValue(1.0)
        self.spin_voice_volume.setSingleStep(0.1)
        self.spin_voice_volume.setSuffix(" 倍")
        
        self.spin_bgm_volume = QDoubleSpinBox()
        self.spin_bgm_volume.setRange(0, 5)
        self.spin_bgm_volume.setValue(0.5)
        self.spin_bgm_volume.setSingleStep(0.1)
        self.spin_bgm_volume.setSuffix(" 倍")
        
        volume_layout.addWidget(QLabel("配音音量:"))
        volume_layout.addWidget(self.spin_voice_volume)
        volume_layout.addWidget(QLabel("背景音量:"))
        volume_layout.addWidget(self.spin_bgm_volume)
        volume_layout.addStretch()
        
        # 添加音量设置帮助按钮
        HelpSystem.add_help_button(volume_layout, "volume_settings")
        
        audio_layout.addLayout(volume_layout)
        
        # 背景音乐设置
        bgm_layout = QHBoxLayout()
        self.edit_bgm_path = QLineEdit()
        self.btn_browse_bgm = QPushButton("选择")
        self.btn_play_bgm = QPushButton("播放")
        
        bgm_layout.addWidget(QLabel("背景音乐:"))
        bgm_layout.addWidget(self.edit_bgm_path)
        bgm_layout.addWidget(self.btn_browse_bgm)
        bgm_layout.addWidget(self.btn_play_bgm)
        bgm_layout.addStretch()
        
        # 添加背景音乐帮助按钮
        HelpSystem.add_help_button(bgm_layout, "background_music")
        
        audio_layout.addLayout(bgm_layout)
        
        # 添加音频设置到主设置布局
        settings_layout.addRow(audio_group)
    
    def _init_menubar(self):
        """初始化菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        
        view_log_action = file_menu.addAction("查看日志文件")
        view_log_action.triggered.connect(self.view_log_file)
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction("退出")
        exit_action.triggered.connect(self.close)
        
        # 工具菜单
        tools_menu = menubar.addMenu("工具")
        
        gpu_test_action = tools_menu.addAction("GPU加速测试")
        gpu_test_action.triggered.connect(self.run_gpu_test)
        
        gpu_status_action = tools_menu.addAction("显示GPU状态")
        gpu_status_action.triggered.connect(self.show_gpu_status)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        
        # 添加主要功能菜单项
        main_features_action = help_menu.addAction("主要功能")
        main_features_action.triggered.connect(self.show_main_features)
        
        # 添加性能优化提示菜单项
        performance_tips_action = help_menu.addAction("性能优化提示")
        performance_tips_action.triggered.connect(self.show_performance_tips)
        
        # 添加抽取模式说明菜单项
        extract_mode_action = help_menu.addAction("抽取模式说明")
        extract_mode_action.triggered.connect(self.show_extract_mode_guide)
        
        ffmpeg_guide_action = help_menu.addAction("安装FFmpeg指南")
        ffmpeg_guide_action.triggered.connect(self.show_ffmpeg_guide)
        
        ffmpeg_config_action = help_menu.addAction("配置FFmpeg路径")
        ffmpeg_config_action.triggered.connect(self.config_ffmpeg_path)
        
        about_action = help_menu.addAction("关于")
        about_action.triggered.connect(self.show_about)
    
    def show_main_features(self):
        """显示主要功能帮助页面"""
        HelpSystem.show_help_dialog("main_features")
    
    def show_performance_tips(self):
        """显示性能优化提示帮助页面"""
        HelpSystem.show_help_dialog("performance_tips")
    
    def show_ffmpeg_guide(self):
        """显示FFmpeg安装指南"""
        instruction_text = """
视频合成需要FFmpeg工具。如果您在使用本软件时遇到"FFmpeg不可用"的错误，请按照以下步骤安装FFmpeg:

1. 下载FFmpeg:
   访问 https://ffmpeg.org/download.html 或者
   https://github.com/BtbN/FFmpeg-Builds/releases 下载Windows版本

2. 解压下载的文件到一个固定位置
   (例如: C:\\FFmpeg)

3. 将FFmpeg的bin目录添加到系统环境变量Path中:
   - 右键点击"此电脑" -> 属性 -> 高级系统设置 -> 环境变量
   - 在"系统变量"中找到"Path"，点击"编辑"
   - 点击"新建"，添加FFmpeg的bin目录路径(例如: C:\\FFmpeg\\bin)
   - 点击"确定"保存所有更改

4. 重启电脑或所有命令行窗口

5. 重启本软件后重试

FFmpeg是一个功能强大的视频处理工具，它是本软件处理视频必不可少的组件。
        """
        
        guide_dialog = QMessageBox(self)
        guide_dialog.setIcon(QMessageBox.Information)
        guide_dialog.setWindowTitle("FFmpeg安装指南")
        guide_dialog.setText("如何安装FFmpeg")
        guide_dialog.setInformativeText(instruction_text)
        guide_dialog.setStandardButtons(QMessageBox.Ok)
        
        # 设置宽度
        guide_dialog.setMinimumWidth(600)
        
        guide_dialog.exec_()
    
    def show_about(self):
        """显示关于对话框"""
        about_text = """
短视频批量混剪工具

版本: 1.0.0

一款强大的视频批量混剪工具，可以从不同场景素材中随机组合生成多个视频作品。

功能包括:
- 批量导入素材
- 实时进度显示
- 多种转场效果
- 音视频处理
- 背景音乐支持

© 2025 All Rights Reserved
        """
        
        QMessageBox.about(self, "关于", about_text)
    
    def _connect_signals(self):
        """连接信号和槽"""
        # 素材操作
        self.btn_add_material.clicked.connect(self.on_add_material)
        self.btn_batch_import.clicked.connect(self.on_batch_import)
        self.btn_refresh_material.clicked.connect(self.on_refresh_material)
        self.btn_clear_material.clicked.connect(self.on_clear_material)
        
        # 目录浏览
        self.btn_browse_save_dir.clicked.connect(self.on_browse_save_dir)
        self.btn_open_save_dir.clicked.connect(self.on_open_save_dir)
        
        # 背景音乐
        self.btn_browse_bgm.clicked.connect(self.on_browse_bgm)
        self.btn_play_bgm.clicked.connect(self.on_play_bgm)
        
        # 水印设置
        self.btn_custom_color.clicked.connect(self.on_choose_custom_color)
        self.combo_watermark_color.currentTextChanged.connect(self.on_watermark_color_changed)
        self.combo_watermark_position.currentTextChanged.connect(self.on_watermark_position_changed)
        self.spin_watermark_size.valueChanged.connect(self.on_watermark_size_changed)
        self.edit_watermark_prefix.textChanged.connect(self.on_watermark_prefix_changed)
        self.spin_pos_x.valueChanged.connect(self.on_pos_x_changed)
        self.spin_pos_y.valueChanged.connect(self.on_pos_y_changed)
        self.reset_btn.clicked.connect(self.on_reset_watermark_position)
        
        # 添加预览水印按钮的连接
        self.btn_preview_watermark.clicked.connect(self.on_preview_watermark)
        
        # 连接水印预览控件的位置变化信号（如果存在）
        if hasattr(self, "watermark_preview") and self.watermark_preview is not None:
            self.watermark_preview.positionChanged.connect(self.on_preview_position_changed)
        
        # 缓存目录
        self.btn_browse_cache_dir.clicked.connect(self.on_browse_cache_dir)
        self.btn_open_cache_dir.clicked.connect(self.on_open_cache_dir)
        self.btn_clear_cache.clicked.connect(self.on_clear_cache)
        
        # GPU检测
        self.btn_detect_gpu.clicked.connect(self.detect_gpu)
        
        # 合成控制
        self.btn_start_compose.clicked.connect(self.on_start_compose)
        self.btn_stop_compose.clicked.connect(self.on_stop_compose)
        
        # 连接设置值变化的信号到设置保存方法
        # 分辨率
        self.combo_resolution.currentTextChanged.connect(
            lambda text: self.user_settings.set_setting("resolution", text)
        )
        
        # 比特率
        self.spin_bitrate.valueChanged.connect(
            lambda value: self.user_settings.set_setting("bitrate", value)
        )
        
        # 原始比特率
        self.chk_original_bitrate.toggled.connect(
            lambda checked: self.user_settings.set_setting("original_bitrate", checked)
        )
        
        # 转场效果
        self.combo_transition.currentTextChanged.connect(
            lambda text: self.user_settings.set_setting("transition", text)
        )
        
        # GPU选择
        self.combo_gpu.currentTextChanged.connect(
            lambda text: self.user_settings.set_setting("gpu", text)
        )
        
        # 水印启用状态
        self.chk_enable_watermark.toggled.connect(
            lambda checked: self.user_settings.set_setting("watermark_enabled", checked)
        )
        
        # 水印前缀
        self.edit_watermark_prefix.textChanged.connect(
            lambda text: self.user_settings.set_setting("watermark_prefix", text)
        )
        
        # 水印大小
        self.spin_watermark_size.valueChanged.connect(
            lambda value: self.user_settings.set_setting("watermark_size", value)
        )
        
        # 水印位置
        self.combo_watermark_position.currentTextChanged.connect(
            lambda text: self.user_settings.set_setting("watermark_position", text)
        )
        
        # 水印坐标
        self.spin_pos_x.valueChanged.connect(
            lambda value: self.user_settings.set_setting("watermark_pos_x", value)
        )
        
        self.spin_pos_y.valueChanged.connect(
            lambda value: self.user_settings.set_setting("watermark_pos_y", value)
        )
        
        # 音量设置
        self.spin_voice_volume.valueChanged.connect(
            lambda value: self.user_settings.set_setting("voice_volume", value)
        )
        
        self.spin_bgm_volume.valueChanged.connect(
            lambda value: self.user_settings.set_setting("bgm_volume", value)
        )
        
        # 生成数量
        self.spin_generate_count.valueChanged.connect(
            lambda value: self.user_settings.set_setting("generate_count", value)
        )
        
        # 编码模式
        self.combo_encode_mode.currentTextChanged.connect(
            lambda text: self.user_settings.set_setting("encode_mode", text)
        )
    
    @pyqtSlot()
    def on_add_material(self):
        """添加素材"""
        # 弹出文件夹选择对话框
        folder = QFileDialog.getExistingDirectory(
            self, "选择素材文件夹", "", QFileDialog.ShowDirsOnly
        )
        
        if folder:
            # 这里添加素材分析和处理逻辑
            folder_name = os.path.basename(folder)
            
            # 添加到表格
            row_count = self.video_table.rowCount()
            self.video_table.insertRow(row_count)
            
            # 设置表格项
            self.video_table.setItem(row_count, 0, QTableWidgetItem(str(row_count + 1)))
            self.video_table.setItem(row_count, 1, QTableWidgetItem(folder_name))
            self.video_table.setItem(row_count, 2, QTableWidgetItem(folder))
            self.video_table.setItem(row_count, 3, QTableWidgetItem("0"))  # 暂时设为0
            self.video_table.setItem(row_count, 4, QTableWidgetItem("0"))  # 暂时设为0
            
            # 使用ExtractModeItem代替普通的QTableWidgetItem
            extract_mode = self.folder_extract_modes.get(folder, "single_video")
            status_item = ExtractModeItem("", extract_mode, folder)
            status_item.set_status("就绪")
            self.video_table.setItem(row_count, 5, status_item)
            
            # 保存设置
            self._save_user_settings()
            
            QMessageBox.information(self, "添加素材", f"已添加素材文件夹: {folder_name}")
    
    @pyqtSlot()
    def on_batch_import(self):
        """批量导入素材文件夹"""
        # 获取上次导入的文件夹路径作为默认路径
        last_import_folder = self.user_settings.get_setting("import_folder", "")
        
        # 选择根目录，如果有上次的路径则使用它作为初始目录
        root_dir = QFileDialog.getExistingDirectory(
            self, 
            "选择素材根目录", 
            last_import_folder
        )
        
        if not root_dir:
            return
        
        # 保存导入的文件夹路径到用户设置
        self.user_settings.set_setting("import_folder", root_dir)
        
        # 清空当前列表
        self.video_table.setRowCount(0)
        
        # 更新界面显示的父文件夹名称（只显示文件夹名）
        folder_name = os.path.basename(root_dir)
        self.parent_folder_title.setText(folder_name)
        
        # 使用_import_material_folder方法导入文件夹
        self._import_material_folder(root_dir)
        
        # 导入完成后保存设置，确保记住素材列表
        self._save_user_settings()
        
        # 显示导入结果
        imported_rows = self.video_table.rowCount()
        if imported_rows > 0:
            QMessageBox.information(
                self, 
                "批量导入完成", 
                f"成功导入 {imported_rows} 个素材文件夹"
            )
        else:
            QMessageBox.warning(
                self, 
                "批量导入", 
                f"未找到符合条件的素材文件夹。请确保子文件夹中包含'视频'或'配音'文件夹，且其中有媒体文件"
            )
    
    @pyqtSlot()
    def on_refresh_material(self):
        """刷新素材列表"""
        # 获取当前选中的文件夹路径
        last_import_folder = self.user_settings.get_setting("import_folder", "")
        
        if not last_import_folder or not os.path.exists(last_import_folder):
            QMessageBox.warning(self, "刷新素材", "请先选择有效的素材根目录")
            return
            
        # 清空表格
        self.video_table.setRowCount(0)
        
        # 刷新导入
        self._import_material_folder(last_import_folder)
        
        # 保存设置
        self._save_user_settings()
        
        # 显示刷新结果
        imported_rows = self.video_table.rowCount()
        QMessageBox.information(
            self, 
            "刷新素材", 
            f"素材列表已刷新，当前有 {imported_rows} 个素材文件夹"
        )
    
    @pyqtSlot()
    def on_clear_material(self):
        """清空素材"""
        if self.video_table.rowCount() > 0:
            reply = QMessageBox.question(self, "清空素材", "确定要清空所有添加的素材吗？",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.video_table.setRowCount(0)
                self.parent_folder_title.setText("未选择文件夹")
                # 清空抽取模式字典
                self.folder_extract_modes.clear()
                # 保存设置变更
                self._save_user_settings()
                logger.info("素材列表已清空")
    
    @pyqtSlot()
    def on_browse_save_dir(self):
        """浏览并选择保存目录"""
        # 获取当前保存目录作为初始目录
        current_dir = self.edit_save_dir.text()
        
        # 如果当前没有设置目录，则使用上次保存的目录
        if not current_dir:
            current_dir = self.user_settings.get_setting("save_dir", "")
        
        save_dir = QFileDialog.getExistingDirectory(
            self, 
            "选择保存目录", 
            current_dir
        )
        
        if save_dir:
            self.edit_save_dir.setText(save_dir)
            # 保存保存目录到用户设置
            self.user_settings.set_setting("save_dir", save_dir)
    
    @pyqtSlot()
    def on_open_save_dir(self):
        """打开保存目录"""
        save_dir = self.edit_save_dir.text()
        
        if save_dir and os.path.exists(save_dir):
            # 打开资源管理器查看目录
            if sys.platform == 'win32':
                os.startfile(save_dir)
            elif sys.platform == 'darwin':  # macOS
                os.system(f'open "{save_dir}"')
            else:  # Linux
                os.system(f'xdg-open "{save_dir}"')
        else:
            QMessageBox.warning(self, "打开目录", "保存目录不存在，请先选择有效的保存目录")
    
    @pyqtSlot()
    def on_browse_bgm(self):
        """浏览并选择背景音乐"""
        # 获取当前BGM路径的目录作为初始目录
        current_bgm = self.edit_bgm_path.text()
        initial_dir = ""
        
        if current_bgm and os.path.exists(current_bgm):
            initial_dir = os.path.dirname(current_bgm)
        else:
            # 如果当前没有设置或路径不存在，则使用上次保存的BGM目录
            last_bgm = self.user_settings.get_setting("bgm_path", "")
            if last_bgm and os.path.exists(last_bgm):
                initial_dir = os.path.dirname(last_bgm)
        
        bgm_file, _ = QFileDialog.getOpenFileName(
            self, 
            "选择背景音乐", 
            initial_dir, 
            "音频文件 (*.mp3 *.wav *.ogg *.flac *.m4a);;所有文件 (*.*)"
        )
        
        if bgm_file:
            self.edit_bgm_path.setText(bgm_file)
            # 保存BGM路径到用户设置
            self.user_settings.set_setting("bgm_path", bgm_file)
    
    @pyqtSlot()
    def on_play_bgm(self):
        """播放背景音乐"""
        bgm_path = self.edit_bgm_path.text()
        
        if not bgm_path:
            QMessageBox.warning(self, "播放音乐", "请先选择背景音乐文件")
            return
            
        if not os.path.exists(bgm_path):
            QMessageBox.warning(self, "播放音乐", f"文件不存在: {bgm_path}\n请确认路径是否正确")
            return
            
        try:
            # 使用系统默认程序播放音乐
            if sys.platform == 'win32':
                os.startfile(bgm_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.run(['open', bgm_path], check=True)
            else:  # Linux
                subprocess.run(['xdg-open', bgm_path], check=True)
                
            QMessageBox.information(self, "播放音乐", f"正在播放: {os.path.basename(bgm_path)}")
        except Exception as e:
            QMessageBox.warning(self, "播放错误", f"无法播放音乐: {str(e)}")
    
    def _update_progress(self, message, percent):
        """
        更新进度显示
        
        Args:
            message: 进度消息
            percent: 进度百分比 (0-100)
        """
        # 使用Qt的信号槽机制确保在主线程中更新UI
        QtCore.QMetaObject.invokeMethod(
            self,
            "_do_update_progress",
            QtCore.Qt.QueuedConnection,
            QtCore.Q_ARG(str, message),
            QtCore.Q_ARG(float, percent)
        )
    
    @QtCore.pyqtSlot(str, float)
    def _do_update_progress(self, message, percent):
        """在主线程中实际执行UI更新"""
        # 防抖动：如果进度变化太小，不更新UI
        current_percent = self.progress_bar.value()
        if abs(current_percent - percent) < 1 and message == self.label_progress.text():
            return
            
        self.label_progress.setText(message)
        self.progress_bar.setValue(int(percent))
    
    def detect_gpu(self):
        """检测GPU并更新UI - 优化版"""
        # 更新状态栏
        self.status_label.setText("正在检测显卡...")
        self.gpu_status_label.setText("GPU: 检测中...")
        
        # 禁用检测按钮，防止重复点击
        self.btn_detect_gpu.setEnabled(False)
        
        # 在单独线程中执行GPU检测，避免阻塞UI
        import threading
        import time
        import logging
        
        def do_detect_gpu():
            try:
                # 记录开始时间
                start_time = time.time()
                
                # 第一阶段：快速检测 - 只检测基本GPU信息，不进行深度检测
                analyzer = SystemAnalyzer(deep_gpu_detection=False)
                system_info = analyzer.analyze()
                self.gpu_info = system_info.get('gpu', {})
                
                # 记录基本检测完成时间
                basic_detection_time = time.time() - start_time
                logging.info(f"基本GPU检测完成，耗时: {basic_detection_time:.3f} 秒")
                
                # 检查是否找到GPU
                if self.gpu_info.get('available', False):
                    # 先用基本信息快速更新UI
                    QtCore.QMetaObject.invokeMethod(
                        self, 
                        "_update_basic_gpu_ui", 
                        QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(bool, True)
                    )
                    
                    # 第二阶段：深度检测 - 检测硬件加速能力和兼容性
                    # 这个过程较慢，但已经有基本信息显示了
                    deep_start_time = time.time()
                    analyzer = SystemAnalyzer(deep_gpu_detection=True)
                    system_info = analyzer.analyze()
                    self.gpu_info = system_info.get('gpu', {})
                    
                    # 记录深度检测完成时间
                    deep_detection_time = time.time() - deep_start_time
                    logging.info(f"深度GPU检测完成，耗时: {deep_detection_time:.3f} 秒")
                    
                    # 尝试自动配置GPU
                    config_start_time = time.time()
                    gpu_configured = self.gpu_config.detect_and_set_optimal_config()
                    config_time = time.time() - config_start_time
                    logging.info(f"GPU配置完成，耗时: {config_time:.3f} 秒")
                    
                    # 更新完整UI
                    QtCore.QMetaObject.invokeMethod(
                        self, 
                        "_update_gpu_ui", 
                        QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(bool, True),
                        QtCore.Q_ARG(bool, gpu_configured)
                    )
                else:
                    # 没有GPU，直接更新UI
                    QtCore.QMetaObject.invokeMethod(
                        self, 
                        "_update_gpu_ui", 
                        QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(bool, False),
                        QtCore.Q_ARG(bool, False)
                    )
                
                # 记录总时间
                total_time = time.time() - start_time
                logging.info(f"GPU检测和配置总耗时: {total_time:.3f} 秒")
            except Exception as e:
                # 在主线程中显示错误
                QtCore.QMetaObject.invokeMethod(
                    self, 
                    "_show_gpu_detection_error", 
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, str(e))
                )
            finally:
                # 重新启用检测按钮
                QtCore.QMetaObject.invokeMethod(
                    self, 
                    "_enable_gpu_button", 
                    QtCore.Qt.QueuedConnection
                )
        
        # 启动检测线程
        detection_thread = threading.Thread(target=do_detect_gpu, daemon=True)
        detection_thread.start()
    
    @QtCore.pyqtSlot(bool)
    def _update_basic_gpu_ui(self, gpu_available):
        """快速更新基本GPU信息"""
        if gpu_available:
            # 获取基本GPU信息
            primary_gpu = self.gpu_info.get('primary_gpu', '未知')
            primary_vendor = self.gpu_info.get('primary_vendor', '未知')
            
            # 更新状态栏 - 只显示基本信息
            self.gpu_status_label.setText(f"GPU: {primary_gpu}")
            self.status_label.setText("检测到显卡，正在分析硬件加速能力...")
            
            # 更新下拉框
            if 'nvidia' in primary_vendor.lower():
                self.combo_gpu.setCurrentText("Nvidia显卡")
            elif 'amd' in primary_vendor.lower():
                self.combo_gpu.setCurrentText("AMD显卡")
            elif 'intel' in primary_vendor.lower():
                self.combo_gpu.setCurrentText("Intel显卡")
            else:
                self.combo_gpu.setCurrentText("自动检测")
        else:
            # 未检测到GPU
            self.combo_gpu.setCurrentText("CPU处理")
            self.gpu_status_label.setText("GPU: 未检测到")
            self.status_label.setText("未检测到GPU，将使用CPU处理")
    
    @QtCore.pyqtSlot()
    def _enable_gpu_button(self):
        """重新启用GPU检测按钮"""
        self.btn_detect_gpu.setEnabled(True)
    
    @QtCore.pyqtSlot(str)
    def _show_gpu_detection_error(self, error):
        """显示GPU检测错误"""
        self.status_label.setText("就绪")
        self.gpu_status_label.setText("GPU: 检测失败")
        QMessageBox.warning(self, "GPU检测错误", f"检测GPU时发生错误:\n{error}")
    
    @QtCore.pyqtSlot(bool, bool)
    def _update_gpu_ui(self, gpu_available, gpu_configured):
        """更新GPU相关的UI，针对远程控制环境优化"""
        if gpu_available:
            # 获取GPU信息
            primary_gpu = self.gpu_info.get('primary_gpu', '未知')
            primary_vendor = self.gpu_info.get('primary_vendor', '未知')
            
            # 如果是远程显示驱动，尝试从gpu_config获取正确的信息
            if 'oray' in primary_vendor.lower() or 'unknown' in primary_vendor.lower() or 'remote' in primary_vendor.lower():
                gpu_name, gpu_vendor = self.gpu_config.get_gpu_info()
                if gpu_vendor != '未知' and 'NVIDIA' in gpu_vendor:
                    primary_gpu = gpu_name
                    primary_vendor = gpu_vendor
            
            # 更新下拉框
            if 'nvidia' in primary_vendor.lower():
                self.combo_gpu.setCurrentText("Nvidia显卡")
            elif 'amd' in primary_vendor.lower():
                self.combo_gpu.setCurrentText("AMD显卡")
            elif 'intel' in primary_vendor.lower():
                self.combo_gpu.setCurrentText("Intel显卡")
            else:
                self.combo_gpu.setCurrentText("自动检测")
            
            # 更新状态栏
            if gpu_configured:
                gpu_name, gpu_vendor = self.gpu_config.get_gpu_info()
                encoder = self.gpu_config.get_encoder()
                self.gpu_status_label.setText(f"GPU: {gpu_name} | 编码器: {encoder}")
                self.status_label.setText(f"已启用GPU硬件加速")
                
                # 显示成功消息
                QMessageBox.information(
                    self, 
                    "GPU检测成功", 
                    f"已检测到GPU并启用硬件加速:\n\n"
                    f"GPU: {primary_gpu} ({primary_vendor})\n"
                    f"编码器: {encoder}"
                )
            else:
                # 检查是否是FFmpeg不可用导致的问题
                ffmpeg_issue = False
                if hasattr(self, 'gpu_info') and 'ffmpeg_compatibility' in self.gpu_info:
                    compat_info = self.gpu_info.get('ffmpeg_compatibility', {})
                    if 'error' in compat_info and "FFmpeg不可用" in compat_info.get('error', ''):
                        ffmpeg_issue = True
                
                if ffmpeg_issue:
                    # 尝试自动解决FFmpeg问题
                    self._try_fix_ffmpeg(primary_gpu, primary_vendor)
                    return
                
                # 检查是否是在远程会话中（可能仍然可以使用NVIDIA加速）
                if 'oray' in primary_vendor.lower() or 'unknown' in primary_vendor.lower() or 'remote' in primary_vendor.lower():
                    # 尝试最后一次通过nvidia-smi检测
                    import subprocess
                    try:
                        process = subprocess.Popen(['nvidia-smi'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
                        try:
                            stdout, stderr = process.communicate(timeout=3)
                            output = stdout.decode('utf-8', errors='ignore')
                            
                            if 'NVIDIA-SMI' in output and 'Driver Version' in output:
                                # 成功检测到NVIDIA GPU，手动配置
                                self.gpu_config._set_nvidia_config_direct()
                                gpu_name, gpu_vendor = self.gpu_config.get_gpu_info()
                                encoder = self.gpu_config.get_encoder()
                                
                                # 更新UI
                                self.combo_gpu.setCurrentText("Nvidia显卡")
                                self.gpu_status_label.setText(f"GPU: {gpu_name} | 编码器: {encoder}")
                                self.status_label.setText(f"已启用GPU硬件加速 (远程会话模式)")
                                
                                # 显示成功消息
                                QMessageBox.information(
                                    self, 
                                    "GPU检测成功", 
                                    f"已在远程会话中检测到NVIDIA GPU并启用硬件加速:\n\n"
                                    f"GPU: {gpu_name}\n"
                                    f"编码器: {encoder}"
                                )
                                return
                        except Exception:
                            pass
                    except Exception:
                        pass
                
                # 常规处理方式
                self.gpu_status_label.setText(f"GPU: {primary_gpu} | 不支持硬件加速")
                self.status_label.setText("GPU检测完成，但未启用硬件加速")
                
                # 显示警告消息
                QMessageBox.warning(
                    self, 
                    "GPU检测完成", 
                    f"已检测到GPU，但未能配置硬件加速:\n\n"
                    f"GPU: {primary_gpu} ({primary_vendor})\n\n"
                    f"可能原因:\n"
                    f"- FFmpeg不支持该GPU的硬件加速\n"
                    f"- 驱动程序版本过旧\n"
                    f"- 系统兼容性问题\n"
                    f"- 远程会话限制\n\n"
                    f"如果您使用远程控制软件(如向日葵)，请尝试断开连接后在本地运行。\n\n"
                    f"将使用CPU模式处理视频。"
                )
        else:
            # 未检测到GPU
            self.combo_gpu.setCurrentText("CPU处理")
            self.gpu_status_label.setText("GPU: 未检测到")
            self.status_label.setText("未检测到GPU，将使用CPU处理")
            
            # 显示消息
            QMessageBox.information(
                self, 
                "GPU检测结果", 
                "未检测到可用的GPU，将使用CPU处理视频。"
            )
    
    def _try_fix_ffmpeg(self, gpu_name, gpu_vendor):
        """尝试修复FFmpeg问题"""
        import os
        import subprocess
        import glob
        import logging
        from pathlib import Path
        
        logger = logging.getLogger(__name__)
        logger.info("尝试修复FFmpeg问题")
        
        self.status_label.setText("正在尝试修复FFmpeg问题...")
        
        # 搜索常见的FFmpeg安装位置
        potential_paths = []
        
        # 1. 检查安装程序目录 - 优先检查
        app_dir = Path(__file__).resolve().parent.parent.parent
        ffmpeg_compat_dir = app_dir / "ffmpeg_compat"
        
        # 检查是否有兼容版本的ffmpeg
        bundled_ffmpeg = ffmpeg_compat_dir / "ffmpeg.exe"
        if bundled_ffmpeg.exists():
            potential_paths.append(str(bundled_ffmpeg))
            logger.info(f"找到兼容版本的FFmpeg: {bundled_ffmpeg}")
        
        # 检查bin目录
        bin_ffmpeg = app_dir / "bin" / "ffmpeg.exe"
        if bin_ffmpeg.exists():
            potential_paths.append(str(bin_ffmpeg))
            logger.info(f"找到bin目录的FFmpeg: {bin_ffmpeg}")
        
        # 2. 检查环境变量
        if "PATH" in os.environ:
            path_dirs = os.environ["PATH"].split(os.pathsep)
            for directory in path_dirs:
                try:
                    ffmpeg_path = os.path.join(directory, "ffmpeg.exe")
                    if os.path.exists(ffmpeg_path):
                        potential_paths.append(ffmpeg_path)
                        logger.info(f"在PATH中找到FFmpeg: {ffmpeg_path}")
                except Exception as e:
                    logger.warning(f"检查PATH时出错: {str(e)}")
        
        # 3. 检查常见安装位置
        common_locations = [
            "C:\\FFmpeg\\bin\\ffmpeg.exe",
            "C:\\Program Files\\FFmpeg\\bin\\ffmpeg.exe", 
            "C:\\Program Files (x86)\\FFmpeg\\bin\\ffmpeg.exe",
            str(Path.home() / "FFmpeg" / "bin" / "ffmpeg.exe"),
            "D:\\FFmpeg\\bin\\ffmpeg.exe",
            "C:\\tools\\ffmpeg\\bin\\ffmpeg.exe",
            os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "ffmpeg", "bin", "ffmpeg.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "ffmpeg", "bin", "ffmpeg.exe")
        ]
        
        for location in common_locations:
            if os.path.exists(location):
                potential_paths.append(location)
                logger.info(f"在常见位置找到FFmpeg: {location}")
        
        # 4. 尝试在C盘和D盘上搜索ffmpeg.exe
        try:
            # 限制搜索深度，避免过长时间
            for drive in ["C:", "D:"]:
                if os.path.exists(drive):
                    # 搜索Program Files和Program Files (x86)
                    for program_dir in ["Program Files", "Program Files (x86)"]:
                        search_path = os.path.join(drive, program_dir)
                        if os.path.exists(search_path):
                            # 使用glob模式匹配
                            for ffmpeg_path in glob.glob(os.path.join(search_path, "*ffmpeg*", "**", "ffmpeg.exe"), recursive=True):
                                if ffmpeg_path not in potential_paths:
                                    potential_paths.append(ffmpeg_path)
                                    logger.info(f"在{search_path}搜索到FFmpeg: {ffmpeg_path}")
        except Exception as e:
            logger.warning(f"搜索FFmpeg时出错: {str(e)}")
        
        # 测试找到的FFmpeg
        valid_paths = []
        for path in potential_paths:
            try:
                logger.info(f"测试FFmpeg: {path}")
                result = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and "ffmpeg version" in result.stdout:
                    valid_paths.append(path)
                    logger.info(f"有效的FFmpeg: {path}, 版本: {result.stdout.split(chr(10))[0]}")
            except Exception as e:
                logger.warning(f"测试FFmpeg时出错: {path}, {str(e)}")
        
        # 如果找到了有效的FFmpeg，询问是否配置
        if valid_paths:
            paths_str = "\n".join(valid_paths)
            
            reply = QMessageBox.question(
                self,
                "找到FFmpeg",
                f"检测到GPU ({gpu_name})，但FFmpeg不可用或不可访问。\n\n"
                f"我们在您的系统中找到了以下可用的FFmpeg程序:\n\n{paths_str}\n\n"
                f"是否要使用第一个路径配置FFmpeg？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                # 使用第一个可用路径配置FFmpeg
                try:
                    selected_path = valid_paths[0]
                    # 确保项目路径存在
                    project_root = Path(__file__).resolve().parent.parent.parent
                    
                    with open(project_root / "ffmpeg_path.txt", "w", encoding="utf-8") as f:
                        f.write(selected_path)
                    
                    logger.info(f"已配置FFmpeg路径: {selected_path}")
                    self.status_label.setText(f"已配置FFmpeg路径: {selected_path}")
                    self.gpu_status_label.setText(f"GPU: {gpu_name}")
                    
                    # 重新检测GPU
                    QMessageBox.information(
                        self,
                        "FFmpeg已配置",
                        f"FFmpeg路径已配置为:\n{selected_path}\n\n"
                        f"请重新点击'检测显卡'按钮以完成GPU配置。"
                    )
                    return
                except Exception as e:
                    logger.error(f"配置FFmpeg路径时出错: {str(e)}")
                    QMessageBox.warning(
                        self,
                        "配置失败",
                        f"配置FFmpeg路径时出错:\n{str(e)}"
                    )
        
        # 如果没有找到FFmpeg或用户拒绝使用找到的路径
        # 先询问是否要安装FFmpeg兼容版本
        reply = QMessageBox.question(
            self,
            "下载FFmpeg",
            f"未在系统中找到可用的FFmpeg，或您选择不使用找到的版本。\n\n"
            f"是否要下载并配置兼容版本的FFmpeg？\n"
            f"(这需要约30MB的下载，并会自动配置)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            # 尝试运行修复脚本
            try:
                self.status_label.setText("正在下载和配置FFmpeg...")
                from pathlib import Path
                import subprocess
                import sys
                
                # 获取fix_gpu.py的完整路径
                fix_script = Path(__file__).resolve().parent.parent.parent / "fix_gpu.py"
                
                if fix_script.exists():
                    logger.info(f"运行FFmpeg修复脚本: {fix_script}")
                    
                    # 创建进度对话框
                    progress = QMessageBox(self)
                    progress.setWindowTitle("正在配置FFmpeg")
                    progress.setText("正在下载和配置FFmpeg，请稍候...\n\n这可能需要几分钟时间。")
                    progress.setStandardButtons(QMessageBox.NoButton)
                    progress.show()
                    QApplication.processEvents()
                    
                    # 运行修复脚本
                    process = subprocess.Popen(
                        [sys.executable, str(fix_script)],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    stdout, stderr = process.communicate()
                    
                    # 关闭进度对话框
                    progress.close()
                    
                    if process.returncode == 0:
                        logger.info("FFmpeg修复成功")
                        QMessageBox.information(
                            self,
                            "FFmpeg配置成功",
                            "兼容版本的FFmpeg已成功下载和配置。\n\n"
                            "请重新点击'检测显卡'按钮以完成GPU配置。"
                        )
                        return
                    else:
                        logger.error(f"FFmpeg修复失败: {stderr}")
                        # 转到自动配置GPU
                else:
                    logger.error(f"未找到修复脚本: {fix_script}")
                    # 转到自动配置GPU
            except Exception as e:
                logger.error(f"运行修复脚本时出错: {str(e)}")
                # 转到自动配置GPU
        
        # 如果下载失败或用户选择不下载，尝试直接配置GPU
        reply = QMessageBox.question(
            self,
            "FFmpeg问题",
            f"检测到GPU ({gpu_name})，但无法使用FFmpeg分析硬件加速兼容性。\n\n"
            f"您可以选择:\n"
            f"1. 手动配置FFmpeg路径\n"
            f"2. 尝试自动配置硬件加速 (不使用FFmpeg)\n\n"
            f"是否要尝试自动配置硬件加速？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            # 尝试根据GPU类型自动配置
            gpu_vendor_lower = gpu_vendor.lower()
            
            # 更新状态栏
            self.status_label.setText("正在尝试自动配置硬件加速...")
            logger.info(f"尝试自动配置GPU: {gpu_name}, 厂商: {gpu_vendor}")
            
            try:
                # 使用通用函数进行无FFmpeg配置
                # 这会根据GPU类型自动设置适合的编码器
                success = self.gpu_config._set_config_without_ffmpeg({
                    'primary_gpu': gpu_name,
                    'primary_vendor': gpu_vendor
                })
                
                if success:
                    # 获取配置
                    gpu_name, gpu_vendor = self.gpu_config.get_gpu_info()
                    encoder = self.gpu_config.get_encoder()
                    
                    # 更新UI
                    self.gpu_status_label.setText(f"GPU: {gpu_name} | 编码器: {encoder}")
                    self.status_label.setText(f"已启用GPU硬件加速")
                    
                    # 显示成功消息
                    QMessageBox.information(
                        self, 
                        "GPU自动配置成功", 
                        f"已自动配置GPU硬件加速:\n\n"
                        f"GPU: {gpu_name}\n"
                        f"编码器: {encoder}\n\n"
                        f"注意: 由于无法使用FFmpeg验证兼容性，实际效果可能会有所不同。\n"
                        f"建议尽快安装FFmpeg以获得完整功能。"
                    )
                else:
                    # 更新UI
                    self.gpu_status_label.setText(f"GPU: {gpu_name} | 不支持硬件加速")
                    self.status_label.setText("无法自动配置GPU，将使用CPU处理")
                    
                    QMessageBox.warning(
                        self,
                        "GPU配置失败",
                        f"无法自动配置GPU硬件加速，将使用CPU处理视频。\n\n"
                        f"建议安装FFmpeg并配置路径后重试。"
                    )
            except Exception as e:
                logger.error(f"自动配置GPU时出错: {str(e)}")
                # 更新UI
                self.gpu_status_label.setText(f"GPU: {gpu_name} | 配置失败")
                self.status_label.setText("GPU配置出错，将使用CPU处理")
                
                QMessageBox.warning(
                    self,
                    "GPU配置错误",
                    f"配置GPU硬件加速时出错:\n{str(e)}\n\n"
                    f"将使用CPU处理视频。"
                )
        else:
            # 用户选择手动配置
            self.config_ffmpeg_path()
            
            # 更新UI提示用户重新检测
            self.gpu_status_label.setText(f"GPU: {gpu_name} | 请重新检测")
            self.status_label.setText("请在配置FFmpeg后重新检测GPU")
    
    def _get_compose_params(self):
        """获取当前合成参数"""
        
        # 将UI中的编码模式转换为处理器需要的格式
        encode_mode_text = self.combo_encode_mode.currentText()
        video_mode = ""
        
        if "快速模式" in encode_mode_text or "不重编码" in encode_mode_text:
            video_mode = "fast_mode"
            logger.info("选择了快速模式(不重编码)")
        else:
            video_mode = "standard_mode"
            logger.info("选择了标准模式(重编码)")
        
        params = {
            "text_mode": self.combo_audio_mode.currentText(),
            "audio_mode": self.combo_audio_mode.currentText(),
            "video_mode": video_mode,  # 使用处理过的video_mode值
            "resolution": self.combo_resolution.currentText(),
            "bitrate": self.spin_bitrate.value(),
            "gpu": self.combo_gpu.currentText(),
            "save_dir": self.edit_save_dir.text(),
            "voice_volume": self.spin_voice_volume.value(),
            "bgm_volume": self.spin_bgm_volume.value(),
            "bgm_path": self.edit_bgm_path.text(),
            "transition": self.combo_transition.currentText(),
            "generate_count": self.spin_generate_count.value(),
            # 添加水印参数
            "watermark_enabled": self.chk_enable_watermark.isChecked(),
            "watermark_prefix": self.edit_watermark_prefix.text(),
            "watermark_size": self.spin_watermark_size.value(),
            "watermark_color": self.watermark_color,
            "watermark_position": self.combo_watermark_position.currentText(),
            "watermark_pos_x": self.spin_pos_x.value(),
            "watermark_pos_y": self.spin_pos_y.value()
        }
        return params

    def process_videos(self):
        """在独立线程中执行视频合成"""
        try:
            from core.video_processor import VideoProcessor
            
            # 获取合成参数
            params = self._get_compose_params()
            save_dir = params["save_dir"]
            
            # 获取素材文件夹，并添加抽取模式设置
            material_folders = []
            for row in range(self.video_table.rowCount()):
                folder_path = self.video_table.item(row, 2).text()
                folder_info = {
                    "name": self.video_table.item(row, 1).text(),
                    "path": folder_path,
                    # 添加抽取模式设置，默认为单视频模式
                    "extract_mode": self.folder_extract_modes.get(folder_path, "single_video")
                }
                material_folders.append(folder_info)
            
            # 使用GPU配置
            hardware_accel = False
            encoder = "libx264"
            
            # 修改使用策略：
            # 1. 如果GPU配置启用了硬件加速，则使用之
            # 2. 或者根据用户选择的显卡类型强制使用
            if self.gpu_config.is_hardware_acceleration_enabled():
                hardware_accel = True
                encoder = self.gpu_config.get_encoder()
                logger.info(f"使用GPU配置中的硬件加速：{encoder}")
            elif params["gpu"] == "Nvidia显卡" or params["gpu"] == "自动检测":
                # 用户选择NVIDIA或自动，强制使用NVENC
                hardware_accel = True
                encoder = "h264_nvenc"
                logger.info(f"用户选择使用NVIDIA，强制启用硬件加速：{encoder}")
            elif params["gpu"] == "AMD显卡":
                hardware_accel = True
                encoder = "h264_amf"
                logger.info(f"用户选择使用AMD，强制启用硬件加速：{encoder}")
            elif params["gpu"] == "Intel显卡":
                hardware_accel = True
                encoder = "h264_qsv"
                logger.info(f"用户选择使用Intel，强制启用硬件加速：{encoder}")
            else:
                # CPU处理或其他选项
                hardware_accel = False
                encoder = "libx264"
                logger.info("使用CPU编码")
                
            # 创建处理器
            settings = {
                "hardware_accel": "auto" if hardware_accel else "none",
                "encoder": encoder,
                "resolution": params["resolution"].split()[1],  # 提取分辨率数字部分
                "bitrate": params["bitrate"],
                "voice_volume": params["voice_volume"],
                "bgm_volume": params["bgm_volume"],
                "transition": params["transition"].lower(),
                "transition_duration": 0.5,  # 默认转场时长
                "threads": 4,  # 默认线程数
                "temp_dir": self.cache_config.get_cache_dir(),  # 使用缓存配置的目录
                "video_mode": params["video_mode"],  # 添加视频模式参数
                # 添加水印设置
                "watermark_enabled": params["watermark_enabled"],
                "watermark_prefix": params["watermark_prefix"],
                "watermark_size": params["watermark_size"],
                "watermark_color": params["watermark_color"],
                "watermark_position": params["watermark_position"],
                "watermark_pos_x": params["watermark_pos_x"],
                "watermark_pos_y": params["watermark_pos_y"]
            }
            
            # 更新状态栏
            if hardware_accel:
                self.status_label.setText(f"正在使用硬件加速处理视频 (编码器: {encoder})")
            else:
                self.status_label.setText(f"正在使用CPU处理视频 (编码器: {encoder})")
            
            # 保存处理器实例以便停止处理
            self.processor = VideoProcessor(settings, progress_callback=self._update_progress)
            
            # 执行批量处理
            bgm_path = params["bgm_path"] if os.path.exists(params["bgm_path"]) else None
            count = params["generate_count"]
            
            # 实际生成视频，注意现在返回值是一个元组(视频列表, 总时长)
            result = self.processor.process_batch(
                material_folders=material_folders,
                output_dir=save_dir,
                count=count,
                bgm_path=bgm_path
            )
            
            # 解包结果
            output_videos, total_time = result
            
            # 处理完成
            QtCore.QMetaObject.invokeMethod(
                self, 
                "on_compose_completed", 
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(bool, len(output_videos) > 0),
                QtCore.Q_ARG(int, len(output_videos)),
                QtCore.Q_ARG(str, save_dir),
                QtCore.Q_ARG(str, total_time)
            )
        except InterruptedError:
            # 处理被用户中断
            QtCore.QMetaObject.invokeMethod(
                self, 
                "on_compose_interrupted", 
                QtCore.Qt.QueuedConnection
            )
        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            QtCore.QMetaObject.invokeMethod(
                self, 
                "on_compose_error", 
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(str, str(e)),
                QtCore.Q_ARG(str, error_msg)
            )
        finally:
            # 清理处理器
            self.processor = None
            # 恢复状态栏
            QtCore.QMetaObject.invokeMethod(
                self,
                "_reset_status_bar",
                QtCore.Qt.QueuedConnection
            )
    
    @QtCore.pyqtSlot()
    def _reset_status_bar(self):
        """重置状态栏"""
        self.status_label.setText("就绪")
    
    @pyqtSlot()
    def on_start_compose(self):
        """开始合成"""
        # 检查必要条件
        if self.video_table.rowCount() == 0:
            QMessageBox.warning(self, "合成错误", "请先添加素材")
            return
        
        save_dir = self.edit_save_dir.text()
        if not save_dir:
            QMessageBox.warning(self, "合成错误", "请选择保存目录")
            return
            
        if not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir, exist_ok=True)
            except Exception as e:
                QMessageBox.warning(self, "合成错误", f"无法创建保存目录: {str(e)}")
            return
        
        # 更新界面状态
        self.btn_start_compose.setEnabled(False)
        self.btn_stop_compose.setEnabled(True)
        self.label_progress.setText("合成进度: 正在初始化...")
        self.progress_bar.setValue(0)
        
        # 更新素材状态
        for row in range(self.video_table.rowCount()):
            folder_path = self.video_table.item(row, 2).text()
            extract_mode = self.folder_extract_modes.get(folder_path, "single_video")
            item = ExtractModeItem("", extract_mode, folder_path)
            item.set_status("处理中")
            self.video_table.setItem(row, 5, item)
        
        # 在单独线程中执行视频合成，避免阻塞UI
        import threading
        self.processing_thread = threading.Thread(target=self.process_videos, daemon=True)
        self.processing_thread.start()
    
    @pyqtSlot()
    def on_stop_compose(self):
        """停止合成"""
        # 确认是否停止
        reply = QMessageBox.question(
            self, "停止合成", "确定要停止当前的合成任务吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 停止处理
            if self.processor:
                self.processor.stop_processing()
                self.label_progress.setText("合成进度: 正在停止...")
    
    @QtCore.pyqtSlot()
    def on_compose_interrupted(self):
        """处理被中断时调用"""
        # 更新界面状态
        self.btn_start_compose.setEnabled(True)
        self.btn_stop_compose.setEnabled(False)
        self.label_progress.setText("合成进度: 已中止")
        
        # 设置表格中素材的状态为"已中止"
        for row in range(self.video_table.rowCount()):
            item = self.video_table.item(row, 5)
            if item and isinstance(item, ExtractModeItem) and item.status == "处理中":
                item.set_status("已中止")
            elif item and "处理中" in item.text():
                folder_path = self.video_table.item(row, 2).text()
                extract_mode = self.folder_extract_modes.get(folder_path, "single_video")
                status_item = ExtractModeItem("", extract_mode, folder_path)
                status_item.set_status("已中止")
                self.video_table.setItem(row, 5, status_item)
        
        # 显示消息
        QMessageBox.information(self, "合成已中止", "视频合成任务已被中止")
    
    @QtCore.pyqtSlot(bool, int, str, str)
    def on_compose_completed(self, success=True, count=0, output_dir="", total_time=""):
        """合成完成时调用"""
        # 更新界面状态
        self.btn_start_compose.setEnabled(True)
        self.btn_stop_compose.setEnabled(False)
        
        # 保存最后合成的视频数量，供批处理统计使用
        self.last_compose_count = count
        
        if success and count > 0:
            self.label_progress.setText(f"合成进度: 已完成 {count} 个视频，用时: {total_time}")
        
            # 设置表格中素材的状态为"已完成"
            for row in range(self.video_table.rowCount()):
                item = self.video_table.item(row, 5)
                if item and isinstance(item, ExtractModeItem):
                    item.set_status("已完成")
                else:
                    folder_path = self.video_table.item(row, 2).text()
                    extract_mode = self.folder_extract_modes.get(folder_path, "single_video")
                    status_item = ExtractModeItem("", extract_mode, folder_path)
                    status_item.set_status("已完成")
                    self.video_table.setItem(row, 5, status_item)
            
            # 显示完成消息
            QMessageBox.information(
                self, 
                "合成完成", 
                f"视频合成任务已完成！\n共合成 {count} 个视频，用时 {total_time}\n\n保存在：\n{output_dir}"
            )
        else:
            self.label_progress.setText("合成进度: 未生成视频")
            
            # 设置表格中素材的状态为"失败"
            for row in range(self.video_table.rowCount()):
                item = self.video_table.item(row, 5)
                if item and isinstance(item, ExtractModeItem):
                    item.set_status("错误")
                else:
                    folder_path = self.video_table.item(row, 2).text()
                    extract_mode = self.folder_extract_modes.get(folder_path, "single_video")
                    status_item = ExtractModeItem("", extract_mode, folder_path)
                    status_item.set_status("错误") 
                    self.video_table.setItem(row, 5, status_item)
            
            # 显示错误消息
            QMessageBox.warning(
                self, 
                "合成失败", 
                "未能成功生成视频，请检查素材和设置。"
            )
    
    @QtCore.pyqtSlot(str, str)
    def on_compose_error(self, error_msg, detail=""):
        """处理合成错误"""
        # 更新界面状态
        self.btn_start_compose.setEnabled(True)
        self.btn_stop_compose.setEnabled(False)
        self.label_progress.setText("合成进度: 出错")
        
        # 设置表格中素材的状态为"错误"
        for row in range(self.video_table.rowCount()):
            item = self.video_table.item(row, 5)
            if item and isinstance(item, ExtractModeItem) and item.status == "处理中":
                item.set_status("错误")
            elif item and "处理中" in item.text():
                folder_path = self.video_table.item(row, 2).text()
                extract_mode = self.folder_extract_modes.get(folder_path, "single_video")
                status_item = ExtractModeItem("", extract_mode, folder_path)
                status_item.set_status("错误")
                self.video_table.setItem(row, 5, status_item)
        
        # 检查是否是FFmpeg相关错误
        if "FFmpeg不可用" in error_msg or "ffmpeg" in error_msg.lower():
            instruction_text = """
视频合成需要FFmpeg工具，但系统中未检测到FFmpeg。

请按照以下步骤安装FFmpeg:

1. 下载FFmpeg:
   访问 https://ffmpeg.org/download.html 或者
   https://github.com/BtbN/FFmpeg-Builds/releases 下载Windows版本

2. 解压下载的文件到一个固定位置
   (例如: C:\\FFmpeg)

3. 将FFmpeg的bin目录添加到系统环境变量Path中:
   - 右键点击"此电脑" -> 属性 -> 高级系统设置 -> 环境变量
   - 在"系统变量"中找到"Path"，点击"编辑"
   - 点击"新建"，添加FFmpeg的bin目录路径(例如: C:\\FFmpeg\\bin)
   - 点击"确定"保存所有更改

4. 重启电脑或所有命令行窗口

5. 重启本软件后重试

或者，您也可以使用菜单中的"帮助 -> 配置FFmpeg路径"来指定FFmpeg可执行文件的位置。
            """
            
            # 显示FFmpeg特定错误消息
            error_dialog = QMessageBox(self)
            error_dialog.setIcon(QMessageBox.Critical)
            error_dialog.setWindowTitle("缺少FFmpeg")
            error_dialog.setText("缺少视频处理所需的FFmpeg工具")
            error_dialog.setInformativeText(instruction_text)
            error_dialog.setDetailedText(detail)
            error_dialog.setStandardButtons(QMessageBox.Ok)
            
            # 设置宽度
            error_dialog.setMinimumWidth(600)
            
            error_dialog.exec_()
        # 检查是否是权限或路径相关错误
        elif any(keyword in error_msg.lower() for keyword in ["permission", "access", "denied", "权限", "拒绝", "访问", "路径"]):
            suggestion_text = """
可能是保存目录权限不足或路径无效。请尝试以下解决方案:

1. 确保选择的保存目录存在且有写入权限
2. 避免使用系统保护的目录(如C盘根目录或Program Files)
3. 尝试使用不包含特殊字符或中文的路径
4. 以管理员身份运行本软件
5. 检查杀毒软件是否阻止了对该目录的写入
            """
            
            error_dialog = QMessageBox(self)
            error_dialog.setIcon(QMessageBox.Critical)
            error_dialog.setWindowTitle("权限或路径错误")
            error_dialog.setText(f"视频合成失败: {error_msg}")
            error_dialog.setInformativeText(suggestion_text)
            error_dialog.setDetailedText(detail)
            error_dialog.setStandardButtons(QMessageBox.Ok)
            error_dialog.setMinimumWidth(600)
            error_dialog.exec_()
        # 检查是否是硬件加速相关错误
        elif any(keyword in error_msg.lower() for keyword in ["gpu", "cuda", "nvidia", "amd", "intel", "hardware", "acceleration", "硬件加速"]):
            suggestion_text = """
可能是硬件加速设置不当。请尝试以下解决方案:

1. 在"显卡加速"选项中选择"CPU处理"，避免使用GPU加速
2. 确保您的显卡驱动是最新的
3. 如果您确实需要使用GPU加速，请确保选择了与您硬件匹配的选项
4. 重启电脑后再试
            """
            
            error_dialog = QMessageBox(self)
            error_dialog.setIcon(QMessageBox.Critical)
            error_dialog.setWindowTitle("硬件加速错误")
            error_dialog.setText(f"视频合成失败: {error_msg}")
            error_dialog.setInformativeText(suggestion_text)
            error_dialog.setDetailedText(detail)
            error_dialog.setStandardButtons(QMessageBox.Ok)
            error_dialog.setMinimumWidth(600)
            error_dialog.exec_()
        # 检查是否是素材相关错误
        elif any(keyword in error_msg.lower() for keyword in ["video", "audio", "media", "format", "codec", "视频", "音频", "媒体", "格式", "编码"]):
            suggestion_text = """
可能是素材文件格式不兼容。请尝试以下解决方案:

1. 确保素材视频和音频可以正常播放
2. 检查素材视频是否使用了不常见的编解码器
3. 尝试使用常见格式如MP4(H.264编码)的视频
4. 转换素材为更兼容的格式后再试
5. 如果使用了背景音乐，确保音乐文件格式正确且可播放
            """
            
            error_dialog = QMessageBox(self)
            error_dialog.setIcon(QMessageBox.Critical)
            error_dialog.setWindowTitle("素材格式错误")
            error_dialog.setText(f"视频合成失败: {error_msg}")
            error_dialog.setInformativeText(suggestion_text)
            error_dialog.setDetailedText(detail)
            error_dialog.setStandardButtons(QMessageBox.Ok)
            error_dialog.setMinimumWidth(600)
            error_dialog.exec_()
        else:
            # 显示一般错误消息，但包含更多上下文和调试信息
            general_suggestion = """
请尝试以下通用解决方案:

1. 检查日志文件获取详细错误信息
   日志位置: %s

2. 尝试关闭其他占用系统资源的程序

3. 检查视频合成设置是否合理

4. 尝试减少生成视频的数量

5. 如果依然失败，可以尝试重启软件或计算机
            """ % (str(Path.home() / "VideoMixTool" / "logs"))
            
            error_dialog = QMessageBox(self)
            error_dialog.setIcon(QMessageBox.Critical)
            error_dialog.setWindowTitle("合成错误")
            error_dialog.setText(f"视频合成过程中出错: {error_msg}")
            error_dialog.setInformativeText(general_suggestion)
            error_dialog.setDetailedText(detail)
            error_dialog.setStandardButtons(QMessageBox.Ok)
            error_dialog.setMinimumWidth(600)
            error_dialog.exec_()
    
    def config_ffmpeg_path(self):
        """配置FFmpeg路径"""
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        import os
        from pathlib import Path
        
        # 获取ffmpeg可执行文件
        ffmpeg_file, _ = QFileDialog.getOpenFileName(
            self, 
            "选择FFmpeg可执行文件", 
            str(Path.home()), 
            "可执行文件 (*.exe);;所有文件 (*.*)"
        )
        
        if not ffmpeg_file:
            return
        
        # 验证是否为有效的FFmpeg文件
        try:
            import subprocess
            result = subprocess.run(
                [ffmpeg_file, "-version"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                timeout=3
            )
            
            if result.returncode != 0 or "ffmpeg version" not in result.stdout.lower():
                QMessageBox.warning(
                    self, 
                    "无效的FFmpeg文件", 
                    f"所选文件不是有效的FFmpeg可执行文件:\n{ffmpeg_file}\n\n错误: {result.stderr}"
                )
                return
        except Exception as e:
            QMessageBox.warning(
                self, 
                "验证FFmpeg失败", 
                f"无法验证所选文件:\n{ffmpeg_file}\n\n错误: {str(e)}"
            )
            return
        
        # 保存路径到配置文件
        try:
            # 获取项目根目录
            project_root = Path(__file__).resolve().parent.parent.parent
            ffmpeg_path_file = project_root / "ffmpeg_path.txt"
            
            with open(ffmpeg_path_file, "w") as f:
                f.write(ffmpeg_file)
            
            QMessageBox.information(
                self, 
                "FFmpeg配置成功", 
                f"FFmpeg路径已成功配置！\n\n路径: {ffmpeg_file}\n\n请重启软件以应用新设置。"
            )
        except Exception as e:
            QMessageBox.critical(
                self, 
                "配置失败", 
                f"保存FFmpeg路径时出错:\n{str(e)}"
            )
    
    def view_log_file(self):
        """查看最新的日志文件"""
        import glob
        from pathlib import Path
        
        log_dir = Path.home() / "VideoMixTool" / "logs"
        
        # 检查日志目录是否存在
        if not log_dir.exists():
            QMessageBox.warning(
                self,
                "日志不存在",
                f"日志目录不存在: {log_dir}\n请先运行一次视频合成操作以生成日志。"
            )
            return
            
        # 查找最新的日志文件
        log_files = sorted(glob.glob(str(log_dir / "*.log")), reverse=True)
        
        if not log_files:
            QMessageBox.warning(
                self,
                "日志不存在",
                f"未找到日志文件，请先运行一次视频合成操作以生成日志。"
            )
            return
            
        latest_log = log_files[0]
        
        # 读取日志内容
        try:
            with open(latest_log, 'r', encoding='utf-8') as f:
                log_content = f.read()
        except Exception as e:
            QMessageBox.critical(
                self,
                "无法读取日志",
                f"无法读取日志文件: {latest_log}\n错误: {str(e)}"
            )
            return
            
        # 创建日志查看对话框
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QLabel
        from PyQt5.QtGui import QFont
        
        log_dialog = QDialog(self)
        log_dialog.setWindowTitle("日志查看器")
        log_dialog.resize(800, 600)
        
        layout = QVBoxLayout(log_dialog)
        
        # 添加文件信息
        info_label = QLabel(f"日志文件: {latest_log}")
        layout.addWidget(info_label)
        
        # 创建文本编辑器显示日志
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Courier New", 10))
        text_edit.setText(log_content)
        layout.addWidget(text_edit)
        
        # 添加按钮：刷新、打开目录、关闭
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("刷新")
        open_dir_btn = QPushButton("打开日志目录")
        close_btn = QPushButton("关闭")
        
        button_layout.addWidget(refresh_btn)
        button_layout.addWidget(open_dir_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # 连接按钮信号
        def refresh_log():
            try:
                with open(latest_log, 'r', encoding='utf-8') as f:
                    text_edit.setText(f.read())
            except Exception as e:
                QMessageBox.warning(log_dialog, "刷新失败", f"无法刷新日志: {str(e)}")
        
        def open_log_dir():
            try:
                if sys.platform == 'win32':
                    os.startfile(str(log_dir))
                elif sys.platform == 'darwin':  # macOS
                    os.system(f'open "{log_dir}"')
                else:  # Linux
                    os.system(f'xdg-open "{log_dir}"')
            except Exception as e:
                QMessageBox.warning(log_dialog, "打开目录失败", f"无法打开日志目录: {str(e)}")
        
        refresh_btn.clicked.connect(refresh_log)
        open_dir_btn.clicked.connect(open_log_dir)
        close_btn.clicked.connect(log_dialog.close)
        
        # 显示对话框
        log_dialog.exec_()

    def _init_statusbar(self):
        """初始化状态栏"""
        # 创建状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        
        # 创建状态标签
        self.status_label = QLabel("就绪")
        self.gpu_status_label = QLabel("GPU: 未检测")
        
        # 添加到状态栏
        self.statusBar.addWidget(self.status_label, 1)  # 1表示拉伸因子
        self.statusBar.addPermanentWidget(self.gpu_status_label)  # 永久显示在右侧
        
        # 在启动时显示当前GPU状态
        self._init_gpu_status()
    
    def _init_gpu_status(self):
        """在启动时初始化GPU状态显示"""
        try:
            # 如果已经配置了GPU，直接显示其信息
            if self.gpu_config.is_hardware_acceleration_enabled():
                gpu_name, gpu_vendor = self.gpu_config.get_gpu_info()
                encoder = self.gpu_config.get_encoder()
                self.gpu_status_label.setText(f"GPU: {gpu_name} | 编码器: {encoder}")
                
                # 更新下拉框
                if 'nvidia' in gpu_vendor.lower():
                    self.combo_gpu.setCurrentText("Nvidia显卡")
                elif 'amd' in gpu_vendor.lower():
                    self.combo_gpu.setCurrentText("AMD显卡")
                elif 'intel' in gpu_vendor.lower():
                    self.combo_gpu.setCurrentText("Intel显卡")
            else:
                # 未配置GPU，显示默认状态
                self.gpu_status_label.setText("GPU: 未检测 (点击检测按钮)")
                
                # 尝试进行简单的GPU检测，不阻塞UI
                import threading
                
                def quick_detect():
                    try:
                        from hardware.system_analyzer import SystemAnalyzer
                        
                        # 仅进行基本检测
                        analyzer = SystemAnalyzer(deep_gpu_detection=False)
                        system_info = analyzer.analyze()
                        gpu_info = system_info.get('gpu', {})
                        
                        # 如果检测到GPU，更新状态栏
                        if gpu_info.get('available', False):
                            primary_gpu = gpu_info.get('primary_gpu', '未知')
                            QtCore.QMetaObject.invokeMethod(
                                self, 
                                "_update_initial_gpu_label", 
                                QtCore.Qt.QueuedConnection,
                                QtCore.Q_ARG(str, primary_gpu)
                            )
                    except Exception:
                        pass
                
                # 启动快速检测线程
                detect_thread = threading.Thread(target=quick_detect, daemon=True)
                detect_thread.start()
        except Exception as e:
            # 出错时不更新GPU状态，保持默认状态
            import logging
            logging.error(f"初始化GPU状态时出错: {str(e)}")
    
    @QtCore.pyqtSlot(str)
    def _update_initial_gpu_label(self, gpu_name):
        """更新初始GPU标签"""
        self.gpu_status_label.setText(f"GPU: {gpu_name} (点击检测按钮启用)")

    def run_gpu_test(self):
        """运行GPU加速测试"""
        import subprocess
        import os
        import time
        from pathlib import Path
        
        # 检查是否启用了硬件加速
        if not self.gpu_config.is_hardware_acceleration_enabled():
            QMessageBox.warning(
                self,
                "硬件加速未启用",
                "请先检测显卡并启用硬件加速，然后再运行此测试。"
            )
            return
        
        # 获取GPU配置
        gpu_name, gpu_vendor = self.gpu_config.get_gpu_info()
        encoder = self.gpu_config.get_encoder()
        
        # 显示确认对话框
        reply = QMessageBox.question(
            self,
            "GPU加速测试",
            f"将执行一个简短的编码测试，以验证GPU硬件加速是否正常工作。\n\n"
            f"测试将创建一个短视频文件，并使用GPU加速编码。\n"
            f"检测到的GPU: {gpu_name}\n"
            f"编码器: {encoder}\n\n"
            f"是否继续?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 创建临时目录
        temp_dir = Path.home() / "VideoMixTool" / "temp"
        os.makedirs(temp_dir, exist_ok=True)
        
        # 创建进度对话框
        progress_dialog = QMessageBox(self)
        progress_dialog.setIcon(QMessageBox.Information)
        progress_dialog.setWindowTitle("GPU测试进行中")
        progress_dialog.setText("正在执行GPU加速测试，请稍候...")
        progress_dialog.setStandardButtons(QMessageBox.NoButton)
        
        # 显示进度对话框但不阻塞
        progress_dialog.show()
        
        # 更新状态栏
        self.status_label.setText("正在执行GPU加速测试...")
        
        # 在后台线程中执行测试
        def run_test():
            test_success = False
            error_message = ""
            gpu_utilization = "未知"
            encoding_speed = "未知"
            
            try:
                # 生成测试视频参数
                test_input = os.path.join(temp_dir, "gpu_test_input.mp4")
                test_output = os.path.join(temp_dir, "gpu_test_output.mp4")
                
                # 获取FFmpeg路径
                ffmpeg_cmd = "ffmpeg"
                ffmpeg_path_file = Path(__file__).resolve().parent.parent.parent / "ffmpeg_path.txt"
                if ffmpeg_path_file.exists():
                    with open(ffmpeg_path_file, 'r') as f:
                        custom_path = f.read().strip()
                        if custom_path and os.path.exists(custom_path):
                            ffmpeg_cmd = custom_path
                
                # 生成测试视频 (10秒,彩条)
                gen_cmd = [
                    ffmpeg_cmd, "-f", "lavfi", "-i", "testsrc=duration=5:size=1920x1080:rate=30",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
                    "-c:v", "libx264", "-c:a", "aac", "-y", test_input
                ]
                
                subprocess.run(gen_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # 设置GPU加速编码命令
                gpu_params = []
                if "nvenc" in encoder:
                    # NVIDIA GPU参数
                    gpu_params = [
                        "-c:v", encoder,
                        "-preset", "p2",
                        "-tune", "hq",
                        "-rc", "vbr_hq",
                        "-spatial-aq", "1",
                        "-temporal-aq", "1"
                    ]
                elif "qsv" in encoder:
                    # Intel GPU参数
                    gpu_params = [
                        "-c:v", encoder,
                        "-preset", "medium",
                        "-global_quality", "23"
                    ]
                elif "amf" in encoder:
                    # AMD GPU参数
                    gpu_params = [
                        "-c:v", encoder,
                        "-quality", "quality",
                        "-usage", "transcoding"
                    ]
                
                # 使用GPU加速编码测试视频
                encode_cmd = [
                    ffmpeg_cmd, "-i", test_input,
                    "-c:a", "copy",
                    "-y"
                ] + gpu_params + [test_output]
                
                # 记录NVIDIA GPU状态（前）
                if "nvenc" in encoder:
                    try:
                        gpu_cmd = ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"]
                        gpu_before = subprocess.check_output(gpu_cmd, universal_newlines=True).strip()
                    except Exception:
                        pass
                
                # 记录开始时间
                start_time = time.time()
                
                # 执行编码命令
                process = subprocess.Popen(
                    encode_cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                
                # 等待进程完成
                stdout, stderr = process.communicate()
                
                # 编码用时
                encode_time = time.time() - start_time
                
                # 记录NVIDIA GPU状态（后）
                if "nvenc" in encoder:
                    try:
                        gpu_cmd = ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"]
                        gpu_after = subprocess.check_output(gpu_cmd, universal_newlines=True).strip()
                        gpu_utilization = f"{gpu_after}%"
                    except Exception:
                        pass
                
                # 验证结果
                if process.returncode == 0 and os.path.exists(test_output) and os.path.getsize(test_output) > 0:
                    # 计算编码速度
                    if encode_time > 0:
                        # 视频是5秒长
                        encoding_speed = f"{5 / encode_time:.2f}x"
                    
                    # 检查输出视频是否正确
                    probe_cmd = [ffmpeg_cmd, "-i", test_output]
                    probe_process = subprocess.run(
                        probe_cmd, 
                        check=False, 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE,
                        universal_newlines=True
                    )
                    
                    if encoder in probe_process.stderr:
                        test_success = True
                    else:
                        error_message = "输出视频未使用指定编码器，GPU加速可能未正常工作"
                else:
                    error_message = f"编码失败，返回码: {process.returncode}"
                    if stderr:
                        error_message += f"\n错误输出: {stderr[:200]}..."
            except Exception as e:
                error_message = f"测试过程中出错: {str(e)}"
            finally:
                # 更新UI
                QtCore.QMetaObject.invokeMethod(
                    self, 
                    "_show_gpu_test_result", 
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(bool, test_success),
                    QtCore.Q_ARG(str, error_message),
                    QtCore.Q_ARG(str, gpu_utilization),
                    QtCore.Q_ARG(str, encoding_speed)
                )
                
                # 清理临时文件
                try:
                    if os.path.exists(test_input):
                        os.remove(test_input)
                    if os.path.exists(test_output):
                        os.remove(test_output)
                except Exception:
                    pass
        
        # 启动测试线程
        import threading
        test_thread = threading.Thread(target=run_test)
        test_thread.daemon = True
        test_thread.start()
    
    @QtCore.pyqtSlot(bool, str, str, str)
    def _show_gpu_test_result(self, success, error_message, gpu_utilization, encoding_speed):
        """显示GPU测试结果"""
        # 关闭可能的进度对话框
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMessageBox) and widget.windowTitle() == "GPU测试进行中":
                widget.close()
        
        # 更新状态栏
        self.status_label.setText("就绪")
        
        # 显示结果
        if success:
            QMessageBox.information(
                self,
                "GPU测试成功",
                f"GPU加速测试成功完成!\n\n"
                f"检测到的GPU: {self.gpu_config.get_gpu_info()[0]}\n"
                f"编码器: {self.gpu_config.get_encoder()}\n"
                f"GPU利用率: {gpu_utilization}\n"
                f"编码速度: {encoding_speed} (实时速度倍数)\n\n"
                f"您的系统已成功使用GPU硬件加速编码视频。"
            )
        else:
            QMessageBox.warning(
                self,
                "GPU测试失败",
                f"GPU加速测试未能成功完成。\n\n"
                f"检测到的GPU: {self.gpu_config.get_gpu_info()[0]}\n"
                f"编码器: {self.gpu_config.get_encoder()}\n"
                f"GPU利用率: {gpu_utilization}\n\n"
                f"错误信息: {error_message}\n\n"
                f"可能原因:\n"
                f"1. FFmpeg编译版本不支持该GPU硬件加速\n"
                f"2. GPU驱动程序版本过旧\n"
                f"3. 系统环境问题\n\n"
                f"建议尝试更新GPU驱动，或使用CPU模式处理视频。"
            )
    
    def show_gpu_status(self):
        """显示当前GPU状态信息"""
        import subprocess
        import threading
        
        # 创建状态对话框
        status_dialog = QMessageBox(self)
        status_dialog.setIcon(QMessageBox.Information)
        status_dialog.setWindowTitle("正在获取GPU状态...")
        status_dialog.setText("正在获取GPU状态信息，请稍候...")
        status_dialog.setStandardButtons(QMessageBox.Cancel)
        
        # 获取更新信息的函数
        def get_gpu_info():
            info_text = ""
            try:
                # 检测FFmpeg
                ffmpeg_cmd = "ffmpeg"
                ffmpeg_path_file = Path(__file__).resolve().parent.parent.parent / "ffmpeg_path.txt"
                if ffmpeg_path_file.exists():
                    with open(ffmpeg_path_file, 'r') as f:
                        custom_path = f.read().strip()
                        if custom_path and os.path.exists(custom_path):
                            ffmpeg_cmd = custom_path
                
                ffmpeg_info = "未检测到"
                try:
                    result = subprocess.run(
                        [ffmpeg_cmd, "-version"], 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=2
                    )
                    if result.returncode == 0:
                        version_line = result.stdout.splitlines()[0]
                        ffmpeg_info = version_line
                except Exception as e:
                    ffmpeg_info = f"错误: {str(e)}"
                
                # GPU基本信息
                gpu_name = "未检测到"
                gpu_driver = "未知"
                gpu_memory = "未知"
                gpu_util = "未知"
                encoder_usage = "未知"
                
                # 尝试通过nvidia-smi获取信息
                try:
                    gpu_cmd = ["nvidia-smi", "--query-gpu=name,driver_version,memory.total,utilization.gpu,utilization.memory", 
                             "--format=csv,noheader,nounits"]
                    gpu_output = subprocess.check_output(gpu_cmd, universal_newlines=True).strip().split(', ')
                    
                    if len(gpu_output) >= 5:
                        gpu_name = gpu_output[0]
                        gpu_driver = gpu_output[1]
                        gpu_memory = f"{int(gpu_output[2]):,} MB"
                        gpu_util = f"{gpu_output[3]}%"
                        memory_util = f"{gpu_output[4]}%"
                        
                        # 获取编码器使用情况
                        enc_cmd = ["nvidia-smi", "--query-gpu=encoder.stats.sessionCount,encoder.stats.averageFps", 
                                 "--format=csv,noheader"]
                        enc_output = subprocess.check_output(enc_cmd, universal_newlines=True).strip().split(', ')
                        
                        if len(enc_output) >= 2:
                            session_count = enc_output[0]
                            avg_fps = enc_output[1]
                            encoder_usage = f"会话数: {session_count}, 平均帧率: {avg_fps}"
                except Exception:
                    pass
                
                # GPU配置信息
                gpu_configured = "未配置"
                encoder_configured = "未配置"
                
                if self.gpu_config.is_hardware_acceleration_enabled():
                    gpu_name_config, _ = self.gpu_config.get_gpu_info()
                    encoder_configured = self.gpu_config.get_encoder()
                    gpu_configured = f"{gpu_name_config} (已配置)"
                
                # 构建信息文本
                info_text = (
                    f"=== 系统信息 ===\n"
                    f"FFmpeg版本: {ffmpeg_info}\n\n"
                    f"=== GPU硬件信息 ===\n"
                    f"检测到的GPU: {gpu_name}\n"
                    f"驱动版本: {gpu_driver}\n"
                    f"显存容量: {gpu_memory}\n"
                    f"当前GPU利用率: {gpu_util}\n"
                    f"编码器使用情况: {encoder_usage}\n\n"
                    f"=== 软件配置信息 ===\n"
                    f"配置的GPU: {gpu_configured}\n"
                    f"配置的编码器: {encoder_configured}\n"
                )
            except Exception as e:
                info_text = f"获取GPU状态时出错:\n{str(e)}"
            
            # 更新UI
            QtCore.QMetaObject.invokeMethod(
                self, 
                "_update_gpu_status_dialog", 
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(str, info_text)
            )
        
        # 启动信息获取线程
        info_thread = threading.Thread(target=get_gpu_info)
        info_thread.daemon = True
        info_thread.start()
        
        # 显示对话框
        status_dialog.exec_()
    
    @QtCore.pyqtSlot(str)
    def _update_gpu_status_dialog(self, info_text):
        """更新GPU状态对话框"""
        # 关闭旧对话框
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMessageBox) and widget.windowTitle() == "正在获取GPU状态...":
                widget.close()
        
        # 创建新的详细对话框
        detail_dialog = QMessageBox(self)
        detail_dialog.setIcon(QMessageBox.Information)
        detail_dialog.setWindowTitle("GPU状态信息")
        detail_dialog.setText(info_text)
        detail_dialog.setStandardButtons(QMessageBox.Ok)
        
        # 显示详细信息对话框
        detail_dialog.exec_()

    def _init_gpu_detection(self):
        """初始化GPU检测部分"""
        # GPU检测布局
        gpu_detection_layout = QVBoxLayout()
        
        # GPU检测标题
        gpu_title_layout = QHBoxLayout()
        gpu_title_label = QLabel("硬件加速设置")
        gpu_title_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        gpu_title_layout.addWidget(gpu_title_label)
        gpu_title_layout.addStretch()
        
        # GPU检测按钮布局
        gpu_btn_layout = QHBoxLayout()
        
        # GPU检测按钮
        self.btn_detect_gpu = QPushButton("检测显卡")
        self.btn_detect_gpu.setIcon(QIcon("resources/icons/gpu-icon.png"))
        self.btn_detect_gpu.clicked.connect(self.detect_gpu)
        gpu_btn_layout.addWidget(self.btn_detect_gpu)
        
        # 硬件加速选择
        self.combo_gpu = QComboBox()
        self.combo_gpu.addItems(["自动检测", "CPU处理", "Nvidia显卡", "AMD显卡", "Intel显卡"])
        self.combo_gpu.setCurrentText("自动检测")
        gpu_btn_layout.addWidget(self.combo_gpu)
        
        # 添加兼容模式复选框
        self.chk_compatibility_mode = QCheckBox("兼容模式")
        self.chk_compatibility_mode.setToolTip("启用兼容模式以支持旧版本驱动，如果遇到编码错误请勾选")
        self.chk_compatibility_mode.setChecked(self.gpu_config.is_compatibility_mode_enabled())
        self.chk_compatibility_mode.stateChanged.connect(self._on_compatibility_mode_changed)
        gpu_btn_layout.addWidget(self.chk_compatibility_mode)
        
        # 组装GPU检测部分布局
        gpu_detection_layout.addLayout(gpu_title_layout)
        gpu_detection_layout.addLayout(gpu_btn_layout)
        
        # 返回完整布局
        return gpu_detection_layout

    @QtCore.pyqtSlot(int)
    def _on_compatibility_mode_changed(self, state):
        """处理兼容模式复选框状态变化"""
        enabled = state == Qt.Checked
        success = self.gpu_config.set_compatibility_mode(enabled)
        
        if success:
            if enabled:
                self.status_label.setText("已启用GPU兼容模式，适用于旧版本驱动")
                logging.info("用户启用了GPU兼容模式")
            else:
                self.status_label.setText("已禁用GPU兼容模式，使用高级编码参数")
                logging.info("用户禁用了GPU兼容模式")
        else:
            self.status_label.setText("更改兼容模式设置需要先检测到NVIDIA显卡")
            logging.warning("更改兼容模式失败：未检测到NVIDIA显卡")

    @pyqtSlot()
    def on_browse_cache_dir(self):
        """选择缓存目录"""
        current_dir = self.edit_cache_dir.text()
        if not current_dir or not os.path.exists(current_dir):
            current_dir = os.path.expanduser("~")
        
        cache_dir = QFileDialog.getExistingDirectory(
            self, "选择缓存目录", current_dir
        )
        
        if cache_dir:
            success = self.cache_config.set_cache_dir(cache_dir)
            if success:
                self.edit_cache_dir.setText(cache_dir)
                QMessageBox.information(
                    self, 
                    "设置成功", 
                    f"缓存目录已更改为：\n{cache_dir}\n\n新的缓存设置将在重启软件后生效。"
                )
            else:
                QMessageBox.warning(
                    self, 
                    "设置失败", 
                    "无法设置缓存目录，请确保选择的目录具有写权限。"
                )

    @pyqtSlot()
    def on_open_cache_dir(self):
        """打开缓存目录"""
        cache_dir = self.edit_cache_dir.text()
        
        if not cache_dir or not os.path.exists(cache_dir):
            QMessageBox.warning(self, "目录不存在", "缓存目录不存在，请先设置有效的缓存目录。")
            return
        
        try:
            if sys.platform == 'win32':
                os.startfile(cache_dir)
            elif sys.platform == 'darwin':  # macOS
                subprocess.run(['open', cache_dir])
            else:  # Linux
                subprocess.run(['xdg-open', cache_dir])
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开缓存目录：{str(e)}")

    @pyqtSlot()
    def on_clear_cache(self):
        """清理缓存目录"""
        reply = QMessageBox.question(
            self, 
            "确认清理缓存", 
            "是否清理缓存目录中的所有文件？\n\n这将删除所有临时文件，但不会影响项目文件。",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        cache_dir = self.edit_cache_dir.text()
        
        if not cache_dir or not os.path.exists(cache_dir):
            QMessageBox.warning(self, "目录不存在", "缓存目录不存在，无法清理。")
            return
        
        try:
            # 清理缓存文件但保留目录
            count = 0
            for file in os.listdir(cache_dir):
                file_path = os.path.join(cache_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    count += 1
            
            QMessageBox.information(
                self, 
                "清理完成", 
                f"已清理 {count} 个缓存文件。"
            )
        except Exception as e:
            QMessageBox.warning(
                self, 
                "清理失败", 
                f"清理缓存文件时出错：{str(e)}"
            )

    @QtCore.pyqtSlot(bool)
    def _on_original_bitrate_toggled(self, checked):
        """处理与原画一致选项的切换"""
        self.spin_bitrate.setEnabled(not checked)  # 当勾选时禁用比特率输入框
        if checked:
            # 当勾选"与原画一致"时，记录当前值（实际应该由视频处理器在处理时检测原视频比特率）
            logger.info("已启用使用原视频比特率")
        else:
            # 不需要在这里重置值，保留用户之前设置的比特率
            pass

    # 添加自定义颜色选择方法
    @pyqtSlot()
    def on_choose_custom_color(self):
        """选择自定义水印颜色"""
        from PyQt5.QtWidgets import QColorDialog
        from PyQt5.QtGui import QColor
        
        current_color = QColor(self.watermark_color)
        color = QColorDialog.getColor(current_color, self, "选择水印颜色")
        
        if color.isValid():
            self.watermark_color = color.name()
            # 将combobox设置为自定义
            if self.combo_watermark_color.findText("自定义") == -1:
                self.combo_watermark_color.addItem("自定义")
            self.combo_watermark_color.setCurrentText("自定义")
    
    def on_watermark_color_changed(self, color_name):
        """处理水印颜色选择改变"""
        color_map = {
            "白色": "#FFFFFF",
            "黑色": "#000000",
            "红色": "#FF0000",
            "绿色": "#00FF00",
            "蓝色": "#0000FF",
            "黄色": "#FFFF00",
            "紫色": "#800080",
            "青色": "#00FFFF",
            "橙色": "#FFA500",
            "粉色": "#FFC0CB",
            "自定义": self.watermark_color  # 使用上次的自定义颜色
        }
        
        if color_name in color_map:
            self.watermark_color = color_map[color_name]
            # 更新颜色按钮
            self._update_color_button(self.watermark_color)
    
    def _update_color_button(self, color_hex):
        """更新颜色按钮的背景色"""
        try:
            from PyQt5.QtGui import QColor
            # 查找自定义颜色按钮
            if hasattr(self, 'btn_custom_color'):
                # 设置按钮背景色
                style = f"background-color: {color_hex}; border: 1px solid #888888;"
                self.btn_custom_color.setStyleSheet(style)
                
                # 根据颜色亮度决定文字颜色
                color = QColor(color_hex)
                luminance = (0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()) / 255
                text_color = "black" if luminance > 0.5 else "white"
                
                # 更新按钮文字颜色
                style = f"background-color: {color_hex}; color: {text_color}; border: 1px solid #888888;"
                self.btn_custom_color.setStyleSheet(style)
        except Exception as e:
            logger.error(f"更新颜色按钮时出错: {e}")

    # 在类中添加用户设置加载和保存的方法
    def _load_user_settings(self):
        """从用户配置加载设置"""
        logger.info("正在加载用户设置...")
        
        # 恢复窗口大小和位置
        try:
            window_size = self.user_settings.get_setting("main_window_size", [1200, 800])
            if len(window_size) == 2 and all(isinstance(x, int) for x in window_size):
                self.resize(window_size[0], window_size[1])
                
            window_pos = self.user_settings.get_setting("main_window_pos", [100, 100])
            if len(window_pos) == 2 and all(isinstance(x, int) for x in window_pos):
                from PyQt5.QtCore import QPoint
                self.move(QPoint(window_pos[0], window_pos[1]))
                
            # 恢复活动标签页
            active_tab = self.user_settings.get_setting("last_active_tab", 0)
            if isinstance(active_tab, int) and 0 <= active_tab < self.tabs.count():
                self.tabs.setCurrentIndex(active_tab)
        except Exception as e:
            logger.error(f"恢复窗口状态时出错: {e}")
        
        # 加载素材列表
        try:
            self.folder_extract_modes = self.user_settings.get_setting("folder_extract_modes", {})
            
            # 加载上次的素材列表
            last_materials = self.user_settings.get_setting("last_material_folders", [])
            
            # 自动导入上次的素材列表
            if last_materials:
                logger.info(f"正在恢复上次的素材列表，共 {len(last_materials)} 项")
                self.video_table.setRowCount(0)  # 清空现有列表
                
                # 首先尝试获取素材根目录
                root_dir = self.user_settings.get_setting("import_folder", "")
                if root_dir and os.path.exists(root_dir):
                    folder_name = os.path.basename(root_dir)
                    self.parent_folder_title.setText(folder_name)
                else:
                    self.parent_folder_title.setText("未选择文件夹")
                
                # 添加素材到表格
                valid_count = 0
                for item in last_materials:
                    # 检查路径是否有效
                    if "path" in item and os.path.exists(item["path"]):
                        folder_path = item["path"]
                        folder_name = item.get("name", os.path.basename(folder_path))
                        extract_mode = item.get("extract_mode", "single_video")
                        
                        # 更新抽取模式
                        self.folder_extract_modes[folder_path] = extract_mode
                        
                        # 添加到表格
                        row_count = self.video_table.rowCount()
                        self.video_table.insertRow(row_count)
                        
                        # 设置表格项
                        self.video_table.setItem(row_count, 0, QTableWidgetItem(str(row_count + 1)))
                        self.video_table.setItem(row_count, 1, QTableWidgetItem(folder_name))
                        self.video_table.setItem(row_count, 2, QTableWidgetItem(folder_path))
                        self.video_table.setItem(row_count, 3, QTableWidgetItem("0"))  # 暂时设为0
                        self.video_table.setItem(row_count, 4, QTableWidgetItem("0"))  # 暂时设为0
                        
                        # 使用ExtractModeItem显示状态
                        status_item = ExtractModeItem("", extract_mode, folder_path)
                        status_item.set_status("就绪")
                        self.video_table.setItem(row_count, 5, status_item)
                        
                        valid_count += 1
                
                logger.info(f"成功恢复 {valid_count} 个有效素材")
                
                # 如果没有有效素材，清空标题
                if valid_count == 0:
                    self.parent_folder_title.setText("未选择文件夹")
        except Exception as e:
            logger.error(f"恢复素材列表时出错: {e}")
        
        # 加载界面设置
        try:
            # 缓存目录设置
            cache_dir = self.user_settings.get_setting("cache_dir", "")
            if cache_dir and os.path.exists(cache_dir):
                self.cache_config.set_cache_dir(cache_dir)
                if hasattr(self, "edit_cache_dir"):
                    self.edit_cache_dir.setText(cache_dir)
            
            # 保存目录
            save_dir = self.user_settings.get_setting("save_dir", "")
            self.edit_save_dir.setText(save_dir)
            
            # 分辨率
            resolution = self.user_settings.get_setting("resolution", "竖屏 1080x1920")
            index = self.combo_resolution.findText(resolution)
            if index >= 0:
                self.combo_resolution.setCurrentIndex(index)
            
            # 比特率
            bitrate = self.user_settings.get_setting("bitrate", 5000)
            self.spin_bitrate.setValue(bitrate)
            
            # 原画比特率选项
            original_bitrate = self.user_settings.get_setting("original_bitrate", False)
            self.chk_original_bitrate.setChecked(original_bitrate)
            # 根据选项状态更新比特率输入框状态
            self.spin_bitrate.setEnabled(not original_bitrate)
            
            # 转场效果
            transition = self.user_settings.get_setting("transition", "不使用转场")
            index = self.combo_transition.findText(transition)
            if index >= 0:
                self.combo_transition.setCurrentIndex(index)
            
            # GPU加速
            gpu = self.user_settings.get_setting("gpu", "自动检测")
            index = self.combo_gpu.findText(gpu)
            if index >= 0:
                self.combo_gpu.setCurrentIndex(index)
            
            # 编码模式
            encode_mode = self.user_settings.get_setting("encode_mode", "标准模式")
            index = self.combo_encode_mode.findText(encode_mode)
            if index >= 0:
                self.combo_encode_mode.setCurrentIndex(index)
            
            # 音频处理模式
            if hasattr(self, "combo_audio_mode"):
                audio_mode = self.user_settings.get_setting("audio_mode", "自动识别")
                index = self.combo_audio_mode.findText(audio_mode)
                if index >= 0:
                    self.combo_audio_mode.setCurrentIndex(index)
            
            # 水印设置
            watermark_enabled = self.user_settings.get_setting("watermark_enabled", False)
            self.chk_enable_watermark.setChecked(watermark_enabled)
            
            watermark_prefix = self.user_settings.get_setting("watermark_prefix", "@视频作者")
            self.edit_watermark_prefix.setText(watermark_prefix)
            
            watermark_size = self.user_settings.get_setting("watermark_size", 36)
            self.spin_watermark_size.setValue(watermark_size)
            
            self.watermark_color = self.user_settings.get_setting("watermark_color", "#FFFFFF")
            self._update_color_button(self.watermark_color)
            
            watermark_position = self.user_settings.get_setting("watermark_position", "右下角")
            index = self.combo_watermark_position.findText(watermark_position)
            if index >= 0:
                self.combo_watermark_position.setCurrentIndex(index)
            
            watermark_pos_x = self.user_settings.get_setting("watermark_pos_x", 20)
            self.spin_pos_x.setValue(watermark_pos_x)
            
            watermark_pos_y = self.user_settings.get_setting("watermark_pos_y", 20)
            self.spin_pos_y.setValue(watermark_pos_y)
            
            # 音量设置
            voice_volume = self.user_settings.get_setting("voice_volume", 1.0)
            self.spin_voice_volume.setValue(voice_volume)
            
            bgm_volume = self.user_settings.get_setting("bgm_volume", 0.5)
            self.spin_bgm_volume.setValue(bgm_volume)
            
            # 背景音乐路径
            bgm_path = self.user_settings.get_setting("bgm_path", "")
            self.edit_bgm_path.setText(bgm_path)
            
            # 生成数量
            generate_count = self.user_settings.get_setting("generate_count", 1)
            self.spin_generate_count.setValue(generate_count)
        except Exception as e:
            logger.error(f"加载界面设置时出错: {e}")
            
        logger.info("用户设置加载完成")
    
    def _import_material_folder(self, root_dir):
        """导入指定的素材文件夹"""
        if not root_dir or not os.path.exists(root_dir):
            # 如果目录不存在，更新界面显示
            self.parent_folder_title.setText("路径不存在")
            return
        
        # 更新界面显示的父文件夹名称（只显示文件夹名）
        folder_name = os.path.basename(root_dir)
        self.parent_folder_title.setText(folder_name)
            
        from src.utils.file_utils import resolve_shortcut
        from src.utils.logger import get_logger
        
        logger = get_logger()
        
        added_count = 0
        skipped_count = 0
        normal_count = 0
        shortcut_count = 0
        shortcut_errors = 0
        
        # 设置鼠标等待状态
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        try:
            # 遍历根目录下的所有子文件夹
            for item in os.listdir(root_dir):
                item_path = os.path.join(root_dir, item)
                
                actual_path = item_path
                is_shortcut = False
                
                # 检查是否是快捷方式
                if item.lower().endswith('.lnk'):
                    logger.info(f"发现可能的快捷方式: {item_path}")
                    shortcut_target = resolve_shortcut(item_path)
                    if shortcut_target:
                        actual_path = shortcut_target
                        is_shortcut = True
                        shortcut_count += 1
                        logger.info(f"检测到快捷方式子文件夹: {item_path} -> {actual_path}")
                    else:
                        shortcut_errors += 1
                        logger.warning(f"无法解析快捷方式: {item_path}")
                        continue
                elif os.path.isdir(item_path):
                    normal_count += 1
                else:
                    logger.debug(f"跳过非文件夹项目: {item_path}")
                    continue
                
                # 只处理文件夹(或解析后的快捷方式目标是文件夹)
                if not os.path.isdir(actual_path):
                    logger.warning(f"项目不是目录，跳过: {actual_path}")
                    continue
                
                # 检查是否有"视频"或"配音"子文件夹
                has_video_folder = os.path.exists(os.path.join(actual_path, "视频"))
                has_audio_folder = os.path.exists(os.path.join(actual_path, "配音"))
                
                if has_video_folder or has_audio_folder:
                    # 检查子文件夹中是否有媒体文件
                    video_count = 0
                    audio_count = 0
                    
                    if has_video_folder:
                        try:
                            media = list_media_files(os.path.join(actual_path, "视频"), recursive=True)
                            video_count = len(media['videos'])
                        except Exception as e:
                            logger.error(f"扫描视频文件夹失败: {str(e)}")
                    
                    if has_audio_folder:
                        try:
                            media = list_media_files(os.path.join(actual_path, "配音"), recursive=True)
                            audio_count = len(media['audios'])
                        except Exception as e:
                            logger.error(f"扫描音频文件夹失败: {str(e)}")
                    
                    # 如果有媒体文件，则添加到素材列表
                    if video_count > 0 or audio_count > 0:
                        row_count = self.video_table.rowCount()
                        self.video_table.setRowCount(row_count + 1)
                        
                        # 如果是快捷方式，显示名称时去掉.lnk后缀
                        display_name = item
                        if is_shortcut:
                            if display_name.lower().endswith('.lnk'):
                                display_name = display_name[:-4]
                            display_name += " (快捷方式)"
                        
                        # 检查是否已有抽取模式设置
                        extract_mode = self.folder_extract_modes.get(actual_path, "single_video")
                        
                        # 如果是多视频拼接模式，更新显示名称
                        if extract_mode == "multi_video" and " [多视频拼接]" not in display_name:
                            display_name += " [多视频拼接]"
                        
                        # 添加图标以区分本体和快捷方式
                        folder_item = QTableWidgetItem(display_name)
                        if is_shortcut:
                            # 使用Qt内置图标
                            folder_item.setIcon(QApplication.style().standardIcon(QStyle.SP_FileLinkIcon))
                        else:
                            folder_item.setIcon(QApplication.style().standardIcon(QStyle.SP_DirIcon))
                        
                        # 根据抽取模式设置字体颜色
                        if extract_mode == "multi_video":
                            folder_item.setForeground(QColor("#0000FF"))  # 蓝色表示多视频拼接模式
                            folder_item.setToolTip("多视频拼接模式：允许多个短视频拼接以满足配音长度")
                        else:
                            folder_item.setForeground(QColor("#000000"))  # 黑色表示单视频模式
                            folder_item.setToolTip("单视频模式：只选择时长大于或等于配音的视频")
                        
                        self.video_table.setItem(row_count, 0, QTableWidgetItem(str(row_count + 1)))  # 序号
                        self.video_table.setItem(row_count, 1, folder_item)  # 素材名称（带图标）
                        self.video_table.setItem(row_count, 2, QTableWidgetItem(actual_path))  # 素材路径 (使用实际路径)
                        
                        # 如果是快捷方式，添加原始路径信息
                        tooltip = folder_item.toolTip() + f"\n实际路径: {actual_path}"
                        if is_shortcut:
                            tooltip = f"快捷方式: {item_path}\n{tooltip}"
                        folder_item.setToolTip(tooltip)
                        
                        self.video_table.setItem(row_count, 3, QTableWidgetItem(str(video_count)))  # 视频数量
                        self.video_table.setItem(row_count, 4, QTableWidgetItem(str(audio_count)))  # 配音数量
                        
                        # 根据抽取模式设置状态文本
                        if extract_mode == "multi_video":
                            status_text = "待处理 (多视频拼接)"
                        else:
                            status_text = "待处理 (单视频)"
                        
                        # 使用自定义的ExtractModeItem来替代普通的QTableWidgetItem
                        status_item = ExtractModeItem(status_text, extract_mode, actual_path)
                        status_item.set_status("待处理")
                        self.video_table.setItem(row_count, 5, status_item)  # 状态
                        
                        added_count += 1
                    else:
                        skipped_count += 1
                        logger.warning(f"跳过没有媒体文件的素材文件夹: {actual_path}")
                else:
                    skipped_count += 1
                    logger.warning(f"跳过没有视频或配音子文件夹的素材文件夹: {actual_path}")
        except Exception as e:
            logger.error(f"导入素材文件夹时出错: {str(e)}")
        finally:
            # 恢复鼠标状态
            QApplication.restoreOverrideCursor()
        
        # 记录导入情况的信息
        if added_count > 0:
            logger.info(f"自动导入完成: 成功导入 {added_count} 个素材文件夹，跳过 {skipped_count} 个不符合条件的文件夹")
            # 记录混合情况的信息
            if normal_count > 0 and shortcut_count > 0:
                logger.info(f"自动导入: 检测到混合模式，包含 {normal_count} 个普通文件夹和 {shortcut_count} 个快捷方式")
            elif shortcut_count > 0:
                logger.info(f"自动导入: 检测到纯快捷方式模式，包含 {shortcut_count} 个快捷方式")
            else:
                logger.info(f"自动导入: 检测到标准模式，包含 {normal_count} 个普通文件夹")
        else:
            logger.warning(f"自动导入: 未找到符合条件的素材文件夹，路径: {root_dir}")
    
    def _save_user_settings(self):
        """保存当前界面设置到用户配置"""
        logger.info("正在保存用户设置...")
        
        # 获取主窗口位置和大小
        window_size = [self.width(), self.height()]
        window_pos = [self.pos().x(), self.pos().y()]
        
        # 获取当前活动的标签页
        active_tab = self.tabs.currentIndex()
        
        # 获取素材列表数据
        material_folders = []
        for row in range(self.video_table.rowCount()):
            try:
                folder_path = self.video_table.item(row, 2).text()
                folder_name = self.video_table.item(row, 1).text()
                
                # 如果有状态列，获取抽取模式
                extract_mode = "single_video"  # 默认值
                status_item = self.video_table.item(row, 5)
                if status_item and isinstance(status_item, ExtractModeItem):
                    extract_mode = status_item.extract_mode
                
                # 只添加有效路径
                if folder_path and os.path.exists(folder_path):
                    material_folders.append({
                        "name": folder_name,
                        "path": folder_path,
                        "extract_mode": extract_mode
                    })
            except Exception as e:
                logger.error(f"保存素材列表数据时出错: {e}")
        
        # 准备设置字典
        settings = {
            # 界面状态
            "main_window_size": window_size,
            "main_window_pos": window_pos,
            "last_active_tab": active_tab,
            
            # 素材设置
            "last_material_folders": material_folders,
            "folder_extract_modes": self.folder_extract_modes,
            
            # 导入设置
            "import_folder": self.user_settings.get_setting("import_folder", ""),
            
            # 输出目录
            "save_dir": self.edit_save_dir.text(),
            
            # 视频参数
            "resolution": self.combo_resolution.currentText(),
            "bitrate": self.spin_bitrate.value(),
            "original_bitrate": self.chk_original_bitrate.isChecked(),
            "transition": self.combo_transition.currentText(),
            "gpu": self.combo_gpu.currentText(),
            "encode_mode": self.combo_encode_mode.currentText(),
            
            # 音频设置
            "voice_volume": self.spin_voice_volume.value(),
            "bgm_volume": self.spin_bgm_volume.value(),
            "bgm_path": self.edit_bgm_path.text(),
            "audio_mode": self.combo_audio_mode.currentText() if hasattr(self, "combo_audio_mode") else "自动识别",
            
            # 水印设置
            "watermark_enabled": self.chk_enable_watermark.isChecked(),
            "watermark_prefix": self.edit_watermark_prefix.text(),
            "watermark_size": self.spin_watermark_size.value(),
            "watermark_color": self.watermark_color,
            "watermark_position": self.combo_watermark_position.currentText(),
            "watermark_pos_x": self.spin_pos_x.value(),
            "watermark_pos_y": self.spin_pos_y.value(),
            
            # 批量处理
            "generate_count": self.spin_generate_count.value(),
            
            # 缓存目录
            "cache_dir": self.cache_config.get_cache_dir()
        }
        
        # 批量保存设置
        self.user_settings.set_multiple_settings(settings)
        logger.info("用户设置保存完成")

    def closeEvent(self, event):
        """窗口关闭事件，保存用户设置"""
        # 保存当前设置
        self._save_user_settings()
        # 继续默认的关闭行为
        super().closeEvent(event)

    # 添加水印位置预览相关的方法
    def on_watermark_position_changed(self, position):
        """处理水印预设位置变化"""
        try:
            # 检查预览控件是否已创建
            if hasattr(self, "watermark_preview") and self.watermark_preview:
                # 更新预览控件
                self.watermark_preview.set_watermark_position(position)
        except Exception as e:
            logger.error(f"更新水印位置时出错: {str(e)}")
        
        # 保存设置
        self.user_settings.set_setting("watermark_position", position)
    
    def on_watermark_size_changed(self, size):
        """处理水印字体大小变化"""
        try:
            # 检查预览控件是否已创建
            if hasattr(self, "watermark_preview") and self.watermark_preview:
                # 更新预览控件
                self.watermark_preview.set_watermark_size(size)
        except Exception as e:
            logger.error(f"更新水印大小时出错: {str(e)}")
        
        # 保存设置
        self.user_settings.set_setting("watermark_size", size)
    
    def on_watermark_prefix_changed(self, prefix):
        """处理水印前缀文本变化"""
        # 更新预览文本
        preview_text = prefix + "2025.0101.0000" if prefix else "2025.0101.0000"
        self.watermark_preview.set_watermark_text(preview_text)
    
    def on_pos_x_changed(self, value):
        """处理X轴微调值变化"""
        try:
            # 如果预览控件不存在，则创建一个
            if not hasattr(self, "watermark_preview") or self.watermark_preview is None:
                self.watermark_preview = WatermarkPreview()
            # 更新预览控件
            self.watermark_preview.set_watermark_offset(value, self.spin_pos_y.value())
        except Exception as e:
            logger.warning(f"更新水印X轴位置时出错: {e}")
        
        # 保存设置
        self.user_settings.set_setting("watermark_pos_x", value)
    
    def on_pos_y_changed(self, value):
        """处理Y轴微调值变化"""
        try:
            # 如果预览控件不存在，则创建一个
            if not hasattr(self, "watermark_preview") or self.watermark_preview is None:
                self.watermark_preview = WatermarkPreview()
            # 更新预览控件
            self.watermark_preview.set_watermark_offset(self.spin_pos_x.value(), value)
        except Exception as e:
            logger.warning(f"更新水印Y轴位置时出错: {e}")
        
        # 保存设置
        self.user_settings.set_setting("watermark_pos_y", value)
    
    def on_preview_position_changed(self, x, y):
        """处理预览控件中拖动位置变化"""
        # 更新微调输入框，但不触发它们的valueChanged信号
        self.spin_pos_x.blockSignals(True)
        self.spin_pos_y.blockSignals(True)
        self.spin_pos_x.setValue(x)
        self.spin_pos_y.setValue(y)
        self.spin_pos_x.blockSignals(False)
        self.spin_pos_y.blockSignals(False)
        
        # 保存设置
        self.user_settings.set_setting("watermark_pos_x", x)
        self.user_settings.set_setting("watermark_pos_y", y)
    
    def on_reset_watermark_position(self):
        """重置水印位置"""
        # 重置微调值
        self.spin_pos_x.setValue(0)
        self.spin_pos_y.setValue(0)
        
        # 重置预览控件
        self.watermark_preview.set_watermark_offset(0, 0)
    
    @pyqtSlot()
    def on_preview_watermark(self):
        """显示水印预览对话框"""
        try:
            # 创建并显示水印预览对话框
            preview_dialog = WatermarkPreviewDialog(self)
            result = preview_dialog.exec_()
            
            # 如果用户点击"确定"，应用新的设置
            if result == QDialog.Accepted:
                position, pos_x, pos_y = preview_dialog.get_position_values()
                
                # 更新UI控件（阻止信号，避免触发额外的更新）
                self.combo_watermark_position.blockSignals(True)
                self.spin_pos_x.blockSignals(True)
                self.spin_pos_y.blockSignals(True)
                
                self.combo_watermark_position.setCurrentText(position)
                self.spin_pos_x.setValue(pos_x)
                self.spin_pos_y.setValue(pos_y)
                
                self.combo_watermark_position.blockSignals(False)
                self.spin_pos_x.blockSignals(False)
                self.spin_pos_y.blockSignals(False)
                
                # 保存设置
                self.user_settings.set_setting("watermark_position", position)
                self.user_settings.set_setting("watermark_pos_x", pos_x)
                self.user_settings.set_setting("watermark_pos_y", pos_y)
                
                # 记录日志
                logger.info(f"已更新水印位置: {position}, 偏移: ({pos_x}, {pos_y})")
        except Exception as e:
            logger.error(f"显示水印预览对话框时出错: {str(e)}")
            QMessageBox.warning(self, "预览错误", f"无法显示水印预览: {str(e)}")

    def _update_watermark_preview(self):
        """更新水印预览控件，应用当前设置"""
        # 不再需要此方法，因为我们不再直接显示预览控件
        # 保留此方法以保持兼容性，但不执行任何操作
        pass

    def _show_folder_context_menu(self, position):
        """显示文件夹的右键菜单，允许设置抽取模式"""
        # 获取当前选中的行
        selected_rows = self.video_table.selectionModel().selectedRows()
        
        if not selected_rows:
            return
            
        # 仅处理单行选择
        row = selected_rows[0].row()
        folder_path = self.video_table.item(row, 2).text()
        folder_name = self.video_table.item(row, 1).text()
        
        # 创建右键菜单
        context_menu = QMenu(self)
        
        # 添加抽取模式选择子菜单
        extract_mode_menu = QMenu("抽取模式", self)
        context_menu.addMenu(extract_mode_menu)
        
        # 获取当前文件夹的抽取模式
        current_mode = self.folder_extract_modes.get(folder_path, "single_video")
        
        # 单视频模式选项
        single_action = QAction("单视频 (只选长于配音的视频)", self)
        single_action.setCheckable(True)
        single_action.setChecked(current_mode == "single_video")
        extract_mode_menu.addAction(single_action)
        
        # 多视频拼接模式选项
        multi_action = QAction("多视频拼接 (多个短视频拼接)", self)
        multi_action.setCheckable(True)
        multi_action.setChecked(current_mode == "multi_video")
        extract_mode_menu.addAction(multi_action)
        
        # 添加分割线
        context_menu.addSeparator()
        
        # 添加查看文件夹选项
        open_folder_action = QAction("打开文件夹", self)
        context_menu.addAction(open_folder_action)
        
        # 添加重置为单视频模式选项
        reset_action = QAction("重置为单视频模式", self)
        context_menu.addAction(reset_action)
        
        # 显示菜单并获取选择结果
        action = context_menu.exec_(self.video_table.viewport().mapToGlobal(position))
        
        # 处理选择结果
        if action == single_action:
            self.folder_extract_modes[folder_path] = "single_video"
            logger.info(f"设置文件夹 '{folder_name}' 的抽取模式为: 单视频")
            
            # 更新表格项图标或文本以显示当前模式
            folder_item = self.video_table.item(row, 1)
            if folder_item:
                # 移除多视频拼接标记
                display_name = folder_name.replace(" [多视频拼接]", "")
                folder_item.setText(display_name)
                folder_item.setToolTip("单视频模式：只选择时长大于或等于配音的视频")
                folder_item.setForeground(QColor("#000000"))  # 黑色表示单视频模式
                
            # 更新状态列
            status_item = self.video_table.item(row, 5)
            if status_item:
                if isinstance(status_item, ExtractModeItem):
                    status_item.extract_mode = "single_video"
                    status_item._update_appearance()
                else:
                    status_item = ExtractModeItem("", "single_video", folder_path)
                    status_item.set_status("待处理")
                    self.video_table.setItem(row, 5, status_item)
            
            # 保存用户设置
            self._save_user_settings()
            
        elif action == multi_action:
            self.folder_extract_modes[folder_path] = "multi_video"
            logger.info(f"设置文件夹 '{folder_name}' 的抽取模式为: 多视频拼接")
            
            # 更新表格项图标或文本以显示当前模式
            folder_item = self.video_table.item(row, 1)
            if folder_item:
                # 如果名称中没有多视频拼接的标记，则添加
                if " [多视频拼接]" not in folder_name:
                    display_name = f"{folder_name.replace(' [多视频拼接]', '')} [多视频拼接]"
                    folder_item.setText(display_name)
                folder_item.setToolTip("多视频拼接模式：允许多个短视频拼接以满足配音长度")
                folder_item.setForeground(QColor("#0000FF"))  # 蓝色表示多视频拼接模式
                
            # 更新状态列
            status_item = self.video_table.item(row, 5)
            if status_item:
                if isinstance(status_item, ExtractModeItem):
                    status_item.extract_mode = "multi_video"
                    status_item._update_appearance()
                else:
                    status_item = ExtractModeItem("", "multi_video", folder_path)
                    status_item.set_status("待处理")
                    self.video_table.setItem(row, 5, status_item)
            
            # 保存用户设置
            self._save_user_settings()
            
        elif action == open_folder_action:
            # 打开文件夹
            try:
                if os.path.exists(folder_path):
                    if os.name == 'nt':  # Windows
                        os.startfile(folder_path)
                    elif os.name == 'posix':  # macOS, Linux
                        subprocess.Popen(['open', folder_path] if sys.platform == 'darwin' else ['xdg-open', folder_path])
                    logger.info(f"打开文件夹: {folder_path}")
                else:
                    logger.warning(f"文件夹不存在: {folder_path}")
                    QMessageBox.warning(self, "打开文件夹", f"文件夹不存在: {folder_path}")
            except Exception as e:
                logger.error(f"打开文件夹 {folder_path} 失败: {str(e)}")
                QMessageBox.warning(self, "打开文件夹", f"打开文件夹失败: {str(e)}")
        
        elif action == reset_action:
            # 从字典中移除该路径的设置，恢复为默认的单视频模式
            if folder_path in self.folder_extract_modes:
                del self.folder_extract_modes[folder_path]
                logger.info(f"重置文件夹 '{folder_name}' 的抽取模式为默认的单视频模式")
                
                # 更新表格项
                folder_item = self.video_table.item(row, 1)
                if folder_item:
                    display_name = folder_name.replace(" [多视频拼接]", "")
                    folder_item.setText(display_name)
                    folder_item.setToolTip("单视频模式（默认）：只选择时长大于或等于配音的视频")
                    folder_item.setForeground(QColor("#000000"))  # 黑色表示单视频模式
                
                # 更新状态列
                status_item = self.video_table.item(row, 5)
                if status_item:
                    if isinstance(status_item, ExtractModeItem):
                        status_item.extract_mode = "single_video"
                        status_item._update_appearance()
                    else:
                        status_item = ExtractModeItem("", "single_video", folder_path)
                        status_item.set_status("待处理")
                        self.video_table.setItem(row, 5, status_item)
                
                # 保存用户设置
                self._save_user_settings()

    def show_extract_mode_guide(self):
        """显示抽取模式说明"""
        guide_text = """
<h3>抽取模式说明</h3>

<p>本软件支持两种视频抽取模式，您可以为每个文件夹单独设置：</p>

<h4>1. 单视频模式（默认）</h4>
<p>在单视频模式下，软件会从文件夹中选择一个<b>时长大于等于配音时长</b>的视频，并将其裁剪为与配音相同的时长。如果没有足够长的视频，将使用最长的一个视频。</p>
<p><b>适用场景：</b>当您有较长的素材视频，需要精确匹配配音时使用。</p>

<h4>2. 多视频拼接模式</h4>
<p>在多视频拼接模式下，软件会从文件夹中选择多个视频并拼接在一起，以满足配音的时长需求。这种模式适合当您只有很多短视频，但需要匹配较长配音的情况。</p>
<p><b>适用场景：</b>当文件夹中的视频都比较短，单个视频无法覆盖配音时长时使用。</p>

<h4>如何设置抽取模式</h4>
<p>右键点击素材列表中的文件夹，从上下文菜单中选择"抽取模式"，然后选择相应的抽取模式：</p>
<ul>
  <li>单视频（只选长于配音的视频）</li>
  <li>多视频拼接（多个短视频拼接）</li>
</ul>

<p>设置后，文件夹名称会更新以反映当前的抽取模式：</p>
<ul>
  <li>单视频模式：显示为黑色</li>
  <li>多视频拼接模式：显示为蓝色，并在名称后添加"[多视频拼接]"标记</li>
</ul>

<p>您可以随时更改抽取模式，每个文件夹可以单独设置不同的抽取模式。软件会自动保存您的设置。</p>
        """
        
        dialog = QDialog(self)
        dialog.setWindowTitle("抽取模式说明")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(500)
        
        layout = QVBoxLayout(dialog)
        
        # 使用QTextBrowser支持HTML格式
        text_browser = QTextBrowser()
        text_browser.setHtml(guide_text)
        text_browser.setOpenExternalLinks(True)
        
        layout.addWidget(text_browser)
        
        # 添加按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
        btn_box.accepted.connect(dialog.accept)
        layout.addWidget(btn_box)
        
        dialog.exec_()

    # 添加处理表格点击事件的方法
    def _on_table_cell_clicked(self, row, column):
        """处理表格单元格点击事件"""
        # 只处理状态列（第6列，索引为5）的点击
        if column == 5:
            item = self.video_table.item(row, column)
            if isinstance(item, ExtractModeItem):
                # 如果状态是处理中，不允许切换
                if item.status == "处理中":
                    QMessageBox.information(
                        self,
                        "无法切换模式",
                        "正在处理中，无法切换抽取模式。\n请等待处理完成后再进行切换。"
                    )
                    return
                
                folder_path = item.folder_path
                if not folder_path:
                    # 如果ExtractModeItem没有存储路径，从路径列获取
                    folder_path = self.video_table.item(row, 2).text()
                
                # 切换抽取模式
                current_mode = self.folder_extract_modes.get(folder_path, "single_video")
                new_mode = "single_video" if current_mode == "multi_video" else "multi_video"
                
                # 更新抽取模式字典
                self.folder_extract_modes[folder_path] = new_mode
                
                # 更新表格项
                item.extract_mode = new_mode
                item._update_appearance()
                
                # 更新文件夹名称显示，添加或删除[多视频拼接]标记
                folder_item = self.video_table.item(row, 1)
                if folder_item:
                    folder_name = folder_item.text()
                    if new_mode == "multi_video" and " [多视频拼接]" not in folder_name:
                        folder_item.setText(f"{folder_name.replace(' [多视频拼接]', '')} [多视频拼接]")
                        folder_item.setForeground(QColor("#0000FF"))  # 蓝色
                    elif new_mode == "single_video" and " [多视频拼接]" in folder_name:
                        folder_item.setText(folder_name.replace(" [多视频拼接]", ""))
                        folder_item.setForeground(QColor("#000000"))  # 黑色
                
                # 保存设置，确保记住拼接模式设置
                self._save_user_settings()
                
                # 记录日志
                folder_name = self.video_table.item(row, 1).text()
                logger.info(f"切换文件夹 '{folder_name}' 的抽取模式为: {new_mode}")
                
                # 显示提示信息
                mode_display = "多视频拼接" if new_mode == "multi_video" else "单视频"
                self.status_label.setText(f"已切换 '{folder_name}' 为{mode_display}模式")
            else:
                # 如果不是ExtractModeItem，则尝试创建一个
                folder_path = self.video_table.item(row, 2).text()
                if folder_path:
                    # 获取当前抽取模式
                    current_mode = self.folder_extract_modes.get(folder_path, "single_video")
                    # 创建新的ExtractModeItem
                    status_item = ExtractModeItem("", current_mode, folder_path)
                    status_item.set_status("待处理")
                    self.video_table.setItem(row, 5, status_item)
                    
                    # 记录日志
                    logger.info(f"将表格项转换为抽取模式项: {folder_path}")

class WatermarkPreview(QFrame):
    """水印位置预览控件，允许用户通过拖动调整水印位置"""
    
    # 自定义信号，当位置变化时发出
    positionChanged = pyqtSignal(int, int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 设置固定尺寸，这是预览框的尺寸
        self.setFixedSize(180, 320)  # 竖屏预览，模拟16:9的视频
        
        # 设置边框
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Sunken)
        
        # 水印位置相关属性
        self.watermark_position = "右上角"  # 预设位置
        self.watermark_pos_x = 0  # X轴微调值
        self.watermark_pos_y = 0  # Y轴微调值
        self.watermark_text = "预览文字"  # 模拟水印文字
        self.watermark_color = "#FFFFFF"  # 水印颜色，默认白色
        self.watermark_size = 24  # 水印字体大小
        
        # 拖动相关属性
        self.dragging = False
        self.drag_start_pos = QPoint()
        self.drag_current_pos = QPoint()
        
        # 启用鼠标追踪，以便我们可以随时获取鼠标位置
        self.setMouseTracking(True)
    
    def set_watermark_position(self, position):
        """设置水印预设位置"""
        self.watermark_position = position
        self._update_watermark_position()
        self.update()  # 重绘界面
    
    def set_watermark_offset(self, x, y):
        """设置水印位置的微调值"""
        self.watermark_pos_x = x
        self.watermark_pos_y = y
        self.update()  # 重绘界面
    
    def set_watermark_color(self, color):
        """设置水印颜色"""
        self.watermark_color = color
        self.update()  # 重绘界面
    
    def set_watermark_size(self, size):
        """设置水印字体大小"""
        self.watermark_size = size
        self.update()  # 重绘界面
    
    def set_watermark_text(self, text):
        """设置水印文本"""
        self.watermark_text = text if text else "预览文字"
        self.update()  # 重绘界面
    
    def _calculate_watermark_rect(self):
        """计算水印文本框的位置和大小"""
        # 获取控件大小
        width = self.width()
        height = self.height()
        
        # 计算水印文本的大小（这是简化计算，实际应该根据字体大小和文本长度计算）
        font_size = max(10, min(self.watermark_size / 3, 20))  # 缩放字体大小以适应预览
        text_width = len(self.watermark_text) * font_size * 0.65
        text_height = font_size * 1.2
        
        # 根据预设位置计算基础坐标
        if self.watermark_position == "右上角":
            x = width - text_width - 10
            y = 10
        elif self.watermark_position == "左上角":
            x = 10
            y = 10
        elif self.watermark_position == "右下角":
            x = width - text_width - 10
            y = height - text_height - 10
        elif self.watermark_position == "左下角":
            x = 10
            y = height - text_height - 10
        elif self.watermark_position == "中心":
            x = (width - text_width) / 2
            y = (height - text_height) / 2
        else:
            x = width - text_width - 10  # 默认右上角
            y = 10
        
        # 应用微调偏移
        x_scale = width / 1080  # 假设原始视频是1080宽（竖屏）
        y_scale = height / 1920  # 假设原始视频是1920高（竖屏）
        
        x += self.watermark_pos_x * x_scale
        y += self.watermark_pos_y * y_scale
        
        # 创建并返回文本框矩形
        return QRect(int(x), int(y), int(text_width), int(text_height))
    
    def _update_watermark_position(self):
        """根据拖动位置更新水印的微调坐标"""
        if not self.dragging:
            return
        
        # 获取当前文本框位置
        text_rect = self._calculate_watermark_rect()
        
        # 计算拖动造成的偏移
        dx = self.drag_current_pos.x() - self.drag_start_pos.x()
        dy = self.drag_current_pos.y() - self.drag_start_pos.y()
        
        # 重新计算微调值
        width = self.width()
        height = self.height()
        x_scale = 1080 / width  # 从预览尺寸转换回实际视频尺寸
        y_scale = 1920 / height
        
        # 计算基于拖拽的新微调值
        new_pos_x = int(self.watermark_pos_x + dx * x_scale)
        new_pos_y = int(self.watermark_pos_y + dy * y_scale)
        
        # 限制范围（可选，防止水印被拖出视频边界太远）
        new_pos_x = max(-100, min(new_pos_x, 100))
        new_pos_y = max(-100, min(new_pos_y, 100))
        
        # 发出位置变化信号
        if new_pos_x != self.watermark_pos_x or new_pos_y != self.watermark_pos_y:
            self.watermark_pos_x = new_pos_x
            self.watermark_pos_y = new_pos_y
            self.positionChanged.emit(new_pos_x, new_pos_y)
    
    def paintEvent(self, event):
        """绘制预览界面"""
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制背景（模拟视频画面的背景）
        painter.fillRect(self.rect(), QColor("#101010"))
        
        # 获取水印颜色的反色作为对比色
        watermark_qcolor = QColor(self.watermark_color)
        contrast_color = QColor(255 - watermark_qcolor.red(), 
                               255 - watermark_qcolor.green(), 
                               255 - watermark_qcolor.blue())
        
        # 计算水印文本框
        text_rect = self._calculate_watermark_rect()
        
        # 绘制水印文本
        font = painter.font()
        font.setPointSize(max(8, min(self.watermark_size / 3, 16)))  # 缩放字体大小以适应预览
        painter.setFont(font)
        painter.setPen(QColor(self.watermark_color))
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, self.watermark_text)
        
        # 如果正在拖动，绘制边框指示
        if self.dragging:
            pen = QPen(contrast_color, 1, Qt.DashLine)
            painter.setPen(pen)
            painter.drawRect(text_rect)
    
    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            # 检查是否点击在文本框内
            text_rect = self._calculate_watermark_rect()
            if text_rect.contains(event.pos()):
                self.dragging = True
                self.drag_start_pos = event.pos()
                self.drag_current_pos = event.pos()
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件"""
        if self.dragging:
            self.drag_current_pos = event.pos()
            self._update_watermark_position()
            self.update()  # 重绘界面
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton and self.dragging:
            self.dragging = False
            self.drag_current_pos = event.pos()
            self._update_watermark_position()
            self.update()  # 重绘界面

class WatermarkPreviewDialog(QDialog):
    """水印位置预览对话框，用于调整水印位置"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 设置窗口标题和大小
        self.setWindowTitle("水印位置预览")
        self.resize(480, 640)
        
        # 保存初始参数
        self.parent_window = parent
        self.position = parent.combo_watermark_position.currentText() if parent else "右上角"
        self.pos_x = parent.spin_pos_x.value() if parent else 0
        self.pos_y = parent.spin_pos_y.value() if parent else 0
        self.size = parent.spin_watermark_size.value() if parent else 24
        self.prefix = parent.edit_watermark_prefix.text() if parent else ""
        self.color = parent.watermark_color if parent else "#FFFFFF"
        
        # 创建布局
        self._init_ui()
        
    def _init_ui(self):
        """初始化UI"""
        # 主布局
        layout = QVBoxLayout(self)
        
        # 添加说明标签
        info_label = QLabel("在预览中拖动水印文字调整位置，设置完成后点击确定保存")
        info_label.setStyleSheet("color: #666666;")
        layout.addWidget(info_label)
        
        # 预览控件
        self.preview = WatermarkPreview()
        self.preview.set_watermark_position(self.position)
        self.preview.set_watermark_offset(self.pos_x, self.pos_y)
        self.preview.set_watermark_color(self.color)
        self.preview.set_watermark_size(self.size)
        
        # 设置预览文字
        preview_text = self.prefix + "2025.0101.0000" if self.prefix else "2025.0101.0000"
        self.preview.set_watermark_text(preview_text)
        
        # 创建设置布局
        settings_layout = QHBoxLayout()
        
        # 左侧：预览显示
        preview_layout = QVBoxLayout()
        preview_label = QLabel("拖拽调整位置:")
        preview_layout.addWidget(preview_label)
        preview_layout.addWidget(self.preview, 1)
        
        # 右侧：设置控件
        control_layout = QVBoxLayout()
        
        # 位置设置
        pos_group = QGroupBox("位置设置")
        pos_layout = QVBoxLayout(pos_group)
        
        # 预设位置
        preset_layout = QHBoxLayout()
        preset_label = QLabel("预设位置:")
        self.combo_position = QComboBox()
        self.combo_position.addItems(["右上角", "左上角", "右下角", "左下角", "中心"])
        self.combo_position.setCurrentText(self.position)
        preset_layout.addWidget(preset_label)
        preset_layout.addWidget(self.combo_position)
        pos_layout.addLayout(preset_layout)
        
        # X坐标微调
        x_layout = QHBoxLayout()
        x_label = QLabel("X坐标:")
        self.spin_x = QSpinBox()
        self.spin_x.setRange(-100, 100)
        self.spin_x.setValue(self.pos_x)
        self.spin_x.setSuffix(" px")
        x_layout.addWidget(x_label)
        x_layout.addWidget(self.spin_x)
        pos_layout.addLayout(x_layout)
        
        # Y坐标微调
        y_layout = QHBoxLayout()
        y_label = QLabel("Y坐标:")
        self.spin_y = QSpinBox()
        self.spin_y.setRange(-100, 100)
        self.spin_y.setValue(self.pos_y)
        self.spin_y.setSuffix(" px")
        y_layout.addWidget(y_label)
        y_layout.addWidget(self.spin_y)
        pos_layout.addLayout(y_layout)
        
        # 重置按钮
        self.btn_reset = QPushButton("重置位置")
        pos_layout.addWidget(self.btn_reset)
        
        # 添加分组到控制布局
        control_layout.addWidget(pos_group)
        control_layout.addStretch(1)
        
        # 组合左右两边
        settings_layout.addLayout(preview_layout, 3)
        settings_layout.addLayout(control_layout, 2)
        
        # 添加设置布局到主布局
        layout.addLayout(settings_layout)
        
        # 按钮区域
        buttons_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("取消")
        self.btn_ok = QPushButton("确定")
        self.btn_ok.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self.btn_cancel)
        buttons_layout.addWidget(self.btn_ok)
        
        layout.addLayout(buttons_layout)
        
        # 连接信号和槽
        self.preview.positionChanged.connect(self.on_preview_position_changed)
        self.combo_position.currentTextChanged.connect(self.on_position_changed)
        self.spin_x.valueChanged.connect(self.on_x_changed)
        self.spin_y.valueChanged.connect(self.on_y_changed)
        self.btn_reset.clicked.connect(self.on_reset)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self.accept)
    
    def on_preview_position_changed(self, x, y):
        """预览控件拖动时更新设置值"""
        self.spin_x.blockSignals(True)
        self.spin_y.blockSignals(True)
        self.spin_x.setValue(x)
        self.spin_y.setValue(y)
        self.spin_x.blockSignals(False)
        self.spin_y.blockSignals(False)
        self.pos_x = x
        self.pos_y = y
    
    def on_position_changed(self, position):
        """位置预设改变"""
        self.position = position
        self.preview.set_watermark_position(position)
    
    def on_x_changed(self, value):
        """X坐标改变"""
        self.pos_x = value
        self.preview.set_watermark_offset(value, self.pos_y)
    
    def on_y_changed(self, value):
        """Y坐标改变"""
        self.pos_y = value
        self.preview.set_watermark_offset(self.pos_x, value)
    
    def on_reset(self):
        """重置位置"""
        self.spin_x.setValue(0)
        self.spin_y.setValue(0)
        self.preview.set_watermark_offset(0, 0)
    
    def get_position_values(self):
        """获取当前设置的位置值
        
        Returns:
            tuple: (预设位置, x坐标, y坐标)
        """
        return (self.position, self.pos_x, self.pos_y)