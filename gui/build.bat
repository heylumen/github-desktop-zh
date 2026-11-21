@echo off
chcp 65001 >nul
rem =====================================================================
rem  GitHub Desktop 汉化工具 — 单文件 EXE 打包脚本（可复现构建）
rem  依赖：Python 3.10–3.13（PySide6 6.11 支持范围）
rem  产物：dist\github-desktop-zh-1.0.3.exe
rem =====================================================================
setlocal

set "HERE=%~dp0"
set "REPO=%HERE%.."

rem 1) 选择 Python 解释器（优先 py 启动器，否则用 python）
where py >nul 2>nul && set "PY=py -3" || set "PY=python"

echo [1/5] 准备构建虚拟环境...
if not exist build_env (
    %PY% -m venv build_env
    if errorlevel 1 goto :fail
)
call build_env\Scripts\activate.bat
if errorlevel 1 goto :fail

python -c "import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] < (3,15) else 1)"
if errorlevel 1 (
    echo [错误] 当前 Python 版本不受支持：需要 Python 3.10 到 3.13（PySide6 6.11 支持范围）
    goto :fail
)

echo [2/5] 安装锁定版本的 PyInstaller 与 PySide6...
python -m pip install --disable-pip-version-check --upgrade pip >nul
python -m pip install --disable-pip-version-check -r requirements-build.txt -c constraints-build.txt
if errorlevel 1 goto :fail
python -m pip check
if errorlevel 1 goto :fail

echo [3/5] 校验字典清单与（可选）JavaScript 语法...
pushd "%REPO%"
python scripts\check_dictionaries.py
set "DICT_RC=%ERRORLEVEL%"
popd
if not "%DICT_RC%"=="0" goto :fail
python "%REPO%\scripts\check_privacy.py"
if errorlevel 1 goto :fail
python "%REPO%\scripts\check_self_methods.py"
if errorlevel 1 goto :fail
python "%REPO%\scripts\check_consistency.py" --skip-build-info
if errorlevel 1 goto :fail
python "%REPO%\scripts\check_contrast.py"
if errorlevel 1 goto :fail
python "%REPO%\scripts\check_visual.py"
if errorlevel 1 goto :fail
echo [4/5] 编译为单文件 EXE...
where upx >nul 2>nul
if errorlevel 1 (
    echo   注意：未找到 UPX，spec 的 upx=True 将不产生压缩。
) else (
    echo   已找到 UPX，将按 spec 压缩二进制。
)
python -m PyInstaller --clean --noconfirm --distpath "dist" --workpath "build" "%REPO%\github-desktop-zh-1.0.3.spec"
if errorlevel 1 goto :fail

echo [5/5] 校验归档并生成发布散列...
python "%REPO%\scripts\verify_archive.py" "dist\github-desktop-zh-1.0.3.exe" --version 1.0.3
if errorlevel 1 goto :fail
python "%REPO%\scripts\smoke_exe.py" "dist\github-desktop-zh-1.0.3.exe"
if errorlevel 1 goto :fail
python "%REPO%\scripts\build_release.py" --exe "dist\github-desktop-zh-1.0.3.exe"
if errorlevel 1 goto :fail
python "%REPO%\scripts\check_consistency.py"
if errorlevel 1 goto :fail

echo.
echo 构建完成：%HERE%dist\github-desktop-zh-1.0.3.exe
endlocal
pause
exit /b 0

:fail
echo.
echo [失败] 构建未完成，请检查上方错误信息后重试。
endlocal
pause
exit /b 1
