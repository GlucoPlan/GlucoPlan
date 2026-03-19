import tkinter as tk
from tkinter import ttk, messagebox
import database
from utils import calculate_gn, calculate_xe
from config import DEFAULT_CARBS_PER_XE
from theme import FONT_BOLD, COLOR_ROW_EVEN, COLOR_ROW_ODD


class HistoryTab(ttk.Frame):
    def __init__(self, parent, calculator_tab=None):
        super().__init__(parent)
        self.calculator_tab = calculator_tab
        self.create_widgets()
        self.refresh_list()
        self.bind('<Map>', lambda e: self.refresh_list())

    def create_widgets(self):
        btn = ttk.Frame(self)
        btn.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Button(btn, text="Обновить",                command=self.refresh_list).pack(side='left', padx=2)
        ttk.Button(btn, text="Просмотреть",             command=self.view_meal).pack(side='left', padx=2)
        ttk.Button(btn, text="Копировать в калькулятор", command=self.copy_to_calculator).pack(side='left', padx=2)
        ttk.Button(btn, text="Удалить",                 command=self.delete_meal).pack(side='left', padx=2)

        tf = ttk.Frame(self)
        tf.pack(fill='both', expand=True, padx=8, pady=(0, 8))
        tf.columnconfigure(0, weight=1)
        tf.rowconfigure(0, weight=1)

        cols = ('id', 'datetime', 'glucose', 'insulin', 'carbs', 'xe', 'notes')
        self.tree = ttk.Treeview(tf, columns=cols, show='headings',
                                 selectmode='browse', style="App.Treeview")

        specs = [
            ('id',       'ID',               45, 'center', False),
            ('datetime', 'Дата и время',     145, 'center', False),
            ('glucose',  'Сахар (ммоль/л)',   95, 'center', False),
            ('insulin',  'Инсулин (ед)',       90, 'center', False),
            ('carbs',    'Углеводы (г)',        85, 'center', False),
            ('xe',       'ХЕ',                 65, 'center', False),
            ('notes',    'Примечание',         200, 'w',    True),
        ]
        for col, text, w, anchor, stretch in specs:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w, anchor=anchor, minwidth=40, stretch=stretch)

        self.tree.tag_configure('even', background=COLOR_ROW_EVEN)
        self.tree.tag_configure('odd',  background=COLOR_ROW_ODD)

        vsb = ttk.Scrollbar(tf, orient='vertical',   command=self.tree.yview)
        hsb = ttk.Scrollbar(tf, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        self.tree.bind('<Double-1>', lambda e: self.view_meal())

    def refresh_list(self):
        for r in self.tree.get_children():
            self.tree.delete(r)
        settings     = database.get_settings()
        carbs_per_xe = settings.get('carbs_per_xe', DEFAULT_CARBS_PER_XE)
        meals = database.get_all_meals()
        for i, m in enumerate(meals):
            glucose = f"{m['glucose']:.1f}"      if m['glucose']      is not None else ''
            insulin = f"{m['insulin_dose']:.1f}" if m['insulin_dose'] is not None else ''
            notes   = m['notes'] or ''
            tc, xe  = self._calc_totals(m['id'], carbs_per_xe)
            carbs_s = f"{tc:.1f}" if tc > 0 else ''
            xe_s    = f"{xe:.2f}" if tc > 0 else ''
            tag = 'even' if i % 2 == 0 else 'odd'
            self.tree.insert('', 'end', tags=(tag,),
                             values=(m['id'], m['datetime'], glucose, insulin, carbs_s, xe_s, notes))

    def _calc_totals(self, meal_id, carbs_per_xe):
        try:
            comps = database.get_meal_components(meal_id)
            tc = 0.0
            for c in comps:
                if c['component_type'] == 'product':
                    p = database.get_product(c['product_id'])
                    if p:
                        tc += p['carbs'] * c['serving_weight'] / 100
                else:
                    for d in c.get('details', []):
                        p = database.get_product(d['product_id'])
                        if p:
                            tc += p['carbs'] * d['weight'] / 100
            return tc, calculate_xe(tc, carbs_per_xe)
        except Exception:
            return 0.0, 0.0

    def get_selected_meal_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Предупреждение", "Выберите запись в истории")
            return None
        return self.tree.item(sel[0])['values'][0]

    def view_meal(self):
        mid = self.get_selected_meal_id()
        if not mid:
            return
        meal  = database.get_meal(mid)
        comps = database.get_meal_components(mid)
        self._show_details(meal, comps)

    def _show_details(self, meal, components):
        dlg = tk.Toplevel(self)
        dlg.title(f"Приём от {meal['datetime']}")
        dlg.geometry("760x540")
        dlg.transient(self); dlg.grab_set()
        dlg.columnconfigure(0, weight=1)
        dlg.rowconfigure(1, weight=1)

        # Основная информация
        info = ttk.LabelFrame(dlg, text="Основная информация", padding=8)
        info.grid(row=0, column=0, sticky='ew', padx=10, pady=(10, 6))

        items_info = [f"Дата и время: {meal['datetime']}"]
        if 'glucose' in meal.keys() and meal['glucose'] is not None:
            items_info.append(f"Сахар: {meal['glucose']:.1f} ммоль/л")
        if meal['insulin_dose'] is not None:
            items_info.append(f"Инсулин: {meal['insulin_dose']:.1f} ед")
        if meal['notes']:
            items_info.append(f"Примечание: {meal['notes']}")
        for item in items_info:
            ttk.Label(info, text=item).pack(anchor='w')

        # Состав
        comp_lf = ttk.LabelFrame(dlg, text="Состав приёма", padding=6)
        comp_lf.grid(row=1, column=0, sticky='nsew', padx=10, pady=(0, 6))
        comp_lf.columnconfigure(0, weight=1)
        comp_lf.rowconfigure(0, weight=1)

        cols = ('type', 'name', 'weight', 'details')
        tree = ttk.Treeview(comp_lf, columns=cols, show='tree headings',
                            style="App.Treeview")
        tree.heading('type',    text='Тип')
        tree.heading('name',    text='Название')
        tree.heading('weight',  text='Вес (г)')
        tree.heading('details', text='Детали')
        tree.column('type',    width=75,  anchor='center', stretch=False)
        tree.column('name',    width=220, anchor='w',      stretch=True)
        tree.column('weight',  width=80,  anchor='center', stretch=False)
        tree.column('details', width=300, anchor='w',      stretch=True)

        vsb = ttk.Scrollbar(comp_lf, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')

        for comp in components:
            if comp['component_type'] == 'product':
                tree.insert('', 'end', values=(
                    'Продукт', comp.get('product_name', '(удалён)'),
                    f"{comp['serving_weight']:.1f}", ''))
            else:
                det_parts = []
                if comp.get('cooked_dish_weight'):
                    det_parts.append(f"готовый вес: {comp['cooked_dish_weight']:.1f} г")
                if comp.get('pan_id'):
                    pn = self._get_pan_name(comp['pan_id'])
                    if pn:
                        det_parts.append(f"кастрюля: {pn}")
                parent_item = tree.insert('', 'end', values=(
                    'Блюдо', comp.get('dish_name', '(удалено)'),
                    f"{comp['serving_weight']:.1f}", ', '.join(det_parts)))
                for d in comp.get('details', []):
                    tree.insert(parent_item, 'end', values=(
                        '  └ продукт', d.get('product_name', '(удалён)'),
                        f"{d['weight']:.1f}", ''))

        ttk.Button(dlg, text="Закрыть", command=dlg.destroy).grid(
            row=2, column=0, pady=(0, 10))

    def _get_pan_name(self, pan_id):
        if not pan_id:
            return None
        p = database.get_pan(pan_id)
        return p['name'] if p else None

    def copy_to_calculator(self):
        if not self.calculator_tab:
            messagebox.showerror("Ошибка", "Калькулятор недоступен"); return
        mid = self.get_selected_meal_id()
        if not mid:
            return
        comps = database.get_meal_components(mid)
        if not comps:
            messagebox.showwarning("Предупреждение", "Приём пуст"); return

        ct = self.calculator_tab
        ct.components.clear()
        for item in ct.tree.get_children():
            ct.tree.delete(item)

        for comp in comps:
            if comp['component_type'] == 'product':
                prod = database.get_product(comp['product_id'])
                if not prod:
                    continue
                gn    = calculate_gn(prod['carbs'], prod['glycemic_index'])
                carbs = prod['carbs'] * comp['serving_weight'] / 100
                tid   = ct.tree.insert('', 'end', tags=('product',), values=(
                    '☑', f"🍎 {prod['name']}",
                    f"{prod['calories']:.0f}", f"{prod['proteins']:.1f}",
                    f"{prod['fats']:.1f}",     f"{prod['carbs']:.1f}",
                    f"{carbs:.1f}", f"{gn:.1f}", f"{comp['serving_weight']:.0f}",
                ))
                ct.components.append(dict(type='product', id=prod['id'], name=prod['name'],
                    product_data=prod, serving_weight=comp['serving_weight'],
                    tree_id=tid, adjustable=True))
            else:
                dish = database.get_dish(comp['dish_id'])
                if not dish:
                    continue
                composition = database.get_dish_composition(comp['dish_id'])
                pan = database.get_pan(dish['default_pan_id']) if dish['default_pan_id'] else None
                nw  = None
                if pan and dish['default_cooked_weight']:
                    nw = dish['default_cooked_weight'] - pan['weight']
                    if nw <= 0:
                        nw = None
                nut = ct._calc_dish_nut_per100(composition, nw)
                if not nut:
                    continue
                carbs = nut['carbs'] * comp['serving_weight'] / 100
                tid   = ct.tree.insert('', 'end', tags=('dish',), values=(
                    '☑', f"🍲 {dish['name']}",
                    f"{nut['calories']:.0f}", f"{nut['proteins']:.1f}",
                    f"{nut['fats']:.1f}",     f"{nut['carbs']:.1f}",
                    f"{carbs:.1f}", f"{nut['gn']:.1f}", f"{comp['serving_weight']:.0f}",
                ))
                ct.components.append(dict(type='dish', id=dish['id'], name=dish['name'],
                    composition=composition, nutrition_per_100=nut,
                    serving_weight=comp['serving_weight'], tree_id=tid, adjustable=True))

        ct.update_totals(); ct.update_insulin_dose()
        self.master.select(ct)
        messagebox.showinfo("Готово", "Приём скопирован в калькулятор")

    def delete_meal(self):
        mid = self.get_selected_meal_id()
        if not mid:
            return
        if messagebox.askyesno("Удаление", "Удалить эту запись истории?"):
            database.delete_meal(mid)
            self.refresh_list()
