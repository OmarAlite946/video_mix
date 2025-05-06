import os
import time
import shutil
import psutil
import sys

"""
注意：这个脚本需要安装psutil库
可以通过运行以下命令安装:
pip install psutil
"""

def wait_for_file_unlock(file_path, max_attempts=5, wait_time=2):
    """
    等待文件解锁，并尝试删除
    Args:
        file_path: 文件路径
        max_attempts: 最大尝试次数
        wait_time: 每次尝试间隔时间（秒）
    """
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return True
    
    for attempt in range(max_attempts):
        try:
            print(f"尝试删除 {file_path} (尝试 {attempt+1}/{max_attempts})")
            os.remove(file_path)
            print(f"成功删除: {file_path}")
            return True
        except PermissionError:
            print(f"文件被锁定，等待 {wait_time} 秒后重试...")
            time.sleep(wait_time)
    
    print(f"无法删除文件: {file_path}")
    return False

def mark_for_deletion_on_reboot(file_path):
    """
    标记文件在系统重启时删除（仅适用于Windows）
    """
    try:
        import winreg
        # 创建Windows注册表键
        with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, 
                              r"System\CurrentControlSet\Control\Session Manager") as key:
            # 获取当前的PendingFileRenameOperations值
            try:
                value, _ = winreg.QueryValueEx(key, "PendingFileRenameOperations")
            except:
                value = b""
            
            # 添加新的删除操作
            new_value = value + b"\0\0" + file_path.encode('utf-16le') + b"\0\0\0"
            
            # 写入值
            winreg.SetValueEx(key, "PendingFileRenameOperations", 0, winreg.REG_MULTI_SZ, new_value)
            
            print(f"文件将在系统重启后删除: {file_path}")
            return True
    except Exception as e:
        print(f"无法标记文件重启时删除: {e}")
        return False

def rename_file_to_delete_later(file_path):
    """
    重命名文件，以便稍后删除
    """
    try:
        dir_name = os.path.dirname(file_path)
        temp_name = os.path.join(dir_name, "to_delete_" + str(int(time.time())))
        
        os.rename(file_path, temp_name)
        print(f"已将文件重命名为: {temp_name}")
        print(f"请稍后手动删除此文件")
        return True
    except Exception as e:
        print(f"无法重命名文件: {e}")
        return False

def create_delete_bat(file_path):
    """
    创建一个批处理文件来删除被锁定的文件
    """
    bat_path = os.path.join(os.path.dirname(file_path), "delete_locked_file.bat")
    
    with open(bat_path, 'w') as bat_file:
        bat_file.write("@echo off\n")
        bat_file.write("echo 正在尝试删除锁定的文件...\n")
        bat_file.write(f'del /F /Q "{file_path}"\n')
        bat_file.write("if exist \"%~1\" (\n")
        bat_file.write("    echo 删除失败，文件仍然被锁定\n")
        bat_file.write(") else (\n")
        bat_file.write("    echo 文件已成功删除\n")
        bat_file.write(")\n")
        bat_file.write("pause\n")
    
    print(f"已创建删除批处理文件: {bat_path}")
    print("请关闭所有相关程序后手动运行此批处理文件")
    return True

def main():
    if len(sys.argv) < 2:
        print("用法: python handle_locked_files.py <文件路径>")
        print("示例: python handle_locked_files.py temp/large_file.exe")
        return
    
    file_path = sys.argv[1]
    
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return
    
    print(f"尝试处理被锁定的文件: {file_path}")
    
    # 尝试直接删除
    if wait_for_file_unlock(file_path):
        return
    
    # 创建一个批处理文件
    create_delete_bat(file_path)
    
    # 尝试重命名文件
    rename_file_to_delete_later(file_path)

if __name__ == "__main__":
    main() 