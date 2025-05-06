#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GPU检测绕过工具
强制启用NVIDIA GPU
"""

import os
import sys
import json
from pathlib import Path

# 检查是否是Windows系统
if sys.platform != "win32":
    print("此脚本仅适用于Windows系统")
    sys.exit(1)

# 配置文件路径
config_dir = Path.home() / "VideoMixTool"
config_file = config_dir / "gpu_config.json"

# 创建配置目录
config_dir.mkdir(exist_ok=True, parents=True)

# 强制NVIDIA GPU配置
force_config = {
    "use_hardware_acceleration": True,
    "encoder": "h264_nvenc",
    "decoder": "h264_cuvid",
    "encoding_preset": "p2",
    "extra_params": {
        "spatial-aq": "1",
        "temporal-aq": "1",
        "rc": "vbr",
        "cq": "19"
    },
    "detected_gpu": "NVIDIA GPU",
    "detected_vendor": "NVIDIA",
    "compatibility_mode": True,
    "driver_version": "Unknown"
}

# 保存配置
with open(config_file, 'w', encoding='utf-8') as f:
    json.dump(force_config, f, ensure_ascii=False, indent=2)

print(f"已强制启用NVIDIA GPU加速配置")
print(f"配置文件: {config_file}")
print("请重启应用程序以应用更改")

# 等待用户确认
input("按回车键继续...")
