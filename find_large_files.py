import os
import sys
from pathlib import Path

def get_size(path):
    total = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                if entry.is_file():
                    total += entry.stat().st_size
                elif entry.is_dir():
                    total += get_size(entry.path)
    except (PermissionError, FileNotFoundError):
        pass
    return total

def format_size(size):
    # 转换字节为可读格式 (KB, MB, GB)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0 or unit == 'GB':
            break
        size /= 1024.0
    return f"{size:.2f} {unit}"

def find_large_files(directory, size_limit_mb=10):
    """查找超过指定大小的文件"""
    size_limit = size_limit_mb * 1024 * 1024  # 转换为字节
    large_files = []
    
    for root, dirs, files in os.walk(directory):
        # 跳过.git目录内容
        if '.git' in dirs:
            dirs.remove('.git')
            
        for file in files:
            file_path = os.path.join(root, file)
            try:
                file_size = os.path.getsize(file_path)
                if file_size > size_limit:
                    large_files.append((file_path, file_size))
            except (OSError, FileNotFoundError):
                pass
    
    # 按大小排序
    return sorted(large_files, key=lambda x: x[1], reverse=True)

def analyze_directory_sizes(directory):
    """分析目录大小"""
    results = []
    
    try:
        with os.scandir(directory) as it:
            for entry in it:
                if entry.is_dir():
                    # 跳过.git目录
                    if '.git' in entry.name:
                        continue
                    
                    dir_size = get_size(entry.path)
                    results.append((entry.name, dir_size))
    except (PermissionError, FileNotFoundError):
        pass
    
    # 按大小排序
    return sorted(results, key=lambda x: x[1], reverse=True)

if __name__ == "__main__":
    # 获取当前工作目录
    current_dir = os.getcwd()
    
    print("=== 超过10MB的大文件 ===")
    large_files = find_large_files(current_dir)
    for file_path, size in large_files:
        print(f"{file_path} - {format_size(size)}")
    
    print("\n=== 目录大小分析 ===")
    dir_sizes = analyze_directory_sizes(current_dir)
    for dir_name, size in dir_sizes:
        print(f"{dir_name} - {format_size(size)}") 