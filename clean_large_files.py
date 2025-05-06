import os
import shutil
import sys

def format_size(size):
    """将字节大小转换为可读格式"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0 or unit == 'GB':
            break
        size /= 1024.0
    return f"{size:.2f} {unit}"

def find_and_clean_large_files(directory='.', size_limit_mb=50, delete=False):
    """
    查找并可选删除大于指定大小的文件
    Args:
        directory: 起始目录
        size_limit_mb: 大小阈值（MB）
        delete: 是否删除文件
    """
    size_limit = size_limit_mb * 1024 * 1024  # 转换为字节
    large_files = []
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                file_size = os.path.getsize(file_path)
                if file_size > size_limit:
                    large_files.append((file_path, file_size))
            except (OSError, FileNotFoundError):
                pass
    
    # 按大小排序
    large_files = sorted(large_files, key=lambda x: x[1], reverse=True)
    
    if large_files:
        print(f"找到 {len(large_files)} 个大于 {size_limit_mb}MB 的文件:")
        for file_path, size in large_files:
            print(f"{file_path} - {format_size(size)}")
            
            if delete:
                try:
                    print(f"正在删除: {file_path}")
                    os.remove(file_path)
                    print(f"删除成功!")
                except Exception as e:
                    print(f"删除失败: {e}")
    else:
        print(f"未找到大于 {size_limit_mb}MB 的文件")

def clean_temp_directory():
    """清空temp目录，但保留目录结构"""
    temp_dir = "temp"
    if not os.path.exists(temp_dir):
        print(f"目录不存在: {temp_dir}")
        return
    
    print(f"正在清理 {temp_dir} 目录...")
    for root, dirs, files in os.walk(temp_dir):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                file_size = os.path.getsize(file_path)
                # 只删除超过10MB的文件
                if file_size > 10 * 1024 * 1024:
                    print(f"正在删除: {file_path} ({format_size(file_size)})")
                    os.remove(file_path)
            except Exception as e:
                print(f"删除失败 {file_path}: {e}")
    
    print("temp目录清理完成")

if __name__ == "__main__":
    action = "scan"  # 默认只扫描，不删除
    
    if len(sys.argv) > 1:
        if sys.argv[1].lower() in ["delete", "clean", "remove"]:
            action = "delete"
        elif sys.argv[1].lower() == "cleantemp":
            action = "cleantemp"
    
    if action == "scan":
        print("=== 仅扫描模式，不会删除文件 ===")
        print("要删除文件，请使用: python clean_large_files.py delete")
        find_and_clean_large_files(size_limit_mb=50, delete=False)
    elif action == "delete":
        print("=== 删除模式，将删除大文件 ===")
        find_and_clean_large_files(size_limit_mb=50, delete=True)
    elif action == "cleantemp":
        print("=== 清理临时目录模式 ===")
        clean_temp_directory() 