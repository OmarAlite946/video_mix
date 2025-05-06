#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
用户设置模块
用于保存和加载用户界面设置，使程序在下次启动时能够记住上次的设置
"""

import os
import json
import logging
import uuid
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional

# 日志设置
logger = logging.getLogger(__name__)

# 配置文件路径
CONFIG_DIR = Path.home() / "VideoMixTool"
SETTINGS_FILE = CONFIG_DIR / "user_settings.json"

# 默认设置
DEFAULT_SETTINGS = {
    # 导入素材设置
    "import_folder": "",           # 最后导入的文件夹路径
    "last_material_folders": [],   # 最后导入的素材文件夹列表 
    "folder_extract_modes": {},    # 文件夹抽取模式设置
    
    # 输出目录设置
    "save_dir": "",                # 保存目录
    
    # 视频参数设置
    "resolution": "竖屏 1080x1920", # 默认分辨率
    "bitrate": 5000,               # 默认比特率
    "original_bitrate": False,     # 是否使用原始比特率
    "transition": "不使用转场",      # 默认转场效果
    "gpu": "自动检测",              # 默认GPU选项
    "encode_mode": "标准模式",       # 编码模式
    
    # 水印设置
    "watermark_enabled": False,    # 是否启用水印
    "watermark_prefix": "",        # 水印前缀
    "watermark_size": 36,          # 水印大小
    "watermark_color": "#FFFFFF",  # 水印颜色
    "watermark_position": "右下角", # 水印位置
    "watermark_pos_x": 10,         # 水印X偏移
    "watermark_pos_y": 10,         # 水印Y偏移
    
    # 音频设置
    "voice_volume": 100,           # 配音音量
    "bgm_volume": 50,              # 背景音乐音量
    "bgm_path": "",                # 背景音乐路径
    "audio_mode": "自动识别",        # 音频处理模式
    
    # 批量处理设置
    "generate_count": 1,           # 生成数量
    
    # 缓存设置
    "cache_dir": "",               # 缓存目录
    
    # 界面状态
    "last_active_tab": 0,          # 最后活动的标签页索引
    "main_window_size": [1200, 800], # 主窗口大小
    "main_window_pos": [100, 100],   # 主窗口位置
    
    # 最后一次操作状态
    "last_operation_success": True    # 最后一次操作是否成功
}


class UserSettings:
    """用户设置管理类"""
    
    # 存储多实例的设置
    _instances = {}
    
    def __init__(self, instance_id: str = None):
        """
        初始化用户设置
        
        Args:
            instance_id: 实例ID，用于区分不同的设置文件
        """
        self.instance_id = instance_id or str(uuid.uuid4())[:8]
        self.settings_dir = Path(os.path.expanduser("~")) / "VideoMixTool"
        self.settings_file = self.settings_dir / "user_settings.json"
        # 初始化为默认设置的副本，而不是空字典
        self.settings = DEFAULT_SETTINGS.copy()
        
        # 确保设置目录存在
        self.settings_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载设置
        self.load_settings()
        
        # 记录实例
        UserSettings._instances[self.instance_id] = self
        
        # 记录标识符
        logger.debug(f"创建新的用户设置实例: {self.instance_id}")
    
    @property
    def instance_id(self):
        """获取实例ID"""
        return self._instance_id
    
    @instance_id.setter
    def instance_id(self, value):
        """设置实例ID"""
        if not value:
            value = f"global_{uuid.uuid4().hex[:8]}"
        
        # 规范化实例ID，确保不会有特殊字符导致文件名问题
        sanitized_id = value
        if not isinstance(value, str):
            sanitized_id = str(value)
        
        # 如果ID太长，使用哈希值缩短它
        if len(sanitized_id) > 50:
            hash_obj = hashlib.md5(sanitized_id.encode())
            sanitized_id = f"tab_{hash_obj.hexdigest()[:16]}"
        
        # 确保实例ID有效（移除非法字符）
        sanitized_id = "".join(c for c in sanitized_id if c.isalnum() or c in "_-.")
        if not sanitized_id:
            sanitized_id = f"tab_{uuid.uuid4().hex[:16]}"
        
        self._instance_id = sanitized_id
        
        # 如果实例ID发生变化，重新加载设置
        logger.debug(f"设置实例ID: {self._instance_id}")
        self.load_settings()
    
    def _get_settings_file(self):
        """获取当前实例的设置文件路径"""
        if self.instance_id == "global" or self.instance_id.startswith("global_"):
            return SETTINGS_FILE
        else:
            # 为每个实例创建单独的设置文件，确保文件名有效
            settings_filename = f"user_settings_{self.instance_id}.json"
            return CONFIG_DIR / settings_filename
    
    def _load_settings(self) -> bool:
        """
        从配置文件加载设置
        
        Returns:
            bool: 加载是否成功
        """
        try:
            settings_file = self._get_settings_file()
            
            # 首先加载全局设置作为基础
            if not self.instance_id.startswith("global") and SETTINGS_FILE.exists():
                try:
                    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                        global_settings = json.load(f)
                        # 更新设置，保留默认值
                        for key, value in global_settings.items():
                            if key in self.settings:
                                self.settings[key] = value
                except Exception as e:
                    logger.warning(f"加载全局设置作为基础时出错: {e}")
            
            # 然后加载实例特定设置
            if settings_file.exists():
                with open(settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    
                    # 检查设置文件的完整性
                    if not isinstance(loaded_settings, dict):
                        logger.warning(f"设置文件 {settings_file} 格式错误，使用默认设置")
                        return False
                    
                    # 更新设置，保留默认值
                    for key, value in loaded_settings.items():
                        if key in self.settings:
                            self.settings[key] = value
                logger.info(f"已从 {settings_file} 加载用户设置，实例ID: {self.instance_id}")
                return True
            else:
                # 如果配置文件不存在，使用全局设置或默认设置
                if not self.instance_id.startswith("global"):
                    logger.info(f"实例 {self.instance_id} 无独立设置文件，使用全局设置或默认设置")
                else:
                    # 如果是全局设置，创建默认设置文件
                    self._save_settings()
                    logger.info("创建了默认用户设置文件")
                return True
        except Exception as e:
            logger.error(f"加载用户设置出错: {e}")
            # 创建备份以防止损坏
            self._save_settings_backup()
            return False
    
    def _save_settings_backup(self):
        """保存设置备份"""
        try:
            if not CONFIG_DIR.exists():
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            
            settings_file = self._get_settings_file()
            backup_file = settings_file.with_suffix(f".bak.{uuid.uuid4().hex[:8]}")
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存用户设置备份到 {backup_file}")
            
            # 清理旧备份文件
            backup_pattern = f"user_settings*.bak.*"
            backup_files = sorted(Path(CONFIG_DIR).glob(backup_pattern), 
                                key=lambda x: os.path.getmtime(x),
                                reverse=True)
            
            # 保留最新的3个备份
            for old_file in backup_files[3:]:
                try:
                    old_file.unlink()
                except Exception as e:
                    logger.warning(f"删除旧备份文件失败: {e}")
                
        except Exception as e:
            logger.error(f"保存用户设置备份失败: {e}")
    
    def _save_settings(self) -> bool:
        """
        保存设置到文件
        
        Returns:
            bool: 保存是否成功
        """
        try:
            # 确保目录存在
            if not CONFIG_DIR.exists():
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            
            settings_file = self._get_settings_file()
            
            # 先保存到临时文件，然后重命名，避免写入过程中文件损坏
            temp_file = settings_file.with_suffix(".tmp")
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
            
            # 如果已存在设置文件，先创建备份
            if settings_file.exists():
                try:
                    backup_file = settings_file.with_suffix(f".bak")
                    if backup_file.exists():
                        backup_file.unlink()  # 删除旧备份
                    settings_file.rename(backup_file)  # 创建新备份
                except Exception as e:
                    logger.warning(f"创建设置文件备份失败: {e}")
                    
            # 重命名临时文件为正式文件
            temp_file.rename(settings_file)
            
            logger.info(f"已保存用户设置到 {settings_file}，实例ID: {self.instance_id}")
            
            # 同时创建一个带时间戳的备份
            self._save_settings_backup()
            
            return True
        except Exception as e:
            logger.error(f"保存用户设置出错: {e}，实例ID: {self.instance_id}")
            # 尝试保存备份
            self._save_settings_backup()
            return False
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        获取指定键的设置值
        
        Args:
            key: 设置键名
            default: 如果键不存在时返回的默认值
            
        Returns:
            Any: 设置值
        """
        return self.settings.get(key, default)
    
    def set_setting(self, key: str, value: Any) -> bool:
        """
        设置指定键的值
        
        Args:
            key: 设置键名
            value: 设置值
            
        Returns:
            bool: 设置是否成功
        """
        if key not in self.settings and key not in DEFAULT_SETTINGS:
            logger.warning(f"尝试设置未知键: {key}，实例ID: {self.instance_id}")
        
        # 记录值变化
        if key in self.settings and self.settings[key] != value:
            logger.debug(f"设置 {key} 从 {self.settings.get(key)} 变更为 {value}, 实例ID: {self.instance_id}")
        
        self.settings[key] = value
        return self._save_settings()
    
    def set_multiple_settings(self, settings_dict: Dict[str, Any]) -> bool:
        """
        批量设置多个键值
        
        Args:
            settings_dict: 包含多个键值对的字典
            
        Returns:
            bool: 设置是否成功
        """
        changes = []
        for key, value in settings_dict.items():
            if key in self.settings and self.settings[key] != value:
                changes.append(f"{key}: {self.settings.get(key)} -> {value}")
            self.settings[key] = value
        
        if changes:
            logger.debug(f"批量更新设置，实例ID: {self.instance_id}, 变更: {', '.join(changes)}")
        
        return self._save_settings()
    
    def get_all_settings(self) -> Dict[str, Any]:
        """
        获取所有设置
        
        Returns:
            Dict[str, Any]: 所有设置的字典
        """
        return self.settings.copy()
    
    def reset_to_defaults(self) -> bool:
        """
        将设置重置为默认值
        
        Returns:
            bool: 重置是否成功
        """
        self.settings = DEFAULT_SETTINGS.copy()
        logger.info(f"重置实例 {self.instance_id} 的设置为默认值")
        return self._save_settings()
    
    def load_settings(self) -> bool:
        """
        加载设置
        
        Returns:
            bool: 加载是否成功
        """
        return self._load_settings()
    
    def save_settings(self) -> bool:
        """
        保存设置
        
        Returns:
            bool: 保存是否成功
        """
        return self._save_settings() 