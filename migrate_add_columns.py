import sqlite3

conn = sqlite3.connect("menu.db")
cursor = conn.cursor()

# Добавляем колонки, если их ещё нет
try:
    cursor.execute("ALTER TABLE products ADD COLUMN quantity REAL DEFAULT 0")
    print("Добавлена колонка: quantity")
except sqlite3.OperationalError:
    print("Колонка quantity уже есть")

try:
    cursor.execute("ALTER TABLE products ADD COLUMN note TEXT DEFAULT ''")
    print("Добавлена колонка: note")
except sqlite3.OperationalError:
    print("Колонка note уже есть")

conn.commit()
conn.close()
print("Готово")