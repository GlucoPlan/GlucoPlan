import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import database
import os
from PIL import Image, ImageTk
from config import BASE_DIR
from theme import FONT_BOLD, COLOR_ROW_EVEN, COLOR_ROW_ODD


class DishesTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.current_dish_id  = None
        self.pans_list        = []
        self.products_list    = []
        self.dish_items       = []
        self.photo_image      = None

        self.create_widgets()
        self.bind('<Map>', self.on_tab_show)
        self.load_pans()
        self.load_products()
        self.refresh_dishes_list()

    def on_tab_show(self, event):
        self.load_pans()
        self.load_products()
        if self.current_dish_id is not None:
            self.load_dish_details()
        self.refresh_dishes_list()

    # ── Компоновка ────────────────────────────────────────────────────────────

    def create_widgets(self):
        # Горизонтальный PanedWindow: список блюд слева, детали справа
        pw = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        pw.pack(fill='both', expand=True, padx=6, pady=6)

        # ── Левая панель: список блюд ─────────────────────────────────────────
        left = ttk.Frame(pw, width=220)
        pw.add(left, weight=0)
        left.pack_propagate(False)

        ttk.Label(left, text="Блюда", font=FONT_BOLD).pack(anchor='w', padx=6, pady=(6, 2))

        lf = ttk.Frame(left)
        lf.pack(fill='both', expand=True, padx=4)
        lf.columnconfigure(0, weight=1)
        lf.rowconfigure(0, weight=1)

        vsb = ttk.Scrollbar(lf, orient='vertical')
        vsb.grid(row=0, column=1, sticky='ns')
        self.dishes_listbox = tk.Listbox(lf, yscrollcommand=vsb.set,
                                          font=('Segoe UI', 10),
                                          selectbackground='#0078d7',
                                          selectforeground='white',
                                          activestyle='none',
                                          relief='flat', borderwidth=1)
        self.dishes_listbox.grid(row=0, column=0, sticky='nsew')
        vsb.config(command=self.dishes_listbox.yview)
        self.dishes_listbox.bind('<<ListboxSelect>>', self.on_dish_select)

        bf = ttk.Frame(left)
        bf.pack(fill='x', padx=4, pady=4)
        ttk.Button(bf, text="+ Новое",  command=self.new_dish).pack(side='left', padx=2)
        ttk.Button(bf, text="Удалить",  command=self.delete_dish).pack(side='left', padx=2)

        # ── Правая панель: детали блюда ───────────────────────────────────────
        right = ttk.Frame(pw)
        pw.add(right, weight=1)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)

        # ── Поля блюда ────────────────────────────────────────────────────────
        meta = ttk.LabelFrame(right, text="Параметры блюда", padding=8)
        meta.grid(row=0, column=0, sticky='ew', pady=(0, 6))
        meta.columnconfigure(1, weight=1)

        # Левая колонка полей + правая (фото)
        fields_col = ttk.Frame(meta)
        fields_col.grid(row=0, column=0, sticky='nsew')
        fields_col.columnconfigure(1, weight=1)

        photo_col = ttk.Frame(meta, width=180, height=180)
        photo_col.grid(row=0, column=1, padx=(12, 0), sticky='ne')
        photo_col.pack_propagate(False)
        self.pan_photo_label = ttk.Label(photo_col, relief='solid', borderwidth=1,
                                          text='Нет фото', anchor='center')
        self.pan_photo_label.pack(fill='both', expand=True)

        pad = dict(padx=(0, 6), pady=3)
        ttk.Label(fields_col, text="Название:").grid(row=0, column=0, sticky='e', **pad)
        self.name_var  = tk.StringVar()
        self.name_entry = ttk.Entry(fields_col, textvariable=self.name_var, width=38)
        self.name_entry.grid(row=0, column=1, sticky='ew', **pad)
        self.name_entry.bind('<FocusOut>', lambda e: self.save_dish_details())

        ttk.Label(fields_col, text="Кастрюля:").grid(row=1, column=0, sticky='e', **pad)
        self.pan_var   = tk.StringVar()
        self.pan_combo = ttk.Combobox(fields_col, textvariable=self.pan_var, width=36, state='readonly')
        self.pan_combo.grid(row=1, column=1, sticky='ew', **pad)
        self.pan_combo.bind('<<ComboboxSelected>>', self.on_pan_selected)

        ttk.Label(fields_col, text="Вес БРУТТО готового (г):").grid(row=2, column=0, sticky='e', **pad)
        self.weight_var = tk.StringVar()
        we = ttk.Entry(fields_col, textvariable=self.weight_var, width=14)
        we.grid(row=2, column=1, sticky='w', **pad)
        we.bind('<FocusOut>', lambda e: self.save_dish_details())

        ttk.Label(fields_col, text="Вес НЕТТО (г):").grid(row=3, column=0, sticky='e', **pad)
        self.net_weight_var = tk.StringVar(value='—')
        ttk.Label(fields_col, textvariable=self.net_weight_var,
                  foreground='gray').grid(row=3, column=1, sticky='w', **pad)

        ttk.Label(fields_col, text="Углеводы / 100 г (г):").grid(row=4, column=0, sticky='e', **pad)
        self.carbs_per_100_var = tk.StringVar(value='—')
        ttk.Label(fields_col, textvariable=self.carbs_per_100_var,
                  font=FONT_BOLD).grid(row=4, column=1, sticky='w', **pad)

        # ── Состав ───────────────────────────────────────────────────────────
        comp_hdr = ttk.Frame(right)
        comp_hdr.grid(row=1, column=0, sticky='ew', pady=(0, 4))
        ttk.Label(comp_hdr, text="Состав блюда:", font=FONT_BOLD).pack(side='left')
        ttk.Button(comp_hdr, text="+ Добавить",   command=self.add_product_to_dish).pack(side='left', padx=6)
        ttk.Button(comp_hdr, text="Изменить вес", command=self.edit_product_weight).pack(side='left', padx=2)
        ttk.Button(comp_hdr, text="Удалить",      command=self.delete_product_from_dish).pack(side='left', padx=2)

        tf = ttk.Frame(right)
        tf.grid(row=2, column=0, sticky='nsew')
        tf.columnconfigure(0, weight=1)
        tf.rowconfigure(0, weight=1)

        cols = ('product', 'carbs_per_100', 'carbs_total', 'weight')
        self.comp_tree = ttk.Treeview(tf, columns=cols, show='headings',
                                       style="App.Treeview")
        specs = [
            ('product',      'Продукт',          200, 'w',      True),
            ('carbs_per_100', 'Углеводы г/100 г', 120, 'center', False),
            ('carbs_total',   'Углеводы г',        100, 'center', False),
            ('weight',        'Вес (г)',            90, 'center', False),
        ]
        for col, text, w, anchor, stretch in specs:
            self.comp_tree.heading(col, text=text)
            self.comp_tree.column(col, width=w, anchor=anchor, minwidth=40, stretch=stretch)

        self.comp_tree.tag_configure('even', background=COLOR_ROW_EVEN)
        self.comp_tree.tag_configure('odd',  background=COLOR_ROW_ODD)

        vsb2 = ttk.Scrollbar(tf, orient='vertical', command=self.comp_tree.yview)
        self.comp_tree.configure(yscrollcommand=vsb2.set)
        self.comp_tree.grid(row=0, column=0, sticky='nsew')
        vsb2.grid(row=0, column=1, sticky='ns')

        self.comp_tree.bind('<Double-1>', lambda e: self.edit_product_weight())

    # ── Данные ───────────────────────────────────────────────────────────────

    def load_pans(self):
        self.pans_list = [(0, '— нет —', 0, None)]
        for p in database.get_all_pans():
            self.pans_list.append((p['id'], p['name'], p['weight'], p['photo_path']))
        self.pan_combo['values'] = [name for _, name, _, _ in self.pans_list]

    def load_products(self):
        self.products_list = [(p['id'], p['name']) for p in database.get_all_products()]

    def refresh_dishes_list(self):
        cur = self.current_dish_id
        self.dishes_listbox.delete(0, tk.END)
        self.dish_items = []
        for d in database.get_all_dishes():
            self.dishes_listbox.insert(tk.END, d['name'])
            self.dish_items.append((d['id'], d['name']))
        if cur is not None:
            for i, (did, _) in enumerate(self.dish_items):
                if did == cur:
                    self.dishes_listbox.selection_set(i)
                    break

    def on_dish_select(self, event):
        sel = self.dishes_listbox.curselection()
        if not sel:
            return
        self.current_dish_id = self.dish_items[sel[0]][0]
        self.load_dish_details()

    def load_dish_details(self):
        if self.current_dish_id is None:
            self.clear_right(); return
        dish = database.get_dish(self.current_dish_id)
        if not dish:
            return
        self.name_var.set(dish['name'])
        pan_id = dish['default_pan_id']
        pan_idx, photo = 0, None
        for i, (pid, _, _, ph) in enumerate(self.pans_list):
            if pid == pan_id:
                pan_idx, photo = i, ph; break
        self.pan_combo.current(pan_idx)
        self.show_pan_photo(photo)
        self.weight_var.set(str(dish['default_cooked_weight']) if dish['default_cooked_weight'] else '')
        self.refresh_composition_table()
        self.update_dish_info()

    def on_pan_selected(self, event):
        self.save_dish_details()
        idx = self.pan_combo.current()
        if 0 <= idx < len(self.pans_list):
            self.show_pan_photo(self.pans_list[idx][3])
        self.update_dish_info()

    def show_pan_photo(self, photo_path):
        if not photo_path:
            self.pan_photo_label.config(image='', text='Нет фото')
            return
        try:
            fp = photo_path if os.path.isabs(photo_path) else os.path.join(BASE_DIR, photo_path)
            if os.path.exists(fp):
                img = Image.open(fp).resize((180, 180), Image.Resampling.LANCZOS)
                self.photo_image = ImageTk.PhotoImage(img)
                self.pan_photo_label.config(image=self.photo_image, text='')
            else:
                self.pan_photo_label.config(image='', text='Фото не найдено')
        except Exception:
            self.pan_photo_label.config(image='', text='Ошибка загрузки')

    def clear_right(self):
        self.name_var.set('')
        if self.pan_combo['values']:
            self.pan_combo.current(0)
        self.weight_var.set('')
        self.net_weight_var.set('—')
        self.carbs_per_100_var.set('—')
        self.pan_photo_label.config(image='', text='Нет фото')
        for r in self.comp_tree.get_children():
            self.comp_tree.delete(r)

    def update_dish_info(self):
        if self.current_dish_id is None:
            self.net_weight_var.set('—')
            self.carbs_per_100_var.set('—')
            return
        ws = self.weight_var.get().strip()
        idx = self.pan_combo.current()
        pw  = self.pans_list[idx][2] if 0 <= idx < len(self.pans_list) else 0
        net = None
        if ws and pw > 0:
            try:
                gross = float(ws)
                net   = gross - pw
                self.net_weight_var.set(f"{net:.1f}" if net >= 0 else "Ошибка: вес < 0")
                if net <= 0:
                    net = None
            except ValueError:
                self.net_weight_var.set('—')
        else:
            self.net_weight_var.set('—')

        comp = database.get_dish_composition(self.current_dish_id)
        if not comp:
            self.carbs_per_100_var.set('—'); return
        total_c = sum(database.get_product(i['product_id'])['carbs'] * i['weight'] / 100
                      for i in comp if database.get_product(i['product_id']))
        if net and net > 0:
            self.carbs_per_100_var.set(f"{total_c * 100 / net:.1f}")
        else:
            self.carbs_per_100_var.set('—')

    def save_dish_details(self):
        if self.current_dish_id is None:
            return
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Ошибка", "Название не может быть пустым")
            dish = database.get_dish(self.current_dish_id)
            if dish:
                self.name_var.set(dish['name'])
            return
        idx    = self.pan_combo.current()
        pan_id = self.pans_list[idx][0] if idx >= 0 else None
        if pan_id == 0:
            pan_id = None
        ws = self.weight_var.get().strip()
        try:
            weight = float(ws) if ws else None
        except ValueError:
            messagebox.showerror("Ошибка", "Вес должен быть числом")
            return
        database.update_dish(self.current_dish_id, name, pan_id, weight)
        self.refresh_dishes_list()
        self.update_dish_info()

    def refresh_composition_table(self):
        for r in self.comp_tree.get_children():
            self.comp_tree.delete(r)
        if self.current_dish_id is None:
            return
        for i, item in enumerate(database.get_dish_composition(self.current_dish_id)):
            p = database.get_product(item['product_id'])
            if p:
                c100  = p['carbs']
                ctot  = c100 * item['weight'] / 100
                tag   = 'even' if i % 2 == 0 else 'odd'
                self.comp_tree.insert('', 'end', tags=(tag, item['product_id']),
                    values=(item['product_name'], f"{c100:.1f}", f"{ctot:.1f}",
                            f"{item['weight']:.1f}"))
        self.update_dish_info()

    # ── CRUD блюд ─────────────────────────────────────────────────────────────

    def new_dish(self):
        name = simpledialog.askstring("Новое блюдо", "Введите название:", parent=self)
        if not name:
            return
        try:
            did = database.add_dish(name, None, None)
        except Exception as ex:
            messagebox.showerror("Ошибка", str(ex)); return
        self.refresh_dishes_list()
        for i, (d, _) in enumerate(self.dish_items):
            if d == did:
                self.dishes_listbox.selection_set(i)
                self.current_dish_id = did
                self.load_dish_details()
                break

    def delete_dish(self):
        if self.current_dish_id is None:
            messagebox.showwarning("Предупреждение", "Выберите блюдо"); return
        if messagebox.askyesno("Удаление", f"Удалить блюдо «{self.name_var.get()}»?"):
            database.delete_dish(self.current_dish_id)
            self.current_dish_id = None
            self.refresh_dishes_list()
            self.clear_right()

    # ── Состав ────────────────────────────────────────────────────────────────

    def add_product_to_dish(self):
        if self.current_dish_id is None:
            messagebox.showwarning("Предупреждение", "Выберите блюдо"); return

        dlg = tk.Toplevel(self)
        dlg.title("Добавить продукт в состав")
        dlg.transient(self); dlg.grab_set()
        dlg.geometry("420x520")
        dlg.columnconfigure(0, weight=1)
        dlg.rowconfigure(1, weight=1)

        ttk.Label(dlg, text="Найдите и выберите продукт:").grid(
            row=0, column=0, padx=10, pady=(10, 4), sticky='w')

        # Поле поиска
        sv = tk.StringVar()
        se = ttk.Entry(dlg, textvariable=sv, width=44)
        se.grid(row=0, column=0, padx=10, pady=(36, 4), sticky='ew')
        se.focus_set()

        lf = ttk.Frame(dlg)
        lf.grid(row=1, column=0, sticky='nsew', padx=10, pady=4)
        lf.columnconfigure(0, weight=1)
        lf.rowconfigure(0, weight=1)
        vsb = ttk.Scrollbar(lf, orient='vertical'); vsb.grid(row=0, column=1, sticky='ns')
        lb  = tk.Listbox(lf, yscrollcommand=vsb.set, font=('Segoe UI', 10),
                          selectbackground='#0078d7', selectforeground='white',
                          activestyle='none', relief='flat')
        lb.grid(row=0, column=0, sticky='nsew')
        vsb.config(command=lb.yview)

        products = database.get_all_products()
        prod_map = {p['name']: p['id'] for p in products}
        all_names = [p['name'] for p in products]

        def refresh_lb(*_):
            q = sv.get().lower()
            lb.delete(0, tk.END)
            for n in all_names:
                if q in n.lower():
                    lb.insert(tk.END, n)
        sv.trace('w', refresh_lb); refresh_lb()

        bottom = ttk.Frame(dlg)
        bottom.grid(row=2, column=0, sticky='ew', padx=10, pady=6)
        ttk.Label(bottom, text="Вес (г):").pack(side='left')
        weight_e = ttk.Entry(bottom, width=10); weight_e.pack(side='left', padx=6)
        weight_e.insert(0, "100")

        selected = [None]
        def on_select(e=None):
            sel = lb.curselection()
            if sel:
                selected[0] = lb.get(sel[0])
                weight_e.focus_set()
        lb.bind('<<ListboxSelect>>', on_select)
        lb.bind('<Double-1>', lambda e: add())
        se.bind('<Return>', lambda e: (lb.curselection() and add()) or None)

        def add():
            name = selected[0]
            if not name:
                sel = lb.curselection()
                if sel:
                    name = lb.get(sel[0])
            if not name:
                messagebox.showerror("Ошибка", "Выберите продукт", parent=dlg); return
            try:
                weight = float(weight_e.get())
                if weight <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Ошибка", "Укажите положительный вес", parent=dlg); return
            pid  = prod_map[name]
            comp = database.get_dish_composition(self.current_dish_id)
            if any(i['product_id'] == pid for i in comp):
                if messagebox.askyesno("Подтверждение",
                        f"«{name}» уже в составе. Заменить вес?", parent=dlg):
                    database.update_dish_composition(self.current_dish_id, pid, weight)
                else:
                    return
            else:
                database.add_dish_composition(self.current_dish_id, pid, weight)
            self.refresh_composition_table(); dlg.destroy()

        bf = ttk.Frame(dlg); bf.grid(row=3, column=0, pady=8)
        ttk.Button(bf, text="Добавить", command=add,         width=14).pack(side='left', padx=5)
        ttk.Button(bf, text="Отмена",   command=dlg.destroy, width=14).pack(side='left', padx=5)

    def edit_product_weight(self):
        if self.current_dish_id is None:
            return
        sel = self.comp_tree.selection()
        if not sel:
            messagebox.showwarning("Предупреждение", "Выберите продукт в составе"); return
        item   = self.comp_tree.item(sel[0])
        pid    = item['tags'][1]
        cur_w  = item['values'][3]
        new_w  = simpledialog.askfloat("Изменить вес", "Новый вес (г):",
                                        initialvalue=cur_w, parent=self)
        if new_w and new_w > 0:
            database.update_dish_composition(self.current_dish_id, pid, new_w)
            self.refresh_composition_table()

    def delete_product_from_dish(self):
        if self.current_dish_id is None:
            return
        sel = self.comp_tree.selection()
        if not sel:
            messagebox.showwarning("Предупреждение", "Выберите продукт в составе"); return
        item = self.comp_tree.item(sel[0])
        pid  = item['tags'][1]
        name = item['values'][0]
        if messagebox.askyesno("Удаление", f"Удалить «{name}» из состава?"):
            database.delete_dish_composition(self.current_dish_id, pid)
            self.refresh_composition_table()
