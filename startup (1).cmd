@echo off
setlocal

:: 1. 获取当前日期 (格式: YYYY-MM-DD)，使用 wmic 保证不同系统语言下格式一致
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set LOG_DATE=%datetime:~0,4%-%datetime:~4,2%-%datetime:~6,2%
set LOG_FILE=xunji-backup\logs\backend_%LOG_DATE%.log

:: 2. 检查并创建 logs 目录
if not exist "xunji-backup\logs" (
    mkdir "xunji-backup\logs"
)

:: 预先创建一个空的日志文件，防止后面的 Get-Content 命令因为找不到文件而报错退出
type nul > "%LOG_FILE%"

:: 3. 启动后端
echo Starting Backend...
:: 启动一个独立的 PowerShell 窗口来运行后端服务
:: 日志会同时显示在窗口中并附加到日志文件
start "Backend Server" powershell -Command "& { cd xunji-backup; uvicorn app.main:app --host 0.0.0.0 --port 21801 | Tee-Object -FilePath logs\backend_%LOG_DATE%.log -Append }"

:: 4. 启动前端
echo Starting Frontend...
:: 启动一个独立窗口来运行前端开发服务器
start "Frontend Server" cmd /c "cd xunji-frontend && npm run dev -- --port 21800"

endlocal