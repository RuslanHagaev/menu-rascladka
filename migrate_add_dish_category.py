import sqlite3

conn = sqlite3.connect("menu.db")
cursor = conn.cursor()

# Добавляем поле category в таблицу dishes
try:
    cursor.execute("ALTER TABLE dishes ADD COLUMN category TEXT DEFAULT 'Второе'")
    print("Добавлено поле category в dishes")
except sqlite3.OperationalError:
    print("Поле category уже есть")

# Проставим категории существующим блюдам (по названию)
updates = {
    "Борщ": "Первое",
    "Каша рисовая": "Второе",
    "Чай с молоком": "Напиток",
}

for name, cat in updates.items():
    cursor.execute("UPDATE dishes SET category = ? WHERE name = ?", (cat, name))

conn.commit()
conn.close()
print("Готово. Категории обновлены.")