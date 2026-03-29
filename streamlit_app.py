import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# 1. Configurazione Pagina
st.set_page_config(page_title="Monitor Salute", layout="centered")

# 2. Funzione Protezione Password
def check_password():
    if "password_correct" not in st.session_state:
        st.title("Accesso Protetto")
        pwd = st.text_input("Inserisci la password per accedere", type="password")
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

# 3. Connessione al Foglio (Usa i Secrets configurati come service_account)
conn = st.connection("gsheets", type=GSheetsConnection)

# 4. Interfaccia di Inserimento
st.title("🩺 Registro Parametri Salute")

with st.form("form_inserimento", clear_on_submit=True):
    col1, col2 = st.columns(2)
    
    with col1:
        data_ins = st.date_input("Data", datetime.now())
        sat = st.text_input("Saturazione % (es. 98 o N/D)", value="N/D")
        max_p = st.text_input("Pressione MAX (es. 120 o N/D)", value="N/D")
        bpm_p = st.text_input("BPM (Misuratore Pressione)", value="N/D")
        
    with col2:
        ora_ins = st.time_input("Ora", datetime.now().time())
        bpm_s = st.text_input("BPM (Saturimetro)", value="N/D")
        min_p = st.text_input("Pressione MIN (es. 80 o N/D)", value="N/D")
        note = st.text_area("Note", value="N/D")

    submit = st.form_submit_button("Salva nel Foglio Google")

# 5. Logica di Salvataggio
if submit:
    # Creazione riga come DataFrame
    nuovo_record = pd.DataFrame([{
        "Data": data_ins.strftime("%d/%m/%Y"),
        "Ora": ora_ins.strftime("%H:%M"),
        "Saturazione": sat,
        "Battiti con saturimetro": bpm_s,
        "Max": max_p,
        "Min": min_p,
        "Battiti con misuratore pressione": bpm_p,
        "Note": note
    }])
    
    try:
        # Legge i dati esistenti
        df_esistente = conn.read()
        # Unisce i dati (append)
        df_aggiornato = pd.concat([df_esistente, nuovo_record], ignore_index=True)
        # Aggiorna il foglio (Streamlit GSheets applica automaticamente i bordi se il foglio è formattato)
        conn.update(data=df_aggiornato)
        st.success("✅ Dati inviati con successo!")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Errore durante il salvataggio: {e}")

st.divider()

# 6. Esportazione PDF
st.subheader("🖨️ Genera Report PDF")
c1, c2 = st.columns(2)
d_inizio = c1.date_input("Data inizio", datetime.now())
d_fine = c2.date_input("Data fine", datetime.now())

if st.button("Scarica Report PDF"):
    try:
        df_totale = conn.read()
        # Filtro date (trasformando la colonna Data in formato datetime temporaneo)
        df_totale['tmp_date'] = pd.to_datetime(df_totale['Data'], format="%d/%m/%Y").dt.date
        mask = (df_totale['tmp_date'] >= d_inizio) & (df_totale['tmp_date'] <= d_fine)
        df_filtrato = df_totale.loc[mask].drop(columns=['tmp_date'])
        
        if df_filtrato.empty:
            st.warning("Nessun dato trovato per le date selezionate.")
        else:
            pdf_path = "report_parametri.pdf"
            doc = SimpleDocTemplate(pdf_path, pagesize=A4)
            styles = getSampleStyleSheet()
            elementi = [Paragraph(f"Report Parametri dal {d_inizio} al {d_fine}", styles['Title'])]
            
            # Preparazione dati tabella
            tab_data = [df_filtrato.columns.tolist()] + df_filtrato.values.tolist()
            
            # Creazione Tabella con Bordi
            tabella = Table(tab_data)
            tabella.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            elementi.append(tabella)
            doc.build(elementi)
            
            with open(pdf_path, "rb") as f:
                st.download_button("Clicca qui per scaricare", f, file_name=f"Salute_{d_inizio}.pdf")
    except Exception as e:
        st.error(f"Errore generazione PDF: {e}")
