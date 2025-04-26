#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
模板状态管理模块
用于保存和加载模板状态信息
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

# 获取日志
logger = logging.getLogger(__name__)

# 配置文件路径
CONFIG_DIR = Path.home() / "VideoMixTool"
TEMPLATE_STATE_FILE = CONFIG_DIR / "template_state.json"

class TemplateState:
    """模板状态管理类"""
    
    def __init__(self):
        """初始化模板状态管理类"""
        # 默认为空列表
        self.template_tabs = []
    
    def save_template_tabs(self, tabs: List[Dict[str, Any]]) -> bool:
        """
        保存模板标签页状态
        
        Args:
            tabs: 包含模板信息的列表
                每个模板包含：
                - name: 模板名称
                - file_path: 模板配置文件路径
                - folder_path: 处理文件夹路径
                
        Returns:
            bool: 保存是否成功
        """
        try:
            # 确保目录存在
            if not CONFIG_DIR.exists():
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            
            # 只保存必要的信息，不保存窗口对象
            tabs_to_save = []
            for tab in tabs:
                if not tab:
                    continue
                    
                tab_info = {
                    "name": tab.get("name", ""),
                    "file_path": tab.get("file_path", ""),
                    "folder_path": tab.get("folder_path", "")
                }
                
                # 只要有模板名称就保存，不再要求必须有文件路径或文件夹路径
                if tab_info["name"]:
                    tabs_to_save.append(tab_info)
            
            # 保存到文件
            with open(TEMPLATE_STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(tabs_to_save, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存 {len(tabs_to_save)} 个模板状态到 {TEMPLATE_STATE_FILE}")
            return True
        except Exception as e:
            logger.error(f"保存模板状态时出错: {str(e)}")
            return False
    
    def load_template_tabs(self) -> List[Dict[str, Any]]:
        """
        加载保存的模板标签页状态
        
        Returns:
            List[Dict]: 模板标签页状态列表
        """
        try:
            if TEMPLATE_STATE_FILE.exists():
                with open(TEMPLATE_STATE_FILE, 'r', encoding='utf-8') as f:
                    tabs = json.load(f)
                
                self.template_tabs = tabs
                logger.info(f"已从 {TEMPLATE_STATE_FILE} 加载 {len(tabs)} 个模板状态")
            else:
                self.template_tabs = []
                logger.info("模板状态文件不存在，使用空模板列表")
        except Exception as e:
            logger.error(f"加载模板状态时出错: {str(e)}")
            self.template_tabs = []
        
        return self.template_tabs 