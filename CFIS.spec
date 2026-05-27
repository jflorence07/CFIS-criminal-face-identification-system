# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for CFIS - Criminal Face Identification System
# Builds 4 executables into a single dist/CFIS/ directory.

import os

block_cipher = None

# Shared data files bundled into every exe
shared_datas = [
    ('haarcascade_frontalface_default.xml', '.'),
    ('criminal.db', '.'),
    ('images', 'images'),
]

a_start = Analysis(
    ['start.py'],
    pathex=[],
    binaries=[],
    datas=shared_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

a_register = Analysis(
    ['registerGUI.py'],
    pathex=[],
    binaries=[],
    datas=shared_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

a_surveillance = Analysis(
    ['surveillance.py'],
    pathex=[],
    binaries=[],
    datas=shared_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

a_detect = Analysis(
    ['detect.py'],
    pathex=[],
    binaries=[],
    datas=shared_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz_start       = PYZ(a_start.pure,       a_start.zipped_data,       cipher=block_cipher)
pyz_register    = PYZ(a_register.pure,    a_register.zipped_data,    cipher=block_cipher)
pyz_surveillance= PYZ(a_surveillance.pure,a_surveillance.zipped_data,cipher=block_cipher)
pyz_detect      = PYZ(a_detect.pure,      a_detect.zipped_data,      cipher=block_cipher)

exe_start = EXE(
    pyz_start,
    a_start.scripts,
    [],
    exclude_binaries=True,
    name='CFIS',
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

exe_register = EXE(
    pyz_register,
    a_register.scripts,
    [],
    exclude_binaries=True,
    name='registerGUI',
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

exe_surveillance = EXE(
    pyz_surveillance,
    a_surveillance.scripts,
    [],
    exclude_binaries=True,
    name='surveillance',
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

exe_detect = EXE(
    pyz_detect,
    a_detect.scripts,
    [],
    exclude_binaries=True,
    name='detect',
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
    exe_start,      a_start.binaries,       a_start.datas,
    exe_register,   a_register.binaries,    a_register.datas,
    exe_surveillance, a_surveillance.binaries, a_surveillance.datas,
    exe_detect,     a_detect.binaries,      a_detect.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CFIS',
    contents_directory='.',
)
