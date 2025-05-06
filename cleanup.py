import os
import shutil
from pathlib import Path

# 获取当前工作目录
current_dir = Path.cwd()

# 创建目标文件夹
target_dir = Path("D:/软件安装包")
target_dir.mkdir(exist_ok=True)

# 要移动的大文件列表
large_files = [
    "Anaconda3-2024.10-1-Windows-x86_64.exe",
    "ShadowBot-5.24.25-x64.exe",
    "regular-investing-in-box-master.zip",
    "铲哥批量剪辑神器.zip",
    "铲哥批量剪辑神器 (1).zip",
    "剪映小助手(客户端) Latest_version.zip",
    "ffmpeg-7.1.1-essentials_build.zip",
    "Spark-TTS-main.zip"
]

# 要删除的临时文件模式
temp_patterns = [
    "temp_raw_*.mp4",
    "TEMP_*.mp4",
    "test_output*.mp4",
    "合成视频_4TEMP_MPY_wvf_snd.mp4"
]

def move_large_files():
    """移动大文件到目标目录"""
    moved_count = 0
    total_size = 0
    
    for filename in large_files:
        src = current_dir / filename
        if src.exists():
            dst = target_dir / filename
            try:
                shutil.move(str(src), str(dst))
                size_mb = src.stat().st_size / (1024 * 1024)
                total_size += size_mb
                moved_count += 1
                print(f"已移动: {filename} ({size_mb:.1f}MB)")
            except Exception as e:
                print(f"移动 {filename} 失败: {e}")
    
    print(f"\n共移动了 {moved_count} 个文件，总大小: {total_size:.1f}MB")

def delete_temp_files():
    """删除临时文件"""
    deleted_count = 0
    total_size = 0
    
    import glob
    for pattern in temp_patterns:
        for file_path in glob.glob(str(current_dir / pattern)):
            try:
                path = Path(file_path)
                size_mb = path.stat().st_size / (1024 * 1024)
                path.unlink()
                total_size += size_mb
                deleted_count += 1
                print(f"已删除: {file_path} ({size_mb:.1f}MB)")
            except Exception as e:
                print(f"删除 {file_path} 失败: {e}")
    
    print(f"\n共删除了 {deleted_count} 个临时文件，总大小: {total_size:.1f}MB")

def cleanup_optional_dirs():
    """清理可选目录"""
    optional_dirs = [
        "CUDA",
        "python_embed",
        "wheels",
        "缓存",
        "work"
    ]
    
    for dirname in optional_dirs:
        dir_path = current_dir / dirname
        if dir_path.exists():
            try:
                size = sum(f.stat().st_size for f in dir_path.glob('**/*') if f.is_file())
                size_mb = size / (1024 * 1024)
                print(f"\n发现目录 {dirname} ({size_mb:.1f}MB)")
                shutil.rmtree(dir_path)
                print(f"已删除目录: {dirname}")
            except Exception as e:
                print(f"处理目录 {dirname} 时出错: {e}")

def cleanup_temp_dir():
    """清理temp目录"""
    temp_dir = Path("temp")
    if not temp_dir.exists():
        print("temp目录不存在")
        return
    
    total_size = 0
    deleted_count = 0
    
    # 删除所有文件和子目录
    for item in temp_dir.glob("*"):
        try:
            if item.is_file():
                size_mb = item.stat().st_size / (1024 * 1024)
                total_size += size_mb
                item.unlink()
                deleted_count += 1
                print(f"已删除: {item.name} ({size_mb:.1f}MB)")
            elif item.is_dir():
                size = sum(f.stat().st_size for f in item.glob('**/*') if f.is_file())
                size_mb = size / (1024 * 1024)
                total_size += size_mb
                shutil.rmtree(item)
                deleted_count += 1
                print(f"已删除目录: {item.name} ({size_mb:.1f}MB)")
        except Exception as e:
            print(f"删除 {item.name} 失败: {e}")
    
    print(f"\n共删除了 {deleted_count} 个文件和目录，总大小: {total_size:.1f}MB")

def cleanup_git():
    """清理.git目录"""
    git_dir = Path(".git")
    if not git_dir.exists():
        print("git目录不存在")
        return
    
    # 保留.git目录，但清理其中的大文件
    for item in git_dir.glob("**/*"):
        if item.is_file() and item.stat().st_size > 10 * 1024 * 1024:  # 大于10MB的文件
            try:
                size_mb = item.stat().st_size / (1024 * 1024)
                item.unlink()
                print(f"已删除大文件: {item.relative_to(git_dir)} ({size_mb:.1f}MB)")
            except Exception as e:
                print(f"删除 {item} 失败: {e}")

def cleanup_ffmpeg():
    """清理ffmpeg_compat目录"""
    ffmpeg_dir = Path("ffmpeg_compat")
    if not ffmpeg_dir.exists():
        print("ffmpeg_compat目录不存在")
        return
    
    # 移动ffmpeg_compat目录到D盘
    target_dir = Path("D:/ffmpeg_compat")
    try:
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.move(str(ffmpeg_dir), str(target_dir))
        print(f"已将ffmpeg_compat目录移动到 {target_dir}")
    except Exception as e:
        print(f"移动ffmpeg_compat目录失败: {e}")

def cleanup_temp():
    """清理temp目录"""
    temp_dir = Path("temp")
    if not temp_dir.exists():
        print("temp目录不存在")
        return
    
    total_size = 0
    deleted_count = 0
    
    for item in temp_dir.glob("*"):
        try:
            if item.is_file():
                size_mb = item.stat().st_size / (1024 * 1024)
                total_size += size_mb
                item.unlink()
                deleted_count += 1
                print(f"已删除: {item.name} ({size_mb:.1f}MB)")
            elif item.is_dir():
                size = sum(f.stat().st_size for f in item.glob('**/*') if f.is_file())
                size_mb = size / (1024 * 1024)
                total_size += size_mb
                shutil.rmtree(item)
                deleted_count += 1
                print(f"已删除目录: {item.name} ({size_mb:.1f}MB)")
        except Exception as e:
            print(f"删除 {item.name} 失败: {e}")
    
    print(f"\n共删除了 {deleted_count} 个文件和目录，总大小: {total_size:.1f}MB")

if __name__ == "__main__":
    print("开始清理...")
    print("\n1. 移动大文件...")
    move_large_files()
    
    print("\n2. 删除临时文件...")
    delete_temp_files()
    
    print("\n3. 处理可选目录...")
    cleanup_optional_dirs()
    
    print("\n4. 清理temp目录...")
    cleanup_temp_dir()
    
    print("\n5. 清理.git目录...")
    cleanup_git()
    
    print("\n6. 移动ffmpeg_compat目录...")
    cleanup_ffmpeg()
    
    print("\n7. 清理temp目录...")
    cleanup_temp()
    
    print("\n清理完成！") 