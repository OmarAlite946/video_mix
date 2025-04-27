#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
模板状态管理模块
用于保存和加载模板状态信息
"""

import os
import json
import logging
import uuid
import time
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
                - tab_index: 标签页在界面中的索引位置（确保顺序正确）
                - instance_id: 实例ID（确保每个标签页有独立设置）
                
        Returns:
            bool: 保存是否成功
        """
        try:
            # 确保目录存在
            if not CONFIG_DIR.exists():
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            
            # 只保存必要的信息，不保存窗口对象
            tabs_to_save = []
            for i, tab in enumerate(tabs):
                if not tab:
                    continue
                    
                # 生成唯一ID，确保不会冲突
                if not tab.get("instance_id"):
                    unique_id = f"tab_{uuid.uuid4().hex}"
                    tab["instance_id"] = unique_id
                
                tab_info = {
                    "name": tab.get("name", ""),
                    "file_path": tab.get("file_path", ""),
                    "folder_path": tab.get("folder_path", ""),
                    "tab_index": i,  # 记录标签页顺序
                    "instance_id": tab.get("instance_id"),  # 记录实例ID
                    "timestamp": time.time()  # 添加时间戳，用于排序和验证
                }
                
                # 只要有模板名称就保存，不再要求必须有文件路径或文件夹路径
                if tab_info["name"]:
                    tabs_to_save.append(tab_info)
            
            # 确保按索引排序
            tabs_to_save = sorted(tabs_to_save, key=lambda x: x["tab_index"])
            
            # 保存到文件
            with open(TEMPLATE_STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(tabs_to_save, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存 {len(tabs_to_save)} 个模板状态到 {TEMPLATE_STATE_FILE}")
            
            # 创建备份文件，防止文件损坏导致标签页丢失
            backup_file = CONFIG_DIR / f"template_state_backup_{int(time.time())}.json"
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(tabs_to_save, f, ensure_ascii=False, indent=2)
            
            # 只保留最近5个备份文件
            backup_files = sorted(CONFIG_DIR.glob("template_state_backup_*.json"), 
                                  key=lambda x: os.path.getmtime(x), 
                                  reverse=True)
            for old_file in backup_files[5:]:
                try:
                    os.remove(old_file)
                except:
                    pass
                
            return True
        except Exception as e:
            logger.error(f"保存模板状态时出错: {str(e)}")
            return False
    
    def load_template_tabs(self) -> List[Dict[str, Any]]:
        """
        加载保存的模板标签页状态
        
        Returns:
            List[Dict]: 模板标签页状态列表（按标签页索引排序）
        """
        try:
            # 尝试从主文件加载
            if TEMPLATE_STATE_FILE.exists():
                with open(TEMPLATE_STATE_FILE, 'r', encoding='utf-8') as f:
                    tabs = json.load(f)
                
                # 确保按tab_index排序，以保持原有顺序
                if tabs and isinstance(tabs, list):
                    # 检查数据完整性
                    valid_tabs = []
                    for i, tab in enumerate(tabs):
                        # 如果没有tab_index字段，则添加默认值
                        if "tab_index" not in tab:
                            tab["tab_index"] = i
                        
                        # 确保实例ID存在
                        if "instance_id" not in tab or not tab["instance_id"]:
                            tab["instance_id"] = f"tab_restored_{uuid.uuid4().hex}"
                        
                        # 验证必要的字段存在
                        if "name" in tab and tab["name"]:
                            valid_tabs.append(tab)
                        else:
                            logger.warning(f"跳过无效的标签页数据: {tab}")
                    
                    # 按标签页索引排序
                    if valid_tabs:
                        tabs = sorted(valid_tabs, key=lambda x: x.get("tab_index", 999))
                    else:
                        logger.warning("未找到有效的标签页数据")
                        tabs = []
                
                self.template_tabs = tabs
                logger.info(f"已从 {TEMPLATE_STATE_FILE} 加载 {len(tabs)} 个模板状态")
            else:
                # 如果主文件不存在，尝试从备份文件恢复
                backup_files = sorted(CONFIG_DIR.glob("template_state_backup_*.json"), 
                                      key=lambda x: os.path.getmtime(x), 
                                      reverse=True)
                
                if backup_files:
                    # 使用最新的备份文件
                    latest_backup = backup_files[0]
                    logger.info(f"主模板状态文件不存在，尝试从备份文件恢复: {latest_backup}")
                    
                    with open(latest_backup, 'r', encoding='utf-8') as f:
                        tabs = json.load(f)
                    
                    # 同样进行排序和验证
                    valid_tabs = []
                    for i, tab in enumerate(tabs):
                        if "tab_index" not in tab:
                            tab["tab_index"] = i
                        
                        if "instance_id" not in tab or not tab["instance_id"]:
                            tab["instance_id"] = f"tab_backup_{uuid.uuid4().hex}"
                        
                        if "name" in tab and tab["name"]:
                            valid_tabs.append(tab)
                    
                    if valid_tabs:
                        self.template_tabs = sorted(valid_tabs, key=lambda x: x.get("tab_index", 999))
                        logger.info(f"已从备份文件 {latest_backup} 恢复 {len(self.template_tabs)} 个模板状态")
                    else:
                        self.template_tabs = []
                        logger.warning("备份文件中未找到有效的标签页数据")
                else:
                    self.template_tabs = []
                    logger.info("模板状态文件不存在，使用空模板列表")
        except Exception as e:
            logger.error(f"加载模板状态时出错: {str(e)}")
            # 如果主文件加载失败，尝试从备份恢复
            try:
                backup_files = sorted(CONFIG_DIR.glob("template_state_backup_*.json"), 
                                    key=lambda x: os.path.getmtime(x), 
                                    reverse=True)
                
                if backup_files:
                    latest_backup = backup_files[0]
                    logger.info(f"主模板状态文件加载失败，尝试从备份文件恢复: {latest_backup}")
                    
                    with open(latest_backup, 'r', encoding='utf-8') as f:
                        self.template_tabs = json.load(f)
                        
                    logger.info(f"已从备份文件恢复 {len(self.template_tabs)} 个模板状态")
                else:
                    self.template_tabs = []
            except:
                self.template_tabs = []
                logger.error("备份恢复也失败，使用空模板列表")
        
        return self.template_tabs 