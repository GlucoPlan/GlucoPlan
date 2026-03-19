import tkinter as tk
from tkinter import ttk, messagebox
import database
import theme
from products_tab   import ProductsTab
from pans_tab       import PansTab
from dishes_tab     import DishesTab
from calculator_tab import CalculatorTab
from history_tab    import HistoryTab
from settings_tab   import SettingsTab
from simulator_tab  import SimulatorTab
from version        import __version__, GITHUB_REPO
import updater


def populate_initial_data():
    """Начальная база продуктов. Порядок: name, calories, proteins, fats, carbs, gi."""
    if database.count_products() > 0:
        return
    products = [
        # name,                          cal,  prot,  fat,  carb,   gi
        # Овощи
        ("Перец болгарский красный",       27,   1.3,  0.1,   5.3,  15),
        ("Фасоль стручковая",              23,   2.5,  0.3,   3.0,  15),
        ("Помидоры",                       20,   1.1,  0.2,   3.7,  15),
        ("Картофель сырой",                80,   2.0,  0.4,  16.0,  70),
        ("Лук репчатый",                   41,   1.4,  0.0,   9.7,  15),
        ("Огурец свежий",                  10,   0.7,  0.1,   1.8,  15),
        ("Капуста белокочанная",            27,   1.8,  0.1,   4.7,  15),
        ("Салат листовой",                  14,   1.5,  0.2,   2.2,  15),
        ("Шпинат",                          22,   2.9,  0.3,   2.0,  15),
        ("Морковь сырая",                   32,   1.3,  0.1,   6.9,  35),
        ("Свёкла сырая",                    48,   1.7,  0.1,  10.8,  30),
        ("Картофель отварной",              82,   2.0,  0.4,  17.0,  70),
        # Крупы
        ("Гречка отварная",                101,   3.6,  2.2,  17.1,  50),
        ("Овсянка на воде",                 88,   3.0,  1.7,  15.0,  53),
        ("Рис бурый отварной",             111,   2.6,  0.9,  23.0,  50),
        ("Рис белый отварной",             116,   2.2,  0.5,  25.0,  70),
        ("Перловка отварная",              106,   3.1,  0.4,  22.2,  25),
        ("Макароны отварные",              131,   4.0,  0.9,  26.0,  50),
        ("Пшено отварное",                 105,   3.0,  0.8,  21.0,  70),
        # Хлеб
        ("Хлеб цельнозерновой",            210,   8.1,  1.2,  42.0,  45),
        ("Хлеб белый",                     236,   7.9,  1.0,  51.9,  70),
        # Белковые
        ("Куриная грудка отварная",        140,  29.0,  2.0,   0.0,   0),
        ("Индейка филе",                   110,  25.0,  1.0,   0.0,   0),
        ("Говядина постная",               158,  22.0,  7.0,   0.0,   0),
        ("Рыба белая (треска)",             78,  18.0,  0.6,   0.0,   0),
        ("Лосось",                         190,  20.0, 12.0,   0.0,   0),
        ("Яйцо куриное",                   157,  12.7, 10.9,   0.7,   0),
        # Бобовые
        ("Чечевица отварная",              116,   9.0,  0.4,  20.0,  30),
        ("Нут отварной",                   164,   8.9,  2.6,  27.0,  35),
        ("Фасоль красная отварная",        123,   7.8,  0.5,  21.0,  35),
        ("Горох отварной",                 118,   8.0,  0.4,  20.0,  45),
        # Фрукты
        ("Яблоко зелёное",                  45,   0.4,  0.4,  10.4,  35),
        ("Груша",                           42,   0.4,  0.3,  10.7,  35),
        ("Апельсин",                        40,   0.9,  0.2,   9.5,  40),
        ("Грейпфрут",                       33,   0.7,  0.2,   7.3,  25),
        ("Клубника",                        35,   0.8,  0.4,   7.5,  40),
        ("Малина",                          43,   0.8,  0.5,   9.0,  30),
        ("Черника",                         40,   1.0,  0.5,   8.0,  45),
        ("Банан",                           95,   1.5,  0.2,  21.8,  55),
        ("Виноград",                        69,   0.6,  0.3,  17.5,  55),
        ("Арбуз",                           38,   0.6,  0.1,   9.0,  70),
        # Молочные
        ("Молоко 2,5%",                     52,   2.8,  2.5,   4.7,  30),
        ("Кефир 2,5%",                      53,   2.8,  2.5,   4.0,  30),
        ("Творог 5%",                      121,  17.2,  5.0,   1.8,  30),
        ("Творог 0%",                       86,  18.0,  0.6,   1.8,  30),
        ("Сыр твёрдый",                    360,  25.0, 30.0,   0.5,   0),
        ("Йогурт натуральный",              60,   4.0,  2.5,   5.0,  35),
        ("Сметана 15%",                    160,   2.8, 15.0,   3.2,   0),
        # Орехи
        ("Миндаль",                        645,  18.6, 57.8,  13.7,  15),
        ("Грецкий орех",                   649,  15.2, 61.3,  10.1,  15),
        ("Семечки подсолнечника",          575,  20.6, 53.0,   5.0,  15),
        ("Арахис",                         548,  26.3, 45.1,   9.6,  15),
        # Прочее
        ("Мёд",                            308,   0.8,  0.0,  80.3,  60),
        ("Сахар",                          374,   0.0,  0.0,  99.8,  70),
        ("Сладкие соки",                    48,   0.5,  0.0,  11.7,  60),
        ("Печенье сладкое",                430,   7.0, 15.0,  65.0,  65),
    ]
    for name, cal, prot, fat, carb, gi in products:
        try:
            database.add_product(name, cal, prot, fat, carb, gi)
        except Exception as e:
            print(f"Ошибка при добавлении '{name}': {e}")


class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"GlucoPlan  v{__version__}")
        self.root.geometry("1150x730")
        self.root.minsize(900, 600)

        # Применяем единую тему ПОСЛЕ создания root
        theme.apply_theme()

        # Кнопка справки — ПЕРЕД notebook чтобы была сверху
        help_bar = ttk.Frame(root)
        help_bar.pack(fill='x', padx=4, pady=(4, 0))
        ttk.Button(help_bar, text="❓ Справка",
                   command=self.open_help).pack(side='right', padx=4)
        ttk.Label(help_bar, text="GlucoPlan",
                  font=('Segoe UI', 9), foreground='gray').pack(side='left', padx=4)

        nb = ttk.Notebook(root)
        nb.pack(fill='both', expand=True, padx=4, pady=(2, 4))
        self.notebook = nb

        self.calculator_tab = CalculatorTab(nb)
        nb.add(self.calculator_tab, text="  Калькулятор  ")

        self.history_tab = HistoryTab(nb, calculator_tab=self.calculator_tab)
        nb.add(self.history_tab, text="  История  ")

        self.products_tab = ProductsTab(nb)
        nb.add(self.products_tab, text="  Продукты  ")

        self.dishes_tab = DishesTab(nb)
        nb.add(self.dishes_tab, text="  Блюда  ")

        self.pans_tab = PansTab(nb)
        nb.add(self.pans_tab, text="  Кастрюли  ")

        self.settings_tab = SettingsTab(nb)
        nb.add(self.settings_tab, text="  Настройки  ")

        self.simulator_tab = SimulatorTab(nb, calculator_tab=self.calculator_tab)
        nb.add(self.simulator_tab, text="  Симулятор  ")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Проверка обновлений в фоне (не чаще раза в сутки)
        if GITHUB_REPO != "your-username/GlucoPlan":
            self._start_update_check()

    def _start_update_check(self):
        """Запускает фоновую проверку обновлений если прошло > 23 ч."""
        if not updater.should_check_today(database):
            self._apply_update_result_from_db()
            return
        updater.mark_checked(database)
        updater.check_for_updates(
            GITHUB_REPO, __version__,
            callback=self._on_update_checked)

    def _on_update_checked(self, result: dict):
        """Колбэк из фонового потока — обновляем UI через after()."""
        updater.save_update_result(database, result)
        self.root.after(0, lambda: self._apply_update_result(result))

    def _apply_update_result_from_db(self):
        """Читает сохранённый результат из БД и показывает баннер."""
        cfg = database.get_ns_config()
        if cfg.get('update_available') == '1':
            result = {
                'available': True,
                'version':   cfg.get('update_version', ''),
                'url':       cfg.get('update_url', ''),
                'error':     None,
            }
            self._apply_update_result(result)
        else:
            # Показываем «всё в порядке» если уже проверяли сегодня
            self._apply_update_result({'available': False, 'error': None})

    def _apply_update_result(self, result: dict):
        """Передаёт результат в вкладку Настройки."""
        if hasattr(self, 'settings_tab'):
            self.settings_tab.show_update_banner(result)

    def open_help(self):
        """Открывает HTML-справку в браузере по умолчанию."""
        import webbrowser
        import os
        help_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'help.html')
        if os.path.exists(help_path):
            webbrowser.open(f'file:///{help_path.replace(os.sep, "/")}')
        else:
            from tkinter import messagebox
            messagebox.showinfo("Справка",
                "Файл справки help.html не найден рядом с программой.")

    def on_close(self):
        if self.calculator_tab.components:
            ans = messagebox.askyesnocancel(
                "Выход",
                "В калькуляторе есть несохранённые данные.\nВыйти без сохранения?")
            if ans is None:
                return
            if not ans:
                self.notebook.select(self.calculator_tab)
                return
        self.root.destroy()


if __name__ == "__main__":
    from logger import log, log_error
    import sys

    log(f"Запуск GlucoPlan, Python {sys.version.split()[0]}")
    log(f"База данных: {database.DB_PATH}")

    try:
        database.init_db()
        log("БД инициализирована")
        populate_initial_data()
    except Exception as e:
        log_error("Ошибка инициализации БД", e)
        raise

    root = tk.Tk()
    app  = MainApp(root)
    log("Приложение запущено")
    root.mainloop()
    log("Приложение закрыто")
