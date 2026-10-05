import sqlite3
import os

DB_PATH = "menu.db"

# Если база уже есть — удалим, чтобы начать чисто
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Таблица продуктов
cursor.execute("""
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    unit TEXT NOT NULL
)
""")

# Таблица блюд
cursor.execute("""
CREATE TABLE dishes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
)
""")

# Состав блюда: какие продукты и сколько грамм на 1 порцию
cursor.execute("""
CREATE TABLE dish_ingredients (
    dish_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    grams_per_portion REAL NOT NULL,
    FOREIGN KEY (dish_id) REFERENCES dishes(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
)
""")

# Меню: какое блюдо в какой день и сколько порций
cursor.execute("""
CREATE TABLE menu (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    dish_id INTEGER NOT NULL,
    portions INTEGER NOT NULL,
    FOREIGN KEY (dish_id) REFERENCES dishes(id)
)
""")

# Тестовые продукты
products = [
    ("Картофель", "кг"),
    ("Морковь", "кг"),
    ("Свёкла", "кг"),
    ("Капуста", "кг"),
    ("Мясо говядина", "кг"),
    ("Крупа рисовая", "кг"),
    ("Молоко", "л"),
    ("Вода", "л"),
    ("Соль", "кг"),
]

cursor.executemany("INSERT INTO products (name, unit) VALUES (?, ?)", products)

# Тестовые блюда
dishes = [
    ("Борщ",),
    ("Каша рисовая",),
]

cursor.executemany("INSERT INTO dishes (name) VALUES (?)", dishes)

# Состав блюд (граммы на 1 порцию)
# id блюд: 1 = Борщ, 2 = Каша рисовая
# id продуктов: 1=Картофель, 2=Морковь, 3=Свёкла, 4=Капуста, 5=Мясо,
#               6=Крупа рисовая, 7=Молоко, 8=Вода, 9=Соль
ingredients = [
    (1, 1, 80),   # Борщ: картофель 80 г
    (1, 2, 20),   # Борщ: морковь 20 г
    (1, 3, 50),   # Борщ: свёкла 50 г
    (1, 4, 40),   # Борщ: капуста 40 г
    (1, 5, 50),   # Борщ: мясо 50 г
    (1, 8, 200),  # Борщ: вода 200 г
    (1, 9, 2),    # Борщ: соль 2 г
    (2, 6, 60),   # Каша: крупа 60 г
    (2, 7, 150),  # Каша: молоко 150 г
    (2, 9, 1),    # Каша: соль 1 г
]

cursor.executemany(
    "INSERT INTO dish_ingredients (dish_id, product_id, grams_per_portion) VALUES (?, ?, ?)",
    ingredients
)

conn.commit()
conn.close()

print("База данных создана: menu.db")
print(f"Продуктов: {len(products)}")
print(f"Блюд: {len(dishes)}")
print(f"Ингредиентов в блюдах: {len(ingredients)}")