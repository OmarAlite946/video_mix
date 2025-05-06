#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
多模板批量处理窗口
"""

import os
import sys
import time
import json
import logging
import threading
import gc
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QProgressBar, QApplication,
    QTabWidget, QCheckBox, QMessageBox, QStatusBar,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMenu, QAction, QToolButton, QFrame, QSplitter
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, pyqtSlot, QSize, QMetaObject, Q_ARG,
    QTimer
)
from PyQt5.QtGui import QIcon, QFont, QColor

from src.ui.main_window import MainWindow
from src.utils.logger import get_logger
from src.utils.template_state import TemplateState

logger = get_logger()

class BatchWindow(QMainWindow):
    """批量处理多个模板的主窗口"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("视频模板批量处理工具")
        self.resize(1200, 800)
        
        # 初始化状态变量
        self.tabs = []  # 存储打开的标签页
        self.current_processing_tab = None  # 当前正在处理的标签页
        self.is_processing = False  # 是否正在处理
        self.processing_thread = None  # 处理线程
        self.processing_queue = []  # 处理队列
        
        # 统计信息
        self.batch_start_time = None  # 批处理开始时间
        self.total_processed_count = 0  # 总处理视频数
        self.total_process_time = 0  # 总处理时间(秒)
        
        # 初始化模板状态管理
        self.template_state = TemplateState()
        
        # 初始化界面
        self._init_ui()
        
        # 初始化状态栏
        self._init_statusbar()
        
        # 设置全局对话框过滤器
        self._setup_dialog_filter()
        
        # 加载之前保存的模板
        self._load_saved_templates()
        
        # 如果没有加载到已保存的模板，添加一个初始标签页
        if len(self.tabs) == 0:
            self._add_new_tab()
    
    def _load_saved_templates(self):
        """加载保存的模板标签页状态"""
        saved_tabs = self.template_state.load_template_tabs()
        if not saved_tabs:
            return
        
        logger.info(f"开始加载 {len(saved_tabs)} 个保存的模板标签页")
        
        # 确保按照之前保存的索引加载标签页
        for tab_info in saved_tabs:
            try:
                tab_name = tab_info.get("name", "")
                tab_index = tab_info.get("tab_index", -1)
                logger.info(f"加载模板: {tab_name}, 索引: {tab_index}")
                self._add_template_from_info(tab_info)
            except Exception as e:
                logger.error(f"加载模板 {tab_info.get('name', '未知')} 时出错: {str(e)}")
        
        # 更新任务表格
        self._update_tasks_table()
        
        # 为所有标签页重新设置正确的索引
        for i, tab in enumerate(self.tabs):
            tab["tab_index"] = i
        
        # 最后再保存一次以确保索引正确
        self._save_template_state()
        
        logger.info(f"已完成 {len(self.tabs)} 个模板标签页的加载")
        
    def _add_template_from_info(self, tab_info):
        """从保存的信息中添加模板标签页"""
        name = tab_info.get("name", "")
        file_path = tab_info.get("file_path", "")
        folder_path = tab_info.get("folder_path", "")
        tab_index = tab_info.get("tab_index", -1)  # 获取标签页索引
        instance_id = tab_info.get("instance_id", f"tab_restored_{time.time()}_{tab_index}")  # 获取实例ID或生成新ID
        
        if not name:
            return False
        
        logger.info(f"正在添加模板: {name}, 文件路径: {file_path}, 文件夹: {folder_path}, 实例ID: {instance_id}")
        
        # 创建新的MainWindow实例，使用保存的实例ID或新生成的ID
        main_window = MainWindow(instance_id=instance_id)
        
        # 保存原始的on_compose_completed方法
        original_completed_func = main_window.on_compose_completed
        
        # 覆盖原方法，批量模式下不显示提示对话框
        def batch_on_completed(success=True, count=0, output_dir="", total_time=""):
            # 调用原方法但不显示MessageBox
            try:
                # 临时替换QMessageBox.information方法
                original_info = QMessageBox.information
                QMessageBox.information = lambda *args, **kwargs: None
                
                # 调用原方法
                original_completed_func(success, count, output_dir, total_time)
                
                # 恢复原方法
                QMessageBox.information = original_info
                
                # 设置完成标志
                main_window.compose_completed = True
                logger.info(f"模板 {name} 处理已完成，设置完成标志")
                
                # 更新进度时间戳
                main_window.last_progress_update = time.time()
                
                # 记录当前处理器和线程状态
                has_processor = hasattr(main_window, "processor") and main_window.processor is not None
                has_thread = hasattr(main_window, "processing_thread") and main_window.processing_thread is not None
                logger.debug(f"完成回调时状态：处理器={has_processor}，线程={has_thread}")
                
                # 如果处理成功，尝试记录输出文件信息
                if success and count > 0:
                    logger.info(f"成功合成 {count} 个视频，保存到: {output_dir}，用时: {total_time}")
            except Exception as e:
                logger.error(f"批处理模式下处理完成回调出错: {str(e)}")
                error_detail = traceback.format_exc()
                logger.error(f"详细错误信息: {error_detail}")
                # 确保即使出错，也设置完成标志
                main_window.compose_completed = True
                main_window.last_progress_update = time.time()
        
        # 覆盖方法
        main_window.on_compose_completed = batch_on_completed
        
        # 确保这个标签页拥有自己独立的用户设置
        if hasattr(main_window, "user_settings") and main_window.user_settings:
            # 使用保存的实例ID
            main_window.user_settings.instance_id = instance_id
            logger.debug(f"为模板 {name} 设置独立的用户设置实例ID: {instance_id}")
        
        # 添加标签页到界面
        tab_index = self.tab_widget.addTab(main_window, name)
        
        # 记录标签页信息
        tab_info = {
            "name": name,
            "window": main_window,
            "status": "准备就绪",
            "last_process_time": None,
            "file_path": file_path,
            "folder_path": folder_path,
            "tab_index": tab_index,  # 保存标签页索引
            "instance_id": instance_id  # 保存实例ID
        }
        
        # 将标签页添加到标签列表
        self.tabs.append(tab_info)
        
        # 注意：文件夹路径需要在加载配置文件之后设置，以避免被覆盖
        # 如果有配置文件路径，尝试加载
        if file_path and os.path.exists(file_path):
            try:
                main_window.load_config(file_path)
                logger.info(f"已加载模板配置文件: {file_path}")
            except Exception as e:
                logger.error(f"加载模板配置文件失败: {str(e)}")
        
        # 如果有文件夹路径，尝试设置 - 这一步要确保在最后进行，避免被其他设置覆盖
        if folder_path and os.path.exists(folder_path):
            try:
                # 设置输入文件夹路径
                main_window.input_folder_path.setText(folder_path)
                
                # 设置用户设置中的import_folder，确保独立性
                if hasattr(main_window, "user_settings"):
                    main_window.user_settings.set_setting("import_folder", folder_path)
                
                # 触发选择文件夹动作，以加载文件列表
                main_window.on_select_folder()
                
                # 再次确认文件夹路径已正确设置
                current_path = main_window.input_folder_path.text().strip()
                if current_path != folder_path:
                    logger.warning(f"文件夹路径设置可能不正确，期望: {folder_path}, 实际: {current_path}")
                    # 再次尝试设置
                    main_window.input_folder_path.setText(folder_path)
                
                logger.info(f"已设置模板输入文件夹: {folder_path}")
            except Exception as e:
                logger.error(f"设置模板输入文件夹失败: {str(e)}")
                logger.error(traceback.format_exc())
        
        logger.info(f"已添加模板标签页: {name}, 索引: {tab_index}, 实例ID: {instance_id}")
        return True
        
    def _init_ui(self):
        """初始化UI界面"""
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter)
        
        # 创建标签页区域
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)  # 允许关闭标签
        self.tab_widget.tabCloseRequested.connect(self._on_tab_close)
        
        # 创建"添加"按钮作为最后一个标签
        self.tab_widget.setTabPosition(QTabWidget.North)
        add_tab_button = QToolButton(self)
        add_tab_button.setText("+")
        add_tab_button.setToolTip("添加新模板")
        add_tab_button.clicked.connect(self._add_new_tab)
        self.tab_widget.setCornerWidget(add_tab_button, Qt.TopRightCorner)
        
        # 批量处理控制面板
        batch_panel = QWidget()
        batch_layout = QVBoxLayout(batch_panel)
        batch_layout.setContentsMargins(10, 10, 10, 10)
        
        # 批量处理任务列表标题
        tasks_header = QLabel("批量处理任务")
        tasks_header.setStyleSheet("font-size: 16px; font-weight: bold;")
        batch_layout.addWidget(tasks_header)
        
        # 任务表格
        self.tasks_table = QTableWidget(0, 6)  # 初始为0行，6列
        self.tasks_table.setHorizontalHeaderLabels(["选择", "模板名称", "状态", "处理数量", "处理时间", "最后处理时间"])
        self.tasks_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        # 设置列宽
        header = self.tasks_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # 选择框固定宽度
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # 名称列自适应
        header.setSectionResizeMode(2, QHeaderView.Fixed)  # 状态列固定宽度
        header.setSectionResizeMode(3, QHeaderView.Fixed)  # 处理数量列固定宽度
        header.setSectionResizeMode(4, QHeaderView.Fixed)  # 处理时间列固定宽度
        header.setSectionResizeMode(5, QHeaderView.Fixed)  # 最后处理时间列固定宽度
        
        self.tasks_table.setColumnWidth(0, 60)  # 选择框列宽
        self.tasks_table.setColumnWidth(2, 80)  # 状态列宽
        self.tasks_table.setColumnWidth(3, 80)  # 处理数量列宽
        self.tasks_table.setColumnWidth(4, 100)  # 处理时间列宽
        self.tasks_table.setColumnWidth(5, 150)  # 时间列宽
        
        batch_layout.addWidget(self.tasks_table)
        
        # 批量处理控制按钮
        batch_buttons = QHBoxLayout()
        batch_buttons.setContentsMargins(0, 0, 0, 0)
        
        # 全选/取消全选
        self.btn_select_all = QPushButton("全选")
        self.btn_select_all.clicked.connect(self._on_select_all)
        
        # 开始批量处理
        self.btn_start_batch = QPushButton("开始批量处理")
        self.btn_start_batch.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 8px 16px;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.btn_start_batch.clicked.connect(self._on_start_batch)
        
        # 停止批量处理
        self.btn_stop_batch = QPushButton("停止批量处理")
        self.btn_stop_batch.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 8px 16px;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        self.btn_stop_batch.setEnabled(False)
        self.btn_stop_batch.clicked.connect(self._on_stop_batch)
        
        batch_buttons.addWidget(self.btn_select_all)
        batch_buttons.addStretch(1)
        batch_buttons.addWidget(self.btn_start_batch)
        batch_buttons.addWidget(self.btn_stop_batch)
        
        batch_layout.addLayout(batch_buttons)
        
        # 批处理进度
        progress_layout = QVBoxLayout()
        progress_layout.setContentsMargins(0, 10, 0, 0)
        
        progress_header = QHBoxLayout()
        self.label_current_task = QLabel("当前任务: 等待中")
        progress_header.addWidget(self.label_current_task)
        
        self.label_queue = QLabel("队列: 0/0")
        progress_header.addWidget(self.label_queue, 0, Qt.AlignRight)
        
        progress_layout.addLayout(progress_header)
        
        self.batch_progress = QProgressBar()
        self.batch_progress.setRange(0, 100)
        self.batch_progress.setValue(0)
        self.batch_progress.setTextVisible(True)
        progress_layout.addWidget(self.batch_progress)
        
        # 添加结果统计区域
        statistics_layout = QHBoxLayout()
        statistics_layout.setContentsMargins(0, 10, 0, 0)
        
        self.label_total_videos = QLabel("总视频数: 0")
        self.label_total_time = QLabel("总用时: 0秒")
        
        statistics_layout.addWidget(self.label_total_videos)
        statistics_layout.addStretch(1)
        statistics_layout.addWidget(self.label_total_time)
        
        progress_layout.addLayout(statistics_layout)
        
        batch_layout.addLayout(progress_layout)
        
        # 添加标签页区域和批量处理面板到分割器
        splitter.addWidget(self.tab_widget)
        splitter.addWidget(batch_panel)
        
        # 设置分割器初始大小比例
        splitter.setSizes([600, 200])
    
    def _init_statusbar(self):
        """初始化状态栏"""
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        
        self.status_label = QLabel("就绪")
        self.statusBar.addWidget(self.status_label, 1)
    
    def _add_new_tab(self):
        """添加新的标签页"""
        # 创建唯一的实例ID
        instance_id = f"tab_new_{time.time()}"
        logger.info(f"创建新标签页, 实例ID: {instance_id}")
        
        # 创建新的MainWindow实例，传入实例ID
        main_window = MainWindow(instance_id=instance_id)
        
        # 保存原始的on_compose_completed方法
        original_completed_func = main_window.on_compose_completed
        
        # 覆盖原方法，批量模式下不显示提示对话框
        def batch_on_completed(success=True, count=0, output_dir="", total_time=""):
            # 调用原方法但不显示MessageBox
            try:
                # 临时替换QMessageBox.information方法
                original_info = QMessageBox.information
                QMessageBox.information = lambda *args, **kwargs: None
                
                # 调用原方法
                original_completed_func(success, count, output_dir, total_time)
                
                # 恢复原方法
                QMessageBox.information = original_info
                
                # 设置完成标志
                main_window.compose_completed = True
                logger.info(f"模板 {tab_name} 处理已完成，设置完成标志")
                
                # 更新进度时间戳
                main_window.last_progress_update = time.time()
                
                # 记录当前处理器和线程状态
                has_processor = hasattr(main_window, "processor") and main_window.processor is not None
                has_thread = hasattr(main_window, "processing_thread") and main_window.processing_thread is not None
                logger.debug(f"完成回调时状态：处理器={has_processor}，线程={has_thread}")
                
                # 如果处理成功，尝试记录输出文件信息
                if success and count > 0:
                    logger.info(f"成功合成 {count} 个视频，保存到: {output_dir}，用时: {total_time}")
            except Exception as e:
                logger.error(f"批处理模式下处理完成回调出错: {str(e)}")
                error_detail = traceback.format_exc()
                logger.error(f"详细错误信息: {error_detail}")
                # 确保即使出错，也设置完成标志
                main_window.compose_completed = True
                main_window.last_progress_update = time.time()
        
        # 覆盖方法
        main_window.on_compose_completed = batch_on_completed
        
        # 覆盖进度更新回调，以确保进度时间戳正确更新
        original_update_progress = None
        if hasattr(main_window, "_do_update_progress"):
            original_update_progress = main_window._do_update_progress
            
            def batch_update_progress(message, percent):
                # 更新进度时间戳
                main_window.last_progress_update = time.time()
                # 调用原方法
                if original_update_progress:
                    original_update_progress(message, percent)
                    
            # 覆盖方法    
            main_window._do_update_progress = batch_update_progress
        
        # 同样处理错误回调，避免出错时弹框
        original_error_func = main_window.on_compose_error
        
        def batch_on_error(error_msg, detail=""):
            try:
                # 临时替换QMessageBox.critical方法
                original_critical = QMessageBox.critical
                QMessageBox.critical = lambda *args, **kwargs: None
                
                # 调用原方法
                original_error_func(error_msg, detail)
                
                # 恢复原方法
                QMessageBox.critical = original_critical
                
                # 设置错误标志，这也表示处理已完成，但有错误
                main_window.compose_completed = True
                main_window.compose_error = True
                main_window.last_progress_update = time.time()
                
                logger.error(f"模板 {tab_name} 处理出错: {error_msg}")
                if detail:
                    logger.error(f"详细错误信息: {detail}")
            except Exception as e:
                logger.error(f"批处理模式下错误回调出错: {str(e)}")
                # 确保即使出错，也设置完成标志
                main_window.compose_completed = True
                main_window.compose_error = True
                main_window.last_progress_update = time.time()
        
        # 覆盖方法
        main_window.on_compose_error = batch_on_error
        
        # 自动为新的标签页创建编号
        tab_name = f"模板 {len(self.tabs) + 1}"
        
        # 添加标签页
        tab_index = self.tab_widget.addTab(main_window, tab_name)
        self.tab_widget.setCurrentIndex(tab_index)
        
        # 记录标签页信息
        tab_info = {
            "name": tab_name,
            "window": main_window,
            "status": "准备就绪",
            "last_process_time": None,
            "file_path": "",
            "folder_path": "",
            "tab_index": tab_index,  # 保存标签页索引
            "instance_id": instance_id  # 保存实例ID
        }
        
        self.tabs.append(tab_info)
        
        # 更新任务表格
        self._update_tasks_table()
        
        # 如果是第一个标签页，默认选中
        if len(self.tabs) == 1:
            # 查找表格中的复选框
            checkbox_container = self.tasks_table.cellWidget(0, 0)
            if checkbox_container:
                checkbox = checkbox_container.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(True)
        
        logger.info(f"已添加新模板标签页: {tab_name}, 实例ID: {instance_id}")
        
        # 自动保存当前模板状态
        self._save_template_state()
        
        return tab_index
    
    def _on_tab_close(self, index):
        """处理标签页关闭事件"""
        # 确保至少保留一个标签页
        if self.tab_widget.count() <= 1:
            QMessageBox.warning(self, "警告", "至少需要保留一个模板标签页")
            return
        
        # 正在处理时不允许关闭标签页
        if self.is_processing:
            QMessageBox.warning(self, "警告", "批量处理过程中不能关闭标签页")
            return
        
        # 确认关闭
        tab_name = self.tab_widget.tabText(index)
        reply = QMessageBox.question(
            self, 
            "关闭模板", 
            f"确定要关闭模板 '{tab_name}' 吗？",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 从列表中移除
            closed_tab = self.tabs.pop(index)
            logger.info(f"关闭标签页: {closed_tab['name']}, 索引: {index}")
            
            # 关闭标签页
            self.tab_widget.removeTab(index)
            
            # 更新所有标签页的索引
            for i, tab in enumerate(self.tabs):
                old_index = tab.get("tab_index", -1)
                tab["tab_index"] = i
                logger.debug(f"更新标签页索引: {tab['name']} - 从 {old_index} 到 {i}")
            
            # 更新任务表格
            self._update_tasks_table()
            
            # 保存当前模板状态
            self._save_template_state()
    
    def _update_tasks_table(self):
        """更新任务表格"""
        self.tasks_table.setRowCount(len(self.tabs))
        
        for row, tab in enumerate(self.tabs):
            # 复选框
            checkbox = QCheckBox()
            checkbox.setChecked(True)  # 默认勾选
            checkbox_container = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_container)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            
            # 保存tab_index到复选框的属性中，以便在选择时正确对应
            checkbox.setProperty("tab_index", row)
            
            self.tasks_table.setCellWidget(row, 0, checkbox_container)
            
            # 模板名称
            self.tasks_table.setItem(row, 1, QTableWidgetItem(tab["name"]))
            
            # 状态
            status_item = QTableWidgetItem(tab["status"])
            if tab["status"] == "完成":
                status_item.setForeground(QColor("#4CAF50"))
            elif tab["status"] == "处理中":
                status_item.setForeground(QColor("#2196F3"))
            elif tab["status"] == "等待中":
                status_item.setForeground(QColor("#FF9800"))
            elif tab["status"] == "失败":
                status_item.setForeground(QColor("#F44336"))
            self.tasks_table.setItem(row, 2, status_item)
            
            # 处理数量
            process_count = tab.get("process_count", 0)
            self.tasks_table.setItem(row, 3, QTableWidgetItem(str(process_count)))
            
            # 处理时间
            process_time = tab.get("process_time", "-")
            if isinstance(process_time, (int, float)) and process_time > 0:
                time_str = self._format_time(process_time)
            else:
                time_str = "-"
            self.tasks_table.setItem(row, 4, QTableWidgetItem(time_str))
            
            # 最后处理时间
            last_time = tab.get("last_process_time", "-")
            if last_time is None:
                last_time = "-"
            self.tasks_table.setItem(row, 5, QTableWidgetItem(last_time))
        
        # 更新统计区域
        self.label_total_videos.setText(f"总视频数: {self.total_processed_count}")
        
        if self.total_process_time > 0:
            self.label_total_time.setText(f"总用时: {self._format_time(self.total_process_time)}")
        else:
            self.label_total_time.setText("总用时: -")
        
        # 如果有统计信息，在状态栏显示
        if self.total_processed_count > 0:
            self.statusBar.showMessage(f"总计: 处理了 {self.total_processed_count} 个视频，总耗时 {self._format_time(self.total_process_time)}")
    
    def _format_time(self, seconds):
        """将秒数格式化为时分秒"""
        if seconds < 60:
            return f"{seconds:.1f}秒"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            seconds = seconds % 60
            return f"{minutes}分{seconds:.1f}秒"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            seconds = seconds % 60
            return f"{hours}时{minutes}分{seconds:.1f}秒"
    
    def _on_select_all(self):
        """全选/取消全选处理"""
        # 检查当前状态
        current_state = True  # 默认假设全部已选
        
        for row in range(self.tasks_table.rowCount()):
            checkbox_container = self.tasks_table.cellWidget(row, 0)
            if checkbox_container:
                checkbox = checkbox_container.findChild(QCheckBox)
                if checkbox and not checkbox.isChecked():
                    current_state = False
                    break
        
        # 切换状态
        new_state = not current_state
        for row in range(self.tasks_table.rowCount()):
            checkbox_container = self.tasks_table.cellWidget(row, 0)
            if checkbox_container:
                checkbox = checkbox_container.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(new_state)
        
        # 更新按钮文本
        self.btn_select_all.setText("取消全选" if new_state else "全选")
    
    def _on_start_batch(self):
        """开始批量处理"""
        # 检查是否有选中的任务
        selected_tasks = []
        selected_indexes = []  # 存储实际tab索引
        
        for row in range(self.tasks_table.rowCount()):
            checkbox_container = self.tasks_table.cellWidget(row, 0)
            if checkbox_container:
                checkbox = checkbox_container.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    # 使用存储在复选框属性中的tab_index
                    tab_index = checkbox.property("tab_index")
                    if isinstance(tab_index, (int)):
                        selected_indexes.append(int(tab_index))
                    else:
                        # 兼容旧版本，直接使用行索引
                        selected_indexes.append(row)
        
        if not selected_indexes:
            QMessageBox.warning(self, "批量处理", "请至少选择一个模板进行处理")
            return
            
        # 确保selected_indexes中的索引有效，过滤掉超出范围的索引
        valid_indexes = [idx for idx in selected_indexes if 0 <= idx < len(self.tabs)]
        if len(valid_indexes) < len(selected_indexes):
            logger.warning(f"过滤掉了{len(selected_indexes) - len(valid_indexes)}个无效的索引")
            selected_indexes = valid_indexes
            
        if not selected_indexes:
            QMessageBox.warning(self, "批量处理", "没有有效的模板可以处理")
            return
        
        # 确认开始处理
        reply = QMessageBox.question(
            self, 
            "批量处理", 
            f"即将开始处理 {len(selected_indexes)} 个模板，是否继续？",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            # 先停止可能正在运行的任何处理
            self._reset_batch_ui()
            
            # 在开始前先进行垃圾回收，释放资源
            gc.collect()
            
            # 重置统计信息
            self.batch_start_time = time.time()
            self.total_processed_count = 0
            self.total_process_time = 0
            
            # 清空处理队列并重新添加选中的任务
            self.processing_queue = selected_indexes.copy()
            
            # 记录处理队列日志
            queue_info = []
            for idx in selected_indexes:
                if 0 <= idx < len(self.tabs):
                    queue_info.append(f"{idx}:{self.tabs[idx]['name']}")
            logger.info(f"处理队列: {', '.join(queue_info)}")
            
            # 更新界面状态
            # 首先重置所有标签页的状态
            for tab in self.tabs:
                if tab["status"] in ["处理中", "等待中"]:
                    tab["status"] = "准备就绪"
            
            # 然后设置选中标签页的状态
            for idx in selected_indexes:
                if 0 <= idx < len(self.tabs):
                    self.tabs[idx]["status"] = "等待中"
                    # 重置各个任务的处理统计
                    self.tabs[idx]["process_count"] = 0
                    self.tabs[idx]["process_time"] = 0
                    self.tabs[idx]["start_time"] = None
            
            self._update_tasks_table()
            
            # 更新界面状态
            self.is_processing = True
            self.btn_start_batch.setEnabled(False)
            self.btn_stop_batch.setEnabled(True)
            
            # 更新队列状态
            self.label_queue.setText(f"队列: 0/{len(selected_indexes)}")
            
            # 批处理模式下启用对话框过滤
            logger.info("启用批处理模式对话框过滤")
            
            # 确保UI完全更新
            QApplication.processEvents()
            
            # 使用定时器延迟开始处理，给UI一些响应时间
            QTimer.singleShot(500, self._process_next_task)
            
            # 记录详细日志，以便排查问题
            logger.info(f"将处理以下标签页索引: {selected_indexes}")
    
    def _on_stop_batch(self):
        """停止批量处理"""
        if not self.is_processing:
            return
        
        # 确认停止
        reply = QMessageBox.question(
            self, 
            "停止处理", 
            "确定要停止当前的批量处理任务吗？",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            logger.info("用户请求停止批量处理")
            
            # 停止当前处理
            if self.current_processing_tab is not None:
                tab_idx = self.current_processing_tab
                if 0 <= tab_idx < len(self.tabs):
                    # 获取MainWindow实例并调用停止方法
                    main_window = self.tabs[tab_idx]["window"]
                    if main_window:
                        try:
                            logger.info(f"正在停止当前处理任务: {self.tabs[tab_idx]['name']}")
                            main_window.on_stop_compose()
                            
                            # 强制清理资源
                            if hasattr(main_window, "processor") and main_window.processor:
                                if hasattr(main_window.processor, "clean_temp_files"):
                                    main_window.processor.clean_temp_files()
                                main_window.processor = None
                        except Exception as e:
                            logger.error(f"停止处理时出错: {str(e)}")
            
            # 清空队列
            previous_queue = self.processing_queue.copy() if self.processing_queue else []
            self.processing_queue = []
            
            # 更新界面状态
            self.label_current_task.setText("当前任务: 已停止")
            self.label_queue.setText("队列: 0/0")
            
            # 恢复界面状态
            self._reset_batch_ui()
            
            # 重置所有处理中或等待中的任务状态
            for i, tab in enumerate(self.tabs):
                if tab["status"] in ["处理中", "等待中"]:
                    tab["status"] = "已停止"
                    
            # 记录日志
            if previous_queue:
                logger.info(f"停止了以下任务索引的处理: {previous_queue}")
                
            # 更新任务表格
            self._update_tasks_table()
            
            # 执行垃圾回收
            gc.collect()
    
    def _reset_batch_ui(self):
        """重置批处理界面状态"""
        logger.info("重置批处理界面状态")
        
        # 备份并清空处理队列
        original_queue = list(self.processing_queue) if self.processing_queue else []
        self.processing_queue = []
        
        # 重置状态变量
        self.is_processing = False
        current_tab = self.current_processing_tab  # 保存以便记录
        self.current_processing_tab = None
        
        # 更新UI元素
        self.btn_start_batch.setEnabled(True)
        self.btn_stop_batch.setEnabled(False)
        self.batch_progress.setValue(0)
        self.statusBar.showMessage("批量处理已停止", 3000)
        
        # 如果不是处理完成后调用的重置，那么也重置统计信息
        if original_queue and len(self.tabs) > 0 and not any(tab["status"] == "完成" for tab in self.tabs):
            self.total_processed_count = 0
            self.total_process_time = 0
            self.batch_start_time = None
            self.label_total_videos.setText("总视频数: 0")
            self.label_total_time.setText("总用时: -")
            logger.info(f"重置统计信息，有 {len(original_queue)} 个任务未处理")
        
        # 尝试释放所有标签页的资源
        for tab in self.tabs:
            if "window" in tab and tab["window"]:
                try:
                    window = tab["window"]
                    # 尝试清理处理器资源
                    if hasattr(window, "processor") and window.processor:
                        if hasattr(window.processor, "stop_processing"):
                            try:
                                window.processor.stop_processing()
                            except:
                                pass
                        window.processor = None
                    
                    # 重置处理线程
                    if hasattr(window, "processing_thread") and window.processing_thread:
                        window.processing_thread = None
                except Exception as e:
                    logger.error(f"重置标签页资源时出错: {str(e)}")
        
        # 强制处理所有挂起的事件
        QApplication.processEvents()
        
        # 执行垃圾回收
        gc.collect()
        
        # 记录详细日志
        if current_tab is not None:
            logger.info(f"重置批处理模式，之前处理的标签页索引: {current_tab}")
        if original_queue:
            logger.info(f"处理队列已清空，原队列包含: {original_queue}")
        
        logger.info("批处理模式已重置")
    
    def _process_next_task(self):
        """处理队列中的下一个任务"""
        # 首先检查是否还在批处理过程中
        if not self.is_processing:
            logger.info("批处理已停止，不再继续处理队列")
            self.statusBar.showMessage("批处理已停止", 3000)
            return
        
        # 检查队列是否为空
        if not self.processing_queue:
            logger.info("批处理队列已处理完毕")
            
            # 计算总的处理时间
            if self.batch_start_time:
                total_batch_time = time.time() - self.batch_start_time
                self.total_process_time = total_batch_time
                
                # 显示完成信息
                completion_message = f"批量处理完成！总计处理了 {self.total_processed_count} 个视频，总耗时 {self._format_time(total_batch_time)}"
                self.statusBar.showMessage(completion_message, 0) # 0表示不会自动消失
                
                # 弹出提示通知
                QMessageBox.information(self, "批量处理完成", completion_message)
            else:
                self.statusBar.showMessage("批量处理完成！", 5000)
                QMessageBox.information(self, "批量处理完成", "所有选中的模板处理已完成！")
                
            self._reset_batch_ui()
            # 发出提示音（如果启用）
            QApplication.beep()
            return
        
        logger.info(f"处理队列中的下一个任务，当前队列长度: {len(self.processing_queue)}")
        
        # 获取下一个任务索引
        next_idx = self.processing_queue[0]
        self.processing_queue.pop(0)
        
        if next_idx < 0 or next_idx >= len(self.tabs):
            logger.error(f"无效的任务索引: {next_idx}，跳过此任务")
            QTimer.singleShot(100, self._process_next_task)
            return
        
        # 获取对应的标签页信息
        tab = self.tabs[next_idx]
        self.current_processing_tab = next_idx
        
        # 记录任务开始时间
        tab["start_time"] = time.time()
        
        logger.info(f"开始处理任务: {tab['name']}，索引: {next_idx}")
        
        # 更新状态
        tab["status"] = "处理中"
        self._update_tasks_table()
        
        # 更新队列状态 - 只计算当前批次中被选中的任务
        # 注意：此处计算逻辑是处理队列的总数 = 已完成任务数 + 队列中剩余任务数 + 当前正在处理的任务(1)
        completed_tasks = sum(1 for t in self.tabs if t["status"] == "完成")
        total_selected_tasks = completed_tasks + len(self.processing_queue) + 1  # 已完成的任务 + 队列中剩余的任务 + 当前正在处理的任务
        
        self.label_queue.setText(f"队列: {completed_tasks}/{total_selected_tasks}")
        
        # 更新当前任务标签
        self.label_current_task.setText(f"当前任务: {tab['name']}")
        
        # 获取标签页的主窗口实例
        window = tab.get("window")
        if not window:
            logger.error(f"标签页 {next_idx} 的窗口实例为空，跳过此任务")
            self.current_processing_tab = None
            tab["status"] = "失败"
            self._update_tasks_table()
            QTimer.singleShot(100, self._process_next_task)
            return
        
        # 更新进度条 - 使用实际完成比例
        if total_selected_tasks > 0:
            progress_percentage = (completed_tasks / total_selected_tasks) * 100
            self.batch_progress.setValue(int(progress_percentage))
        
        # 显示当前处理的任务信息
        self.statusBar.showMessage(f"正在处理: {tab['name']}")
        
        # 确保UI更新
        QApplication.processEvents()
        
        try:
            # 设置一个检查完成状态的定时器函数
            def check_completion():
                try:
                    if not self.is_processing:
                        logger.info("批处理已停止，不再检查任务完成状态")
                        return
                    
                    # 添加更详细的日志，帮助诊断问题
                    logger.debug(f"检查任务 {tab['name']} 完成状态:")
                    
                    # 检查线程状态
                    thread_exists = hasattr(window, "processing_thread")
                    thread_running = thread_exists and window.processing_thread is not None
                    thread_alive = thread_running and (
                        hasattr(window.processing_thread, "is_alive") and 
                        window.processing_thread.is_alive()
                    )
                    
                    # 检查完成标志状态
                    has_completion_attr = hasattr(window, "compose_completed")
                    completion_flag = has_completion_attr and window.compose_completed
                    
                    # 记录详细状态日志
                    logger.debug(f"  - 线程状态: 存在={thread_exists}, 运行中={thread_running}, 活跃={thread_alive}")
                    logger.debug(f"  - 完成标志: 存在={has_completion_attr}, 已设置={completion_flag}")
                    
                    # 检查是否有文件正在生成
                    is_generating_files = False
                    if hasattr(window, "processor") and window.processor:
                        is_generating_files = True
                    
                    # 检查是否完成的条件：1.线程不存在或已结束 2.有专门的完成标志
                    thread_completed = not thread_running or (thread_running and not thread_alive)
                    has_completion_flag = completion_flag
                    
                    # 添加处理器检查 - 如果处理器已被清空，也视为完成
                    processor_cleared = not hasattr(window, "processor") or window.processor is None
                    logger.debug(f"  - 处理器状态: 已清除={processor_cleared}, 正在生成文件={is_generating_files}")
                    
                    if thread_completed or has_completion_flag or processor_cleared:
                        # 处理已完成，更新状态
                        logger.info(f"检测到任务 {tab['name']} 已完成，更新状态")
                        
                        # 记录结束时间和处理时间
                        end_time = time.time()
                        if tab.get("start_time"):
                            process_time = end_time - tab["start_time"]
                            tab["process_time"] = process_time
                        
                        # 获取处理数量
                        process_count = 0
                        if hasattr(window, "last_compose_count"):
                            process_count = window.last_compose_count
                        tab["process_count"] = process_count
                        
                        # 更新总计数据
                        self.total_processed_count += process_count
                        if tab.get("process_time"):
                            self.total_process_time += tab["process_time"]
                        
                        # 更新状态
                        tab["status"] = "完成"
                        tab["last_process_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        self._update_tasks_table()
                        self.current_processing_tab = None
                        
                        # 更新进度信息 - 使用当前批次中被选中的任务进行计算
                        # 注意：此处当前任务已被标记为"完成"，因此计算逻辑是 总数 = 已完成任务数(包含当前任务) + 队列中剩余任务数
                        completed_tasks = sum(1 for t in self.tabs if t["status"] == "完成")
                        total_selected_tasks = completed_tasks + len(self.processing_queue)  # 已完成的任务 + 队列中剩余的任务
                        
                        self.label_queue.setText(f"队列: {completed_tasks}/{total_selected_tasks}")
                        
                        if total_selected_tasks > 0:
                            progress_percentage = (completed_tasks / total_selected_tasks) * 100
                            self.batch_progress.setValue(int(progress_percentage))
                        
                        # 确保资源被清理
                        try:
                            if hasattr(window, "processor") and window.processor:
                                if hasattr(window.processor, "stop_processing"):
                                    window.processor.stop_processing()
                                window.processor = None
                            if hasattr(window, "processing_thread") and window.processing_thread:
                                window.processing_thread = None
                        except Exception as e:
                            logger.error(f"清理资源时出错: {str(e)}")
                        
                        # 处理完成后，立即启动下一个任务
                        logger.info(f"标签页 {next_idx} 处理完成，准备处理下一个任务")
                        
                        # 使用短时间延迟调用下一个任务，确保UI有时间更新
                        QTimer.singleShot(500, self._process_next_task)
                    else:
                        # 如果线程仍在运行，再次检查
                        # 为了避免卡住，我们也检查一下是否线程确实在工作
                        if hasattr(window, "last_progress_update"):
                            current_time = time.time()
                            time_since_update = current_time - window.last_progress_update
                            logger.debug(f"  - 上次进度更新: {time_since_update:.1f}秒前")
                            
                            # 增加超时时间到30秒，视频处理可能需要更长时间
                            if time_since_update > 30:  # 如果30秒没有进度更新
                                logger.warning(f"任务 {tab['name']} 似乎已卡住 (>30秒无进度更新)，尝试重启处理流程")
                                
                                # 尝试直接调用处理过程来恢复
                                try:
                                    # 检查是否有进度标签
                                    if hasattr(window, "label_progress"):
                                        progress_text = window.label_progress.text()
                                        logger.debug(f"  - 当前进度标签: {progress_text}")
                                    
                                    # 如果处理器存在，尝试强制更新进度来触发进度检测
                                    if hasattr(window, "processor") and window.processor:
                                        if hasattr(window.processor, "report_progress"):
                                            window.processor.report_progress("批处理模式中重新触发进度更新", 50.0)
                                            window.last_progress_update = time.time()
                                            logger.info("已重新触发进度更新")
                                            QTimer.singleShot(500, check_completion)
                                            return
                                        
                                    # 如果无法恢复处理流程，则放弃当前任务，继续下一个
                                    logger.warning(f"无法恢复任务 {tab['name']} 的处理流程，放弃当前任务")
                                    tab["status"] = "失败(超时)"
                                    self._update_tasks_table()
                                    self.current_processing_tab = None
                                    
                                    # 尝试停止当前任务
                                    window.on_stop_compose()
                                    
                                    # 延迟一下再处理下一个任务
                                    QTimer.singleShot(1000, self._process_next_task)
                                    return
                                except Exception as e:
                                    logger.error(f"尝试恢复处理流程时出错: {str(e)}")
                                    error_detail = traceback.format_exc()
                                    logger.error(f"详细错误信息: {error_detail}")
                                    
                                    # 停止当前任务，继续下一个
                                    tab["status"] = "失败(处理错误)"
                                    self._update_tasks_table()
                                    self.current_processing_tab = None
                                    window.on_stop_compose()
                                    QTimer.singleShot(1000, self._process_next_task)
                                    return
                        
                        # 更快地检查状态 - 1秒检查一次
                        QTimer.singleShot(1000, check_completion)
                except Exception as e:
                    logger.error(f"检查任务完成状态时出错: {str(e)}")
                    error_detail = traceback.format_exc()
                    logger.error(f"详细错误信息: {error_detail}")
                    
                    # 出错后也要继续下一个任务
                    tab["status"] = "失败"
                    self._update_tasks_table()
                    self.current_processing_tab = None
                    QTimer.singleShot(500, self._process_next_task)
            
            # 在启动前，确保窗口已经初始化完成
            if hasattr(window, "last_progress_update"):
                window.last_progress_update = time.time()
            else:
                # 如果没有这个属性，添加一个
                window.last_progress_update = time.time()
            
            # 重置处理状态标志
            window.compose_completed = False
            window.compose_error = False
            logger.info(f"开始处理标签页 {next_idx}: {tab['name']}")
            
            # 确保标签页处于可见状态，切换到相应标签
            self.tab_widget.setCurrentIndex(next_idx)
            QApplication.processEvents()  # 确保UI更新
            
            # 启动合成
            try:
                # 尝试触发关键UI事件，确保实际点击按钮而不只是调用后台函数
                if hasattr(window, "btn_start_compose") and window.btn_start_compose:
                    window.btn_start_compose.click()
                    logger.info(f"通过点击按钮启动合成: {tab['name']}")
                else:
                    # 如果无法找到按钮，直接调用方法
                    window.on_start_compose()
                    logger.info(f"通过调用方法启动合成: {tab['name']}")
            except Exception as e:
                logger.error(f"启动合成过程时出错: {str(e)}")
                error_detail = traceback.format_exc()
                logger.error(f"详细错误信息: {error_detail}")
                
                # 尝试一次直接方法调用
                try:
                    window.on_start_compose()
                    logger.info("使用备用方法启动合成")
                except Exception as e2:
                    logger.error(f"备用启动方法也失败: {str(e2)}")
                    # 失败后继续下一个任务
                    tab["status"] = "失败(无法启动)"
                    self._update_tasks_table()
                    self.current_processing_tab = None
                    QTimer.singleShot(500, self._process_next_task)
                    return
            
            # 启动检查完成状态的定时器，稍微延迟一下确保处理已经开始
            QTimer.singleShot(1000, check_completion)
            
        except Exception as e:
            logger.error(f"处理标签页 {next_idx} 时出错: {str(e)}")
            # 添加详细的错误信息
            error_detail = traceback.format_exc()
            logger.error(f"详细错误信息: {error_detail}")
            
            tab["status"] = "失败"
            self._update_tasks_table()
            self.current_processing_tab = None
            
            # 出错后，继续处理下一个任务
            QTimer.singleShot(500, self._process_next_task)
    
    def _update_task_status(self, tab_idx, status):
        """更新任务状态（由工作线程调用，保证在UI线程执行）"""
        try:
            if 0 <= tab_idx < len(self.tabs):
                old_status = self.tabs[tab_idx].get("status", "")
                self.tabs[tab_idx]["status"] = status
                
                # 如果是完成状态，更新最后处理时间
                if status in ["完成", "失败"]:
                    import datetime
                    self.tabs[tab_idx]["last_process_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # 处理完成后自动保存模板状态
                    self._save_template_state()
                
                self._update_tasks_table()
                logger.info(f"任务 '{self.tabs[tab_idx]['name']}' 状态更新为: {status} (之前: {old_status})")
                
                # 如果是在批处理过程中，并且状态变为"失败"，需要处理队列
                if self.is_processing and status == "失败" and self.current_processing_tab == tab_idx:
                    logger.info(f"任务 '{self.tabs[tab_idx]['name']}' 失败，准备处理下一个任务")
                    self.current_processing_tab = None
                    # 使用短延迟再处理下一个任务，以确保UI有时间更新
                    QTimer.singleShot(500, self._process_next_task)
            else:
                logger.warning(f"无效的标签索引: {tab_idx}")
        except Exception as e:
            logger.error(f"更新任务状态时出错: {str(e)}")
            logger.error(traceback.format_exc())
    
    def _setup_dialog_filter(self):
        """设置全局对话框过滤器，用于在批处理模式下抑制对话框"""
        # 保存原始的QMessageBox方法
        self._original_info = QMessageBox.information
        self._original_warning = QMessageBox.warning
        self._original_critical = QMessageBox.critical
        self._original_question = QMessageBox.question
        
        # 定义在批处理模式下使用的替代方法
        def _filtered_info(parent, title, text, *args, **kwargs):
            # 如果正在批处理且不是来自BatchWindow的消息，则忽略
            if self.is_processing and parent is not self:
                logger.info(f"批处理模式抑制信息对话框: {title} - {text}")
                # 通常信息对话框返回QMessageBox.Ok
                return QMessageBox.Ok
            # 否则使用原始方法
            return self._original_info(parent, title, text, *args, **kwargs)
        
        def _filtered_warning(parent, title, text, *args, **kwargs):
            # 如果正在批处理且不是来自BatchWindow的消息，则忽略
            if self.is_processing and parent is not self:
                logger.warning(f"批处理模式抑制警告对话框: {title} - {text}")
                # 通常警告对话框返回QMessageBox.Ok
                return QMessageBox.Ok
            # 否则使用原始方法
            return self._original_warning(parent, title, text, *args, **kwargs)
        
        def _filtered_critical(parent, title, text, *args, **kwargs):
            # 如果正在批处理且不是来自BatchWindow的消息，则忽略
            if self.is_processing and parent is not self:
                logger.error(f"批处理模式抑制错误对话框: {title} - {text}")
                # 通常错误对话框返回QMessageBox.Ok
                return QMessageBox.Ok
            # 否则使用原始方法
            return self._original_critical(parent, title, text, *args, **kwargs)
        
        def _filtered_question(parent, title, text, *args, **kwargs):
            # 如果正在批处理且不是来自BatchWindow的消息，则忽略
            if self.is_processing and parent is not self:
                logger.info(f"批处理模式抑制问题对话框: {title} - {text}")
                # 对于问题对话框，通常返回Yes作为肯定回答
                return QMessageBox.Yes
            # 否则使用原始方法
            return self._original_question(parent, title, text, *args, **kwargs)
        
        # 替换全局方法
        QMessageBox.information = _filtered_info
        QMessageBox.warning = _filtered_warning
        QMessageBox.critical = _filtered_critical
        QMessageBox.question = _filtered_question
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 检查是否有正在进行的处理
        if self.is_processing:
            reply = QMessageBox.question(
                self, 
                "确认退出", 
                "批量处理正在进行中，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                event.ignore()
                return
            
            # 停止所有处理
            self._on_stop_batch()
        
        try:
            # 保存当前模板状态
            self._save_template_state()
        except Exception as e:
            logger.error(f"保存模板状态时出错: {str(e)}")
        
        # 恢复原始对话框方法
        if hasattr(self, '_original_info'):
            QMessageBox.information = self._original_info
        if hasattr(self, '_original_warning'):
            QMessageBox.warning = self._original_warning
        if hasattr(self, '_original_critical'):
            QMessageBox.critical = self._original_critical
        if hasattr(self, '_original_question'):
            QMessageBox.question = self._original_question
        
        logger.info("正在关闭所有标签页")
        
        # 关闭所有标签页
        for i, tab in enumerate(self.tabs):
            if "window" in tab and tab["window"]:
                try:
                    # 先清理资源
                    window = tab["window"]
                    if hasattr(window, "processor") and window.processor:
                        window.processor = None
                    if hasattr(window, "processing_thread") and window.processing_thread:
                        window.processing_thread = None
                    
                    # 关闭窗口
                    window.close()
                    
                    logger.info(f"已关闭标签页 {i+1}/{len(self.tabs)}")
                except Exception as e:
                    logger.error(f"关闭标签页 {tab['name']} 时出错: {str(e)}")
        
        # 执行垃圾回收
        gc.collect()
        
        # 接受关闭事件
        event.accept()
    
    def _save_template_state(self):
        """保存当前模板状态"""
        try:
            # 收集各标签页的文件路径和文件夹路径信息
            for i, tab in enumerate(self.tabs):
                if "window" in tab and tab["window"]:
                    window = tab["window"]
                    
                    # 获取当前配置文件路径
                    config_file = ""
                    if hasattr(window, "config_file") and window.config_file:
                        config_file = window.config_file
                    
                    # 获取当前处理文件夹路径
                    folder_path = ""
                    if hasattr(window, "input_folder_path"):
                        folder_path = window.input_folder_path.text().strip()
                    
                    # 获取实例ID
                    instance_id = tab.get("instance_id", "")
                    if not instance_id and hasattr(window, "user_settings") and hasattr(window.user_settings, "instance_id"):
                        instance_id = window.user_settings.instance_id
                    
                    # 更新标签页信息
                    tab["file_path"] = config_file
                    tab["folder_path"] = folder_path
                    tab["tab_index"] = i  # 更新标签页索引，确保与当前显示顺序一致
                    
                    # 确保有实例ID
                    if not tab.get("instance_id"):
                        tab["instance_id"] = instance_id or f"tab_saved_{i}_{time.time()}"
                    
                    logger.debug(f"保存模板状态: {tab['name']}, 索引: {i}, 文件夹: {folder_path}, 实例ID: {tab.get('instance_id', '')}")
            
            # 保存到配置文件
            self.template_state.save_template_tabs(self.tabs)
            logger.info(f"已保存 {len(self.tabs)} 个模板状态")
        except Exception as e:
            logger.error(f"保存模板状态时出错: {str(e)}") 