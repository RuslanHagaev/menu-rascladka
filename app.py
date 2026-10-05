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
    st.info("Здесь будет справочник блюд с технологическими картами.")

with tab_menu:
    st.info("Здесь будет составление меню на день.")

with tab_calc:
    st.info("Здесь будет автоматический расчёт заявки.")