#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试混合模式下的快捷方式导入功能
"""

import os
import sys
import logging
from typing import List, Dict, Any, Tuple, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MixedModeTest")

# 导入工具函数
from src.utils.file_utils import resolve_shortcut
from src.core.video_processor import VideoProcessor

def test_mixed_mode_import(test_dir: str):
    """测试混合模式下的导入功能"""
    logger.info(f"开始测试混合模式导入: {test_dir}")
    
    # 检查测试目录是否存在
    if not os.path.isdir(test_dir):
        logger.error(f"测试目录不存在: {test_dir}")
        return
    
    # 初始化视频处理器
    processor = VideoProcessor()
    
    # 模拟导入素材文件夹
    material_folders = [{
        "path": test_dir,
        "name": os.path.basename(test_dir)
    }]
    
    # 定义进度回调函数
    def progress_callback(message: str, percent: float):
        logger.info(f"进度: {percent:.1f}% - {message}")
    
    # 设置进度回调
    processor.set_progress_callback(progress_callback)
    
    # 扫描素材文件夹
    logger.info("开始扫描素材文件夹...")
    material_data = processor._scan_material_folders(material_folders)
    
    # 显示扫描结果
    logger.info(f"扫描完成，共找到 {len(material_data)} 个素材段落:")
    
    # 计算统计数据
    normal_segments = 0
    shortcut_segments = 0
    total_videos = 0
    total_audios = 0
    
    # 分析和显示扫描结果
    for key, data in sorted(material_data.items()):
        is_shortcut = data.get("is_shortcut", False)
        segment_type = "快捷方式" if is_shortcut else "普通文件夹"
        
        if is_shortcut:
            shortcut_segments += 1
        else:
            normal_segments += 1
            
        video_count = len(data.get("videos", []))
        audio_count = len(data.get("audios", []))
        total_videos += video_count
        total_audios += audio_count
        
        logger.info(f"段落: {key}")
        logger.info(f"  - 类型: {segment_type}")
        logger.info(f"  - 显示名称: {data.get('display_name', 'N/A')}")
        logger.info(f"  - 路径: {data.get('path', 'N/A')}")
        if is_shortcut:
            logger.info(f"  - 原始快捷方式: {data.get('original_path', 'N/A')}")
        logger.info(f"  - 视频文件数: {video_count}")
        logger.info(f"  - 配音文件数: {audio_count}")
    
    # 显示总结信息
    logger.info(f"\n导入结果统计:")
    logger.info(f"  - 总段落数: {len(material_data)}")
    logger.info(f"  - 普通文件夹段落: {normal_segments}")
    logger.info(f"  - 快捷方式段落: {shortcut_segments}")
    logger.info(f"  - 总视频文件数: {total_videos}")
    logger.info(f"  - 总配音文件数: {total_audios}")

if __name__ == "__main__":
    # 获取测试目录
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    else:
        test_dir = "test_mixed_mode"  # 默认测试目录
    
    # 运行测试
    test_mixed_mode_import(test_dir) 