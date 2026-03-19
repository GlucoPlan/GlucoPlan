import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
import database
from theme import FONT_BOLD, COLOR_ROW_EVEN, COLOR_ROW_ODD


class ProductsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._sort_col = 'name'
        self._sort_rev = False
        self.create_widgets()
        self.refresh_table()
        self.bind('<Map>', lambda e: self.refresh_table())

    def create_widgets(self):
        # ── Кнопки ───────────────────────────────────────────────────────────
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill='x', padx=8, pady=(8, 4))

        ttk.Button(btn_frame, text="Добавить",      command=self.add_product).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Редактировать", command=self.edit_product).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Удалить",       command=self.delete_product).pack(side='left', padx=2)
        ttk.Separator(btn_frame, orient='vertical').pack(side='left', fill='y', padx=10)
        ttk.Button(btn_frame, text="⬇ Импорт CSV", command=self.import_csv).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="⬆ Экспорт CSV", command=self.export_csv).pack(side='left', padx=2)

        # ── Поиск ────────────────────────────────────────────────────────────
        sf = ttk.Frame(self)
        sf.pack(fill='x', padx=8, pady=(0, 6))
        ttk.Label(sf, text="Поиск:").pack(side='left', padx=(0, 6))
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *_: self.refresh_table())
        ttk.Entry(sf, textvariable=self.search_var, width=35).pack(side='left')
        ttk.Button(sf, text="✕", width=3,
                   command=lambda: self.search_var.set('')).pack(side='left', padx=4)
        self.count_var = tk.StringVar()
        ttk.Label(sf, textvariable=self.count_var, foreground='gray').pack(side='right', padx=8)

        # ── Таблица ───────────────────────────────────────────────────────────
        tf = ttk.Frame(self)
        tf.pack(fill='both', expand=True, padx=8, pady=(0, 8))
        tf.columnconfigure(0, weight=1)
        tf.rowconfigure(0, weight=1)

        cols = ('id', 'name', 'calories', 'proteins', 'fats', 'carbs', 'gi')
        self.tree = ttk.Treeview(tf, columns=cols, show='headings',
                                 selectmode='browse', style="App.Treeview")

        specs = [
            ('id',       'ID',                   45,  'center'),
            ('name',     'Название',             220,  'w'),
            ('calories', 'Ккал / 100 г',         110,  'center'),
            ('proteins', 'Белки, г / 100 г',     105,  'center'),
            ('fats',     'Жиры, г / 100 г',      105,  'center'),
            ('carbs',    'Углеводы, г / 100 г',  120,  'center'),
            ('gi',       'ГИ',                    55,  'center'),
        ]
        for col, text, w, anchor in specs:
            self.tree.heading(col, text=text, command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=w, anchor=anchor, minwidth=40, stretch=(col == 'name'))

        self.tree.tag_configure('even', background=COLOR_ROW_EVEN)
        self.tree.tag_configure('odd',  background=COLOR_ROW_ODD)

        vsb = ttk.Scrollbar(tf, orient='vertical',   command=self.tree.yview)
        hsb = ttk.Scrollbar(tf, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        self.tree.bind('<Double-1>', lambda e: self.edit_product())

    # ── Данные ───────────────────────────────────────────────────────────────

    def refresh_table(self, *_):
        for r in self.tree.get_children():
            self.tree.delete(r)
        query    = self.search_var.get().lower() if hasattr(self, 'search_var') else ''
        products = database.get_all_products()
        shown    = 0
        for p in products:
            if query and query not in p['name'].lower():
                continue
            tag = 'even' if shown % 2 == 0 else 'odd'
            self.tree.insert('', 'end', tags=(tag,), values=(
                p['id'], p['name'],
                f"{p['calories']:.1f}"  if p['calories']       else '0',
                f"{p['proteins']:.1f}"  if p['proteins']       else '0',
                f"{p['fats']:.1f}"      if p['fats']           else '0',
                f"{p['carbs']:.1f}"     if p['carbs']          else '0',
                str(p['glycemic_index']) if p['glycemic_index'] is not None else '',
            ))
            shown += 1
        total = len(products)
        self.count_var.set(f"Найдено: {shown} из {total}" if query else f"Всего: {total}")

    def _sort_by(self, col):
        if self._sort_col == col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col, self._sort_rev = col, False
        rows = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        try:
            rows.sort(key=lambda t: float(t[0]) if t[0] else -1, reverse=self._sort_rev)
        except ValueError:
            rows.sort(key=lambda t: t[0].lower(), reverse=self._sort_rev)
        for i, (_, k) in enumerate(rows):
            self.tree.move(k, '', i)
            self.tree.item(k, tags=('even' if i % 2 == 0 else 'odd',))

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def add_product(self):    self._edit_dialog()
    def edit_product(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Предупреждение", "Выберите продукт для редактирования")
            return
        self._edit_dialog(self.tree.item(sel[0])['values'][0])

    def delete_product(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Предупреждение", "Выберите продукт для удаления")
            return
        name = self.tree.item(sel[0])['values'][1]
        if messagebox.askyesno("Удаление", f"Удалить продукт «{name}»?"):
            database.delete_product(self.tree.item(sel[0])['values'][0])
            self.refresh_table()

    def _edit_dialog(self, product_id=None):
        dlg = tk.Toplevel(self)
        dlg.title("Добавление продукта" if product_id is None else "Редактирование продукта")
        dlg.transient(self); dlg.grab_set(); dlg.resizable(False, False)
        pad = dict(padx=8, pady=5)
        fields = [
            ('Название:',                   'name',     False),
            ('Калории (ккал / 100 г):',     'calories', True),
            ('Белки (г / 100 г):',          'proteins', True),
            ('Жиры (г / 100 г):',           'fats',     True),
            ('Углеводы (г / 100 г):',       'carbs',    True),
            ('Гликемический индекс (0–100):', 'gi',     True),
        ]
        entries = {}
        prod = database.get_product(product_id) if product_id else None
        for i, (lbl, key, _) in enumerate(fields):
            ttk.Label(dlg, text=lbl).grid(row=i, column=0, sticky='e', **pad)
            e = ttk.Entry(dlg, width=26)
            e.grid(row=i, column=1, sticky='w', **pad)
            entries[key] = e
            if prod:
                if key == 'name':   e.insert(0, prod['name'])
                elif key == 'gi':
                    if prod['glycemic_index'] is not None:
                        e.insert(0, str(prod['glycemic_index']))
                else:               e.insert(0, f"{prod[key]:.1f}")
        entries['name'].focus_set()

        def save():
            try:
                name = entries['name'].get().strip()
                if not name:
                    messagebox.showerror("Ошибка", "Название обязательно", parent=dlg); return
                cal  = float(entries['calories'].get() or 0)
                prot = float(entries['proteins'].get() or 0)
                fat  = float(entries['fats'].get()     or 0)
                carb = float(entries['carbs'].get()    or 0)
                gi_s = entries['gi'].get().strip()
                gi   = int(gi_s) if gi_s else None
                if gi is not None and not (0 <= gi <= 100):
                    messagebox.showerror("Ошибка", "ГИ должен быть от 0 до 100", parent=dlg); return
                if product_id is None: database.add_product(name, cal, prot, fat, carb, gi)
                else:                  database.update_product(product_id, name, cal, prot, fat, carb, gi)
                dlg.destroy(); self.refresh_table()
            except ValueError as ex:
                messagebox.showerror("Ошибка", f"Проверьте числовые поля: {ex}", parent=dlg)

        bf = ttk.Frame(dlg)
        bf.grid(row=len(fields), column=0, columnspan=2, pady=12)
        ttk.Button(bf, text="Сохранить", command=save,       width=14).pack(side='left', padx=5)
        ttk.Button(bf, text="Отмена",   command=dlg.destroy, width=14).pack(side='left', padx=5)
        dlg.bind('<Return>', lambda e: save())

    # ── CSV ──────────────────────────────────────────────────────────────────

    _HEADERS = ('Название', 'Калории', 'Белки', 'Жиры', 'Углеводы', 'ГИ')

    def export_csv(self):
        path = filedialog.asksaveasfilename(
            title="Экспорт продуктов",
            defaultextension=".csv",
            filetypes=[("CSV файлы", "*.csv"), ("Все файлы", "*.*")],
            initialfile="products_export.csv",
        )
        if not path:
            return
        products = database.get_all_products()
        try:
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                w = csv.writer(f, delimiter=';')
                w.writerow(self._HEADERS)
                for p in products:
                    w.writerow([p['name'], p['calories'], p['proteins'], p['fats'], p['carbs'],
                                p['glycemic_index'] if p['glycemic_index'] is not None else ''])
            messagebox.showinfo("Экспорт завершён",
                                f"Экспортировано продуктов: {len(products)}\n{path}")
        except Exception as ex:
            messagebox.showerror("Ошибка экспорта", str(ex))

    def import_csv(self):
        path = filedialog.askopenfilename(
            title="Импорт продуктов из CSV",
            filetypes=[("CSV файлы", "*.csv"), ("Все файлы", "*.*")],
        )
        if not path:
            return

        dlg = tk.Toplevel(self)
        dlg.title("Настройки импорта")
        dlg.transient(self); dlg.grab_set(); dlg.resizable(False, False)

        ttk.Label(dlg, text="Что делать с уже существующими продуктами?",
                  font=FONT_BOLD).grid(row=0, column=0, columnspan=2, padx=14, pady=(14, 8), sticky='w')
        mode_var = tk.StringVar(value='skip')
        modes = [("Пропустить", 'skip'), ("Обновить данные", 'update'),
                 ("Добавить как новый (с суффиксом)", 'add')]
        for i, (txt, val) in enumerate(modes, 1):
            ttk.Radiobutton(dlg, text=txt, variable=mode_var, value=val).grid(
                row=i, column=0, columnspan=2, padx=24, sticky='w', pady=2)

        ttk.Label(dlg, text="Разделитель в файле:").grid(
            row=4, column=0, padx=14, pady=(10, 4), sticky='e')
        sep_var = tk.StringVar(value=';')
        sep_frame = ttk.Frame(dlg)
        sep_frame.grid(row=4, column=1, sticky='w', padx=8)
        for txt, val in [("; (точка с запятой)", ';'), (", (запятая)", ','), ("Tab", '\t')]:
            ttk.Radiobutton(sep_frame, text=txt, variable=sep_var, value=val).pack(anchor='w')

        result = [None]
        def go():
            result[0] = (mode_var.get(), sep_var.get()); dlg.destroy()

        bf = ttk.Frame(dlg); bf.grid(row=5, column=0, columnspan=2, pady=14)
        ttk.Button(bf, text="Импортировать", command=go,          width=16).pack(side='left', padx=5)
        ttk.Button(bf, text="Отмена",        command=dlg.destroy, width=12).pack(side='left', padx=5)
        dlg.wait_window()
        if result[0] is None:
            return
        self._do_import(path, *result[0])

    def _do_import(self, path, mode, sep):
        added = updated = skipped = errors = 0
        err_lines = []
        try:
            with open(path, newline='', encoding='utf-8-sig') as f:
                sample = f.read(512); f.seek(0)
                # Определяем, есть ли заголовок — первый символ не цифра
                has_header = sample.lstrip()[:1] not in '0123456789'
                reader = csv.reader(f, delimiter=sep)
                if has_header:
                    next(reader, None)
                existing = {p['name']: p for p in database.get_all_products()}
                for ln, row in enumerate(reader, 2 if has_header else 1):
                    if not row or not any(r.strip() for r in row):
                        continue
                    try:
                        if len(row) < 5:
                            raise ValueError(f"Нужно минимум 5 столбцов, получено {len(row)}")
                        name = row[0].strip()
                        if not name:
                            raise ValueError("Пустое название")
                        cal  = float(row[1].replace(',', '.'))
                        prot = float(row[2].replace(',', '.'))
                        fat  = float(row[3].replace(',', '.'))
                        carb = float(row[4].replace(',', '.'))
                        gi_s = row[5].strip() if len(row) > 5 else ''
                        gi   = int(gi_s) if gi_s else None
                        if name in existing:
                            if mode == 'skip':
                                skipped += 1
                            elif mode == 'update':
                                p = existing[name]
                                database.update_product(p['id'], name, cal, prot, fat, carb, gi)
                                updated += 1
                            else:
                                n, sfx = name, 1
                                while n in existing:
                                    n = f"{name} ({sfx})"; sfx += 1
                                database.add_product(n, cal, prot, fat, carb, gi)
                                existing[n] = True; added += 1
                        else:
                            database.add_product(name, cal, prot, fat, carb, gi)
                            existing[name] = True; added += 1
                    except Exception as ex:
                        errors += 1
                        err_lines.append(f"Строка {ln}: {ex}")
        except Exception as ex:
            messagebox.showerror("Ошибка чтения файла", str(ex)); return

        self.refresh_table()
        msg = f"Импорт завершён:\n  Добавлено: {added}\n  Обновлено: {updated}\n  Пропущено: {skipped}"
        if errors:
            msg += f"\n  Ошибок: {errors}"
            if err_lines:
                msg += "\n\nПервые ошибки:\n" + "\n".join(err_lines[:5])
        messagebox.showinfo("Импорт CSV", msg)
