import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import shutil
import database
from config import PANS_PHOTO_DIR
from theme import COLOR_ROW_EVEN, COLOR_ROW_ODD


class PansTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.create_widgets()
        self.refresh_table()
        self.bind('<Map>', lambda e: self.refresh_table())

    def create_widgets(self):
        btn = ttk.Frame(self)
        btn.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Button(btn, text="Добавить",      command=self.add_pan).pack(side='left', padx=2)
        ttk.Button(btn, text="Редактировать", command=self.edit_pan).pack(side='left', padx=2)
        ttk.Button(btn, text="Удалить",       command=self.delete_pan).pack(side='left', padx=2)

        tf = ttk.Frame(self)
        tf.pack(fill='both', expand=True, padx=8, pady=(0, 8))
        tf.columnconfigure(0, weight=1)
        tf.rowconfigure(0, weight=1)

        cols = ('id', 'name', 'weight', 'photo')
        self.tree = ttk.Treeview(tf, columns=cols, show='headings',
                                 selectmode='browse', style="App.Treeview")
        specs = [
            ('id',     'ID',        45,  'center', False),
            ('name',   'Название', 200,  'w',      True),
            ('weight', 'Вес (г)',  100,  'center', False),
            ('photo',  'Фото',     260,  'w',      False),
        ]
        for col, text, w, anchor, stretch in specs:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w, anchor=anchor, minwidth=40, stretch=stretch)

        self.tree.tag_configure('even', background=COLOR_ROW_EVEN)
        self.tree.tag_configure('odd',  background=COLOR_ROW_ODD)

        vsb = ttk.Scrollbar(tf, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')

        self.tree.bind('<Double-1>', lambda e: self.edit_pan())

    def refresh_table(self):
        for r in self.tree.get_children():
            self.tree.delete(r)
        for i, p in enumerate(database.get_all_pans()):
            photo = os.path.basename(p['photo_path']) if p['photo_path'] else ''
            tag   = 'even' if i % 2 == 0 else 'odd'
            self.tree.insert('', 'end', tags=(tag,), values=(
                p['id'], p['name'],
                f"{p['weight']:.0f}" if p['weight'] else '0',
                photo,
            ))

    def add_pan(self):    self._edit_dialog()
    def edit_pan(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Предупреждение", "Выберите кастрюлю для редактирования")
            return
        self._edit_dialog(self.tree.item(sel[0])['values'][0])

    def delete_pan(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Предупреждение", "Выберите кастрюлю для удаления")
            return
        name = self.tree.item(sel[0])['values'][1]
        if messagebox.askyesno("Удаление",
                f"Удалить кастрюлю «{name}»?\nФото с диска удалено не будет."):
            database.delete_pan(self.tree.item(sel[0])['values'][0])
            self.refresh_table()

    def _edit_dialog(self, pan_id=None):
        dlg = tk.Toplevel(self)
        dlg.title("Добавление кастрюли" if pan_id is None else "Редактирование кастрюли")
        dlg.transient(self); dlg.grab_set(); dlg.resizable(False, False)
        pad = dict(padx=8, pady=5)

        ttk.Label(dlg, text="Название:").grid(row=0, column=0, sticky='e', **pad)
        name_e = ttk.Entry(dlg, width=28); name_e.grid(row=0, column=1, columnspan=2, sticky='w', **pad)

        ttk.Label(dlg, text="Вес тары (г):").grid(row=1, column=0, sticky='e', **pad)
        weight_e = ttk.Entry(dlg, width=14); weight_e.grid(row=1, column=1, sticky='w', **pad)

        ttk.Label(dlg, text="Фото:").grid(row=2, column=0, sticky='e', **pad)
        photo_var = tk.StringVar()
        photo_e = ttk.Entry(dlg, textvariable=photo_var, width=22, state='readonly')
        photo_e.grid(row=2, column=1, sticky='w', **pad)
        ttk.Button(dlg, text="Обзор…",
                   command=lambda: self._pick_photo(photo_var)).grid(row=2, column=2, **pad)

        if pan_id:
            p = database.get_pan(pan_id)
            if p:
                name_e.insert(0, p['name'])
                weight_e.insert(0, str(p['weight']))
                if p['photo_path']:
                    photo_var.set(p['photo_path'])

        def save():
            name = name_e.get().strip()
            if not name:
                messagebox.showerror("Ошибка", "Название обязательно", parent=dlg); return
            try:
                weight = float(weight_e.get())
                if weight <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Ошибка", "Вес должен быть положительным числом", parent=dlg)
                return
            photo = photo_var.get().strip() or None
            try:
                if pan_id is None: database.add_pan(name, weight, photo)
                else:              database.update_pan(pan_id, name, weight, photo)
                dlg.destroy(); self.refresh_table()
            except Exception as ex:
                messagebox.showerror("Ошибка", str(ex), parent=dlg)

        bf = ttk.Frame(dlg); bf.grid(row=3, column=0, columnspan=3, pady=12)
        ttk.Button(bf, text="Сохранить", command=save,       width=14).pack(side='left', padx=5)
        ttk.Button(bf, text="Отмена",   command=dlg.destroy, width=14).pack(side='left', padx=5)

    def _pick_photo(self, var):
        fn = filedialog.askopenfilename(
            title="Выберите фото",
            filetypes=[("Изображения", "*.jpg *.jpeg *.png *.bmp"), ("Все файлы", "*.*")])
        if not fn:
            return
        try:
            base = os.path.basename(fn)
            dst  = os.path.join(PANS_PHOTO_DIR, base)
            n, ext = os.path.splitext(base)
            cnt = 1
            while os.path.exists(dst):
                dst = os.path.join(PANS_PHOTO_DIR, f"{n}_{cnt}{ext}"); cnt += 1
            shutil.copy2(fn, dst)
            var.set(os.path.relpath(dst, start=os.path.dirname(database.DB_PATH)))
        except Exception as ex:
            messagebox.showerror("Ошибка", f"Не удалось скопировать фото: {ex}")
