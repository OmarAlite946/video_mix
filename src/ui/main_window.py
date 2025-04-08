#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
主窗口实现
"""

import os
import sys
import subprocess
from pathlib import Path
from PyQt5.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QComboBox, QSpinBox, QLineEdit, 
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView, 
    QMessageBox, QGroupBox, QFormLayout, QDoubleSpinBox, QCheckBox,
    QProgressBar
)
from PyQt5 import QtCore
from PyQt5.QtCore import Qt, QSize, pyqtSlot
from PyQt5.QtGui import QIcon, QFont
from utils.file_utils import list_media_files

class MainWindow(QMainWindow):
    """应用程序主窗口"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("短视频批量混剪工具")
        self.resize(1200, 800)
        
        # 初始化状态变量
        self.processor = None
        self.processing_thread = None
        
        # 初始化界面
        self._init_ui()
        
        # 创建菜单栏
        self._init_menubar()
        
        # 连接信号槽
        self._connect_signals()
    
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
        compose_layout = QVBoxLayout(self.tab_compose)
        
        # 视频列表区域
        list_group = QGroupBox("素材列表")
        compose_layout.addWidget(list_group)
        
        list_layout = QVBoxLayout(list_group)
        
        # 创建视频列表表格
        self.video_table = QTableWidget()
        self.video_table.setColumnCount(6)
        self.video_table.setHorizontalHeaderLabels(["序号", "场景名称", "路径", "视频数量", "配音数量", "状态"])
        self.video_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.video_table.verticalHeader().setVisible(False)
        list_layout.addWidget(self.video_table)
        
        # 素材操作按钮
        btn_layout = QHBoxLayout()
        list_layout.addLayout(btn_layout)
        
        self.btn_add_material = QPushButton("添加素材")
        self.btn_batch_import = QPushButton("批量导入")
        self.btn_refresh_material = QPushButton("刷新素材")
        self.btn_clear_material = QPushButton("清空素材")
        
        btn_layout.addWidget(self.btn_add_material)
        btn_layout.addWidget(self.btn_batch_import)
        btn_layout.addWidget(self.btn_refresh_material)
        btn_layout.addWidget(self.btn_clear_material)
        
        # 合成设置区域
        settings_group = QGroupBox("合成设置")
        compose_layout.addWidget(settings_group)
        
        settings_layout = QFormLayout(settings_group)
        
        # 合成模式选择
        mode_layout = QHBoxLayout()
        self.combo_text_mode = QComboBox()
        self.combo_text_mode.addItems(["文字模式"])
        self.combo_audio_mode = QComboBox()
        self.combo_audio_mode.addItems(["配音模式"])
        
        mode_layout.addWidget(QLabel("合成模式:"))
        mode_layout.addWidget(self.combo_text_mode)
        mode_layout.addWidget(self.combo_audio_mode)
        mode_layout.addStretch()
        
        video_mode_layout = QHBoxLayout()
        self.combo_video_mode = QComboBox()
        self.combo_video_mode.addItems(["标准模式（重编码）", "快速模式（不重编码）"])
        
        video_mode_layout.addWidget(QLabel("视频模式:"))
        video_mode_layout.addWidget(self.combo_video_mode)
        video_mode_layout.addStretch()
        
        settings_layout.addRow(mode_layout)
        settings_layout.addRow(video_mode_layout)
        
        # 分辨率和比特率
        resolution_layout = QHBoxLayout()
        self.combo_resolution = QComboBox()
        self.combo_resolution.addItems(["竖屏 1080x1920", "横屏 1920x1080", "竖屏 720x1280", "横屏 1280x720"])
        
        resolution_layout.addWidget(QLabel("分辨率:"))
        resolution_layout.addWidget(self.combo_resolution)
        resolution_layout.addStretch()
        
        bitrate_layout = QHBoxLayout()
        self.spin_bitrate = QSpinBox()
        self.spin_bitrate.setRange(1000, 20000)
        self.spin_bitrate.setValue(5000)
        self.spin_bitrate.setSuffix(" k")
        
        bitrate_layout.addWidget(QLabel("比特率:"))
        bitrate_layout.addWidget(self.spin_bitrate)
        bitrate_layout.addStretch()
        
        settings_layout.addRow(resolution_layout)
        settings_layout.addRow(bitrate_layout)
        
        # GPU加速
        gpu_layout = QHBoxLayout()
        self.combo_gpu = QComboBox()
        self.combo_gpu.addItems(["Nvidia显卡", "AMD显卡", "Intel显卡", "CPU处理"])
        
        gpu_layout.addWidget(QLabel("显卡加速:"))
        gpu_layout.addWidget(self.combo_gpu)
        gpu_layout.addStretch()
        
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
        
        settings_layout.addRow(save_dir_layout)
        
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
        
        settings_layout.addRow(volume_layout)
        
        # 背景音乐设置
        bgm_layout = QHBoxLayout()
        self.edit_bgm_path = QLineEdit()
        self.btn_browse_bgm = QPushButton("选择")
        self.btn_play_bgm = QPushButton("播放")
        
        bgm_layout.addWidget(QLabel("背景音乐:"))
        bgm_layout.addWidget(self.edit_bgm_path)
        bgm_layout.addWidget(self.btn_browse_bgm)
        bgm_layout.addWidget(self.btn_play_bgm)
        
        settings_layout.addRow(bgm_layout)
        
        # 转场效果设置
        transition_layout = QHBoxLayout()
        self.combo_transition = QComboBox()
        self.combo_transition.addItems([
            "随机转场", "镜像翻转", "色相偏移", "光束扫描", 
            "像素化过渡", "轻微旋转缩放", "倒放闪回", "速度波动过渡", "分屏滑动"
        ])
        
        transition_layout.addWidget(QLabel("转场效果:"))
        transition_layout.addWidget(self.combo_transition)
        transition_layout.addStretch()
        
        settings_layout.addRow(transition_layout)
        
        # 生成数量设置
        count_layout = QHBoxLayout()
        self.spin_generate_count = QSpinBox()
        self.spin_generate_count.setRange(1, 500)
        self.spin_generate_count.setValue(20)
        self.spin_generate_count.setSuffix(" 个")
        
        count_layout.addWidget(QLabel("生成数量:"))
        count_layout.addWidget(self.spin_generate_count)
        count_layout.addStretch()
        
        settings_layout.addRow(count_layout)
        
        # 操作按钮
        btn_control_layout = QHBoxLayout()
        compose_layout.addLayout(btn_control_layout)
        
        self.btn_start_compose = QPushButton("开始合成")
        self.btn_stop_compose = QPushButton("停止合成")
        
        btn_control_layout.addStretch()
        btn_control_layout.addWidget(self.btn_start_compose)
        btn_control_layout.addWidget(self.btn_stop_compose)
        btn_control_layout.addStretch()
        
        # 进度显示区域
        progress_group = QGroupBox("合成进度")
        compose_layout.addWidget(progress_group)
        
        progress_layout = QVBoxLayout(progress_group)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        # 状态文本
        self.label_progress = QLabel("等待合成任务...")
        progress_layout.addWidget(self.label_progress)
        
        # 设置默认禁用停止按钮
        self.btn_stop_compose.setEnabled(False)

        # 添加其他选项卡
        self.tabs.addTab(QWidget(), "字幕院线")
        self.tabs.addTab(QWidget(), "导出院线")
        self.tabs.addTab(QWidget(), "识别配音")
        self.tabs.addTab(QWidget(), "视频分割")
    
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
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        
        ffmpeg_guide_action = help_menu.addAction("安装FFmpeg指南")
        ffmpeg_guide_action.triggered.connect(self.show_ffmpeg_guide)
        
        ffmpeg_config_action = help_menu.addAction("配置FFmpeg路径")
        ffmpeg_config_action.triggered.connect(self.config_ffmpeg_path)
        
        about_action = help_menu.addAction("关于")
        about_action.triggered.connect(self.show_about)
    
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
        """连接信号槽"""
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
        
        # 合成控制
        self.btn_start_compose.clicked.connect(self.on_start_compose)
        self.btn_stop_compose.clicked.connect(self.on_stop_compose)
    
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
            self.video_table.setItem(row_count, 5, QTableWidgetItem("就绪"))
            
            QMessageBox.information(self, "添加素材", f"已添加素材文件夹: {folder_name}")
    
    @pyqtSlot()
    def on_refresh_material(self):
        """刷新素材"""
        # 刷新表格中的素材信息
        # 实际应用中，这里应该重新扫描素材文件夹，更新视频和配音数量
        QMessageBox.information(self, "刷新素材", "素材列表已刷新")
    
    @pyqtSlot()
    def on_clear_material(self):
        """清空素材"""
        # 清空表格
        self.video_table.setRowCount(0)
        QMessageBox.information(self, "清空素材", "已清空素材列表")
    
    @pyqtSlot()
    def on_browse_save_dir(self):
        """浏览保存目录"""
        folder = QFileDialog.getExistingDirectory(
            self, "选择保存目录", "", QFileDialog.ShowDirsOnly
        )
        
        if folder:
            self.edit_save_dir.setText(folder)
    
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
        """选择背景音乐文件"""
        file, _ = QFileDialog.getOpenFileName(
            self, "选择背景音乐", "", "音频文件 (*.mp3 *.wav *.flac *.ogg *.m4a)"
        )
        
        if file:
            self.edit_bgm_path.setText(file)
    
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
        
        # 获取合成参数
        params = self._get_compose_params()
        
        # 收集素材文件夹信息
        material_folders = []
        for row in range(self.video_table.rowCount()):
            folder_info = {
                "name": self.video_table.item(row, 1).text(),
                "path": self.video_table.item(row, 2).text()
            }
            material_folders.append(folder_info)
            
            # 更新状态为处理中
            self.video_table.setItem(row, 5, QTableWidgetItem("处理中"))
        
        # 在单独线程中执行视频合成，避免阻塞UI
        import threading
        
        def process_videos():
            try:
                from core.video_processor import VideoProcessor
                
                # 创建处理器
                settings = {
                    "hardware_accel": "auto" if "Nvidia" in params["gpu"] else "none",
                    "encoder": "h264_nvenc" if "Nvidia" in params["gpu"] else "libx264",
                    "resolution": params["resolution"].split()[1],  # 提取分辨率数字部分
                    "bitrate": params["bitrate"],
                    "voice_volume": params["voice_volume"],
                    "bgm_volume": params["bgm_volume"],
                    "transition": params["transition"].lower(),
                    "transition_duration": 0.5,  # 默认转场时长
                    "threads": 4  # 默认线程数
                }
                
                # 保存处理器实例以便停止处理
                self.processor = VideoProcessor(settings, progress_callback=self._update_progress)
                
                # 执行批量处理
                bgm_path = params["bgm_path"] if os.path.exists(params["bgm_path"]) else None
                count = params["generate_count"]
                
                # 实际生成视频
                output_videos = self.processor.process_batch(
                    material_folders=material_folders,
                    output_dir=save_dir,
                    count=count,
                    bgm_path=bgm_path
                )
                
                # 处理完成
                QtCore.QMetaObject.invokeMethod(
                    self, 
                    "on_compose_completed", 
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(bool, len(output_videos) > 0),
                    QtCore.Q_ARG(int, len(output_videos)),
                    QtCore.Q_ARG(str, save_dir)
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
        
        # 启动处理线程
        self.processing_thread = threading.Thread(target=process_videos, daemon=True)
        self.processing_thread.start()
    
    def _get_compose_params(self):
        """获取当前合成参数"""
        params = {
            "text_mode": self.combo_text_mode.currentText(),
            "audio_mode": self.combo_audio_mode.currentText(),
            "video_mode": self.combo_video_mode.currentText(),
            "resolution": self.combo_resolution.currentText(),
            "bitrate": self.spin_bitrate.value(),
            "gpu": self.combo_gpu.currentText(),
            "save_dir": self.edit_save_dir.text(),
            "voice_volume": self.spin_voice_volume.value(),
            "bgm_volume": self.spin_bgm_volume.value(),
            "bgm_path": self.edit_bgm_path.text(),
            "transition": self.combo_transition.currentText(),
            "generate_count": self.spin_generate_count.value()
        }
        return params
    
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
            if item and item.text() == "处理中":
                self.video_table.setItem(row, 5, QTableWidgetItem("已中止"))
        # 显示消息
        QMessageBox.information(self, "合成已中止", "视频合成任务已被中止")
    
    @QtCore.pyqtSlot(bool, int, str)
    def on_compose_completed(self, success=True, count=0, output_dir=""):
        """合成完成时调用"""
        # 更新界面状态
        self.btn_start_compose.setEnabled(True)
        self.btn_stop_compose.setEnabled(False)
        
        if success and count > 0:
            self.label_progress.setText(f"合成进度: 已完成 {count} 个视频")
        
            # 设置表格中素材的状态为"已完成"
            for row in range(self.video_table.rowCount()):
                self.video_table.setItem(row, 5, QTableWidgetItem("已完成"))
            # 显示完成消息
            QMessageBox.information(
                self, 
                "合成完成", 
                f"视频合成任务已完成！成功生成 {count} 个视频，保存在：\n{output_dir}"
            )
        else:
            self.label_progress.setText("合成进度: 未生成视频")
            
            # 设置表格中素材的状态为"失败"
            for row in range(self.video_table.rowCount()):
                self.video_table.setItem(row, 5, QTableWidgetItem("失败"))
            
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
            if item and item.text() == "处理中":
                self.video_table.setItem(row, 5, QTableWidgetItem("错误"))
        
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
    
    @pyqtSlot()
    def on_batch_import(self):
        """批量导入素材文件夹"""
        # 选择根目录
        root_dir = QFileDialog.getExistingDirectory(self, "选择素材根目录")
        if not root_dir:
            return
        
        # 递归扫描所有包含视频和音频的子文件夹
        import os
        from pathlib import Path
        
        added_count = 0
        skipped_count = 0
        
        # 遍历根目录下的所有子文件夹
        for item in os.listdir(root_dir):
            item_path = os.path.join(root_dir, item)
            
            # 只处理文件夹
            if not os.path.isdir(item_path):
                continue
            
            # 检查是否有"视频"或"配音"子文件夹
            has_video_folder = os.path.exists(os.path.join(item_path, "视频"))
            has_audio_folder = os.path.exists(os.path.join(item_path, "配音"))
            
            if has_video_folder or has_audio_folder:
                # 检查子文件夹中是否有媒体文件
                video_count = 0
                audio_count = 0
                
                if has_video_folder:
                    media = list_media_files(os.path.join(item_path, "视频"), recursive=True)
                    video_count = len(media['videos'])
                
                if has_audio_folder:
                    media = list_media_files(os.path.join(item_path, "配音"), recursive=True)
                    audio_count = len(media['audios'])
                
                # 如果有媒体文件，则添加到素材列表
                if video_count > 0 or audio_count > 0:
                    row_count = self.video_table.rowCount()
                    self.video_table.setRowCount(row_count + 1)
                    
                    self.video_table.setItem(row_count, 0, QTableWidgetItem(str(row_count + 1)))  # 序号
                    self.video_table.setItem(row_count, 1, QTableWidgetItem(item))  # 素材名称
                    self.video_table.setItem(row_count, 2, QTableWidgetItem(item_path))  # 素材路径
                    self.video_table.setItem(row_count, 3, QTableWidgetItem(str(video_count)))  # 视频数量
                    self.video_table.setItem(row_count, 4, QTableWidgetItem(str(audio_count)))  # 配音数量
                    self.video_table.setItem(row_count, 5, QTableWidgetItem("待处理"))  # 状态
                    
                    added_count += 1
                else:
                    skipped_count += 1
        
        if added_count > 0:
            QMessageBox.information(
                self, 
                "批量导入完成", 
                f"成功导入 {added_count} 个素材文件夹\n跳过 {skipped_count} 个不包含媒体文件的文件夹"
            )
        else:
            QMessageBox.warning(
                self, 
                "批量导入", 
                f"未找到符合条件的素材文件夹。请确保子文件夹中包含'视频'或'配音'文件夹，且其中有媒体文件"
            )
    
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