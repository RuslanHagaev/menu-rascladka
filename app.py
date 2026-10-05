import streamlit as st
import sqlite3
import pandas as pd
import io
from datetime import date
from fpdf import FPDF

DB_PATH = "menu.db"
FONT_PATH = "C:/Windows/Fonts/arial.ttf"

st.set_page_config(
    page_title="Меню-раскладка",
    page_icon="🍲",
    layout="wide",
)

st.title("🍲 Меню-раскладка")
st.caption("Система расчёта продуктов для школьного питания")


# ==================== РАБОТА С БАЗОЙ ====================
def get_products_df():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT id, name, unit, quantity, note FROM products ORDER BY id",
        conn,
    )
    conn.close()
    return df


def save_products_df(df):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    existing = pd.read_sql_query("SELECT id FROM products", conn)["id"].tolist()
    incoming_ids = df["id"].dropna().astype(int).tolist()

    to_delete = [i for i in existing if i not in incoming_ids]
    for i in to_delete:
        cursor.execute("DELETE FROM products WHERE id = ?", (i,))

    for _, row in df.iterrows():
        name = str(row["name"]).strip() if pd.notna(row["name"]) else ""
        if not name:
            continue

        unit = str(row["unit"]).strip() if pd.notna(row["unit"]) else "кг"
        quantity = float(row["quantity"]) if pd.notna(row["quantity"]) else 0.0
        note = str(row["note"]).strip() if pd.notna(row["note"]) else ""

        if pd.isna(row["id"]):
            cursor.execute(
                "INSERT INTO products (name, unit, quantity, note) VALUES (?, ?, ?, ?)",
                (name, unit, quantity, note),
            )
        else:
            cursor.execute(
                "UPDATE products SET name = ?, unit = ?, quantity = ?, note = ? WHERE id = ?",
                (name, unit, quantity, note, int(row["id"])),
            )

    conn.commit()
    conn.close()


def get_settings():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT key, value FROM settings", conn)
    conn.close()
    return dict(zip(df["key"], df["value"]))


def save_settings(data: dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for key, value in data.items():
        cursor.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
    conn.commit()
    conn.close()

def get_dishes_df(category=None):
    conn = sqlite3.connect(DB_PATH)
    if category and category != "Все":
        df = pd.read_sql_query(
            "SELECT id, name, category FROM dishes WHERE category = ? ORDER BY name",
            conn,
            params=(category,),
        )
    else:
        df = pd.read_sql_query(
            "SELECT id, name, category FROM dishes ORDER BY category, name",
            conn,
        )
    conn.close()
    return df


def get_all_dishes_df():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT id, name, category FROM dishes ORDER BY name", conn)
    conn.close()
    return df


def add_dish(name, category):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO dishes (name, category) VALUES (?, ?)", (name, category))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def update_dish_category(dish_id, category):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE dishes SET category = ? WHERE id = ?", (category, dish_id))
    conn.commit()
    conn.close()


CATEGORY_ICONS = {
    "Первое": "🍲",
    "Второе": "🍛",
    "Напиток": "🍵",
    "Салат": "🥗",
    "Выпечка": "🥐",
    "Прочее": "🍽",
}

def delete_dish(dish_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM dish_ingredients WHERE dish_id = ?", (dish_id,))
    cursor.execute("DELETE FROM dishes WHERE id = ?", (dish_id,))
    conn.commit()
    conn.close()


def rename_dish(dish_id, new_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE dishes SET name = ? WHERE id = ?", (new_name, dish_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_dish_ingredients(dish_id):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT di.product_id, p.name AS product_name, p.unit,
               di.grams_per_portion
        FROM dish_ingredients di
        JOIN products p ON p.id = di.product_id
        WHERE di.dish_id = ?
        ORDER BY p.name
        """,
        conn,
        params=(dish_id,),
    )
    conn.close()
    return df


def add_dish_ingredient(dish_id, product_id, grams):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Проверим, нет ли уже такого продукта в блюде
    cursor.execute(
        "SELECT COUNT(*) FROM dish_ingredients WHERE dish_id = ? AND product_id = ?",
        (dish_id, product_id),
    )
    exists = cursor.fetchone()[0]
    if exists:
        cursor.execute(
            "UPDATE dish_ingredients SET grams_per_portion = ? WHERE dish_id = ? AND product_id = ?",
            (grams, dish_id, product_id),
        )
    else:
        cursor.execute(
            "INSERT INTO dish_ingredients (dish_id, product_id, grams_per_portion) VALUES (?, ?, ?)",
            (dish_id, product_id, grams),
        )
    conn.commit()
    conn.close()


def delete_dish_ingredient(dish_id, product_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM dish_ingredients WHERE dish_id = ? AND product_id = ?",
        (dish_id, product_id),
    )
    conn.commit()
    conn.close()

# ==================== ГЕНЕРАЦИЯ PDF ====================
class InvoicePDF(FPDF):
    pass


def format_qty(value, unit):
    """5.0 кг → '5 кг', 2.5 л → '2.5 л'"""
    if value == int(value):
        return f"{int(value)} {unit}"
    return f"{value:g} {unit}"


def build_invoice_pdf(rows, settings, invoice_date):
    pdf = InvoicePDF(orientation="P", unit="mm", format="A4")
    pdf.add_font("Arial", "", FONT_PATH)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Шапка
    pdf.set_font("Arial", size=14)
    pdf.cell(0, 8, settings.get("school_name", ""), ln=1, align="C")

    pdf.set_font("Arial", size=10)
    address_parts = []
    if settings.get("school_address"):
        address_parts.append(settings["school_address"])
    if settings.get("school_phone"):
        address_parts.append(f"тел.: {settings['school_phone']}")
    if address_parts:
        pdf.cell(0, 5, " | ".join(address_parts), ln=1, align="C")

    if settings.get("school_inn"):
        pdf.cell(0, 5, f"ИНН: {settings['school_inn']}", ln=1, align="C")

    pdf.ln(4)

    # Заголовок
    pdf.set_font("Arial", size=13)
    pdf.cell(0, 8, "НАКЛАДНАЯ НА ПРОДУКТЫ", ln=1, align="C")
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, f"от {invoice_date.strftime('%d.%m.%Y')}", ln=1, align="C")

    pdf.ln(2)

    if settings.get("supplier"):
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 6, f"Поставщик: {settings['supplier']}", ln=1)

    pdf.ln(2)

    # Таблица
    pdf.set_font("Arial", size=10)
    col_widths = [12, 90, 15, 25, 40]
    headers = ["№", "Наименование", "Ед.", "Кол-во", "Примечание"]

    pdf.set_fill_color(230, 230, 230)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 8, h, border=1, align="C", fill=True)
    pdf.ln()

    # Перебираем строки DataFrame через iterrows
    for i, (_, row) in enumerate(rows.iterrows(), start=1):
        name = str(row.get("name", ""))[:60]
        unit = str(row.get("unit", ""))
        qty = row.get("quantity", 0) or 0
        note = str(row.get("note", "") or "")[:35]

        pdf.cell(col_widths[0], 7, str(i), border=1, align="C")
        pdf.cell(col_widths[1], 7, name, border=1)
        pdf.cell(col_widths[2], 7, unit, border=1, align="C")
        pdf.cell(col_widths[3], 7, f"{qty:g}", border=1, align="C")
        pdf.cell(col_widths[4], 7, note, border=1)
        pdf.ln()

    # Итог
    pdf.ln(2)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, f"Всего позиций: {len(rows)}", ln=1)

    pdf.ln(8)

    # Подпись
    pdf.set_font("Arial", size=10)
    position = settings.get("signer_position", "")
    signer = settings.get("signer_name", "")

    pdf.cell(0, 6, f"{position}", ln=1)
    pdf.ln(4)
    pdf.cell(80, 6, "Подпись: _______________", ln=0)
    pdf.cell(0, 6, f" / {signer} /", ln=1)

    pdf.ln(6)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, "М.П.", ln=1)

    return bytes(pdf.output())


# ==================== ВКЛАДКИ ====================
tab_products, tab_dishes, tab_menu, tab_calc, tab_settings = st.tabs([
    "📦 Продукты",
    "🍲 Блюда",
    "📅 Меню",
    "🧮 Расчёт",
    "⚙️ Настройки",
])


# ==================== ВКЛАДКА «ПРОДУКТЫ» ====================
with tab_products:
    st.subheader("Справочник продуктов")
    st.caption("Отметь продукты галочкой «✓», чтобы включить их в накладную.")

    df = get_products_df()
    df.insert(0, "select", False)  # колонка выбора

    edited_df = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "select": st.column_config.CheckboxColumn(
                "✓",
                width="small",
                default=False,
                help="Отметь, чтобы включить в накладную",
            ),
            "id": st.column_config.NumberColumn(
                "№", width="small", disabled=True, format="%d",
            ),
            "name": st.column_config.TextColumn(
                "Название", width="medium", required=True,
            ),
            "unit": st.column_config.SelectboxColumn(
                "Ед.", width="small", options=["кг", "л", "шт"], required=True,
            ),
            "quantity": st.column_config.NumberColumn(
                "Кол-во", width="small", min_value=0.0, step=0.1, format="%.2f",
            ),
            "note": st.column_config.TextColumn(
                "Примечание", width="large",
            ),
        },
        key="products_editor",
    )

    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

    with col1:
        if st.button("💾 Сохранить", type="primary"):
            save_df = edited_df.drop(columns=["select"])
            save_products_df(save_df)
            st.success("Сохранено")
            st.rerun()

    with col2:
        selected = edited_df[edited_df["select"] == True]
        if st.button("📄 Накладная (выбранные)"):
            if len(selected) == 0:
                st.warning("Ничего не выбрано. Поставь галочки в колонке ✓")
            else:
                settings = get_settings()
                pdf_bytes = build_invoice_pdf(selected, settings, date.today())
                st.download_button(
                    "⬇️ Скачать PDF",
                    data=pdf_bytes,
                    file_name=f"накладная_{date.today().isoformat()}.pdf",
                    mime="application/pdf",
                    key="dl_selected",
                )

    with col3:
        if st.button("📄 Накладная (все)"):
            settings = get_settings()
            pdf_bytes = build_invoice_pdf(edited_df, settings, date.today())
            st.download_button(
                "⬇️ Скачать PDF",
                data=pdf_bytes,
                file_name=f"накладная_полная_{date.today().isoformat()}.pdf",
                mime="application/pdf",
                key="dl_all",
            )

    with col4:
        csv_data = edited_df.drop(columns=["select"]).to_csv(index=False, sep=";", encoding="utf-8-sig")
        st.download_button(
            "📊 Скачать CSV",
            data=csv_data.encode("utf-8-sig"),
            file_name=f"продукты_{date.today().isoformat()}.csv",
            mime="text/csv",
            key="dl_csv",
        )


# ==================== ВКЛАДКА «НАСТРОЙКИ» ====================
with tab_settings:
    st.subheader("Настройки школы и накладной")
    st.caption("Заполни один раз — эти данные будут автоматически попадать в накладную.")

    settings = get_settings()

    col1, col2 = st.columns(2)

    with col1:
        school_name = st.text_input("Название школы", value=settings.get("school_name", ""))
        school_address = st.text_input("Адрес", value=settings.get("school_address", ""))
        school_phone = st.text_input("Телефон", value=settings.get("school_phone", ""))
        school_inn = st.text_input("ИНН", value=settings.get("school_inn", ""))

    with col2:
        supplier = st.text_input("Поставщик", value=settings.get("supplier", ""))
        signer_position = st.text_input("Должность подписанта", value=settings.get("signer_position", ""))
        signer_name = st.text_input("ФИО подписанта", value=settings.get("signer_name", ""))

    if st.button("💾 Сохранить настройки", type="primary"):
        save_settings({
            "school_name": school_name,
            "school_address": school_address,
            "school_phone": school_phone,
            "school_inn": school_inn,
            "supplier": supplier,
            "signer_position": signer_position,
            "signer_name": signer_name,
        })
        st.success("Настройки сохранены")
        st.rerun()


# ==================== ЗАГЛУШКИ ====================
with tab_dishes:
    st.subheader("Справочник блюд")
    st.caption("Выбери блюдо слева — справа увидишь состав. Всё в граммах на 1 порцию.")

    col_list, col_detail = st.columns([1, 2])

    # --- Левая колонка: список блюд с фильтром по категориям ---
    with col_list:
        st.markdown("**Категория**")
        categories = ["Все", "Первое", "Второе", "Напиток", "Салат", "Выпечка", "Прочее"]
        if "selected_category" not in st.session_state:
            st.session_state.selected_category = "Все"

        # Кнопки-фильтры в две строки
        cat_cols = st.columns(2)
        for i, cat in enumerate(categories):
            with cat_cols[i % 2]:
                icon = CATEGORY_ICONS.get(cat, "📋") if cat != "Все" else "📋"
                is_sel = st.session_state.selected_category == cat
                label = f"{icon} **{cat}**" if is_sel else f"{icon} {cat}"
                if st.button(label, key=f"cat_{cat}", use_container_width=True):
                    st.session_state.selected_category = cat
                    st.rerun()

        st.markdown("---")
        st.markdown("**Блюда**")

        dishes_df = get_dishes_df(st.session_state.selected_category)

        if len(dishes_df) == 0:
            st.info("В этой категории пока нет блюд.")

        for _, dish in dishes_df.iterrows():
            dish_id = int(dish["id"])
            dish_name = dish["name"]
            dish_cat = dish.get("category", "Прочее")
            dish_icon = CATEGORY_ICONS.get(dish_cat, "🍽")

            is_selected = st.session_state.get("selected_dish_id") == dish_id
            label = f"{dish_icon} **{dish_name}**" if is_selected else f"{dish_icon} {dish_name}"

            if st.button(label, key=f"dish_{dish_id}", use_container_width=True):
                st.session_state.selected_dish_id = dish_id
                st.rerun()

        st.markdown("---")
        st.markdown("**Добавить блюдо**")
        new_dish_name = st.text_input(
            "Название",
            key="new_dish_name",
            label_visibility="collapsed",
            placeholder="Название блюда",
        )
        new_dish_cat = st.selectbox(
            "Категория",
            ["Первое", "Второе", "Напиток", "Салат", "Выпечка", "Прочее"],
            key="new_dish_cat",
            label_visibility="collapsed",
        )
        if st.button("➕ Добавить блюдо", key="add_dish_btn", use_container_width=True):
            if new_dish_name.strip():
                ok = add_dish(new_dish_name.strip(), new_dish_cat)
                if ok:
                    st.success(f"Добавлено: {new_dish_name}")
                    st.rerun()
                else:
                    st.warning("Такое блюдо уже есть")
            else:
                st.error("Введи название")

    # --- Правая колонка: состав выбранного блюда ---
    with col_detail:
        if st.session_state.get("selected_dish_id") is None:
            st.info("Слева выбери блюдо или добавь новое.")
        else:
            selected_id = st.session_state.selected_dish_id
            all_dishes = get_all_dishes_df()
            selected_row = all_dishes[all_dishes["id"] == selected_id]

            if len(selected_row) == 0:
                st.warning("Блюдо не найдено")
                st.session_state.selected_dish_id = None
            else:
                selected_name = selected_row.iloc[0]["name"]
                selected_cat = selected_row.iloc[0].get("category", "Прочее")
                selected_icon = CATEGORY_ICONS.get(selected_cat, "🍽")

                col_title, col_cat, col_rename, col_delete = st.columns([3, 2, 2, 2])
                with col_title:
                    st.markdown(f"### {selected_icon} {selected_name}")
                with col_cat:
                    new_cat = st.selectbox(
                        "Категория",
                        ["Первое", "Второе", "Напиток", "Салат", "Выпечка", "Прочее"],
                        index=["Первое", "Второе", "Напиток", "Салат", "Выпечка", "Прочее"].index(selected_cat)
                        if selected_cat in ["Первое", "Второе", "Напиток", "Салат", "Выпечка", "Прочее"] else 5,
                        key=f"cat_select_{selected_id}",
                        label_visibility="collapsed",
                    )
                    if new_cat != selected_cat:
                        update_dish_category(selected_id, new_cat)
                        st.rerun()
                with col_rename:
                    new_name = st.text_input(
                        "Переименовать",
                        value=selected_name,
                        key=f"rename_{selected_id}",
                        label_visibility="collapsed",
                    )
                    if new_name != selected_name and new_name.strip():
                        if st.button("✏️ Переименовать", key=f"rename_btn_{selected_id}", use_container_width=True):
                            ok = rename_dish(selected_id, new_name.strip())
                            if ok:
                                st.rerun()
                            else:
                                st.error("Такое имя уже есть")
                with col_delete:
                    st.write("")  # отступ
                    if st.button("🗑 Удалить", key=f"del_dish_{selected_id}", use_container_width=True):
                        delete_dish(selected_id)
                        st.session_state.selected_dish_id = None
                        st.rerun()

                st.markdown("**Ингредиенты на 1 порцию:**")

                ingredients_df = get_dish_ingredients(selected_id)

                if len(ingredients_df) == 0:
                    st.info("Состав пуст. Добавь ингредиенты ниже.")
                else:
                    for _, ing in ingredients_df.iterrows():
                        col1, col2, col3 = st.columns([4, 1, 1])
                        with col1:
                            st.write(f"**{ing['product_name']}**")
                        with col2:
                            st.write(f"{ing['grams_per_portion']:g} г")
                        with col3:
                            if st.button("🗑 Удалить", key=f"del_ing_{selected_id}_{ing['product_id']}", use_container_width=True):
                                delete_dish_ingredient(selected_id, int(ing["product_id"]))
                                st.rerun()

                st.markdown("---")
                st.markdown("**Добавить ингредиент**")

                products_df = get_products_df()
                if len(products_df) == 0:
                    st.warning("Сначала добавь продукты на вкладке «Продукты».")
                else:
                    product_options = {
                        f"{row['name']} ({row['unit']})": int(row["id"])
                        for _, row in products_df.iterrows()
                    }
                    col_p, col_g, col_b = st.columns([3, 1, 1])
                    with col_p:
                        chosen_label = st.selectbox(
                            "Продукт",
                            options=list(product_options.keys()),
                            key=f"new_ing_product_{selected_id}",
                            label_visibility="collapsed",
                        )
                    with col_g:
                        grams = st.number_input(
                            "Грамм",
                            min_value=0.1,
                            value=10.0,
                            step=1.0,
                            key=f"new_ing_grams_{selected_id}",
                            label_visibility="collapsed",
                        )
                    with col_b:
                        if st.button("➕ Добавить", key=f"add_ing_{selected_id}", use_container_width=True):
                            add_dish_ingredient(
                                selected_id,
                                product_options[chosen_label],
                                float(grams),
                            )
                            st.rerun()

with tab_menu:
    st.info("Здесь будет составление меню на день.")

with tab_calc:
    st.info("Здесь будет автоматический расчёт заявки.")

# Подключаем стили
with open("styles.css", "r", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)