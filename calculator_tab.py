import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime
import threading
import database
from utils import calculate_product_nutrition, calculate_gn, calculate_xe
from config import DEFAULT_CARBS_PER_XE
from theme import FONT_BOLD, FONT_BIG, COLOR_ROW_EVEN, COLOR_ROW_ODD

DATE_FORMAT = "%Y-%m-%d %H:%M"


def _parse_datetime(s):
    try:
        return datetime.strptime(s.strip(), DATE_FORMAT)
    except ValueError:
        return None


class CalculatorTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.components   = []
        self.products_list = []
        self.dishes_list  = []
        self.pans_list    = []
        self.carbs_per_xe = DEFAULT_CARBS_PER_XE
        self.insulin_step = 0.5
        self.insulin_factors = {
            'carb_coefficient': 1.0,
            'target_glucose':   6.0,
            'sensitivity':      2.0,
        }
        self.insulin_food_var  = tk.StringVar(value="0.0")
        self.insulin_corr_var  = tk.StringVar(value="0.0")
        self.insulin_dose_var  = tk.StringVar(value="0.0")
        self.insulin_lower_var = tk.StringVar(value="0.0")
        self.insulin_upper_var = tk.StringVar(value="0.0")
        self.target_dose_var   = tk.StringVar(value="lower")
        self._trend_delta      = 0.0
        self._glucose_from_cgm = False  # True если сахар подставлен CGM, False = ручной ввод
        self.ns_widget         = None

        self.create_widgets()
        self.load_lists()
        self.load_settings()
        self.bind('<Map>', self.on_tab_show)

    def on_tab_show(self, event):
        self.load_lists()
        self.load_settings()

    def load_settings(self):
        s = database.get_settings()
        if not s:
            return
        self.insulin_factors['carb_coefficient'] = s.get('carb_coefficient', 1.0)
        self.insulin_factors['target_glucose']   = s.get('target_glucose', 6.0)
        self.insulin_factors['sensitivity']      = s.get('sensitivity', 2.0)
        self.carbs_per_xe = s.get('carbs_per_xe', DEFAULT_CARBS_PER_XE)
        self.insulin_step = s.get('insulin_step', 0.5)
        # Обновляем отображаемые поля (только те, что остались в калькуляторе)
        self.carb_coef_var.set(str(self.insulin_factors['carb_coefficient']))
        self.target_glucose_var.set(str(self.insulin_factors['target_glucose']))
        self.sensitivity_var.set(str(self.insulin_factors['sensitivity']))
        self.carbs_per_xe_var.set(str(self.carbs_per_xe))
        self.update_insulin_dose()

    # ── Автосохранение инлайн-полей калькулятора ─────────────────────────────

    def _save_field(self, key, var, old_val, positive=True, callback=None):
        try:
            val = float(var.get())
            if positive and val <= 0:
                raise ValueError
            s = database.get_settings() or {}
            s[key] = val
            database.save_settings(s)
            if callback:
                callback(val)
            self.update_insulin_dose()
        except ValueError:
            var.set(str(old_val))

    def save_carb_coef(self, e=None):
        def cb(v): self.insulin_factors['carb_coefficient'] = v
        self._save_field('carb_coefficient', self.carb_coef_var,
                         self.insulin_factors['carb_coefficient'], callback=cb)

    def save_target_glucose(self, e=None):
        def cb(v): self.insulin_factors['target_glucose'] = v
        self._save_field('target_glucose', self.target_glucose_var,
                         self.insulin_factors['target_glucose'], callback=cb)

    def save_sensitivity(self, e=None):
        def cb(v): self.insulin_factors['sensitivity'] = v
        self._save_field('sensitivity', self.sensitivity_var,
                         self.insulin_factors['sensitivity'], callback=cb)

    def save_xe_coefficient(self, e=None):
        def cb(v):
            self.carbs_per_xe = v
            self.update_totals()
        self._save_field('carbs_per_xe', self.carbs_per_xe_var, self.carbs_per_xe, callback=cb)

    # ── Компоновка ───────────────────────────────────────────────────────────

    def create_widgets(self):
        # Главный вертикальный PanedWindow — верхняя часть (таблица) и нижняя (итоги+инсулин)
        main_pw = ttk.PanedWindow(self, orient=tk.VERTICAL)
        main_pw.pack(fill='both', expand=True, padx=6, pady=6)

        # ══ Верхняя область ══════════════════════════════════════════════════
        top = ttk.Frame(main_pw)
        main_pw.add(top, weight=3)

        btn_frame = ttk.Frame(top)
        btn_frame.pack(fill='x', pady=(0, 4))
        ttk.Button(btn_frame, text="+ Блюдо",          command=self.add_dish).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="+ Продукт",        command=self.add_product).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Удалить выбранное", command=self.delete_component).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Очистить всё",      command=self.clear_all).pack(side='left', padx=12)

        cols = ('adjust', 'name', 'calories', 'proteins', 'fats', 'carbs', 'carbs_amount', 'gn', 'weight')
        self.tree = ttk.Treeview(top, columns=cols, show='headings', style="App.Treeview")
        specs = [
            ('adjust',       'Корр.',         52, 'center', False),
            ('name',         'Название',      240, 'w',     True),
            ('calories',     'Ккал/100г',      80, 'center', False),
            ('proteins',     'Б/100г',         65, 'center', False),
            ('fats',         'Ж/100г',         65, 'center', False),
            ('carbs',        'У/100г',         65, 'center', False),
            ('carbs_amount', 'Углеводы (г)',   90, 'center', False),
            ('gn',           'ГН/100г',        72, 'center', False),
            ('weight',       'Вес порции (г)', 100, 'center', False),
        ]
        for col, text, w, anchor, stretch in specs:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w, anchor=anchor, minwidth=40, stretch=stretch)

        self.tree.tag_configure('dish',    font=FONT_BOLD, background=COLOR_ROW_EVEN)
        self.tree.tag_configure('product', background=COLOR_ROW_ODD)

        vsb = ttk.Scrollbar(top, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        self.tree.bind('<Double-1>', self.on_item_double_click)
        self.tree.bind('<Button-1>', self.on_tree_click)

        # ══ Нижняя область ═══════════════════════════════════════════════════
        bottom_pw = ttk.PanedWindow(main_pw, orient=tk.HORIZONTAL)
        main_pw.add(bottom_pw, weight=1)

        # ── Итоги (левая часть низа) ──────────────────────────────────────────
        totals_frame = ttk.LabelFrame(bottom_pw, text="Итого за приём", padding=8)
        bottom_pw.add(totals_frame, weight=2)

        self.total_vars = {k: tk.StringVar(value='0.0')
                           for k in ('calories', 'proteins', 'fats', 'carbs', 'gn', 'xe')}

        rows_data = [
            [("Калории:",  'calories', "ккал"), ("Белки:",  'proteins', "г")],
            [("Жиры:",     'fats',     "г"),    ("Углеводы:", 'carbs',  "г")],
            [("ГН:",       'gn',       ""),     ("ХЕ:",     'xe',       "")],
        ]
        for r, row in enumerate(rows_data):
            for c_base, (lbl, key, unit) in enumerate(row):
                col = c_base * 3
                ttk.Label(totals_frame, text=lbl).grid(
                    row=r, column=col, sticky='e', padx=(8, 2), pady=3)
                ttk.Label(totals_frame, textvariable=self.total_vars[key],
                          font=FONT_BOLD, width=8, anchor='e').grid(
                    row=r, column=col+1, sticky='w')
                ttk.Label(totals_frame, text=unit, foreground='gray').grid(
                    row=r, column=col+2, sticky='w', padx=(2, 14))

        # Подсказка по времени укола
        self.timing_var = tk.StringVar(value="")
        self.timing_lbl = ttk.Label(totals_frame, textvariable=self.timing_var,
                                     foreground='#e67e22', wraplength=320,
                                     font=('Segoe UI', 9, 'italic'))
        self.timing_lbl.grid(row=4, column=0, columnspan=6,
                              sticky='w', padx=8, pady=(4, 0))

        ttk.Button(totals_frame, text="💾  Записать приём",
                   command=self.save_meal, style="Save.TButton"
                   ).grid(row=5, column=0, columnspan=6,
                           pady=(8, 4), sticky='w', padx=8)

        # ── Расчёт инсулина (правая часть низа) ──────────────────────────────
        ins_frame = ttk.LabelFrame(bottom_pw, text="Расчёт инсулина", padding=(8, 6))
        bottom_pw.add(ins_frame, weight=1)
        ins_frame.columnconfigure(1, weight=0)
        ins_frame.columnconfigure(3, weight=1)

        # ── CGM-виджет ────────────────────────────────────────────────────────
        from ns_glucose_widget import NSGlucoseWidget
        self.ns_widget = NSGlucoseWidget(
            ins_frame,
            on_glucose_ready=self._on_cgm_glucose,
            compact=True,
        )
        self.ns_widget.grid(row=0, column=0, columnspan=4, sticky='ew', pady=(0, 4))

        ttk.Separator(ins_frame, orient='horizontal').grid(
            row=1, column=0, columnspan=4, sticky='ew', pady=2)

        # ── Коэффициенты — две колонки ────────────────────────────────────────
        self.carb_coef_var       = tk.StringVar(value=str(self.insulin_factors['carb_coefficient']))
        self.target_glucose_var  = tk.StringVar(value=str(self.insulin_factors['target_glucose']))
        self.sensitivity_var     = tk.StringVar(value=str(self.insulin_factors['sensitivity']))
        self.carbs_per_xe_var    = tk.StringVar(value=str(self.carbs_per_xe))
        self.current_glucose_var = tk.StringVar()

        def _lbl(r, c, text):
            ttk.Label(ins_frame, text=text).grid(
                row=r, column=c, sticky='e', padx=(6, 2), pady=2)

        def _ent(r, c, var, save_fn=None):
            e = ttk.Entry(ins_frame, textvariable=var, width=7)
            e.grid(row=r, column=c, sticky='w', pady=2, padx=(0, 6))
            if save_fn:
                e.bind('<FocusOut>', save_fn)
                e.bind('<Return>',   save_fn)
            return e

        _lbl(2, 0, "ед на 1 ХЕ:");        _ent(2, 1, self.carb_coef_var,      self.save_carb_coef)
        _lbl(2, 2, "Цель (ммоль/л):");    _ent(2, 3, self.target_glucose_var, self.save_target_glucose)
        _lbl(3, 0, "1 ед снижает:");      _ent(3, 1, self.sensitivity_var,    self.save_sensitivity)
        _lbl(3, 2, "1 ХЕ = г углев.:");   _ent(3, 3, self.carbs_per_xe_var,   self.save_xe_coefficient)
        _lbl(4, 0, "Текущий сахар:");
        _ent(4, 1, self.current_glucose_var)
        ttk.Label(ins_frame, text="ммоль/л", foreground='gray').grid(
            row=4, column=2, columnspan=2, sticky='w')
        self.current_glucose_var.trace('w', lambda *_: self.update_insulin_dose())

        ttk.Separator(ins_frame, orient='horizontal').grid(
            row=5, column=0, columnspan=4, sticky='ew', pady=3)

        # ── Результаты — горизонтальная строка ────────────────────────────────
        res = ttk.Frame(ins_frame)
        res.grid(row=6, column=0, columnspan=4, sticky='ew', pady=(2, 0))

        def _rcell(parent, lbl_text, var, col, big=False, fg=None):
            ttk.Label(parent, text=lbl_text, foreground='gray',
                      font=('Segoe UI', 8)).grid(row=0, column=col, sticky='s', padx=(4, 1))
            kw = dict(font=FONT_BIG if big else FONT_BOLD, anchor='e', width=5)
            if fg: kw['foreground'] = fg
            ttk.Label(parent, textvariable=var, **kw).grid(
                row=1, column=col, sticky='n', padx=(4, 0))
            ttk.Label(parent, text="ед", foreground='gray',
                      font=('Segoe UI', 8)).grid(row=1, column=col+1, sticky='sw', padx=(1, 4))

        _rcell(res, "На еду",    self.insulin_food_var,  0)
        _rcell(res, "Коррекция", self.insulin_corr_var,  2)

        self.trend_dose_var  = tk.StringVar(value="0.0")
        self.trend_res_lbl   = ttk.Label(res, text="Тренд", foreground='gray', font=('Segoe UI', 8))
        self.trend_res_val   = ttk.Label(res, textvariable=self.trend_dose_var,
                                          font=FONT_BOLD, width=5, anchor='e', foreground='#e67e22')
        self.trend_res_unit  = ttk.Label(res, text="ед", foreground='gray', font=('Segoe UI', 8))
        self._trend_row_visible = False

        ttk.Separator(res, orient='vertical').grid(
            row=0, column=6, rowspan=2, sticky='ns', padx=4)
        _rcell(res, "ИТОГО", self.insulin_dose_var, 7, big=True, fg='#1a6fc4')

        # ── Округление — однострочно ──────────────────────────────────────────
        adj = ttk.Frame(ins_frame)
        adj.grid(row=7, column=0, columnspan=4, sticky='ew', pady=(4, 2))

        ttk.Radiobutton(adj, text="↓", variable=self.target_dose_var,
                        value="lower").pack(side='left')
        ttk.Label(adj, textvariable=self.insulin_lower_var,
                  font=FONT_BOLD, width=5, anchor='e').pack(side='left')
        ttk.Label(adj, text="ед", foreground='gray').pack(side='left', padx=(0, 8))
        ttk.Radiobutton(adj, text="↑", variable=self.target_dose_var,
                        value="upper").pack(side='left')
        ttk.Label(adj, textvariable=self.insulin_upper_var,
                  font=FONT_BOLD, width=5, anchor='e').pack(side='left')
        ttk.Label(adj, text="ед", foreground='gray').pack(side='left', padx=(0, 8))
        ttk.Button(adj, text="Скорректировать",
                   command=self.adjust_meal).pack(side='left', padx=4)

    # ── Загрузка данных ───────────────────────────────────────────────────────

    def load_lists(self):
        prods = database.get_all_products()
        self.products_list = [(p['id'], p['name'], p) for p in prods]

        pans = database.get_all_pans()
        self.pans_list = [(p['id'], p['name'], p['weight']) for p in pans]

        dishes = database.get_all_dishes()
        self.dishes_list = []
        for dish in dishes:
            comp = database.get_dish_composition(dish['id'])
            pw   = self._get_pan_weight(dish['default_pan_id'])
            nw   = None
            if dish['default_cooked_weight'] and pw is not None:
                nw = dish['default_cooked_weight'] - pw
                if nw <= 0:
                    nw = None
            nut = self._calc_dish_nut_per100(comp, nw)
            self.dishes_list.append((dish['id'], dish['name'], comp, nut))

    def _get_pan_weight(self, pan_id):
        if not pan_id:
            return None
        for pid, _, w in self.pans_list:
            if pid == pan_id:
                return w
        return None

    def _calc_dish_nut_per100(self, composition, net_weight=None):
        tc = tp = tf = tcarb = tgn = tiw = 0.0
        for item in composition:
            p = database.get_product(item['product_id'])
            if p:
                n = calculate_product_nutrition(p, item['weight'])
                tc   += n['calories']; tp += n['proteins']
                tf   += n['fats'];     tcarb += n['carbs']
                tgn  += calculate_gn(n['carbs'], p['glycemic_index'])
                tiw  += item['weight']
        div = net_weight if (net_weight and net_weight > 0) else tiw
        if div > 0:
            f = 100 / div
            return dict(calories=tc*f, proteins=tp*f, fats=tf*f, carbs=tcarb*f, gn=tgn*f)
        return None

    # ── Диалог выбора ────────────────────────────────────────────────────────

    def _selection_dialog(self, title, items, label):
        """items = [(display_name, value), ...]  →  returns value or None"""
        dlg = tk.Toplevel(self)
        dlg.title(title); dlg.transient(self); dlg.grab_set()
        dlg.geometry("420x520")

        ttk.Label(dlg, text=label, font=FONT_BOLD).pack(pady=(10, 4))

        sv = tk.StringVar()
        se = ttk.Entry(dlg, textvariable=sv, width=40)
        se.pack(padx=10, pady=(0, 6))
        se.focus_set()

        lf = ttk.Frame(dlg); lf.pack(fill='both', expand=True, padx=10, pady=4)
        vsb = ttk.Scrollbar(lf, orient='vertical'); vsb.pack(side='right', fill='y')
        lb  = tk.Listbox(lf, yscrollcommand=vsb.set, font=('Segoe UI', 10),
                         activestyle='dotbox', selectbackground='#0078d7',
                         selectforeground='white')
        lb.pack(side='left', fill='both', expand=True)
        vsb.config(command=lb.yview)

        all_names = [name for name, _ in items]

        def refresh(*_):
            q = sv.get().lower()
            lb.delete(0, tk.END)
            for n in all_names:
                if q in n.lower():
                    lb.insert(tk.END, n)

        sv.trace('w', refresh); refresh()

        chosen = [None]

        def pick():
            sel = lb.curselection()
            if not sel:
                return
            name = lb.get(sel[0])
            for n, v in items:
                if n == name:
                    chosen[0] = v; break
            dlg.destroy()

        lb.bind('<Double-1>', lambda e: pick())
        se.bind('<Return>',   lambda e: pick())

        bf = ttk.Frame(dlg); bf.pack(pady=10)
        ttk.Button(bf, text="Выбрать", command=pick,        width=14).pack(side='left', padx=5)
        ttk.Button(bf, text="Отмена",  command=dlg.destroy, width=14).pack(side='left', padx=5)

        dlg.wait_window()
        return chosen[0]

    # ── Добавление / удаление ─────────────────────────────────────────────────

    def add_dish(self):
        if not self.dishes_list:
            messagebox.showwarning("Предупреждение", "Сначала создайте хотя бы одно блюдо")
            return
        items = [(name, (did, name, comp, nut))
                 for did, name, comp, nut in self.dishes_list]
        res = self._selection_dialog("Выбор блюда", items, "Выберите блюдо:")
        if res is None:
            return
        dish_id, dish_name, composition, nutrition = res
        if nutrition is None:
            messagebox.showerror("Ошибка",
                f"Блюдо «{dish_name}» не настроено полностью.\n"
                "Задайте вес готового блюда и кастрюлю во вкладке «Блюда».")
            return
        tree_id = self.tree.insert('', 'end', tags=('dish',), values=(
            '☑', f"🍲 {dish_name}",
            f"{nutrition['calories']:.0f}", f"{nutrition['proteins']:.1f}",
            f"{nutrition['fats']:.1f}",     f"{nutrition['carbs']:.1f}",
            "0", f"{nutrition['gn']:.1f}",  "",
        ))
        self.components.append(dict(type='dish', id=dish_id, name=dish_name,
            composition=composition, nutrition_per_100=nutrition,
            serving_weight=None, tree_id=tree_id, adjustable=True))

    def add_product(self):
        if not self.products_list:
            messagebox.showwarning("Предупреждение", "Сначала добавьте продукты во вкладке «Продукты»")
            return
        items = [(name, (pid, name, pdata)) for pid, name, pdata in self.products_list]
        res = self._selection_dialog("Выбор продукта", items, "Выберите продукт:")
        if res is None:
            return
        prod_id, prod_name, prod_data = res
        tree_id = self.tree.insert('', 'end', tags=('product',), values=(
            '☑', f"🍎 {prod_name}",
            f"{prod_data['calories']:.0f}", f"{prod_data['proteins']:.1f}",
            f"{prod_data['fats']:.1f}",     f"{prod_data['carbs']:.1f}",
            "0", f"{calculate_gn(prod_data['carbs'], prod_data['glycemic_index']):.1f}", "",
        ))
        self.components.append(dict(type='product', id=prod_id, name=prod_name,
            product_data=prod_data, serving_weight=None,
            tree_id=tree_id, adjustable=True))

    def delete_component(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Предупреждение", "Выберите строку для удаления")
            return
        if messagebox.askyesno("Удаление", "Удалить выбранный компонент?"):
            tid = sel[0]
            self.components = [c for c in self.components if c.get('tree_id') != tid]
            self.tree.delete(tid)
            self.update_totals(); self.update_insulin_dose()

    def clear_all(self):
        if not self.components:
            return
        if messagebox.askyesno("Очистить", "Очистить весь текущий приём?"):
            self._do_clear()

    def _do_clear(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.components.clear()
        for v in self.total_vars.values():
            v.set("0.0")
        for v in (self.insulin_dose_var, self.insulin_food_var,
                  self.insulin_corr_var, self.insulin_lower_var, self.insulin_upper_var):
            v.set("0.0")

    # ── Взаимодействие с таблицей ─────────────────────────────────────────────

    def on_item_double_click(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        tid  = sel[0]
        comp = next((c for c in self.components if c.get('tree_id') == tid), None)
        if not comp:
            return
        w = simpledialog.askfloat("Вес порции",
            f"Вес порции для «{comp['name']}» (г):",
            initialvalue=comp.get('serving_weight') or 100,
            parent=self)
        if w and w > 0:
            comp['serving_weight'] = w
            n = comp.get('nutrition_per_100') if comp['type'] == 'dish' else None
            pd = comp.get('product_data')
            carbs = (pd['carbs'] * w / 100) if pd else ((n['carbs'] * w / 100) if n else 0)
            vals = list(self.tree.item(tid, 'values'))
            vals[6] = f"{carbs:.1f}"; vals[8] = f"{w:.0f}"
            self.tree.item(tid, values=vals)
            self.update_totals(); self.update_insulin_dose()

    def on_tree_click(self, event):
        if self.tree.identify_region(event.x, event.y) != 'cell':
            return
        if self.tree.identify_column(event.x) != '#1':
            return
        item = self.tree.identify_row(event.y)
        if not item:
            return
        vals = list(self.tree.item(item, 'values'))
        vals[0] = '☐' if vals[0] == '☑' else '☑'
        self.tree.item(item, values=vals)
        for c in self.components:
            if c.get('tree_id') == item:
                c['adjustable'] = (vals[0] == '☑'); break

    # ── Расчёты ──────────────────────────────────────────────────────────────

    def update_totals(self):
        tc = tp = tf = tcarb = tgn = 0.0
        for comp in self.components:
            if not comp.get('serving_weight'):
                continue
            w = comp['serving_weight']
            if comp['type'] == 'product':
                pd = comp['product_data']
                n  = calculate_product_nutrition(pd, w)
                tc += n['calories']; tp += n['proteins']
                tf += n['fats'];     tcarb += n['carbs']
                tgn += calculate_gn(n['carbs'], pd['glycemic_index'])
            else:
                n = comp.get('nutrition_per_100')
                if n:
                    f = w / 100
                    tc += n['calories']*f; tp += n['proteins']*f
                    tf += n['fats']*f;     tcarb += n['carbs']*f
                    tgn += n['gn']*f
        xe = calculate_xe(tcarb, self.carbs_per_xe)
        self.total_vars['calories'].set(f"{tc:.1f}")
        self.total_vars['proteins'].set(f"{tp:.1f}")
        self.total_vars['fats'].set(f"{tf:.1f}")
        self.total_vars['carbs'].set(f"{tcarb:.1f}")
        self.total_vars['gn'].set(f"{tgn:.1f}")
        self.total_vars['xe'].set(f"{xe:.2f}")
        self._update_timing_hint(tcarb)

    def _post_to_nightscout(self, meal_id, carbs_g, insulin_units,
                             glucose_mmol, notes, dt_str):
        """Отправляет приём пищи на NightScout в фоновом потоке."""
        cfg = database.get_ns_config()
        if cfg.get('enabled') != '1' or not cfg.get('url', '').strip():
            return

        def _worker():
            try:
                from nightscout import NightScoutClient, NightScoutConfig
                from datetime import datetime as _dt
                client = NightScoutClient(NightScoutConfig(
                    url=cfg['url'], token=cfg.get('token', ''), enabled=True))
                meal_dt = _dt.strptime(dt_str, "%Y-%m-%d %H:%M")
                client.post_meal(
                    carbs_g=carbs_g,
                    insulin_units=insulin_units,
                    glucose_mmol=glucose_mmol,
                    notes=notes,
                    dt=meal_dt,
                )
                database.log_ns_sync(meal_id, 'ok', 'Отправлено успешно')
            except Exception as ex:
                database.log_ns_sync(meal_id, 'error', str(ex))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_cgm_glucose(self, mmol: float, trend_delta: float):
        """
        Колбэк от NSGlucoseWidget — вызывается при получении свежего показания.
        Всегда обновляет поле «текущий сахар» (CGM-данные свежее ручного ввода).
        """
        self._trend_delta      = trend_delta
        self._glucose_from_cgm = True   # помечаем, что значение пришло от CGM

        # Временно отключаем trace, чтобы не вызывать update_insulin_dose дважды
        self.current_glucose_var.set(f"{mmol:.1f}")

        self.update_insulin_dose()
        self._update_trend_row_visibility(trend_delta)

    def _update_trend_row_visibility(self, delta: float):
        """Показывает/скрывает ячейку тренда в строке результатов."""
        if not hasattr(self, 'trend_res_lbl'):
            return
        if delta != 0 and not self._trend_row_visible:
            self.trend_res_lbl.grid(row=0, column=4, sticky='s', padx=(4, 1))
            self.trend_res_val.grid(row=1, column=4, sticky='n', padx=(4, 0))
            self.trend_res_unit.grid(row=1, column=5, sticky='sw', padx=(1, 4))
            self._trend_row_visible = True
        elif delta == 0 and self._trend_row_visible:
            self.trend_res_lbl.grid_remove()
            self.trend_res_val.grid_remove()
            self.trend_res_unit.grid_remove()
            self._trend_row_visible = False

    def _update_timing_hint(self, total_carbs: float):
        """
        Показывает рекомендацию по времени укола Фиаспа/Люмьева.
        Фиасп: пик 30–45 мин, быстрое начало — можно колоть за 0–5 мин до еды.
        При высоком сахаре (> цели) — лучше за 10–15 мин до еды.
        При низком (< цели) — после еды или во время.
        """
        if not hasattr(self, 'timing_var') or total_carbs < 0.5:
            if hasattr(self, 'timing_var'):
                self.timing_var.set("")
            return

        try:
            cur_gl  = float(self.current_glucose_var.get() or 0)
            target  = self.insulin_factors['target_glucose']
        except ValueError:
            cur_gl = 0
            target = 6.0

        s = database.get_ns_config()
        insulin_type = s.get('insulin_type', 'fiasp')

        if insulin_type == 'fiasp':
            if cur_gl <= 0:
                hint = "⏱ Фиасп: колите за 0–5 мин до начала еды"
            elif cur_gl > target + 2:
                hint = f"⏱ Фиасп: сахар высокий ({cur_gl:.1f}) — колите за 10–15 мин до еды"
            elif cur_gl < target - 1:
                hint = f"⏱ Фиасп: сахар низкий ({cur_gl:.1f}) — колите в начале еды или после"
            else:
                hint = "⏱ Фиасп: колите за 0–5 мин до начала еды"
        elif insulin_type == 'novorapid':
            if cur_gl > target + 2:
                hint = f"⏱ Новорапид: сахар высокий — колите за 20–30 мин до еды"
            elif cur_gl < target - 1:
                hint = f"⏱ Новорапид: сахар низкий — колите в начале еды"
            else:
                hint = "⏱ Новорапид: колите за 15–20 мин до начала еды"
        else:
            hint = ""

        self.timing_var.set(hint)

    def update_insulin_dose(self, *_):
        try:
            xe        = float(self.total_vars['xe'].get())
            food_dose = xe * self.insulin_factors['carb_coefficient']
            self.insulin_food_var.set(f"{food_dose:.1f}")

            cur_gl = float(self.current_glucose_var.get() or 0)
            corr   = max(0.0, (cur_gl - self.insulin_factors['target_glucose'])
                         / self.insulin_factors['sensitivity']) if cur_gl > 0 else 0.0
            self.insulin_corr_var.set(f"{corr:.1f}")

            # Поправка тренда CGM
            trend = self._trend_delta
            if trend != 0 and hasattr(self, 'trend_dose_var'):
                sign = '+' if trend > 0 else ''
                self.trend_dose_var.set(f"{sign}{trend:.1f}")

            total  = food_dose + corr + trend
            self.insulin_dose_var.set(f"{total:.1f}")

            step   = self.insulin_step
            lower  = max(0.0, (total // step) * step)
            upper  = lower + step
            self.insulin_lower_var.set(f"{lower:.1f}")
            self.insulin_upper_var.set(f"{upper:.1f}")
        except (ValueError, ZeroDivisionError):
            for v in (self.insulin_food_var, self.insulin_corr_var, self.insulin_dose_var,
                      self.insulin_lower_var, self.insulin_upper_var):
                v.set("0.0")

    # ── Корректировка порции ─────────────────────────────────────────────────

    def adjust_meal(self):
        for comp in self.components:
            if not comp.get('serving_weight'):
                messagebox.showerror("Ошибка", f"«{comp['name']}»: не указан вес порции")
                return
        target = self.target_dose_var.get()
        t_dose = float(self.insulin_lower_var.get() if target == 'lower' else self.insulin_upper_var.get())
        c_dose = float(self.insulin_dose_var.get())
        if abs(c_dose - t_dose) < 0.01:
            messagebox.showinfo("Инфо", "Текущая доза уже равна целевой"); return

        total_carbs = sum(
            (c['product_data']['carbs'] * c['serving_weight'] / 100
             if c['type'] == 'product'
             else (c['nutrition_per_100']['carbs'] * c['serving_weight'] / 100
                   if c.get('nutrition_per_100') else 0))
            for c in self.components)

        corr   = float(self.insulin_corr_var.get())
        t_carbs = (t_dose - corr) * self.carbs_per_xe / self.insulin_factors['carb_coefficient']
        if t_carbs < 0:
            messagebox.showerror("Ошибка", "Целевая доза слишком мала"); return

        adj = [{'comp': c,
                'cur_carbs': c['product_data']['carbs'] * c['serving_weight'] / 100,
                'c100': c['product_data']['carbs']}
               for c in self.components
               if c['type'] == 'product' and c.get('adjustable')]
        if not adj:
            messagebox.showwarning("Предупреждение", "Нет отмеченных продуктов для корректировки")
            return
        total_adj = sum(a['cur_carbs'] for a in adj)
        if total_adj == 0:
            messagebox.showerror("Ошибка", "Сумма углеводов отмеченных продуктов = 0"); return

        delta = t_carbs - total_carbs
        for a in adj:
            share      = a['cur_carbs'] / total_adj
            new_carbs  = max(0.0, a['cur_carbs'] + delta * share)
            new_weight = max(0.0, new_carbs * 100 / a['c100'])
            a['comp']['serving_weight'] = new_weight
            pd  = a['comp']['product_data']
            tid = a['comp']['tree_id']
            self.tree.item(tid, values=(
                '☑' if a['comp']['adjustable'] else '☐',
                f"🍎 {a['comp']['name']}",
                f"{pd['calories']:.0f}", f"{pd['proteins']:.1f}",
                f"{pd['fats']:.1f}",     f"{pd['carbs']:.1f}",
                f"{new_carbs:.1f}",
                f"{calculate_gn(pd['carbs'], pd['glycemic_index']):.1f}",
                f"{new_weight:.0f}",
            ))
        self.update_totals(); self.update_insulin_dose()
        messagebox.showinfo("Успех", f"Веса скорректированы — целевая доза {t_dose:.1f} ед")

    # ── Сохранение приёма ────────────────────────────────────────────────────

    def save_meal(self):
        if not self.components:
            messagebox.showwarning("Предупреждение", "Нет компонентов для сохранения"); return
        for c in self.components:
            if not c.get('serving_weight'):
                messagebox.showerror("Ошибка", f"«{c['name']}»: не указан вес порции"); return

        dlg = tk.Toplevel(self)
        dlg.title("Запись приёма пищи"); dlg.transient(self); dlg.grab_set()
        dlg.resizable(False, False)

        now = datetime.now().strftime(DATE_FORMAT)

        ttk.Label(dlg, text="Дата и время (ГГГГ-ММ-ДД ЧЧ:ММ):").grid(
            row=0, column=0, padx=12, pady=(14, 4), sticky='e')
        dt_var = tk.StringVar(value=now)
        ttk.Entry(dlg, textvariable=dt_var, width=20).grid(row=0, column=1, padx=12, pady=(14, 4), sticky='w')

        # Итоги в диалоге
        sf = ttk.LabelFrame(dlg, text="Итоги приёма", padding=6)
        sf.grid(row=1, column=0, columnspan=2, padx=12, pady=6, sticky='ew')
        ttk.Label(sf, text=f"Углеводы: {self.total_vars['carbs'].get()} г   "
                            f"ХЕ: {self.total_vars['xe'].get()}   "
                            f"Калории: {self.total_vars['calories'].get()} ккал"
                  ).pack()

        ttk.Label(dlg, text="Сахар (ммоль/л):").grid(
            row=2, column=0, padx=12, pady=4, sticky='e')
        gl_var = tk.StringVar(value=self.current_glucose_var.get())
        ttk.Entry(dlg, textvariable=gl_var, width=10).grid(row=2, column=1, padx=12, pady=4, sticky='w')

        ttk.Label(dlg, text="Доза инсулина (ед):").grid(
            row=3, column=0, padx=12, pady=4, sticky='e')
        ins_var = tk.StringVar(value=self.insulin_dose_var.get())
        ttk.Entry(dlg, textvariable=ins_var, width=10).grid(row=3, column=1, padx=12, pady=4, sticky='w')

        ttk.Label(dlg, text="Примечание:").grid(
            row=4, column=0, padx=12, pady=4, sticky='e')
        notes_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=notes_var, width=28).grid(row=4, column=1, padx=12, pady=4, sticky='w')

        def do_save():
            dt_s = dt_var.get().strip()
            if _parse_datetime(dt_s) is None:
                messagebox.showerror("Ошибка",
                    f"Неверный формат даты.\nОжидается: ГГГГ-ММ-ДД ЧЧ:ММ\nПример: {now}",
                    parent=dlg); return
            gl  = gl_var.get().strip()
            ins = ins_var.get().strip()
            notes = notes_var.get().strip() or None
            db_comps = []
            for comp in self.components:
                if comp['type'] == 'product':
                    db_comps.append(dict(type='product', id=comp['id'],
                        name=comp['name'], serving_weight=comp['serving_weight']))
                else:
                    portion = []
                    if comp.get('composition'):
                        tw = sum(i['weight'] for i in comp['composition'])
                        if tw > 0:
                            f = comp['serving_weight'] / tw
                            portion = [dict(product_id=i['product_id'], weight=i['weight']*f)
                                       for i in comp['composition']]
                    db_comps.append(dict(type='dish', id=comp['id'],
                        name=comp['name'], serving_weight=comp['serving_weight'],
                        composition=portion))
            try:
                meal_id = database.save_meal(
                    dt_s, float(ins) if ins else None, notes, db_comps,
                    float(gl) if gl else None)
                messagebox.showinfo("Сохранено", "Приём пищи записан в историю")
                dlg.destroy()

                # ── Отправка на NightScout в фоне ────────────────────────
                self._post_to_nightscout(
                    meal_id=meal_id,
                    carbs_g=float(self.total_vars['carbs'].get()),
                    insulin_units=float(ins) if ins else 0.0,
                    glucose_mmol=float(gl) if gl else None,
                    notes=notes or '',
                    dt_str=dt_s,
                )

                if messagebox.askyesno("Очистить", "Очистить текущий приём?"):
                    self._do_clear()
                    self._trend_delta = 0.0
            except Exception as ex:
                messagebox.showerror("Ошибка", str(ex), parent=dlg)

        bf = ttk.Frame(dlg)
        bf.grid(row=5, column=0, columnspan=2, pady=12)
        ttk.Button(bf, text="Сохранить", command=do_save,      width=14).pack(side='left', padx=5)
        ttk.Button(bf, text="Отмена",    command=dlg.destroy,  width=14).pack(side='left', padx=5)
