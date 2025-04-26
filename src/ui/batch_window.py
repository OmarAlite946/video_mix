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
from pathlib import Path
from typing import Dict, List, Any, Optional

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QProgressBar, QApplication,
    QTabWidget, QCheckBox, QMessageBox, QStatusBar,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMenu, QAction, QToolButton, QFrame, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QSize, QMetaObject, Q_ARG
from PyQt5.QtGui import QIcon, QFont, QColor

from src.ui.main_window import MainWindow
from src.utils.logger import get_logger

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
        
        # 初始化界面
        self._init_ui()
        
        # 初始化状态栏
        self._init_statusbar()
        
        # 添加初始标签页
        self._add_new_tab()
    
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
        self.tasks_table = QTableWidget(0, 4)  # 初始为0行，4列
        self.tasks_table.setHorizontalHeaderLabels(["选择", "模板名称", "状态", "最后处理时间"])
        self.tasks_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        # 设置列宽
        header = self.tasks_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # 选择框固定宽度
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # 名称列自适应
        header.setSectionResizeMode(2, QHeaderView.Fixed)  # 状态列固定宽度
        header.setSectionResizeMode(3, QHeaderView.Fixed)  # 时间列固定宽度
        
        self.tasks_table.setColumnWidth(0, 60)  # 选择框列宽
        self.tasks_table.setColumnWidth(2, 120)  # 状态列宽
        self.tasks_table.setColumnWidth(3, 180)  # 时间列宽
        
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
        # 创建新的MainWindow实例
        main_window = MainWindow()
        
        # 创建标签页并将MainWindow添加到其中
        tab_index = self.tab_widget.count()
        tab_name = f"模板 {tab_index + 1}"
        
        # 将窗口添加到标签页
        self.tab_widget.addTab(main_window, tab_name)
        
        # 添加到标签列表
        self.tabs.append({
            "window": main_window,
            "name": tab_name,
            "status": "就绪",
            "last_processed": "-"
        })
        
        # 更新任务表格
        self._update_tasks_table()
        
        # 切换到新标签页
        self.tab_widget.setCurrentIndex(tab_index)
        
        logger.info(f"添加了新标签页: {tab_name}")
    
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
            self.tabs.pop(index)
            
            # 关闭标签页
            self.tab_widget.removeTab(index)
            
            # 更新任务表格
            self._update_tasks_table()
            
            logger.info(f"关闭了标签页: {tab_name}")
    
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
            
            # 最后处理时间
            self.tasks_table.setItem(row, 3, QTableWidgetItem(tab["last_processed"]))
    
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
        
        for row in range(self.tasks_table.rowCount()):
            checkbox_container = self.tasks_table.cellWidget(row, 0)
            if checkbox_container:
                checkbox = checkbox_container.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    selected_tasks.append(row)
        
        if not selected_tasks:
            QMessageBox.warning(self, "批量处理", "请至少选择一个模板进行处理")
            return
        
        # 确认开始处理
        reply = QMessageBox.question(
            self, 
            "批量处理", 
            f"即将开始处理 {len(selected_tasks)} 个模板，是否继续？",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            # 清空处理队列
            self.processing_queue = selected_tasks.copy()
            
            # 更新界面状态
            for idx in selected_tasks:
                self.tabs[idx]["status"] = "等待中"
            
            self._update_tasks_table()
            
            # 更新界面状态
            self.is_processing = True
            self.btn_start_batch.setEnabled(False)
            self.btn_stop_batch.setEnabled(True)
            
            # 更新队列状态
            self.label_queue.setText(f"队列: 0/{len(selected_tasks)}")
            
            # 开始处理
            self._process_next_task()
    
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
            # 停止当前处理
            if self.current_processing_tab is not None:
                tab_idx = self.current_processing_tab
                if 0 <= tab_idx < len(self.tabs):
                    # 获取MainWindow实例并调用停止方法
                    main_window = self.tabs[tab_idx]["window"]
                    if main_window:
                        main_window.on_stop_compose()
            
            # 清空队列
            self.processing_queue = []
            
            # 更新界面状态
            self.label_current_task.setText("当前任务: 已停止")
            self.label_queue.setText("队列: 0/0")
            
            # 恢复界面状态
            self._reset_batch_ui()
    
    def _reset_batch_ui(self):
        """重置批处理界面状态"""
        self.is_processing = False
        self.current_processing_tab = None
        self.btn_start_batch.setEnabled(True)
        self.btn_stop_batch.setEnabled(False)
        self.batch_progress.setValue(0)
        self.statusBar.showMessage("批量处理已停止", 3000)
    
    def _process_next_task(self):
        """处理队列中的下一个任务"""
        if not self.processing_queue or not self.is_processing:
            # 处理完成或已停止
            if self.is_processing:
                # 正常完成所有任务
                self.label_current_task.setText("当前任务: 全部完成")
                self.batch_progress.setValue(100)
                self.statusBar.showMessage("批量处理已完成", 3000)
                QMessageBox.information(self, "批量处理", "所有模板处理完成！")
                self._reset_batch_ui()
            return
        
        # 获取下一个任务
        tab_idx = self.processing_queue.pop(0)
        self.current_processing_tab = tab_idx
        
        # 切换到对应标签
        self.tab_widget.setCurrentIndex(tab_idx)
        
        # 更新状态
        tab_name = self.tabs[tab_idx]["name"]
        self.tabs[tab_idx]["status"] = "处理中"
        self.tabs[tab_idx]["last_processed"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._update_tasks_table()
        
        # 更新当前任务显示
        self.label_current_task.setText(f"当前任务: {tab_name}")
        
        # 更新队列状态
        completed = len(self.tabs) - len(self.processing_queue) - 1
        total = len(self.tabs)
        self.label_queue.setText(f"队列: {completed}/{total}")
        
        # 更新总进度
        progress_percent = int(completed * 100 / total)
        self.batch_progress.setValue(progress_percent)
        
        # 获取MainWindow实例
        main_window = self.tabs[tab_idx]["window"]
        
        # 在单独线程中启动处理
        def run_process():
            try:
                # 模拟点击"开始合成"按钮
                main_window.on_start_compose()
                
                # 等待处理完成
                while main_window.processing_thread and main_window.processing_thread.is_alive():
                    time.sleep(0.5)
                    
                # 记录完成状态
                self.tabs[tab_idx]["status"] = "完成"
                self._update_tasks_table()
                
                # 处理下一个任务
                if self.is_processing:
                    QMetaObject.invokeMethod(self, "_process_next_task", Qt.QueuedConnection)
            except Exception as e:
                logger.error(f"处理模板 '{tab_name}' 时发生错误: {str(e)}")
                self.tabs[tab_idx]["status"] = "失败"
                self._update_tasks_table()
                
                # 处理下一个任务
                if self.is_processing:
                    QMetaObject.invokeMethod(self, "_process_next_task", Qt.QueuedConnection)
        
        # 启动处理线程
        self.processing_thread = threading.Thread(target=run_process, daemon=True)
        self.processing_thread.start()
    
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
        
        # 关闭所有标签页
        for tab in self.tabs:
            if "window" in tab and tab["window"]:
                tab["window"].close()
        
        # 接受关闭事件
        event.accept() 