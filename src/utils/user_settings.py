#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
用户设置模块
用于保存和加载用户界面设置，使程序在下次启动时能够记住上次的设置
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# 日志设置
logger = logging.getLogger(__name__)

# 配置文件路径
CONFIG_DIR = Path.home() / "VideoMixTool"
SETTINGS_FILE = CONFIG_DIR / "user_settings.json"

# 默认设置
DEFAULT_SETTINGS = {
    "import_folder": "",           # 最后导入的文件夹路径
    "save_dir": "",                # 保存目录
    "resolution": "竖屏 1080x1920", # 默认分辨率
    "bitrate": 5000,               # 默认比特率
    "original_bitrate": False,     # 是否使用原始比特率
    "transition": "不使用转场",      # 默认转场效果
    "gpu": "自动检测",              # 默认GPU选项
    "watermark_enabled": False,    # 是否启用水印
    "watermark_prefix": "",        # 水印前缀
    "watermark_size": 36,          # 水印大小
    "watermark_color": "#FFFFFF",  # 水印颜色
    "watermark_position": "右下角", # 水印位置
    "watermark_pos_x": 10,         # 水印X偏移
    "watermark_pos_y": 10,         # 水印Y偏移
    "voice_volume": 100,           # 配音音量
    "bgm_volume": 50,              # 背景音乐音量
    "bgm_path": "",                # 背景音乐路径
    "generate_count": 1,           # 生成数量
    "encode_mode": "标准模式"        # 编码模式
}


class UserSettings:
    """用户设置管理类"""
    
    def __init__(self):
        """初始化用户设置类"""
        # 使用默认设置的拷贝
        self.settings = DEFAULT_SETTINGS.copy()
        
        # 加载已有设置
        self.load_settings()
    
    def _load_settings(self) -> bool:
        """
        从配置文件加载设置
        
        Returns:
            bool: 加载是否成功
        """
        try:
            if SETTINGS_FILE.exists():
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    # 更新设置，保留默认值
                    for key, value in loaded_settings.items():
                        if key in self.settings:
                            self.settings[key] = value
                logger.info(f"已从 {SETTINGS_FILE} 加载用户设置")
                return True
            else:
                # 如果配置文件不存在，创建默认设置
                self._save_settings()
                logger.info("创建了默认用户设置文件")
                return True
        except Exception as e:
            logger.error(f"加载用户设置出错: {e}")
            return False
    
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
            
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存用户设置到 {SETTINGS_FILE}")
            return True
        except Exception as e:
            logger.error(f"保存用户设置出错: {e}")
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
            logger.warning(f"尝试设置未知键: {key}")
        
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
        for key, value in settings_dict.items():
            self.settings[key] = value
        
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