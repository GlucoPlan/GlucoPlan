import tkinter as tk
from tkinter import ttk, messagebox
import threading
import webbrowser
import database
from theme import FONT_BOLD, FONT_TITLE
from version import __version__


class SettingsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.create_widgets()
        self.load_settings()
        self.bind('<Map>', lambda e: self.load_settings())

    def create_widgets(self):
        canvas = tk.Canvas(self, highlightthickness=0)
        vsb    = ttk.Scrollbar(self, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        inner = ttk.Frame(canvas)
        win   = canvas.create_window((0, 0), window=inner, anchor='nw')

        def _resize(e):
            canvas.configure(scrollregion=canvas.bbox('all'))
            canvas.itemconfig(win, width=e.width)
        inner.bind('<Configure>', _resize)
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(win, width=e.width))

        # ── Баннер обновления ────────────────────────────────────────────────
        self._update_banner = tk.Frame(inner, bg='#fff3cd')
        self._update_banner.grid(row=0, column=0, columnspan=3,
                                  sticky='ew', padx=0, pady=0)
        self._update_banner_lbl = tk.Label(
            self._update_banner, text="", bg='#fff3cd', fg='#856404',
            font=('Segoe UI', 10, 'bold'), padx=14, pady=8,
            anchor='w', justify='left')
        self._update_banner_lbl.pack(side='left', fill='x', expand=True)
        self._update_banner_btn = tk.Label(
            self._update_banner, text="⬇ Скачать новую версию",
            bg='#fff3cd', fg='#0d6efd',
            font=('Segoe UI', 10, 'underline'),
            padx=14, pady=8, cursor='hand2')
        self._update_banner_btn.pack(side='right')
        self._update_url = ''
        self._update_banner_btn.bind(
            '<Button-1>',
            lambda e: webbrowser.open(self._update_url) if self._update_url else None)
        self._update_banner.grid_remove()   # скрыт по умолчанию

        # Строка текущей версии + ссылка на канал
        ver_f = tk.Frame(inner)
        ver_f.grid(row=1, column=0, columnspan=3, sticky='w', padx=16, pady=(6, 0))
        tk.Label(ver_f, text=f"Установлена версия: {__version__}",
                 font=('Segoe UI', 9), fg='gray').pack(side='left')
        self._ver_status_lbl = tk.Label(ver_f, text="",
                                         font=('Segoe UI', 9), fg='gray')
        self._ver_status_lbl.pack(side='left')

        # Разделитель
        tk.Label(ver_f, text="  │  ", font=('Segoe UI', 9), fg='#cccccc').pack(side='left')

        # Ссылка на Telegram-канал
        tg_lbl = tk.Label(ver_f,
                           text="📢 Telegram-канал GlucoPlan",
                           font=('Segoe UI', 9, 'underline'),
                           fg='#0d6efd', cursor='hand2')
        tg_lbl.pack(side='left')
        tg_lbl.bind('<Button-1>',
                    lambda e: webbrowser.open('https://t.me/glucoplan_soft'))

        row = [1]   # начинаем с 1, т.к. 0=баннер, 1=версия уже заняты
        def nr():
            row[0] += 1
            return row[0]

        # ── Углеводы и ХЕ ────────────────────────────────────────────────────
        self._section(inner, "Углеводы и хлебные единицы", nr())
        self.carbs_per_xe_var = self._field(inner, nr(),
            "1 ХЕ = … г углеводов:",
            "Сколько граммов углеводов в одной ХЕ (обычно 10–12 г)", "12")

        # ── Инсулин ───────────────────────────────────────────────────────────
        self._section(inner, "Инсулин", nr())
        self.carb_coef_var    = self._field(inner, nr(),
            "Единиц инсулина на 1 ХЕ:",
            "Углеводный коэффициент — сколько ед. инсулина на 1 ХЕ", "1.0")
        self.sensitivity_var  = self._field(inner, nr(),
            "1 ед снижает сахар на (ммоль/л):",
            "Фактор чувствительности к инсулину", "2.0")
        self.insulin_step_var = self._field(inner, nr(),
            "Шаг ручки шприц-ручки (ед):",
            "Минимальный шаг дозирования (обычно 0.5 или 1.0)", "0.5")

        # Тип короткого инсулина — влияет на подсказку по времени укола
        ins_type_row = nr()
        ttk.Label(inner, text="Тип короткого инсулина:").grid(
            row=ins_type_row, column=0, sticky='e', padx=(24, 8), pady=5)
        self.insulin_type_var = tk.StringVar(value='fiasp')
        type_frame = ttk.Frame(inner)
        type_frame.grid(row=ins_type_row, column=1, columnspan=2, sticky='w', pady=5)
        for label, val in [("Фиасп / Люмьев", 'fiasp'),
                            ("Новорапид / НовоЛог", 'novorapid'),
                            ("Хумалог / Апидра", 'humalog')]:
            ttk.Radiobutton(type_frame, text=label,
                            variable=self.insulin_type_var, value=val).pack(side='left', padx=(0, 10))

        # ── Целевой сахар ─────────────────────────────────────────────────────
        self._section(inner, "Целевой уровень сахара", nr())
        self.target_glucose_min_var = self._field(inner, nr(),
            "Целевой сахар, минимум (ммоль/л):",
            "Нижняя граница целевого диапазона", "5.0")
        self.target_glucose_max_var = self._field(inner, nr(),
            "Целевой сахар, максимум (ммоль/л):",
            "Верхняя граница целевого диапазона", "7.8")

        # ── Базальный инсулин ────────────────────────────────────────────────
        self._section(inner, "Базальный инсулин (длинный)", nr())

        basal_type_row = nr()
        ttk.Label(inner, text="Тип длинного инсулина:").grid(
            row=basal_type_row, column=0, sticky='e', padx=(24, 8), pady=5)
        self.basal_type_var = tk.StringVar(value='lantus')
        bt_frame = ttk.Frame(inner)
        bt_frame.grid(row=basal_type_row, column=1, columnspan=2, sticky='w', pady=5)
        for lbl, val in [("Лантус / Туджео (24 ч)", 'lantus'),
                          ("Левемир (16–18 ч)", 'levemir'),
                          ("Не использую", 'none')]:
            ttk.Radiobutton(bt_frame, text=lbl,
                            variable=self.basal_type_var, value=val).pack(side='left', padx=(0, 10))

        self.basal_dose_var = self._field(inner, nr(),
            "Суточная доза (ед):",
            "Например: 10. Используется в симуляторе для учёта базального фона", "0")

        self.basal_time_var = self._field(inner, nr(),
            "Время укола (ЧЧ:ММ):",
            "Например: 22:00. Нужно для расчёта, сколько длинного инсулина активно прямо сейчас", "22:00")

        # ── NightScout ────────────────────────────────────────────────────────        self._section(inner, "NightScout / CGM", nr())

        ns_row = nr()
        ttk.Label(inner, text="Включить NightScout:").grid(
            row=ns_row, column=0, sticky='e', padx=(24, 8), pady=5)
        self.ns_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(inner, variable=self.ns_enabled_var,
                        command=self._on_ns_toggle).grid(
            row=ns_row, column=1, sticky='w', pady=5)
        ttk.Label(inner,
                  text="При включении в калькуляторе появится индикатор CGM",
                  foreground='gray', wraplength=340).grid(
            row=ns_row, column=2, sticky='w', padx=(8, 16), pady=5)

        url_row = nr()
        ttk.Label(inner, text="URL сервера:").grid(
            row=url_row, column=0, sticky='e', padx=(24, 8), pady=5)
        self.ns_url_var = tk.StringVar()
        ttk.Entry(inner, textvariable=self.ns_url_var, width=36).grid(
            row=url_row, column=1, columnspan=2, sticky='w', pady=5, padx=(0, 16))

        token_row = nr()
        ttk.Label(inner, text="API Secret:").grid(
            row=token_row, column=0, sticky='e', padx=(24, 8), pady=5)
        self.ns_token_var = tk.StringVar()
        token_entry = ttk.Entry(inner, textvariable=self.ns_token_var,
                                width=36, show='*')
        token_entry.grid(row=token_row, column=1, columnspan=2,
                         sticky='w', pady=5, padx=(0, 16))
        ttk.Label(inner,
                  text="API Secret из настроек NightScout (не токен авторизации)",
                  foreground='gray', wraplength=340).grid(
            row=nr(), column=0, columnspan=3, sticky='w', padx=(24, 16), pady=(0, 4))

        # Кнопка проверки связи
        test_row = nr()
        self.ns_test_btn = ttk.Button(inner, text="Проверить соединение",
                                      command=self._test_ns_connection, width=22)
        self.ns_test_btn.grid(row=test_row, column=1, sticky='w', pady=4)
        self.ns_status_var = tk.StringVar(value="")
        self.ns_status_lbl = ttk.Label(inner, textvariable=self.ns_status_var,
                                        foreground='gray', wraplength=340)
        self.ns_status_lbl.grid(row=test_row, column=2, sticky='w', padx=(8, 16))

        # Кнопка сохранения
        save_row = nr()
        ttk.Button(inner, text="💾  Сохранить настройки",
                   command=self.save_settings, style="Save.TButton"
                   ).grid(row=save_row, column=0, columnspan=3, pady=20)

        ttk.Label(inner,
                  text="Настройки применяются сразу после сохранения.",
                  foreground='gray'
                  ).grid(row=nr(), column=0, columnspan=3, pady=(0, 20))

    def _section(self, parent, title, row):
        f = ttk.Frame(parent)
        f.grid(row=row, column=0, columnspan=3, sticky='ew', padx=16, pady=(18, 4))
        ttk.Label(f, text=title, font=FONT_BOLD).pack(side='left', padx=(0, 8))
        ttk.Separator(f, orient='horizontal').pack(side='left', fill='x', expand=True)

    def _field(self, parent, row, label, hint, default):
        ttk.Label(parent, text=label).grid(
            row=row, column=0, sticky='e', padx=(24, 8), pady=5)
        var = tk.StringVar(value=default)
        ttk.Entry(parent, textvariable=var, width=10).grid(
            row=row, column=1, sticky='w', pady=5)
        ttk.Label(parent, text=hint, foreground='gray',
                  wraplength=340).grid(
            row=row, column=2, sticky='w', padx=(8, 16), pady=5)
        return var

    def _on_ns_toggle(self):
        """Меняет цвет статуса при включении/выключении."""
        if not self.ns_enabled_var.get():
            self.ns_status_var.set("")

    # ── NS connection test ─────────────────────────────────────────────────────

    def _test_ns_connection(self):
        url   = self.ns_url_var.get().strip()
        token = self.ns_token_var.get().strip()
        if not url:
            messagebox.showwarning("NightScout", "Введите URL сервера")
            return
        self.ns_test_btn.config(state='disabled')
        self.ns_status_var.set("Проверяю соединение…")
        self.ns_status_lbl.config(foreground='gray')

        def _worker():
            from nightscout import NightScoutClient, NightScoutConfig
            client = NightScoutClient(NightScoutConfig(url=url, token=token, enabled=True))
            ok, msg = client.check_connection()
            self.after(0, lambda: self._on_test_done(ok, msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_test_done(self, ok: bool, msg: str):
        self.ns_test_btn.config(state='normal')
        self.ns_status_var.set(msg)
        self.ns_status_lbl.config(foreground='#27ae60' if ok else '#c0392b')

    # ── Загрузка / Сохранение ─────────────────────────────────────────────────

    def show_update_banner(self, result: dict):
        """Вызывается из main.py после проверки обновлений."""
        if not hasattr(self, '_update_banner'):
            return
        if result.get('available'):
            new_ver = result.get('version', '?')
            self._update_url = result.get('url', '')
            self._update_banner_lbl.config(
                text=f"🔔  Доступна новая версия {new_ver}  "
                     f"(у вас установлена {__version__})")
            self._update_banner.grid()
            self._ver_status_lbl.config(text="")
        else:
            self._update_banner.grid_remove()
            err = result.get('error')
            if err in (None, 'no_releases', 'not_configured'):
                # Нет релизов или не настроен — не пугаем пользователя
                if err == 'not_configured':
                    self._ver_status_lbl.config(text="", fg='gray')
                else:
                    self._ver_status_lbl.config(
                        text="  ✓ установлена последняя версия", fg='#27ae60')
            elif err:
                self._ver_status_lbl.config(
                    text="  (нет соединения для проверки обновлений)",
                    fg='#999999')

    def load_settings(self):
        s      = database.get_settings()
        ns_cfg = database.get_ns_config()
        target = s.get('target_glucose', 6.0)
        self.carbs_per_xe_var.set(str(s.get('carbs_per_xe',       12)))
        self.carb_coef_var.set(str(s.get('carb_coefficient',      1.0)))
        self.sensitivity_var.set(str(s.get('sensitivity',          2.0)))
        self.insulin_step_var.set(str(s.get('insulin_step',        0.5)))
        self.insulin_type_var.set(str(s.get('insulin_type',        'fiasp')))
        self.target_glucose_min_var.set(str(s.get('target_glucose_min', target)))
        self.target_glucose_max_var.set(str(s.get('target_glucose_max', target)))
        # NS
        self.ns_enabled_var.set(ns_cfg.get('enabled', '0') == '1')
        self.ns_url_var.set(ns_cfg.get('url', ''))
        self.ns_token_var.set(ns_cfg.get('token', ''))
        # Basal
        self.basal_type_var.set(ns_cfg.get('basal_type', 'lantus'))
        self.basal_dose_var.set(ns_cfg.get('basal_dose', '0'))
        self.basal_time_var.set(ns_cfg.get('basal_time', '22:00'))

    def save_settings(self):
        try:
            carbs_per_xe = float(self.carbs_per_xe_var.get())
            carb_coef    = float(self.carb_coef_var.get())
            sensitivity  = float(self.sensitivity_var.get())
            insulin_step = float(self.insulin_step_var.get())
            t_min        = float(self.target_glucose_min_var.get())
            t_max        = float(self.target_glucose_max_var.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Все числовые поля должны содержать числа")
            return

        if carbs_per_xe <= 0 or carb_coef <= 0 or sensitivity <= 0 or insulin_step <= 0:
            messagebox.showerror("Ошибка", "Все значения должны быть положительными")
            return
        if t_min > t_max:
            messagebox.showerror("Ошибка",
                "Минимум целевого сахара не может быть больше максимума")
            return

        database.save_settings({
            'carbs_per_xe':       carbs_per_xe,
            'carb_coefficient':   carb_coef,
            'sensitivity':        sensitivity,
            'insulin_step':       insulin_step,
            'target_glucose_min': t_min,
            'target_glucose_max': t_max,
            'target_glucose':     (t_min + t_max) / 2,
        })
        # Сохраняем NS-конфиг + типы инсулина + базальный
        database.save_ns_config(
            url=self.ns_url_var.get().strip(),
            token=self.ns_token_var.get().strip(),
            enabled=self.ns_enabled_var.get(),
        )
        with database.get_connection() as conn:
            database._ensure_ns_tables(conn)
            for key, value in [
                ('insulin_type', self.insulin_type_var.get()),
                ('basal_type',   self.basal_type_var.get()),
                ('basal_dose',   self.basal_dose_var.get().strip()),
                ('basal_time',   self.basal_time_var.get().strip()),
            ]:
                conn.execute("INSERT OR REPLACE INTO ns_config (key, value) VALUES (?, ?)",
                             (key, value))
            conn.commit()

        # Синхронизируем все вкладки
        try:
            nb = self.master
            for tab_id in nb.tabs():
                w = nb.nametowidget(tab_id)
                if hasattr(w, 'load_settings') and w is not self:
                    w.load_settings()
        except Exception:
            pass

        messagebox.showinfo("Сохранено",
            "Настройки сохранены.\n"
            + ("NightScout включён — CGM-виджет появится в Калькуляторе."
               if self.ns_enabled_var.get() else "NightScout отключён."))
