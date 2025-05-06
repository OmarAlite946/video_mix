#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
缓存配置模块
用于管理缓存文件的存储位置
"""

import os
import json
import logging
from pathlib import Path

# 日志设置
logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_CONFIG = {
    "cache_dir": str(Path.home() / "VideoMixTool" / "temp"),  # 默认缓存目录
}

# 配置文件路径
CONFIG_DIR = Path.home() / "VideoMixTool"
CONFIG_FILE = CONFIG_DIR / "cache_config.json"


class CacheConfig:
    """缓存配置管理类"""
    
    def __init__(self):
        """初始化缓存配置类"""
        # 默认配置
        self.config = DEFAULT_CONFIG.copy()
        
        # 加载已有配置
        self.load_config()
    
    def _load_config(self):
        """从配置文件加载配置"""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 更新配置，保留默认值
                    for key, value in loaded_config.items():
                        if key in self.config:
                            self.config[key] = value
                logger.info(f"已从 {CONFIG_FILE} 加载缓存配置")
            else:
                # 如果配置文件不存在，创建默认配置
                self._save_config()
        except Exception as e:
            logger.error(f"加载缓存配置出错: {e}")
    
    def _save_config(self):
        """保存配置到文件"""
        try:
            # 确保目录存在
            if not CONFIG_DIR.exists():
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存缓存配置到 {CONFIG_FILE}")
        except Exception as e:
            logger.error(f"保存缓存配置出错: {e}")
    
    def get_cache_dir(self) -> str:
        """
        获取当前配置的缓存目录
        
        Returns:
            str: 缓存目录路径
        """
        cache_dir = self.config.get("cache_dir", DEFAULT_CONFIG["cache_dir"])
        
        # 确保目录存在
        os.makedirs(cache_dir, exist_ok=True)
        
        return cache_dir
    
    def set_cache_dir(self, cache_dir: str) -> bool:
        """
        设置缓存目录
        
        Args:
            cache_dir: 新的缓存目录路径
            
        Returns:
            bool: 设置是否成功
        """
        if not cache_dir:
            logger.error("缓存目录路径不能为空")
            return False
        
        try:
            # 转换为Path对象处理路径
            cache_path = Path(cache_dir)
            
            # 创建目录（如果不存在）
            os.makedirs(cache_path, exist_ok=True)
            
            # 检查目录是否可写
            test_file = cache_path / f"test_write_{os.getpid()}.tmp"
            try:
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
            except Exception as e:
                logger.error(f"缓存目录不可写: {str(e)}")
                return False
            
            # 更新配置
            self.config["cache_dir"] = str(cache_path)
            self._save_config()
            
            logger.info(f"已设置缓存目录: {cache_path}")
            return True
        except Exception as e:
            logger.error(f"设置缓存目录时出错: {str(e)}")
            return False
    
    def load_config(self):
        """加载配置"""
        self._load_config()
    
    def save_config(self):
        """保存配置"""
        self._save_config() 