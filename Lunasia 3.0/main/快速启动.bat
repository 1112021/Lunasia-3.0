@echo off
chcp 65001 >nul
title 露尼西亚AI助手 - 快速启动

:: 快速检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误：未找到Python
    echo 请使用"启动露尼西亚.bat"进行完整检查和安装
    pause
    exit /b 1
)

:: 快速检查项目目录
if not exist "main.py" (
    echo ❌ 错误：未找到main.py文件
    echo 请确保在露尼西亚项目目录中运行此脚本
    pause
    exit /b 1
)

echo 🚀 启动露尼西亚AI助手...
python main.py

if errorlevel 1 (
    echo.
    echo ❌ 启动失败，请检查：
    echo 1. Python环境是否正确
    echo 2. 依赖包是否已安装
    echo 3. 配置文件是否正确
    echo.
    echo 💡 提示：使用"启动露尼西亚.bat"可自动检查并修复问题
    pause
)
