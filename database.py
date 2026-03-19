import sqlite3
from config import DB_PATH


def get_connection():
    """Возвращает соединение с БД с включёнными внешними ключами."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Создаёт все таблицы, если они ещё не существуют."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                calories REAL NOT NULL,
                proteins REAL NOT NULL,
                fats REAL NOT NULL,
                carbs REAL NOT NULL,
                glycemic_index INTEGER
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                weight REAL NOT NULL,
                photo_path TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dishes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                default_pan_id INTEGER,
                default_cooked_weight REAL,
                FOREIGN KEY (default_pan_id) REFERENCES pans(id) ON DELETE SET NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dish_composition (
                dish_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                weight REAL NOT NULL,
                PRIMARY KEY (dish_id, product_id),
                FOREIGN KEY (dish_id) REFERENCES dishes(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                datetime TEXT NOT NULL,
                insulin_dose REAL,
                glucose REAL,
                notes TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS meal_components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meal_id INTEGER NOT NULL,
                component_type TEXT NOT NULL CHECK(component_type IN ('product', 'dish')),
                product_id INTEGER,
                dish_id INTEGER,
                serving_weight REAL NOT NULL,
                cooked_dish_weight REAL,
                pan_id INTEGER,
                FOREIGN KEY (meal_id) REFERENCES meals(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL,
                FOREIGN KEY (dish_id) REFERENCES dishes(id) ON DELETE SET NULL,
                FOREIGN KEY (pan_id) REFERENCES pans(id) ON DELETE SET NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS meal_composition_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meal_id INTEGER NOT NULL,
                meal_component_id INTEGER NOT NULL,
                product_id INTEGER,
                weight REAL NOT NULL,
                is_part_of_dish BOOLEAN NOT NULL,
                FOREIGN KEY (meal_id) REFERENCES meals(id) ON DELETE CASCADE,
                FOREIGN KEY (meal_component_id) REFERENCES meal_components(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
            )
        ''')

        # Таблица настроек — создаётся один раз здесь, не в get_settings/save_settings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value REAL
            )
        ''')

        conn.commit()


# ---- Продукты ----

def get_all_products():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products ORDER BY name")
        return cursor.fetchall()


def add_product(name, calories, proteins, fats, carbs, glycemic_index):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO products (name, calories, proteins, fats, carbs, glycemic_index)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, calories, proteins, fats, carbs, glycemic_index))
        conn.commit()
        return cursor.lastrowid


def update_product(product_id, name, calories, proteins, fats, carbs, glycemic_index):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE products
            SET name=?, calories=?, proteins=?, fats=?, carbs=?, glycemic_index=?
            WHERE id=?
        ''', (name, calories, proteins, fats, carbs, glycemic_index, product_id))
        conn.commit()


def delete_product(product_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE id=?", (product_id,))
        conn.commit()


def get_product(product_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE id=?", (product_id,))
        return cursor.fetchone()


def count_products():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM products")
        return cursor.fetchone()[0]


# ---- Кастрюли ----

def get_all_pans():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pans ORDER BY name")
        return cursor.fetchall()


def add_pan(name, weight, photo_path):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO pans (name, weight, photo_path)
            VALUES (?, ?, ?)
        ''', (name, weight, photo_path))
        conn.commit()
        return cursor.lastrowid


def update_pan(pan_id, name, weight, photo_path):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE pans
            SET name=?, weight=?, photo_path=?
            WHERE id=?
        ''', (name, weight, photo_path, pan_id))
        conn.commit()


def delete_pan(pan_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pans WHERE id=?", (pan_id,))
        conn.commit()


def get_pan(pan_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pans WHERE id=?", (pan_id,))
        return cursor.fetchone()


# ---- Блюда ----

def get_all_dishes():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dishes ORDER BY name")
        return cursor.fetchall()


def add_dish(name, default_pan_id=None, default_cooked_weight=None):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO dishes (name, default_pan_id, default_cooked_weight)
            VALUES (?, ?, ?)
        ''', (name, default_pan_id, default_cooked_weight))
        conn.commit()
        return cursor.lastrowid


def update_dish(dish_id, name, default_pan_id=None, default_cooked_weight=None):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE dishes
            SET name=?, default_pan_id=?, default_cooked_weight=?
            WHERE id=?
        ''', (name, default_pan_id, default_cooked_weight, dish_id))
        conn.commit()


def delete_dish(dish_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM dishes WHERE id=?", (dish_id,))
        conn.commit()


def get_dish(dish_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dishes WHERE id=?", (dish_id,))
        return cursor.fetchone()


# ---- Состав блюда ----

def get_dish_composition(dish_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT dc.*, p.name as product_name
            FROM dish_composition dc
            JOIN products p ON dc.product_id = p.id
            WHERE dc.dish_id = ?
            ORDER BY p.name
        ''', (dish_id,))
        return cursor.fetchall()


def add_dish_composition(dish_id, product_id, weight):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO dish_composition (dish_id, product_id, weight)
            VALUES (?, ?, ?)
        ''', (dish_id, product_id, weight))
        conn.commit()


def update_dish_composition(dish_id, product_id, weight):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE dish_composition
            SET weight=?
            WHERE dish_id=? AND product_id=?
        ''', (weight, dish_id, product_id))
        conn.commit()


def delete_dish_composition(dish_id, product_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM dish_composition
            WHERE dish_id=? AND product_id=?
        ''', (dish_id, product_id))
        conn.commit()


# ---- Приёмы пищи ----

def save_meal(datetime_str, insulin_dose, notes, components, glucose=None):
    """Сохраняет приём пищи."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO meals (datetime, insulin_dose, notes, glucose)
            VALUES (?, ?, ?, ?)
        ''', (datetime_str, insulin_dose, notes, glucose))
        meal_id = cursor.lastrowid

        for comp in components:
            if comp['type'] == 'product':
                cursor.execute('''
                    INSERT INTO meal_components
                    (meal_id, component_type, product_id, serving_weight)
                    VALUES (?, ?, ?, ?)
                ''', (meal_id, 'product', comp['id'], comp['serving_weight']))
                comp_id = cursor.lastrowid
                cursor.execute('''
                    INSERT INTO meal_composition_details
                    (meal_id, meal_component_id, product_id, weight, is_part_of_dish)
                    VALUES (?, ?, ?, ?, 0)
                ''', (meal_id, comp_id, comp['id'], comp['serving_weight']))
            else:  # dish
                cursor.execute('''
                    INSERT INTO meal_components
                    (meal_id, component_type, dish_id, serving_weight)
                    VALUES (?, ?, ?, ?)
                ''', (meal_id, 'dish', comp['id'], comp['serving_weight']))
                comp_id = cursor.lastrowid
                for prod in comp.get('composition', []):
                    cursor.execute('''
                        INSERT INTO meal_composition_details
                        (meal_id, meal_component_id, product_id, weight, is_part_of_dish)
                        VALUES (?, ?, ?, ?, 1)
                    ''', (meal_id, comp_id, prod['product_id'], prod['weight']))
        conn.commit()
        return meal_id


def get_all_meals():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, datetime, insulin_dose, glucose, notes
            FROM meals
            ORDER BY datetime DESC
        ''')
        return cursor.fetchall()


def get_meal(meal_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, datetime, insulin_dose, glucose, notes
            FROM meals
            WHERE id = ?
        ''', (meal_id,))
        return cursor.fetchone()


def get_meal_components(meal_id):
    """Возвращает список компонентов приёма с деталями."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, component_type, product_id, dish_id, serving_weight,
                   cooked_dish_weight, pan_id
            FROM meal_components
            WHERE meal_id = ?
            ORDER BY id
        ''', (meal_id,))
        components = cursor.fetchall()

        result = []
        for comp in components:
            comp_dict = dict(comp)
            if comp_dict['component_type'] == 'product':
                prod = get_product(comp_dict['product_id'])
                comp_dict['product_name'] = prod['name'] if prod else '(удалён)'
                comp_dict['details'] = []
            else:
                dish = get_dish(comp_dict['dish_id'])
                comp_dict['dish_name'] = dish['name'] if dish else '(удалено)'
                cursor.execute('''
                    SELECT product_id, weight, is_part_of_dish
                    FROM meal_composition_details
                    WHERE meal_component_id = ?
                ''', (comp_dict['id'],))
                details = cursor.fetchall()
                comp_dict['details'] = [dict(d) for d in details]
                for d in comp_dict['details']:
                    prod = get_product(d['product_id'])
                    d['product_name'] = prod['name'] if prod else '(удалён)'
            result.append(comp_dict)
        return result


def delete_meal(meal_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM meals WHERE id=?", (meal_id,))
        conn.commit()


def update_meal(meal_id, datetime_str, insulin_dose, glucose, notes):
    """Обновляет основные данные приёма, включая уровень сахара."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE meals
            SET datetime=?, insulin_dose=?, glucose=?, notes=?
            WHERE id=?
        ''', (datetime_str, insulin_dose, glucose, notes, meal_id))
        conn.commit()


# ---- Настройки ----

def get_settings():
    """Загружает настройки из базы данных."""
    with get_connection() as conn:
        cursor = conn.cursor()
        settings = {}
        cursor.execute("SELECT key, value FROM settings")
        for key, value in cursor.fetchall():
            settings[key] = value
        return settings


def save_settings(settings_dict):
    """Сохраняет настройки в базу данных."""
    with get_connection() as conn:
        cursor = conn.cursor()
        for key, value in settings_dict.items():
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value)
                VALUES (?, ?)
            ''', (key, value))
        conn.commit()


# ---- NightScout конфигурация ----
# URL и токен хранятся в отдельной таблице ns_config (ключ-значение, TEXT),
# потому что основная таблица settings использует REAL для числовых настроек.

def _ensure_ns_tables(conn):
    conn.execute('''
        CREATE TABLE IF NOT EXISTS ns_config (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    # Лог успешных отправок на NS — для отладки и повторной отправки
    conn.execute('''
        CREATE TABLE IF NOT EXISTS ns_sync_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            meal_id     INTEGER,
            synced_at   TEXT NOT NULL,
            status      TEXT NOT NULL,   -- 'ok' | 'error'
            message     TEXT,
            FOREIGN KEY (meal_id) REFERENCES meals(id) ON DELETE SET NULL
        )
    ''')


def get_ns_config() -> dict:
    """Возвращает {'url': ..., 'token': ..., 'enabled': '0'/'1'}."""
    with get_connection() as conn:
        _ensure_ns_tables(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM ns_config")
        result = {row['key']: row['value'] for row in cursor.fetchall()}
    return result


def save_ns_config(url: str, token: str, enabled: bool):
    """Сохраняет настройки NightScout."""
    with get_connection() as conn:
        _ensure_ns_tables(conn)
        for key, value in [('url', url), ('token', token),
                           ('enabled', '1' if enabled else '0')]:
            conn.execute('''
                INSERT OR REPLACE INTO ns_config (key, value) VALUES (?, ?)
            ''', (key, value))
        conn.commit()


def log_ns_sync(meal_id, status: str, message: str = ''):
    """Записывает результат синхронизации с NS."""
    from datetime import datetime
    with get_connection() as conn:
        _ensure_ns_tables(conn)
        conn.execute('''
            INSERT INTO ns_sync_log (meal_id, synced_at, status, message)
            VALUES (?, ?, ?, ?)
        ''', (meal_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), status, message))
        conn.commit()


def get_ns_sync_log(limit: int = 50) -> list:
    """Возвращает последние записи лога синхронизации."""
    with get_connection() as conn:
        _ensure_ns_tables(conn)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT l.id, l.meal_id, l.synced_at, l.status, l.message,
                   m.datetime as meal_datetime
            FROM ns_sync_log l
            LEFT JOIN meals m ON l.meal_id = m.id
            ORDER BY l.id DESC LIMIT ?
        ''', (limit,))
        return cursor.fetchall()
