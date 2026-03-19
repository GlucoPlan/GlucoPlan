"""
theme.py — единые настройки шрифта и стилей для всего приложения.
Все вкладки импортируют константы отсюда, чтобы шрифт был одинаковым везде.
"""
import tkinter as tk
from tkinter import ttk

# ── Базовый шрифт ───────────────────────────────────────────────────────────
FONT_FAMILY = "Segoe UI"   # хорошо читается на Windows; на других ОС ttk подберёт похожий
FONT_SIZE   = 10

FONT_NORMAL = (FONT_FAMILY, FONT_SIZE)
FONT_BOLD   = (FONT_FAMILY, FONT_SIZE, "bold")
FONT_SMALL  = (FONT_FAMILY, FONT_SIZE - 1)
FONT_TITLE  = (FONT_FAMILY, FONT_SIZE + 2, "bold")
FONT_BIG    = (FONT_FAMILY, FONT_SIZE + 2, "bold")   # для крупных чисел (доза инсулина)

# ── Высота строки (авто по шрифту) ──────────────────────────────────────────
def _measure_row_height(root=None):
    """Вычисляет высоту строки для Treeview на основе текущего шрифта."""
    try:
        import tkinter.font as tkfont
        f = tkfont.Font(family=FONT_FAMILY, size=FONT_SIZE)
        return f.metrics("linespace") + 8   # 8 px padding сверху+снизу
    except Exception:
        return 22

ROW_HEIGHT = None   # инициализируется в apply_theme() после создания root

# ── Цвета ────────────────────────────────────────────────────────────────────
COLOR_ROW_EVEN   = "#f5f5f5"
COLOR_ROW_ODD    = "#ffffff"
COLOR_SELECT_BG  = "#0078d7"
COLOR_SELECT_FG  = "#ffffff"
COLOR_ACCENT     = "#0078d7"   # синий акцент
COLOR_DANGER     = "#c0392b"
COLOR_SUCCESS    = "#27ae60"
COLOR_MUTED      = "#888888"

# ── Применение глобальных стилей ─────────────────────────────────────────────
def apply_theme():
    """
    Вызывается один раз из main.py после создания root.
    Настраивает ttk.Style глобально для всего приложения.
    """
    global ROW_HEIGHT
    ROW_HEIGHT = _measure_row_height()

    style = ttk.Style()

    # Базовый стиль для всех виджетов
    style.configure(".",
        font=FONT_NORMAL,
    )

    # TLabel
    style.configure("TLabel", font=FONT_NORMAL, padding=1)

    # TButton — чуть больше padding, чтобы кнопки выглядели солиднее
    style.configure("TButton", font=FONT_NORMAL, padding=(8, 4))

    # TEntry
    style.configure("TEntry", font=FONT_NORMAL, padding=3)

    # TCombobox
    style.configure("TCombobox", font=FONT_NORMAL)

    # TLabelframe
    style.configure("TLabelframe.Label", font=FONT_BOLD)

    # ── Единый стиль Treeview ────────────────────────────────────────────────
    style.configure("App.Treeview",
        font=FONT_NORMAL,
        rowheight=ROW_HEIGHT,
        background=COLOR_ROW_ODD,
        fieldbackground=COLOR_ROW_ODD,
        borderwidth=0,
    )
    style.configure("App.Treeview.Heading",
        font=FONT_BOLD,
        relief="flat",
        padding=(4, 4),
    )
    style.map("App.Treeview",
        background=[("selected", COLOR_SELECT_BG)],
        foreground=[("selected", COLOR_SELECT_FG)],
    )

    # Акцентные стили
    style.configure("Accent.TButton",
        font=FONT_BOLD,
        padding=(10, 5),
        foreground=COLOR_ACCENT,
    )
    style.configure("Save.TButton",
        font=FONT_BOLD,
        padding=(10, 5),
    )

    return style
