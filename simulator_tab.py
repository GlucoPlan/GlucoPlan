"""
simulator_tab.py — вкладка «Симулятор».

Показывает три кривые на одном графике (Canvas, без внешних библиотек):
  1. Рост сахара от углеводов текущего приёма
  2. Действие болюса инсулина (снижение)
  3. Суммарный прогноз сахара
"""

import tkinter as tk
from tkinter import ttk
import math
import database
from theme import FONT_BOLD, FONT_SMALL, FONT_NORMAL

# ── Профили инсулина ──────────────────────────────────────────────────────────
#
# onset  — задержка начала действия (мин). До этого момента инсулин не снижает сахар.
#          У Фиаспа ~10 мин, у Новорапида ~15 мин.
# tp     — время пика от момента укола (мин). Для Фиаспа 35, для Новорапида 75.
# td     — суммарная длительность активного действия (мин).
#
# Профили соответствуют клинически наблюдаемым кривым из литературы
# (Heise et al. 2020 для Фиаспа, Mudaliar et al. для аналогов).

INSULIN_PROFILES = {
    'fiasp': {
        'label':  'Фиасп / Люмьев',
        # Откалибровано по инструкции к препарату (medi.ru/fiasp, Heise et al.):
        # пик мгновенного действия ~55 мин, при t=120 мин ~64% от пика.
        'onset':  3,     # начало действия ~2–5 мин
        'tp':     45,    # параметр биэкспоненты → пик скорости на ~55 мин
        'td':     270,   # длительность активного окна 4.5 ч
    },
    'novorapid': {
        'label':  'Новорапид / НовоЛог',
        # Пик ~80 мин, при t=120 мин ~90% от пика, длительность ~6 ч
        'onset':  5,
        'tp':     65,
        'td':     360,
    },
    'humalog': {
        'label':  'Хумалог / Апидра',
        # Пик ~75 мин, чуть быстрее Новорапида
        'onset':  5,
        'tp':     60,
        'td':     300,
    },
}


def _biexp(t: float, tp: float, td: float) -> float:
    """
    Биэкспоненциальная кривая действия инсулина (модель Hovorka).
    t  — время от начала активного действия (уже с учётом onset, снаружи).
    tp — время пика (мин от начала действия).
    td — длительность (мин).
    Возвращает плотность действия (не нормированную).
    """
    if t <= 0:
        return 0.0
    # Защита от вырожденных параметров
    if 2 * tp >= td:
        td = 2 * tp + 1
    tau = tp * (1 - tp / td) / (1 - 2 * tp / td)
    if tau <= 0:
        return 0.0
    a   = 2 * tau / td
    S   = 1 / (1 - a)
    val = S / tau**2 * t * math.exp(-t / tau)
    return max(0.0, val)


def insulin_action_curve(insulin_units: float, profile: dict,
                          minutes: int = 300, step: int = 5) -> list:
    """
    Возвращает список (t_от_укола, суммарное_снижение_ммоль_л).
    Значения отрицательные (инсулин снижает сахар).

    Учитывает onset: до onset минут действие равно нулю,
    затем кривая _biexp строится от (t - onset).
    """
    s    = database.get_settings()
    sens = s.get('sensitivity', 2.0)
    tp   = profile['tp']
    td   = profile['td']
    onset = profile.get('onset', 0)

    # Эффективное tp/td — отсчитываем от момента начала действия
    tp_eff = tp - onset   # пик от момента начала действия
    td_eff = td - onset   # длительность активного окна

    if tp_eff <= 0:
        tp_eff = 1
    if td_eff <= 2 * tp_eff:
        td_eff = 2 * tp_eff + 10

    # Нормировочный интеграл (от начала действия до конца)
    dt   = 1.0
    norm = sum(_biexp(float(tt), tp_eff, td_eff) * dt
               for tt in range(1, int(td_eff) + 1))
    if norm <= 0:
        return []

    result = []
    for t in range(0, minutes + step, step):
        t_active = t - onset              # время от начала действия инсулина
        if t_active <= 0:
            iob_fraction = 0.0            # ещё не начал действовать
        else:
            iob_fraction = min(1.0,
                sum(_biexp(float(tt), tp_eff, td_eff) * dt
                    for tt in range(1, int(t_active) + 1)) / norm)
        result.append((t, -iob_fraction * insulin_units * sens))
    return result


def carb_absorption_curve(carbs_g: float, gi: float,
                           minutes: int = 300, step: int = 5) -> list:
    """
    Модель всасывания углеводов: логистическая кривая с масштабированием по ГИ.
    Возвращает список (t, delta_mmol) — прирост сахара от начала.
    Параметры: скорость всасывания зависит от ГИ (высокий ГИ = быстрее).
    """
    s          = database.get_settings()
    carbs_per_xe = s.get('carbs_per_xe', 12)
    # Оценка: 1 ХЕ поднимает сахар примерно на 2–2.5 ммоль/л (зависит от чувствит.)
    # Используем простой коэффициент 2.2 ммоль/л на ХЕ
    xe         = carbs_g / carbs_per_xe
    peak_rise  = xe * 2.2   # ммоль/л максимальный подъём

    # Скорость всасывания по ГИ: высокий ГИ (>70) → пик ~45 мин, низкий (<40) → ~90 мин
    gi_clamped = max(30.0, min(100.0, gi if gi else 55.0))
    t_peak     = 90 - (gi_clamped - 30) * (45 / 70)   # от 90 до 45 мин

    result = []
    for t in range(0, minutes + step, step):
        # Логистическая кривая: быстрый рост до пика, затем медленное снижение
        rise_frac = 1 / (1 + math.exp(-(t - t_peak) / (t_peak / 3)))
        fall_frac = math.exp(-max(0, t - t_peak) / (t_peak * 2))
        val = peak_rise * rise_frac * fall_frac * 2   # нормировка
        result.append((t, min(val, peak_rise)))
    return result


class SimulatorTab(ttk.Frame):
    """
    Вкладка симулятора прогноза сахара.
    calculator_tab передаётся для чтения текущих данных приёма.
    """

    def __init__(self, parent, calculator_tab=None):
        super().__init__(parent)
        self.calculator_tab = calculator_tab
        self._create_widgets()
        self.bind('<Map>', self.on_tab_show)

    def on_tab_show(self, event):
        """Автоматически загружает данные из калькулятора при переходе на вкладку."""
        self._sync_from_calculator()
        self._redraw()

    def _create_widgets(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)   # chart растягивается

        # ── row 0: Параметры симуляции ────────────────────────────────────────
        ctrl = ttk.LabelFrame(self, text="Параметры симуляции", padding=8)
        ctrl.grid(row=0, column=0, sticky='ew', padx=8, pady=(8, 2))

        def _lbl(parent, text, r, c):
            ttk.Label(parent, text=text).grid(
                row=r, column=c, sticky='e', padx=(10, 3), pady=4)

        def _ent(parent, var, r, c, w=8):
            e = ttk.Entry(parent, textvariable=var, width=w)
            e.grid(row=r, column=c, sticky='w', pady=4)
            e.bind('<Return>',   lambda _: self._redraw())
            e.bind('<FocusOut>', lambda _: self._redraw())
            return e

        self.carbs_var   = tk.StringVar(value="0")
        self.gi_var      = tk.StringVar(value="55")
        self.insulin_var = tk.StringVar(value="0")
        self.glucose_var = tk.StringVar(value="7.0")
        self.offset_var  = tk.StringVar(value="0")

        # Строка 0: числовые параметры приёма
        _lbl(ctrl, "Углеводы (г):",  0, 0); _ent(ctrl, self.carbs_var,  0, 1)
        _lbl(ctrl, "ГИ:",            0, 2); _ent(ctrl, self.gi_var,      0, 3, 5)
        _lbl(ctrl, "Инсулин (ед):",  0, 4); _ent(ctrl, self.insulin_var, 0, 5)
        _lbl(ctrl, "Текущий сахар:", 0, 6); _ent(ctrl, self.glucose_var, 0, 7, 6)
        ttk.Label(ctrl, text="ммоль/л",
                  foreground='gray').grid(row=0, column=8, sticky='w')

        # Строка 1: укол + тип инсулина
        _lbl(ctrl, "Укол (мин от начала еды):", 1, 0)
        _ent(ctrl, self.offset_var, 1, 1)
        ttk.Label(ctrl, text="0 = одновременно с едой  \n  +10 = за 10 мин ДО еды  \n  −15 = через 15 мин ПОСЛЕ начала еды",
                  foreground='gray',
                  font=('Segoe UI', 8)).grid(row=1, column=2, columnspan=3,
                                              sticky='w', padx=8)

        _lbl(ctrl, "Тип инсулина:", 1, 5)
        self.ins_type_var = tk.StringVar(value='fiasp')
        ins_f = ttk.Frame(ctrl)
        ins_f.grid(row=1, column=6, columnspan=3, sticky='w')
        for lbl, val in [("Фиасп", 'fiasp'),
                          ("Новорапид", 'novorapid'),
                          ("Хумалог", 'humalog')]:
            ttk.Radiobutton(ins_f, text=lbl, variable=self.ins_type_var,
                            value=val, command=self._on_type_change
                            ).pack(side='left', padx=4)

        ttk.Button(ctrl, text="↺ Из калькулятора",
                   command=lambda: (self._sync_from_calculator(), self._redraw())
                   ).grid(row=0, column=9, rowspan=2, padx=12, sticky='ns')

        # ── row 1: Параметры профиля инсулина ────────────────────────────────
        prof = ttk.LabelFrame(self,
                               text="Параметры профиля инсулина  "
                                    "(можно подстроить под себя)",
                               padding=(8, 4))
        prof.grid(row=1, column=0, sticky='ew', padx=8, pady=(2, 2))

        self.onset_var = tk.StringVar(value="10")
        self.tp_var    = tk.StringVar(value="35")
        self.td_var    = tk.StringVar(value="210")

        def _plbl(text, c):
            ttk.Label(prof, text=text).grid(
                row=0, column=c, sticky='e', padx=(10, 3), pady=3)

        def _pent(var, c, tip):
            e = ttk.Entry(prof, textvariable=var, width=6)
            e.grid(row=0, column=c, sticky='w', pady=3)
            e.bind('<Return>',   lambda _: self._redraw())
            e.bind('<FocusOut>', lambda _: self._redraw())
            ttk.Label(prof, text=tip, foreground='gray',
                      font=('Segoe UI', 8)).grid(
                row=0, column=c+1, sticky='w', padx=(2, 8))

        _plbl("Задержка начала (мин):", 0); _pent(self.onset_var, 1, "Фиасп ≈ 10")
        _plbl("Пик действия (мин):",    3); _pent(self.tp_var,    4, "Фиасп ≈ 35")
        _plbl("Длительность (мин):",    6); _pent(self.td_var,    7, "Фиасп ≈ 210")

        ttk.Label(prof,
                  text="💡 Увеличьте «задержку» если инсулин медленнее, "
                       "«пик» если сахар снижается позже чем на графике",
                  foreground='gray', font=('Segoe UI', 8)
                  ).grid(row=1, column=0, columnspan=9,
                          sticky='w', padx=10, pady=(0, 2))

        # ── row 2: График ─────────────────────────────────────────────────────
        chart_f = ttk.LabelFrame(self, text="Прогноз сахара", padding=4)
        chart_f.grid(row=2, column=0, sticky='nsew', padx=8, pady=(2, 0))
        chart_f.columnconfigure(0, weight=1)
        chart_f.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(chart_f, background='white',
                                 highlightthickness=1,
                                 highlightbackground='#cccccc')
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.canvas.bind('<Configure>', lambda e: self._redraw())

        # ── row 3: Легенда ────────────────────────────────────────────────────
        legend = ttk.Frame(self)
        legend.grid(row=3, column=0, sticky='w', padx=12, pady=(2, 6))
        for color, text in [('#2980b9', '── Сахар: только еда (без укола)'),
                             ('#e74c3c', '── Сахар: только укол (без еды)'),
                             ('#27ae60', '── Прогноз: еда + укол')]:
            f = ttk.Frame(legend)
            f.pack(side='left', padx=10)
            tk.Label(f, text='━━', foreground=color, background='white',
                     font=('Segoe UI', 10, 'bold')).pack(side='left')
            ttk.Label(f, text=text,
                      font=('Segoe UI', 9)).pack(side='left', padx=2)

    def _get_basal_rate_per_min(self) -> float:
        """
        Возвращает скорость снижения сахара от длинного инсулина (ммоль/л в мин).
        Лантус/Туджео: равномерный профиль 24 ч.
        Левемир: активен ~16–18 ч, потом спад.
        """
        cfg  = database.get_ns_config()
        s    = database.get_settings()
        btype = cfg.get('basal_type', 'none')
        if btype == 'none':
            return 0.0
        try:
            dose = float(cfg.get('basal_dose', '0') or 0)
        except ValueError:
            return 0.0
        if dose <= 0:
            return 0.0

        sens = s.get('sensitivity', 2.0)

        if btype == 'lantus':
            duration_min = 24 * 60   # равномерно 24 ч
        else:  # levemir
            duration_min = 17 * 60   # ~17 ч

        # Суммарный эффект = доза × чувствительность
        # Распределяем равномерно по активному окну
        total_drop = dose * sens           # ммоль/л за всё время действия
        rate       = total_drop / duration_min
        return rate

    def _on_type_change(self):
        """При смене типа инсулина — подставляем стандартные параметры профиля."""
        p = INSULIN_PROFILES.get(self.ins_type_var.get(), INSULIN_PROFILES['fiasp'])
        self.onset_var.set(str(p['onset']))
        self.tp_var.set(str(p['tp']))
        self.td_var.set(str(p['td']))
        self._redraw()

    def _get_current_profile(self) -> dict:
        """Возвращает профиль с учётом пользовательских правок полей."""
        base = dict(INSULIN_PROFILES.get(self.ins_type_var.get(), INSULIN_PROFILES['fiasp']))
        try:
            base['onset'] = int(float(self.onset_var.get()))
            base['tp']    = int(float(self.tp_var.get()))
            base['td']    = int(float(self.td_var.get()))
        except ValueError:
            pass
        return base

    def _sync_from_calculator(self):
        """Копирует данные из калькулятора в поля симулятора."""
        if not self.calculator_tab:
            return
        ct = self.calculator_tab
        try:
            carbs = float(ct.total_vars['carbs'].get())
            self.carbs_var.set(f"{carbs:.1f}")
        except Exception:
            pass
        try:
            ins = float(ct.insulin_dose_var.get())
            self.insulin_var.set(f"{ins:.1f}")
        except Exception:
            pass
        try:
            gl = float(ct.current_glucose_var.get() or 0)
            if gl > 0:
                self.glucose_var.set(f"{gl:.1f}")
        except Exception:
            pass
        # Тип инсулина из настроек
        cfg = database.get_ns_config()
        ins_type = cfg.get('insulin_type', 'fiasp')
        self.ins_type_var.set(ins_type)
        # Подставляем стандартные параметры этого типа
        p = INSULIN_PROFILES.get(ins_type, INSULIN_PROFILES['fiasp'])
        self.onset_var.set(str(p['onset']))
        self.tp_var.set(str(p['tp']))
        self.td_var.set(str(p['td']))

        # ГИ — берём среднее по продуктам из калькулятора
        gis = []
        for comp in ct.components:
            if comp['type'] == 'product':
                pd = comp['product_data']
                # sqlite3.Row поддерживает доступ по ключу через []
                try:
                    gi = pd['glycemic_index'] or 0
                except (KeyError, TypeError):
                    gi = 0
                if gi and gi > 0:
                    gis.append(gi)
        if gis:
            self.gi_var.set(str(int(sum(gis) / len(gis))))

    # ── Отрисовка ─────────────────────────────────────────────────────────────

    def _redraw(self, *_):
        self.canvas.delete('all')
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 50 or h < 50:
            return

        try:
            carbs      = max(0.0, float(self.carbs_var.get()  or 0))
            gi         = max(1.0, float(self.gi_var.get()     or 55))
            insulin    = max(0.0, float(self.insulin_var.get() or 0))
            glucose0   = max(2.0, float(self.glucose_var.get() or 7))
            offset_min = int(float(self.offset_var.get() or 0))
        except ValueError:
            self._draw_error("Проверьте числовые поля")
            return

        profile = self._get_current_profile()
        # Горизонт: если укол после еды — нужно больше времени, чтобы увидеть снижение
        # offset_min < 0 означает «через |offset_min| мин после еды»
        T_MAX = max(240, 240 + max(0, -offset_min))
        STEP  = 5

        # Кривые
        carb_curve = carb_absorption_curve(carbs, gi, T_MAX, STEP) if carbs > 0 else []
        ins_curve  = insulin_action_curve(insulin, profile, T_MAX, STEP) if insulin > 0 else []

        carb_map = dict(carb_curve)
        ins_map  = dict(ins_curve)

        # Базальный инсулин — фоновое снижение
        basal_rate = self._get_basal_rate_per_min()
        times = list(range(0, T_MAX + STEP, STEP))

        combined = []
        for t in times:
            carb_d = carb_map.get(t, 0)
            # offset_min > 0: укол ДО еды.  offset_min < 0: укол ПОСЛЕ начала еды.
            # t_shot (от оси еды) = -offset_min.
            # Время работы инсулина в момент t = t - t_shot = t + offset_min
            t_ins = t + offset_min
            ins_d = ins_map.get(t_ins, 0) if t_ins >= 0 else 0
            basal_d = -basal_rate * t
            combined.append((t, glucose0 + carb_d + ins_d + basal_d))

        # Оси
        PAD_L, PAD_R, PAD_T, PAD_B = 55, 20, 20, 35
        plot_w = w - PAD_L - PAD_R
        plot_h = h - PAD_T - PAD_B

        # Диапазон Y
        all_y = ([glucose0 + v for _, v in carb_curve] +
                 [glucose0 + v for _, v in ins_curve] +
                 [v for _, v in combined])
        y_min = max(0.0, min(all_y) - 1.0)
        y_max = max(all_y) + 1.0
        if y_max - y_min < 4:
            y_max = y_min + 4

        def px(t):   return PAD_L + t / T_MAX * plot_w
        def py(val): return PAD_T + (1 - (val - y_min) / (y_max - y_min)) * plot_h

        # ── Зоны ──────────────────────────────────────────────────────────────
        s       = database.get_settings()
        tgt_min = s.get('target_glucose_min', 5.0)
        tgt_max = s.get('target_glucose_max', 8.0)

        y_tgt_min_px = py(tgt_min)
        y_tgt_max_px = py(tgt_max)
        # Зелёная полоса целевого диапазона
        self.canvas.create_rectangle(
            PAD_L, max(PAD_T, y_tgt_max_px),
            w - PAD_R, min(PAD_T + plot_h, y_tgt_min_px),
            fill='#eafaf1', outline='', tags='bg')
        # Горизонтальные линии
        for gl_val, dash in [(tgt_min, (4, 3)), (tgt_max, (4, 3))]:
            yp = py(gl_val)
            if PAD_T <= yp <= PAD_T + plot_h:
                self.canvas.create_line(PAD_L, yp, w - PAD_R, yp,
                                        fill='#82e0aa', dash=dash)

        # ── Сетка и оси ───────────────────────────────────────────────────────
        self.canvas.create_rectangle(PAD_L, PAD_T, w - PAD_R, PAD_T + plot_h,
                                      outline='#cccccc')

        # Горизонтальные линии сетки (ммоль/л)
        step_y = 1.0
        y_tick = math.ceil(y_min)
        while y_tick <= y_max:
            yp = py(y_tick)
            if PAD_T <= yp <= PAD_T + plot_h:
                self.canvas.create_line(PAD_L, yp, w - PAD_R, yp,
                                        fill='#eeeeee')
                self.canvas.create_text(PAD_L - 4, yp, text=f"{y_tick:.0f}",
                                        anchor='e', font=('Segoe UI', 8),
                                        fill='#666666')
            y_tick += step_y

        # Вертикальные линии сетки (время)
        for t_tick in range(0, T_MAX + 1, 30):
            xp = px(t_tick)
            self.canvas.create_line(xp, PAD_T, xp, PAD_T + plot_h,
                                    fill='#eeeeee')
            label = f"{t_tick}′" if t_tick % 60 != 0 else f"{t_tick // 60}ч"
            self.canvas.create_text(xp, PAD_T + plot_h + 5, text=label,
                                    anchor='n', font=('Segoe UI', 8),
                                    fill='#666666')

        # ── Кривые ────────────────────────────────────────────────────────────
        def draw_curve(points, color, dash=(), width=2):
            if len(points) < 2:
                return
            pts = []
            for t, val in points:
                xp = px(t)
                yp = py(val)
                yp = max(PAD_T, min(PAD_T + plot_h, yp))
                pts.extend([xp, yp])
            self.canvas.create_line(*pts, fill=color, width=width,
                                    dash=dash, smooth=True)

        # Синяя: только еда — куда пойдёт сахар без укола
        if carb_curve:
            draw_curve([(t, glucose0 + v) for t, v in carb_curve],
                       '#2980b9', dash=(6, 3))

        # Красная: только укол — куда пойдёт сахар без еды
        if ins_curve:
            draw_curve([(t, glucose0 + ins_map.get(t + offset_min, 0))
                        for t in times],
                       '#e74c3c', dash=(6, 3))

        # Итоговый прогноз (зелёная сплошная, жирная)
        draw_curve(combined, '#27ae60', width=3)

        # ── Метка текущего момента ────────────────────────────────────────────
        self.canvas.create_line(px(0), PAD_T, px(0), PAD_T + plot_h,
                                fill='#34495e', width=1, dash=(3, 2))
        self.canvas.create_oval(px(0) - 4, py(glucose0) - 4,
                                px(0) + 4, py(glucose0) + 4,
                                fill='#34495e', outline='white', width=1)
        self.canvas.create_text(px(0) + 6, py(glucose0) - 8,
                                text=f"{glucose0:.1f}",
                                anchor='w', font=('Segoe UI', 9, 'bold'),
                                fill='#34495e')

        # ── Метка момента укола ───────────────────────────────────────────────
        if insulin > 0:
            shot_t = -offset_min   # время укола относительно начала еды
            # shot_t > 0: укол до еды (в прошлом от точки t=0)
            # shot_t = 0: одновременно
            # shot_t < 0: укол после начала еды (в будущем от t=0)
            if shot_t >= 0:
                # Укол был до или в момент еды — рисуем метку на оси
                shot_x = px(0)   # всегда в t=0, т.к. ось = начало еды
                shot_label = f"💉 −{offset_min}′" if offset_min > 0 else "💉 сейчас"
                shot_glucose = glucose0 + ins_map.get(0, 0)
            else:
                # Укол будет после начала еды — рисуем на t = |offset_min|
                shot_t_draw = abs(offset_min)
                shot_x = px(shot_t_draw)
                combined_at_shot = next((v for t, v in combined if t == shot_t_draw), glucose0)
                shot_glucose = combined_at_shot
                shot_label = f"💉 +{abs(offset_min)}′"

            # Вертикальная пунктирная линия в момент укола
            if shot_t < 0:   # укол после еды — рисуем вертикаль
                self.canvas.create_line(
                    shot_x, PAD_T, shot_x, PAD_T + plot_h,
                    fill='#e74c3c', width=1, dash=(3, 3))
            self.canvas.create_text(
                shot_x + 4, PAD_T + 6,
                text=shot_label, anchor='nw',
                font=('Segoe UI', 8, 'bold'), fill='#e74c3c')

        # ── Итоговые показатели ───────────────────────────────────────────────
        if combined:
            peak_val  = max(v for _, v in combined)
            peak_t    = next(t for t, v in combined if v == peak_val)
            final_val = combined[-1][1]
            basal_rate = self._get_basal_rate_per_min()
            basal_info = f"  │  Базал: {basal_rate*60:.2f} ммоль/ч" if basal_rate > 0 else ""
            summary = (f"Пик: {peak_val:.1f} ммоль/л (t={peak_t}′)  "
                       f"│  Через 4 ч: {final_val:.1f} ммоль/л{basal_info}")
            self.canvas.create_text(w // 2, h - 5, text=summary,
                                    anchor='s', font=('Segoe UI', 8),
                                    fill='#34495e')

    def _draw_error(self, msg: str):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        self.canvas.create_text(w // 2, h // 2, text=msg,
                                fill='red', font=('Segoe UI', 10))
