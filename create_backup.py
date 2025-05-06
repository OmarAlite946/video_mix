import os
import shutil
import zipfile
import datetime
import sys

def create_backup(output_dir=None, include_temp=False):
    """
    创建项目的备份
    Args:
        output_dir: 输出目录，默认为当前目录
        include_temp: 是否包含临时文件夹
    """
    current_dir = os.getcwd()
    if not output_dir:
        output_dir = current_dir
    
    # 创建时间戳文件名
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f'source_backup_{timestamp}.zip'
    backup_path = os.path.join(output_dir, backup_filename)
    
    # 要排除的文件和目录
    exclude_dirs = ['.git']
    if not include_temp:
        exclude_dirs.append('temp')
    
    print(f"开始创建备份到: {backup_path}")
    
    # 创建ZIP文件
    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(current_dir):
            # 跳过排除的目录
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                # 跳过备份文件本身
                if file == backup_filename:
                    continue
                    
                file_path = os.path.join(root, file)
                # 获取相对路径，用于ZIP文件内的路径
                rel_path = os.path.relpath(file_path, current_dir)
                
                try:
                    print(f"添加文件: {rel_path}")
                    zipf.write(file_path, rel_path)
                except Exception as e:
                    print(f"无法添加 {rel_path}: {e}")
    
    print(f"\n备份完成! 文件已保存到: {backup_path}")
    print(f"备份文件大小: {format_size(os.path.getsize(backup_path))}")

def format_size(size):
    # 转换字节为可读格式 (KB, MB, GB)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0 or unit == 'GB':
            break
        size /= 1024.0
    return f"{size:.2f} {unit}"

if __name__ == "__main__":
    # 命令行参数处理
    output_dir = None
    include_temp = False
    
    if len(sys.argv) > 1:
        output_dir = sys.argv[1]
    
    if len(sys.argv) > 2 and sys.argv[2].lower() == 'true':
        include_temp = True
    
    create_backup(output_dir, include_temp) 