# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


data_patterns = [
    "**/*.json",
    "**/*.tsv",
    "**/*.png",
    "**/*.svg",
    "**/*.ico",
    "**/*.qss",
    "**/*.xpm",
    "**/*.ttf",
    "**/*.otf",
]

app_icon = "medusa_analyzer/frontend/styles/medusa_task_icon.png"

datas = (
    collect_data_files("medusa_analyzer", includes=data_patterns)
    + collect_data_files("medusa", includes=data_patterns)
    + collect_data_files("medusa_style", includes=data_patterns)
)

hiddenimports = (
    collect_submodules("medusa_analyzer")
    + collect_submodules("medusa_style")
)


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MedusaAnalyzer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=app_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MedusaAnalyzer",
)
