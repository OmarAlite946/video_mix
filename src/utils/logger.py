#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
日志模块
"""

import os
import logging
import sys
from pathlib import Path
from datetime import datetime

# 日志级别
LOG_LEVEL = logging.DEBUG

# 默认日志目录
DEFAULT_LOG_DIR = Path.home() / "VideoMixTool" / "logs"

# 全局日志对象
logger = None

def setup_logger(log_dir=None):
    """
    设置日志系统
    
    Args:
        log_dir: 日志保存目录，如果为None则使用默认目录
    
    Returns:
        logging.Logger: 日志对象
    """
    global logger
    
    if logger is not None:
        return logger
    
    # 设置日志目录
    if log_dir is None:
        log_dir = DEFAULT_LOG_DIR
    
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建日志文件名，包含日期
    log_filename = f"videomixtool_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_path = log_dir / log_filename
    
    # 创建日志器
    logger = logging.getLogger("VideoMixTool")
    logger.setLevel(LOG_LEVEL)
    
    # 创建文件处理器
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(LOG_LEVEL)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(LOG_LEVEL)
    
    # 设置日志格式
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] - %(message)s"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # 记录初始日志
    logger.info("日志系统初始化完成")
    logger.info(f"日志文件保存在: {log_path}")
    
    return logger

def get_logger():
    """
    获取日志对象
    
    Returns:
        logging.Logger: 日志对象
    """
    global logger
    
    if logger is None:
        logger = setup_logger()
    
    return logger 