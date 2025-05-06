@echo off
echo ===== GPU检测修复工具 =====
echo 此工具将自动修复GPU检测问题
echo.

set PYTHON_EXE=""

REM 检查Python是否安装
python --version > nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_EXE=python
    goto :run_script
)

REM 检查python3命令
python3 --version > nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_EXE=python3
    goto :run_script
)

REM 尝试查找Python安装路径
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set PYTHON_EXE="%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    goto :run_script
)

if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set PYTHON_EXE="%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    goto :run_script
)

if exist "%LOCALAPPDATA%\Programs\Python\Python39\python.exe" (
    set PYTHON_EXE="%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
    goto :run_script
)

if exist "C:\Python311\python.exe" (
    set PYTHON_EXE="C:\Python311\python.exe"
    goto :run_script
)

if exist "C:\Python310\python.exe" (
    set PYTHON_EXE="C:\Python310\python.exe"
    goto :run_script
)

if exist "C:\Python39\python.exe" (
    set PYTHON_EXE="C:\Python39\python.exe"
    goto :run_script
)

if exist "python_embed\python.exe" (
    set PYTHON_EXE="python_embed\python.exe"
    goto :run_script
)

echo 错误: 未找到Python安装
echo 请安装Python 3.9或更高版本
pause
exit /b 1

:run_script
echo 正在运行修复工具...
%PYTHON_EXE% "一键修复GPU检测.py"

echo.
echo 修复完成，请重启应用程序
pause 