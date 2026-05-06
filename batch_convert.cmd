@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion

REM 批量NSZ转NSP转换脚本
REM 自动将input文件夹中的所有NSZ文件转换为NSP文件并保存到output文件夹

echo ============================================================
echo                NSZ批量转换工具 v1.0
echo ============================================================
echo.

REM 获取脚本所在目录
set SCRIPT_DIR=%~dp0
set INPUT_DIR=%SCRIPT_DIR%input
set OUTPUT_DIR=%SCRIPT_DIR%output

echo 输入目录: %INPUT_DIR%
echo 输出目录: %OUTPUT_DIR%
echo.

REM 检查input目录是否存在
if not exist "%INPUT_DIR%" (
    echo 错误：input目录不存在！
    pause
    exit /b 1
)

REM 创建output目录（如果不存在）
if not exist "%OUTPUT_DIR%" (
    mkdir "%OUTPUT_DIR%"
)

REM 检查是否有nsz文件
set NSZ_COUNT=0
for /r "%INPUT_DIR%" %%f in (*.nsz) do (
    set /a NSZ_COUNT+=1
)

if %NSZ_COUNT%==0 (
    echo 在input目录中没有找到任何.nsz文件
    pause
    exit /b 0
)

echo 找到 %NSZ_COUNT% 个NSZ文件
echo.

REM 显示找到的文件
echo 准备转换的文件：
set FILE_INDEX=0
for /r "%INPUT_DIR%" %%f in (*.nsz) do (
    set /a FILE_INDEX+=1
    set RELATIVE_PATH=%%f
    set RELATIVE_PATH=!RELATIVE_PATH:%INPUT_DIR%\=!
    echo   !FILE_INDEX!. !RELATIVE_PATH!
)
echo.

REM 询问用户是否继续
set /p CONFIRM=是否开始转换? (y/n): 
if /i "%CONFIRM%" neq "y" if /i "%CONFIRM%" neq "yes" if "%CONFIRM%" neq "是" (
    echo 已取消转换
    pause
    exit /b 0
)

echo.
echo 开始批量转换...
echo ============================================================

set SUCCESS_COUNT=0
set FAILED_COUNT=0
set SUSPICIOUS_COUNT=0
set CURRENT_INDEX=0

set "LOG_DIR=%OUTPUT_DIR%\_logs"
if not exist "!LOG_DIR!" mkdir "!LOG_DIR!"

for /r "%INPUT_DIR%" %%f in (*.nsz) do (
    set /a CURRENT_INDEX+=1
    set RELATIVE_PATH=%%f
    set RELATIVE_PATH=!RELATIVE_PATH:%INPUT_DIR%\=!

    echo.
    echo [!CURRENT_INDEX!/%NSZ_COUNT%] 正在转换: !RELATIVE_PATH!

    REM 获取文件夹路径（保持目录结构）
    for %%d in ("!RELATIVE_PATH!") do set "RELATIVE_DIR=%%~dpd"
    set "RELATIVE_DIR=!RELATIVE_DIR:~0,-1!"
    set "TARGET_OUTPUT_DIR=%OUTPUT_DIR%\!RELATIVE_DIR!"

    REM 创建目标目录（如果不存在）
    if not exist "!TARGET_OUTPUT_DIR!" mkdir "!TARGET_OUTPUT_DIR!"
    echo   输出到: !TARGET_OUTPUT_DIR!

    REM 单文件日志：用于事后定位 hash mismatch / 缺 key 这类硬伤
    set "LOG_NAME=!RELATIVE_PATH!"
    set "LOG_NAME=!LOG_NAME:\=_!"
    set "LOG_NAME=!LOG_NAME:/=_!"
    set "LOG_NAME=!LOG_NAME: =_!"
    set "LOG_FILE=!LOG_DIR!\!LOG_NAME!.log"

    REM 默认带 --fix-padding 与 --quick-verify：前者改齐 PFS0 padding 让 Ryujinx 能稳定挂载，
    REM 后者校验 NCA hash 把坏包暴露在日志里
    if exist "%SCRIPT_DIR%venv\Scripts\python.exe" (
        "%SCRIPT_DIR%venv\Scripts\python.exe" "%SCRIPT_DIR%nsz.py" -D --fix-padding --quick-verify -o "!TARGET_OUTPUT_DIR!" "%%f" >"!LOG_FILE!" 2>&1
    ) else (
        python "%SCRIPT_DIR%nsz.py" -D --fix-padding --quick-verify -o "!TARGET_OUTPUT_DIR!" "%%f" >"!LOG_FILE!" 2>&1
    )

    if !errorlevel! equ 0 (
        findstr /R /C:"\[CORRUPTED\]" /C:"\[MISMATCH\]" /C:"\[MISSMATCH\]" /C:"missing from" /C:"crc32 missmatch" /C:"Failed to load default keys" "!LOG_FILE!" >nul
        if !errorlevel! equ 0 (
            echo   ⚠ 转换看似成功但日志有可疑信号，不要直接拷进 Ryujinx
            echo     完整日志: !LOG_FILE!
            set /a SUSPICIOUS_COUNT+=1
        ) else (
            echo   ✓ 转换成功
            set /a SUCCESS_COUNT+=1
        )
    ) else (
        echo   ✗ 转换失败，nsz.py 日志:
        type "!LOG_FILE!"
        echo     完整日志: !LOG_FILE!
        set /a FAILED_COUNT+=1
    )
)

REM 显示转换结果
echo.
echo ============================================================
echo 转换完成！
echo 成功转换: %SUCCESS_COUNT% 个文件
echo 转换失败: %FAILED_COUNT% 个文件
echo 可疑产物: %SUSPICIOUS_COUNT% 个 (退出码0但日志有 corrupted/missing key 等告警)
echo.
echo 转换后的NSP文件已保存到: %OUTPUT_DIR%
echo 单文件日志位于: %LOG_DIR%
echo ============================================================

pause
