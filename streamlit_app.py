import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Monitor Salute", layout="centered")

# --- PROTEZIONE PASSWORD ---
def check_password():
    if "password_correct" not in st.session_state:
        st.title("Accesso Protetto")
        pwd = st.text_input("Inserisci Password", type="password")
        if st.button("Entra"):
            if pwd == st.secrets["passwords"]["access_password"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Password errata")
        return False
    return True

if not check_password():
    st.stop()

# --- CONNESSIONE ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNZIONE PER INPUT PERSONALIZZATO (NUMERO O N/D) ---
def salute_input(label):
    col_a, col_b = st.columns([3, 1])
    with col_a:
        val = st.text_input(f"{label}", value="", placeholder="Inserisci valore...")
    with col_b:
        nd = st.checkbox("N/D", key=f"nd_{label}")
    return "N/D" if nd else val

# --- INTERFACCIA ---
st.title("🩺 Registro Parametri Salute")

with st.form("form_inserimento", clear_on_submit=True):
    col1, col2 = st.columns(2)
    
    with col1:
        data_ins = st.date_input("Data", datetime.now())
        sat = salute_input("Saturazione %")
        max_p = salute_input("Pressione MAX")
        bpm_p = salute_input("BPM (Pressione)")
        
    with col2:
        ora_ins = st.time_input("Ora", datetime.now().time())
        bpm_s = salute_input("BPM (Saturimetro)")
        min_p = salute_input("Pressione MIN")
        note = st.text_area("Note", value="")

    submit = st.form_submit_button("Salva nel Foglio e Formatta")

# --- LOGICA SALVATAGGIO ---
if submit:
    nuovo_record = pd.DataFrame([{
        "Data": data_ins.strftime("%d/%m/%Y"),
        "Ora": ora_ins.strftime("%H:%M"),
        "Saturazione": sat if sat != "" else "N/D",
        "Battiti con saturimetro": bpm_s if bpm_s != "" else "N/D",
        "Max": max_p if max_p != "" else "N/D",
        "Min": min_p if min_p != "" else "N/D",
        "Battiti con misuratore pressione": bpm_p if bpm_p != "" else "N/D",
        "Note": note if note != "" else "N/D"
    }])
    
    try:
        df_esistente = conn.read()
        df_aggiornato = pd.concat([df_esistente, nuovo_record], ignore_index=True)
        
        # Update con formattazione (i bordi vengono mantenuti se impostati nel foglio master)
        conn.update(data=df_aggiornato)
        
        st.success("✅ Dati salvati! Ricordati di impostare i bordi su Google Sheets 'Formato > Bordi' per la griglia automatica.")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Errore: {e}")

st.divider()

# --- ESPORTAZIONE PDF ---
st.subheader("🖨️ Genera Report PDF Stampabile")
c1, c2 = st.columns(2)
d_inizio = c1.date_input("Inizio", datetime.now())
d_fine = c2.date_input("Fine", datetime.now())

if st.button("Scarica Report PDF"):
    try:
        df_totale = conn.read()
        df_totale['tmp_date'] = pd.to_datetime(df_totale['Data'], format="%d/%m/%Y", errors='coerce').dt.date
        df_filtrato = df_totale.dropna(subset=['tmp_date'])
        mask = (df_filtrato['tmp_date'] >= d_inizio) & (df_filtrato['tmp_date'] <= d_fine)
        df_finale = df_filtrato.loc[mask].drop(columns=['tmp_date']).astype(str)
        
        if df_finale.empty:
            st.warning("Nessun dato nel range selezionato.")
        else:
            pdf_path = "report.pdf"
            doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
            styles = getSampleStyleSheet()
            elementi = [Paragraph(f"DIARIO PRESSIONE E OSSIGENO ({d_inizio} / {d_fine})", styles['Title'])]
            
            # Tabella PDF con griglia pesante
            tab_data = [df_finale.columns.tolist()] + df_finale.values.tolist()
            tabella = Table(tab_data)
            tabella.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 1, colors.black), # Griglia per PDF
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            
            elementi.append(tabella)
            doc.build(elementi)
            
            with open(pdf_path, "rb") as f:
                st.download_button("Scarica PDF", f, file_name=f"Report_Salute.pdf")
    except Exception as e:
        st.error(f"Errore PDF: {e}")
