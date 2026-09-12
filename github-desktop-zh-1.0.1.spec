# -*- mode: python ; coding: utf-8 -*-
# GitHub Desktop 汉化工具 —— 体积优化版构建 spec (v2)
# ================================================================
# 关键优化：
#   1) excludes 排除所有未使用的 PySide6.Qt* 子模块
#   2) 收尾过滤 a.binaries / a.datas：剔除未用 Qt DLL、多余插件、全部翻译
#   3) 字典仅内置最新 5 版（3.6.1–3.6.5），其余用户可放 EXE 同级 dictionaries/
#   4) optimize=2 移除 assert + docstring，减小 .pyc 体积
#   5) upx_exclude 中保护 Python DLL 不被 UPX 压缩（防杀软误报）
#
# 修复记录（v2）：
#   - 修复 spec_debug.txt 写入在 build/ 目录不存在时导致构建崩溃的 bug
#   - 移除已弃用的 block_cipher 变量
#   - 排除全部 Qt 翻译文件（app.py 未使用 QTranslator）
#   - upx_exclude 添加 python313.dll / python3.dll 防止杀软误报
import os
import re

# 本 spec 位于仓库根目录，SPECPATH 即仓库根
REPO = SPECPATH
APP = os.path.join(REPO, 'gui', 'app.py')
ICON = os.path.join(REPO, 'gui', 'assets', 'icon.ico')
DICT_DIR = os.path.join(REPO, 'dictionaries')


def _ver_key(v):
    return [int(x) for x in re.findall(r'\d+', v)]


# ---- 字典：仅内置最新 5 版 ----
_dict_versions = []
if os.path.isdir(DICT_DIR):
    for name in os.listdir(DICT_DIR):
        d = os.path.join(DICT_DIR, name)
        if (os.path.isdir(d)
                and os.path.isfile(os.path.join(d, 'main.js'))
                and os.path.isfile(os.path.join(d, 'renderer.js'))):
            _dict_versions.append(name)
_dict_versions.sort(key=_ver_key, reverse=True)
DICT_LATEST = _dict_versions[:5]

_dict_datas = [(os.path.join(DICT_DIR, v), os.path.join('dictionaries', v)) for v in DICT_LATEST]
# 运行时窗口图标：onefile 下 app.py 从 sys._MEIPASS/assets/icon.ico 加载
# 注意 dest 必须是目录 'assets'，PyInstaller 会自动追加源文件名 → assets/icon.ico
_dict_datas.append((ICON, 'assets'))

# [DEBUG] 记录 spec 实际解析到的路径（安全写入：目录不存在时自动创建）
_debug_dir = os.path.join(REPO, 'gui', 'build')
os.makedirs(_debug_dir, exist_ok=True)
with open(os.path.join(_debug_dir, 'spec_debug.txt'), 'w', encoding='utf-8') as _f:
    _f.write(f"SPECPATH={SPECPATH}\nREPO={REPO}\nDICT_DIR={DICT_DIR}\nDICT_LATEST={DICT_LATEST}\n")

a = Analysis(
    [APP],
    pathex=[REPO],
    binaries=[],
    datas=_dict_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PySide6.QtQuick', 'PySide6.QtQml', 'PySide6.QtQmlModels', 'PySide6.QtQmlMeta', 'PySide6.QtQmlWorkerScript',
        'PySide6.QtPdf', 'PySide6.QtPdfWidgets',
        'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets',
        'PySide6.QtVirtualKeyboard',
        'PySide6.QtNetwork', 'PySide6.QtNetworkAuth',
        'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
        'PySide6.QtCharts', 'PySide6.QtGraphs', 'PySide6.QtDataVisualization',
        'PySide6.QtQuick3D', 'PySide6.QtQuickControls2', 'PySide6.QtQuickWidgets',
        'PySide6.QtQuickTemplates2', 'PySide6.QtQuickDialogs2', 'PySide6.QtQuickParticles',
        'PySide6.QtDesigner', 'PySide6.QtUiTools', 'PySide6.QtHelp', 'PySide6.QtXmlPatterns',
        'PySide6.QtScxml', 'PySide6.QtStateMachine',
        'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineQuick',
        'PySide6.QtWebChannel', 'PySide6.QtWebView',
        'PySide6.QtLocation', 'PySide6.QtPositioning', 'PySide6.QtSensors', 'PySide6.QtSerialPort',
        'PySide6.QtBluetooth', 'PySide6.QtNfc', 'PySide6.QtTextToSpeech', 'PySide6.QtRemoteObjects', 'PySide6.QtSpatialAudio',
        'PySide6.QtSql', 'PySide6.QtSqlWidgets', 'PySide6.QtSvg', 'PySide6.QtSvgWidgets',
        'PySide6.QtTest', 'PySide6.QtPrintSupport',
        'tkinter', 'unittest', 'pydoc', 'doctest',
        'http', 'email', 'xmlrpc', 'ftplib', 'smtplib', 'nntplib', 'telnetlib', 'imaplib',
        'pdb', 'profile', 'pstats',
    ],
    noarchive=False,
    optimize=2,
)

# ---- 剔除未使用的 Qt 二进制 / 软件 GL / 多余插件 / 全部翻译 ----
_DROP_DLL = (
    'opengl32sw',                     # SwiftShader 软件 GL，2D Widgets 用不到
    'Qt6Svg', 'Qt6SvgWidgets',
    'Qt6Quick', 'Qt6Qml', 'Qt6QmlModels', 'Qt6QmlMeta', 'Qt6QmlWorkerScript',
    'Qt6Pdf', 'Qt6PdfWidgets',
    'Qt6OpenGL', 'Qt6OpenGLWidgets',
    'Qt6VirtualKeyboard',
    'Qt6Network', 'QtNetwork.pyd', 'Qt6NetworkAuth',
    'Qt6Multimedia', 'Qt6MultimediaWidgets',
    'Qt6Charts', 'Qt6Graphs', 'Qt6DataVisualization',
    'Qt6Quick3D', 'Qt6QuickControls2', 'Qt6QuickWidgets', 'Qt6QuickTemplates2',
    'Qt6QuickDialogs2', 'Qt6QuickParticles',
    'Qt6Designer', 'Qt6UiTools', 'Qt6Help', 'Qt6XmlPatterns',
    'Qt6Scxml', 'Qt6StateMachine',
    'Qt6WebEngineCore', 'Qt6WebEngineWidgets', 'Qt6WebEngineQuick',
    'Qt6WebChannel', 'Qt6WebView',
    'Qt6Location', 'Qt6Positioning', 'Qt6Sensors', 'Qt6SerialPort',
    'Qt6Bluetooth', 'Qt6Nfc', 'Qt6TextToSpeech', 'Qt6RemoteObjects', 'Qt6SpatialAudio',
    'Qt6LabsAnimations', 'Qt6LabsFolderListModel', 'Qt6LabsQmlModels',
    'Qt6LabsSettings', 'Qt6LabsSharedImage', 'Qt6LabsWavefrontMesh',
    'Qt6Sql', 'Qt6PrintSupport', 'Qt6Test',
)
_DROP_PLUGIN = (
    'qdirect2d', 'qoffscreen', 'qminimal',                 # 备用平台插件（保留 qwindows）
    'qwebp', 'qtiff', 'qicns', 'qgif', 'qtga', 'qwbmp', 'qpdf', 'qsvg', 'qsvgicon',
    'qtuiotouch', 'qnetworklistmanager', 'qtvirtualkeyboardplugin',
    'qcertonlybackend', 'qopensslbackend', 'qschannelbackend',  # TLS（纯离线）
)


def _keep_bin(name):
    low = name.lower()
    if any(k.lower() in low for k in _DROP_DLL):
        return False
    if any(p in low for p in _DROP_PLUGIN):
        return False
    # 排除全部 Qt 翻译文件（app.py 未使用 QTranslator，无需任何 .qm）
    if 'translations' in low and '.qm' in low:
        return False
    return True


a.binaries = [b for b in a.binaries if _keep_bin(b[0])]

# ---- 翻译同样可能落在 a.datas，需一并过滤 ----
def _keep_data(name):
    low = name.lower()
    if 'translations' in low and '.qm' in low:
        return False
    return True


a.datas = [d for d in a.datas if _keep_data(d[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='github-desktop-zh-1.0.1',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # 保护 Python 核心 DLL 不被 UPX 压缩（防杀软误报 + 保证启动速度）
    upx_exclude=[
        'python313.dll', 'python3.dll', 'VCRUNTIME140.dll',
        'vcruntime140_1.dll', 'ucrtbase.dll',
    ],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)
