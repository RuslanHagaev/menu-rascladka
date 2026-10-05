import sqlite3

conn = sqlite3.connect("menu.db")
cursor = conn.cursor()

# Таблица настроек: ключ-значение, чтобы не переделывать при добавлении новых полей
cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

# Значения по умолчанию (если ключа ещё нет)
defaults = {
    "school_name": "МБОУ СОШ № ___",
    "school_address": "",
    "school_phone": "",
    "school_inn": "",
    "supplier": "",
    "signer_position": "Заведующий хозяйством",
    "signer_name": "________________________",
}

for key, value in defaults.items():
    cursor.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )

conn.commit()
conn.close()
print("Таблица settings создана, настройки по умолчанию добавлены")