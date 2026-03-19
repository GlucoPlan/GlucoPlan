"""
ns_glucose_widget.py — виджет показаний CGM для вкладки Калькулятор.

Показывает:
  - текущий сахар (ммоль/л) с цветовой индикацией
  - стрелку тренда + подпись
  - возраст показания
  - поправку к дозе инсулина из-за тренда
  - кнопку «Обновить»

Работает только если NightScout настроен и включён.
Запросы идут в фоновом потоке, чтобы не подвешивать UI.
"""

import tkinter as tk
from tkinter import ttk
import threading
import database
from nightscout import NightScoutClient, NightScoutConfig, NightScoutError
from theme import FONT_BOLD, FONT_BIG, FONT_SMALL, FONT_NORMAL

try:
    from logger import log_cgm, log_error
except ImportError:
    def log_cgm(msg): print(f"[CGM] {msg}", flush=True)
    def log_error(msg, exc=None): print(f"[ERROR] {msg}", flush=True)


# Цвета по уровню сахара
def _glucose_color(mmol: float) -> str:
    if mmol < 3.9:   return '#c0392b'   # гипо — красный
    if mmol < 5.0:   return '#e67e22'   # ниже цели — оранжевый
    if mmol <= 8.0:  return '#27ae60'   # в цели — зелёный
    if mmol <= 10.0: return '#e67e22'   # выше цели — оранжевый
    return '#c0392b'                     # гипер — красный


class NSGlucoseWidget(ttk.LabelFrame):
    """
    Виджет показаний CGM.
    compact=True — горизонтальная однострочная компоновка для встройки в панель.
    compact=False — вертикальная полная версия.
    """

    POLL_INTERVAL_MS = 60_000

    def __init__(self, parent, on_glucose_ready=None, compact=False, **kwargs):
        super().__init__(parent, text="CGM / NightScout", padding=(6, 4), **kwargs)
        self.on_glucose_ready = on_glucose_ready
        self.compact          = compact
        self._after_id        = None
        self._loading         = False
        self._last_reading    = None
        self._readings_cache  = []

        self._build_ui()
        self._schedule_poll()

    def _build_ui(self):
        if self.compact:
            self._build_compact()
        else:
            self._build_full()

    def _build_compact(self):
        """Горизонтальная однострочная компоновка."""
        self.columnconfigure(4, weight=1)

        # Большое число
        self.glucose_lbl = ttk.Label(self, text="—",
                                      font=('Segoe UI', 18, 'bold'),
                                      foreground='gray', width=5, anchor='e')
        self.glucose_lbl.grid(row=0, column=0, rowspan=2, padx=(0, 4))

        # Стрелка тренда
        self.trend_lbl = ttk.Label(self, text="", font=('Segoe UI', 14))
        self.trend_lbl.grid(row=0, column=1, sticky='sw', padx=(0, 2))

        # Подпись тренда
        self.trend_text = ttk.Label(self, text="", font=('Segoe UI', 8),
                                     foreground='gray')
        self.trend_text.grid(row=1, column=1, sticky='nw', padx=(0, 8))

        # Возраст
        self.age_lbl = ttk.Label(self, text="", font=('Segoe UI', 8),
                                  foreground='gray')
        self.age_lbl.grid(row=0, column=2, sticky='sw')

        # Прогноз
        self.delta_lbl = ttk.Label(self, text="", font=('Segoe UI', 8))
        self.delta_lbl.grid(row=1, column=2, sticky='nw', padx=(0, 8))

        # Кнопка и статус
        self.refresh_btn = ttk.Button(self, text="⟳", width=3,
                                       command=self.refresh)
        self.refresh_btn.grid(row=0, column=3, rowspan=2, padx=(4, 4))

        self.status_lbl = ttk.Label(self, text="", font=('Segoe UI', 8),
                                     foreground='gray', wraplength=200)
        self.status_lbl.grid(row=0, column=4, rowspan=2, sticky='w')

    def _build_full(self):
        """Вертикальная полная компоновка (для будущего использования)."""
        self.columnconfigure(1, weight=1)

        self.glucose_lbl = ttk.Label(self, text="—",
                                      font=('Segoe UI', 22, 'bold'),
                                      foreground='gray')
        self.glucose_lbl.grid(row=0, column=0, rowspan=2, padx=(0, 10), sticky='w')

        self.trend_lbl  = ttk.Label(self, text="", font=('Segoe UI', 16))
        self.trend_lbl.grid(row=0, column=1, sticky='w')
        self.trend_text = ttk.Label(self, text="", font=FONT_SMALL, foreground='gray')
        self.trend_text.grid(row=1, column=1, sticky='w')
        self.age_lbl    = ttk.Label(self, text="", font=FONT_SMALL, foreground='gray')
        self.age_lbl.grid(row=2, column=0, columnspan=2, sticky='w', pady=(4, 0))
        self.delta_lbl  = ttk.Label(self, text="", font=FONT_SMALL)
        self.delta_lbl.grid(row=3, column=0, columnspan=2, sticky='w')
        self.refresh_btn = ttk.Button(self, text="⟳ Обновить",
                                       command=self.refresh, width=12)
        self.refresh_btn.grid(row=4, column=0, columnspan=2, pady=(8, 0), sticky='w')
        self.status_lbl = ttk.Label(self, text="", font=FONT_SMALL,
                                     foreground='gray', wraplength=200)
        self.status_lbl.grid(row=5, column=0, columnspan=2, sticky='w')

    # ── Публичные методы ─────────────────────────────────────────────────────

    def refresh(self):
        """Запускает немедленное обновление в фоне."""
        if self._loading:
            return
        self._loading = True
        self.refresh_btn.config(state='disabled')
        self.status_lbl.config(text="Запрос к NightScout…")
        threading.Thread(target=self._fetch, daemon=True).start()

    def reset(self):
        """Сбрасывает виджет (например, при отключении NS)."""
        self._last_reading = None
        self.glucose_lbl.config(text="—", foreground='gray')
        self.trend_lbl.config(text="")
        self.trend_text.config(text="")
        self.age_lbl.config(text="")
        self.delta_lbl.config(text="")
        self.status_lbl.config(text="NightScout не настроен")

    # ── Внутренние ───────────────────────────────────────────────────────────

    def _get_client(self):
        cfg_raw = database.get_ns_config()
        url     = cfg_raw.get('url', '').strip()
        token   = cfg_raw.get('token', '').strip()
        enabled = cfg_raw.get('enabled', '0') == '1'
        if not enabled or not url:
            return None
        from nightscout import NightScoutConfig
        return NightScoutClient(NightScoutConfig(url=url, token=token, enabled=enabled))

    def _fetch(self):
        """Фоновый поток — запрашивает NS и обновляет UI через after()."""
        try:
            client = self._get_client()
            if client is None:
                log_cgm("NightScout отключён или не настроен — пропускаем запрос")
                self.after(0, lambda: self._set_status("NightScout отключён или не настроен"))
                return

            log_cgm("Запрос показаний CGM...")
            readings = client.get_entries(count=5)
            if not readings:
                log_cgm("Ответ пуст — нет данных от CGM")
                self.after(0, lambda: self._set_status("Нет данных от CGM"))
                return

            latest = readings[0]
            log_cgm(f"Получено: {latest.mmol} ммоль/л, direction={latest.direction}, "
                    f"возраст={latest.age_str}, свежее={latest.is_fresh}")

            # Если NS не дал тренд — вычисляем сами
            if latest.direction in ('None', 'NOT COMPUTABLE', '') and len(readings) >= 3:
                latest.direction = client._calc_direction(readings[:4])
                log_cgm(f"Тренд вычислен локально: {latest.direction}")

            self._readings_cache = readings
            self._last_reading   = latest

            # Прогноз через 20 минут
            proj = client.calc_trend_projection(readings, minutes_ahead=20)
            if proj:
                log_cgm(f"Прогноз через 20 мин: {proj} ммоль/л")

            self.after(0, lambda: self._update_ui(latest, proj))

        except NightScoutError as e:
            msg = str(e)
            log_error(f"NightScout ошибка: {msg}")
            self.after(0, lambda: self._set_status(f"Ошибка: {msg}"))
        except Exception as e:
            log_error(f"Неожиданная ошибка в CGM-виджете: {e}", e)
            self.after(0, lambda: self._set_status(f"Неожиданная ошибка: {e}"))
        finally:
            self.after(0, self._done_loading)

    def _update_ui(self, reading, projected_mmol=None):
        color = _glucose_color(reading.mmol)
        self.glucose_lbl.config(text=f"{reading.mmol:.1f}", foreground=color)
        self.trend_lbl.config(
            text=reading.arrow,
            foreground=color if reading.direction not in ('Flat', 'None') else 'gray')
        self.trend_text.config(text=reading.trend_label)
        self.age_lbl.config(text=reading.age_str)

        # Поправка к дозе
        delta = reading.dose_delta
        if delta != 0:
            sign    = '+' if delta > 0 else ''
            color_d = '#c0392b' if delta > 0 else '#27ae60'
            if self.compact:
                self.delta_lbl.config(
                    text=f"Поправка: {sign}{delta:.1f} ед",
                    foreground=color_d)
            else:
                self.delta_lbl.config(
                    text=f"Поправка к дозе: {sign}{delta:+.1f} ед (тренд)",
                    foreground=color_d)
        else:
            self.delta_lbl.config(text="", foreground='gray')

        # Прогноз в status
        if projected_mmol is not None:
            pcolor = _glucose_color(projected_mmol)
            if self.compact:
                self.status_lbl.config(
                    text=f"→ {projected_mmol:.1f} (20′)",
                    foreground=pcolor)
            else:
                self.status_lbl.config(
                    text=f"→ через 20 мин: {projected_mmol:.1f}",
                    foreground=pcolor)
        else:
            self.status_lbl.config(text="", foreground='gray')

        # Уведомляем калькулятор — всегда, независимо от возраста показания
        # (пользователь нажал «Обновить» — значит хочет это значение)
        if self.on_glucose_ready:
            self.on_glucose_ready(reading.mmol, delta)

    def _set_status(self, text: str):
        self.status_lbl.config(text=text)

    def _done_loading(self):
        self._loading = False
        self.refresh_btn.config(state='normal')

    def _schedule_poll(self):
        """Автообновление раз в минуту."""
        def poll():
            cfg_raw = database.get_ns_config()
            if cfg_raw.get('enabled') == '1' and cfg_raw.get('url', '').strip():
                self.refresh()
            self._after_id = self.after(self.POLL_INTERVAL_MS, poll)
        # Первый запрос — через 2 секунды после старта
        self._after_id = self.after(2000, poll)

    def destroy(self):
        if self._after_id:
            self.after_cancel(self._after_id)
        super().destroy()
