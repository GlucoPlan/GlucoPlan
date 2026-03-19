"""
logger.py — централизованное логирование в консоль.

Использование:
    from logger import log, log_error, log_ns, log_db

Все сообщения идут в stdout с меткой времени и категорией.
При запуске из PyInstaller-сборки без консоли — пишет в файл app.log рядом с exe.
"""

import sys
import os
import traceback
from datetime import datetime


# ── Настройка вывода ─────────────────────────────────────────────────────────

def _get_log_file():
    """Если нет консоли (frozen exe) — логируем в файл рядом с exe."""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
        return open(os.path.join(base, 'app.log'), 'a', encoding='utf-8')
    return None


_log_file = _get_log_file()


def _write(category: str, message: str):
    ts  = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    line = f"[{ts}] [{category}] {message}"
    print(line, flush=True)
    if _log_file:
        try:
            _log_file.write(line + '\n')
            _log_file.flush()
        except Exception:
            pass


# ── Публичные функции ─────────────────────────────────────────────────────────

def log(message: str):
    """Общий лог."""
    _write('APP', message)


def log_error(message: str, exc: Exception = None):
    """Ошибка с опциональным трейсбеком."""
    _write('ERROR', message)
    if exc:
        tb = traceback.format_exc()
        if tb.strip() != 'NoneType: None':
            for line in tb.splitlines():
                _write('ERROR', '  ' + line)


def log_ns(message: str):
    """NightScout-специфичный лог."""
    _write('NS', message)


def log_db(message: str):
    """База данных."""
    _write('DB', message)


def log_ui(message: str):
    """UI-события (переключение вкладок, клики)."""
    _write('UI', message)


def log_cgm(message: str):
    """CGM / показания глюкозы."""
    _write('CGM', message)
