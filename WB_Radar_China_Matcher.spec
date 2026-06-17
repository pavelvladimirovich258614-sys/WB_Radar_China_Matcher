# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[('config.yaml', '.'), ('fixtures', 'fixtures')],
    hiddenimports=['flet', 'core.config', 'core.models', 'core.storage', 'core.wb_public', 'core.browser', 'core.llm', 'core.llm.base', 'core.llm.openrouter', 'core.llm.zai', 'core.llm.groq', 'core.llm.ollama', 'matcher.input', 'matcher.rank', 'matcher.video_china', 'matcher.china', 'matcher.china.alibaba', 'matcher.china.s1688', 'matcher.china.taobao', 'matcher.china.base', 'harvest.discovery', 'harvest.reviews', 'harvest.voc', 'harvest.hooks', 'harvest.review_video', 'harvest.download', 'harvest.describe', 'gui.app', 'gui.settings', 'PIL', 'PIL.Image', 'yaml', 'httpx', 'tenacity', 'imagehash', 'pydantic', 'pydantic_settings', 'pandas', 'dotenv', 'bs4'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['.env', 'sessions', 'output', '.venv', 'build', 'dist'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WB_Radar_China_Matcher',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WB_Radar_China_Matcher',
)
