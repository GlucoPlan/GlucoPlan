# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ['main.py'],                # главный скрипт
    pathex=[],                  # дополнительные пути для поиска модулей
    binaries=[],                # бинарные файлы (например, DLL)
    datas=[],                   # небинарные данные
    hiddenimports=[],           # скрытые импорты, если есть
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

# Создаём исполняемый файл (этот шаг нужен всегда)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='GlucoPlan',       # имя exe-файла
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,              # скрыть консоль
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='GlucoPlan.ico'             # если есть иконка, укажите путь
)

# COLLECT создаёт папку со всеми необходимыми файлами.
# Именно этот шаг обеспечивает "без распаковки" – программа лежит в папке и запускается оттуда.
COLLECT(
    exe,                         # включаем исполняемый файл
    a.binaries,                  # бинарные файлы
    a.datas,                     # данные (включая pans_photos)
    strip=False,
    upx=False,
    upx_exclude=[],
    name='GlucoPlan'         # имя выходной папки (будет создана в dist)
)