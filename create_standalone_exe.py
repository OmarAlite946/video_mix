import os
import sys
import subprocess
import shutil
import time

def run_command(command):
    """运行命令并返回输出"""
    try:
        result = subprocess.run(command, shell=True, check=True, 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"命令执行失败: {e}")
        print(f"错误输出: {e.stderr}")
        return None

def ensure_pyinstaller():
    """确保PyInstaller已安装"""
    try:
        import PyInstaller
        print("PyInstaller已安装")
    except ImportError:
        print("正在安装PyInstaller...")
        run_command("pip install pyinstaller")
        print("PyInstaller安装完成")

def create_standalone_exe(main_script="main.py", output_name=None, add_data=None, icon=None):
    """
    创建独立的可执行文件，包含所有依赖
    Args:
        main_script: 主Python脚本文件
        output_name: 输出的可执行文件名 (不包含.exe)
        add_data: 要包含的额外数据文件列表 [(源路径, 目标路径), ...]
        icon: 图标文件路径
    """
    # 检查主脚本是否存在
    if not os.path.exists(main_script):
        print(f"错误: 找不到主脚本 {main_script}")
        return False
    
    # 确保PyInstaller已安装
    ensure_pyinstaller()
    
    # 设置默认输出名称
    if not output_name:
        output_name = os.path.splitext(main_script)[0]
    
    # 构建PyInstaller命令
    cmd = f"pyinstaller --onefile --clean"
    
    # 添加图标
    if icon and os.path.exists(icon):
        cmd += f" --icon={icon}"
    
    # 添加数据文件
    if add_data:
        for src, dest in add_data:
            if os.path.exists(src):
                cmd += f" --add-data=\"{src};{dest}\""
    
    # 添加名称和脚本
    cmd += f" --name={output_name} {main_script}"
    
    print("开始构建可执行文件...")
    print(f"命令: {cmd}")
    
    # 运行PyInstaller
    start_time = time.time()
    output = run_command(cmd)
    if output is None:
        return False
    
    end_time = time.time()
    build_time = end_time - start_time
    
    print(f"\n构建完成! 用时: {build_time:.2f} 秒")
    exe_path = os.path.join("dist", f"{output_name}.exe")
    if os.path.exists(exe_path):
        print(f"可执行文件已生成: {exe_path}")
        print(f"文件大小: {os.path.getsize(exe_path) / (1024*1024):.2f} MB")
        return True
    else:
        print("错误: 无法找到生成的可执行文件")
        return False

def find_data_files(data_dirs=None):
    """查找需要包含的数据文件"""
    data_files = []
    
    # 默认的数据目录
    if data_dirs is None:
        data_dirs = [
            ('ui', 'ui'),
            ('docs', 'docs'),
            ('src', 'src')
        ]
    
    for src_dir, dest_dir in data_dirs:
        if os.path.exists(src_dir) and os.path.isdir(src_dir):
            data_files.append((src_dir, dest_dir))
    
    return data_files

if __name__ == "__main__":
    # 默认设置
    main_script = "main.py"
    output_name = "视频混剪工具"
    icon_file = None
    
    # 查找图标文件
    for icon_path in ["icon.ico", "ui/icon.ico", "src/icon.ico"]:
        if os.path.exists(icon_path):
            icon_file = icon_path
            break
    
    # 查找数据文件
    data_files = find_data_files()
    
    # 命令行参数处理
    if len(sys.argv) > 1:
        main_script = sys.argv[1]
    
    if len(sys.argv) > 2:
        output_name = sys.argv[2]
    
    # 打印配置信息
    print("=== 构建独立可执行文件 ===")
    print(f"主脚本: {main_script}")
    print(f"输出名称: {output_name}")
    print(f"图标文件: {icon_file}")
    print("包含的数据目录:")
    for src, dest in data_files:
        print(f"  - {src} -> {dest}")
    
    # 创建可执行文件
    create_standalone_exe(main_script, output_name, data_files, icon_file) 