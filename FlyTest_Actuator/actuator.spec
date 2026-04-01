# -*- mode: python ; coding: utf-8 -*-
"""
FlyTest Actuator PyInstaller 打包配置

使用方法:
    pyinstaller actuator.spec

生成文件:
    dist/FlyTest_Actuator/  - 包含所有依赖的目录
    dist/FlyTest_Actuator/FlyTest_Actuator.exe  - 主程序
"""

import sys
import glob
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

# 收集 playwright 相关文件
playwright_datas, playwright_binaries, playwright_hiddenimports = collect_all('playwright')

# 收集 pydantic 相关文件
pydantic_datas, pydantic_binaries, pydantic_hiddenimports = collect_all('pydantic')
pydantic_core_datas, pydantic_core_binaries, pydantic_core_hiddenimports = collect_all('pydantic_core')

# 收集完整 PySide6（确保 GUI 功能正常）
pyside6_datas, pyside6_binaries, pyside6_hiddenimports = collect_all('PySide6')
shiboken6_datas, shiboken6_binaries, shiboken6_hiddenimports = collect_all('shiboken6')

# 收集 httpx/httpcore 相关（包含 mypyc 编译的模块）
httpx_datas, httpx_binaries, httpx_hiddenimports = collect_all('httpx')
httpcore_datas, httpcore_binaries, httpcore_hiddenimports = collect_all('httpcore')

# 手动收集 site-packages 根目录的 mypyc 编译模块
import site
site_packages_list = site.getsitepackages()
mypyc_binaries = []
for sp in site_packages_list:
    for pyd in glob.glob(f"{sp}/*mypyc*.pyd"):
        mypyc_binaries.append((pyd, '.'))
    for pyd in glob.glob(f"{sp}/*mypyc*.so"):
        mypyc_binaries.append((pyd, '.'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=(
        playwright_binaries + 
        pydantic_binaries + 
        pydantic_core_binaries + 
        pyside6_binaries + 
        shiboken6_binaries + 
        httpx_binaries +
        httpcore_binaries +
        mypyc_binaries
    ),
    datas=[
        ('config.example.toml', '.'),
        ('data/FlyTest.png', 'data'),  # 图标文件
        *playwright_datas,
        *pydantic_datas,
        *pydantic_core_datas,
        *pyside6_datas,
        *shiboken6_datas,
        *httpx_datas,
        *httpcore_datas,
    ],
    hiddenimports=[
        # Playwright 相关
        'playwright',
        'playwright.async_api',
        'playwright.sync_api',
        'playwright._impl',
        'playwright._impl._driver',
        *playwright_hiddenimports,
        
        # Pydantic 相关
        'pydantic',
        'pydantic_core',
        *pydantic_hiddenimports,
        *pydantic_core_hiddenimports,
        
        # PySide6 完整模块
        *pyside6_hiddenimports,
        *shiboken6_hiddenimports,
        
        # HTTP 相关
        *httpx_hiddenimports,
        *httpcore_hiddenimports,
        
        # 网络相关
        'websockets',
        'websockets.legacy',
        'websockets.legacy.client',
        'anyio',
        'anyio._backends._asyncio',
        'h11',
        'sniffio',
        
        # TOML 相关
        'tomli',
        'tomllib',
        'tomli_w',
        
        # 本地模块
        'browser_installer',
        'websocket_client',
        'consumer',
        'executor',
        'models',
        'data_processor',
        'gui',
        'gui.login_window',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的大型模块
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FlyTest_Actuator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FlyTest_Actuator',
)
