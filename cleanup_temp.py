import os
import shutil

def cleanup_temp_files():
    """清理temp目录下的大文件"""
    files_to_remove = [
        os.path.join("temp", "vscode-stable-undefined-x64-v7f2lp8l59", "CodeSetup-stable-0.49.6.exe"),
        os.path.join("temp", "vscode-stable-undefined-x64-z1xkc7axr3s", "CodeSetup-stable-0.49.6.exe")
    ]
    
    for file_path in files_to_remove:
        if os.path.exists(file_path):
            try:
                print(f"正在删除: {file_path}")
                os.remove(file_path)
                print(f"删除成功: {file_path}")
            except Exception as e:
                print(f"删除失败: {file_path}, 错误: {e}")
        else:
            print(f"文件不存在: {file_path}")
    
    print("\n清理完成!")

if __name__ == "__main__":
    cleanup_temp_files() 