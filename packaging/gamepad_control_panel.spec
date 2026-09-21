# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all


ROOT = Path(SPECPATH).parent
pygame_datas, pygame_binaries, pygame_hiddenimports = collect_all("pygame")


a = Analysis(
    [str(ROOT / "packaging" / "windows_gamepad_control_panel.py")],
    pathex=[
        str(ROOT),
        str(ROOT / "packaging"),
        str(ROOT / "reference_clients" / "python"),
    ],
    binaries=pygame_binaries,
    datas=pygame_datas + [
        (
            str(ROOT / "control_panel" / "gamepad_control_panel" / "device_profiles.json"),
            "control_panel/gamepad_control_panel",
        ),
    ],
    hiddenimports=pygame_hiddenimports,
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
    name="gamepad_control_panel",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="gamepad_control_panel",
)
