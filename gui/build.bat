@echo off
chcp 65001 >nul
rem =====================================================================
rem  GitHub Desktop 汉化工具 — 单文件 EXE 打包脚本
rem  依赖：官方 Python 3.8+（需 pip install pyside6，即 Qt6）
rem  产物：dist\github-desktop-zh-1.0.0.exe  （双击即用，不依赖任何运行环境）
rem  目标平台：Windows 10 / 11（官方 GitHub Desktop 已不支持 Windows 7）
rem =====================================================================
setlocal

rem 1) 选择 Python 解释器（优先 py 启动器，否则用 python）
where py >nul 2>nul && set "PY=py -3" || set "PY=python"

echo [1/4] 准备构建虚拟环境（隔离依赖，不污染系统）...
if not exist build_env (
    %PY% -m venv build_env
)
call build_env\Scripts\activate.bat

echo [2/4] 安装 PyInstaller 与 PySide6（Qt6，不升级以保持版本锁定）...
python -m pip install --upgrade pip >nul
python -m pip install pyinstaller pyside6

echo [3/4] 编译为单文件 EXE（GUI 版，隐藏控制台；体积优化见仓库根 github-desktop-zh-1.0.0.spec）...
python -m PyInstaller --clean --noconfirm --distpath "dist" --workpath "build" "..\github-desktop-zh-1.0.0.spec"

rem 如需同时打包命令行版 EXE，取消下行注释：
rem python -m PyInstaller --onefile --name github-desktop-zh-1.0.0-cli --add-data "..\dictionaries;dictionaries" cli.py

echo [4/4] 完成。产物位于：dist\github-desktop-zh-1.0.0.exe
if exist "dist\github-desktop-zh-1.0.0.exe" (
    echo 文件大小：
    for %%F in ("dist\github-desktop-zh-1.0.0.exe") do echo   %%~zF 字节
)
echo.
echo 提示：
echo   - 若写入 GitHub Desktop 安装目录（如 Program Files）时报权限错误，
echo     请以管理员身份运行本 EXE。默认安装路径 %LOCALAPPDATA%\GitHubDesktop 无需管理员。
echo   - 构建临时文件在 build_env/ build/ *.spec，可安全删除。
endlocal
pause
