@echo off
echo ===== NVIDIA GPU������������ =====
echo �˹��߽������޸�NVIDIA GPU�������
echo.

REM ������ԱȨ��
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ����: ��Ҫ����ԱȨ�������д˽ű�!
    echo ���Ҽ�����˽ű���ѡ��"�Թ���Ա�������"
    pause
    exit /b 1
)

echo ���ڼ��NVIDIA����...
nvidia-smi >nul 2>&1
if %errorLevel% neq 0 (
    echo δ��⵽NVIDIA��������ȷ������ȷ��װ����
    pause
    exit /b 1
)

echo NVIDIA�����Ѽ�⵽��������������...
echo.

echo 1. ֹͣNVIDIA��ʾ��������...
net stop "NVIDIA Display Driver Service" /y
timeout /t 2 /nobreak >nul

echo 2. ����NVIDIA��ʾ��������...
net start "NVIDIA Display Driver Service"
timeout /t 2 /nobreak >nul

echo 3. ����ϵͳ����...
ipconfig /flushdns >nul 2>&1
timeout /t 1 /nobreak >nul

echo.
echo NVIDIA��������������!
echo ��������������Ӧ�ó������GPU���

pause
