@echo off
echo ===== NVIDIA GPU驱动补丁工具 =====
echo 此工具将尝试修复NVIDIA GPU检测问题
echo.

REM 检查管理员权限
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo 错误: 需要管理员权限来运行此脚本!
    echo 请右键点击此脚本，选择"以管理员身份运行"
    pause
    exit /b 1
)

echo 正在检查NVIDIA驱动...
nvidia-smi >nul 2>&1
if %errorLevel% neq 0 (
    echo 未检测到NVIDIA驱动，请确保已正确安装驱动
    pause
    exit /b 1
)

echo NVIDIA驱动已检测到，正在重启服务...
echo.

echo 1. 停止NVIDIA显示驱动服务...
net stop "NVIDIA Display Driver Service" /y
timeout /t 2 /nobreak >nul

echo 2. 重启NVIDIA显示驱动服务...
net start "NVIDIA Display Driver Service"
timeout /t 2 /nobreak >nul

echo 3. 清理系统缓存...
ipconfig /flushdns >nul 2>&1
timeout /t 1 /nobreak >nul

echo.
echo NVIDIA服务已重新启动!
echo 请重新启动您的应用程序测试GPU检测

pause
