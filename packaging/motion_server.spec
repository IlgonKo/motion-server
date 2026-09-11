# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


ROOT = Path(SPECPATH).parent


a = Analysis(
    [str(ROOT / "packaging" / "windows_motion_server.py")],
    pathex=[str(ROOT), str(ROOT / "packaging")],
    binaries=[],
    datas=[
        (str(ROOT / "motion_server" / "api" / "schema"), "motion_server/api/schema"),
        (str(ROOT / "device" / "cmmt" / "esi"), "device/cmmt/esi"),
        (str(ROOT / "device" / "cpx_ap_i_ec" / "esi"), "device/cpx_ap_i_ec/esi"),
        (str(ROOT / "device" / "io_link" / "iodd"), "device/io_link/iodd"),
        (str(ROOT / "Reference" / "cmmt_error_catalog.json"), "Reference"),
    ],
    hiddenimports=["pysoem"],
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
    name="motion_server",
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
    icon=str(ROOT / "packaging" / "motion_server.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="motion_server",
)
