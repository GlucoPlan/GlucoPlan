import os
import sys

def get_base_dir():
    """Возвращает правильную базовую директорию в зависимости от способа запуска."""
    if getattr(sys, 'frozen', False):
        # Запуск в собранном виде (PyInstaller) – папка с exe
        return os.path.dirname(sys.executable)
    else:
        # Запуск из исходников
        return os.path.dirname(os.path.abspath(__file__))

# Базовая папка программы
BASE_DIR = get_base_dir()

# Путь к файлу базы данных
DB_PATH = os.path.join(BASE_DIR, 'glucoplan.db')

# Папка для фото кастрюль
PANS_PHOTO_DIR = os.path.join(BASE_DIR, 'pans_photos')
if not os.path.exists(PANS_PHOTO_DIR):
    os.makedirs(PANS_PHOTO_DIR)

# Значение по умолчанию для коэффициента ХЕ
DEFAULT_CARBS_PER_XE = 12