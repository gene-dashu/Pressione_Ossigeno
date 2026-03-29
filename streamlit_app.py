import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors

# Configurazione Pagina
st.set_page_config(page_title="Monitor Salute", layout="centered")

# --- PROTEZIONE PASSWORD ---
def check_password():
    if "password_correct" not in st.session_state:
        st.text_input("Inserisci Password", type="password", on_change=password_entered, key="password")
        return False
    return st.session_state["password_correct"]

def password_entered():
    if st.session_state["password"] == st.secrets["passwords"]["access_password"]:
        st.session_state["password_correct"] = True
        del st.session_state["password"]
    else:
        st.error("Password errata")

if not check_password():
    st.stop()

# --- CONNESSIONE GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- INTERFACCIA UTENTE ---
st.title("🩺 Registro Parametri")

with st.form("entry_form"):
    col1, col2 = st.columns(2)
    with col1:
        date = st.date_input("Data", datetime.now())
        saturazione = st.text_input("Saturazione (%)", value="N/D")
        max_press = st.text_input("Sistolica (Max)", value="N/D")
    with col2:
        time = st.time_input("Ora", datetime.now().time())
        bpm_sat = st.text_input("Battiti (Saturimetro)", value="N/D")
        min_press = st.text_input("Diastolica (Min)", value="N/D")
    
    bpm_press = st.text_input("Battiti (Misuratore Pressione)", value="N/D")
    note = st.text_area("Note", value="-")
    
    submit = st.form_submit_button("Salva nel Foglio")

if submit:
    new_data = pd.DataFrame([{
        "Data": date.strftime("%d/%m/%Y"),
        "Ora": time.strftime("%H:%M"),
        "Saturazione": saturazione,
        "Battiti con saturimetro": bpm_sat,
        "Max": max_press,
        "Min": min_press,
        "Battiti con misuratore pressione": bpm_press,
        "Note": note
    }])
    
    # Lettura dati esistenti e aggiunta
    existing_data = conn.read()
    updated_df = pd.concat([existing_data, new_data], ignore_index=True)
    conn.update(data=updated_df)
    st.success("Dati salvati correttamente!")

# --- SEZIONE PDF ---
st.divider()
st.subheader("🖨️ Esporta PDF")
col_a, col_b = st.columns(2)
start_date = col_a.date_input("Dal", datetime.now())
end_date = col_b.date_input("Al", datetime.now())

if st.button("Genera PDF"):
    df = conn.read()
    df['Data_dt'] = pd.to_datetime(df['Data'], format="%d/%m/%Y")
    mask = (df['Data_dt'].dt.date >= start_date) & (df['Data_dt'].dt.date <= end_date)
    filtered_df = df.loc[mask].drop(columns=['Data_dt'])
    
    pdf_file = "report_salute.pdf"
    doc = SimpleDocTemplate(pdf_file, pagesize=letter)
    elements = []
    
    # Preparazione tabella per PDF
    data_list = [filtered_df.columns.tolist()] + filtered_df.values.tolist()
    t = Table(data_list)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]))
    elements.append(t)
    doc.build(elements)
    
    with open(pdf_file, "rb") as f:
        st.download_button("Scarica il PDF", f, file_name=f"Report_{start_date}_{end_date}.pdf")
