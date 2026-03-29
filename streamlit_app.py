import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Monitor Salute", layout="centered")

# --- PROTEZIONE PASSWORD ---
def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 Accesso Protetto")
        pwd = st.text_input("Inserisci la password per continuare", type="password")
        if st.button("Accedi"):
            if pwd == st.secrets["passwords"]["access_password"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Password errata")
        return False
    return True

if not check_password():
    st.stop()

# --- CONNESSIONE GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNZIONE INPUT (CAMPO VUOTO + CHECKBOX N/D) ---
def salute_input(label, key):
    col_text, col_nd = st.columns([3, 1])
    with col_text:
        valore = st.text_input(label, value="", placeholder="Inserisci valore...", key=f"txt_{key}")
    with col_nd:
        st.write(" ") # Allineamento estetico
        nd = st.checkbox("N/D", key=f"chk_{key}")
    return "N/D" if nd else valore

# --- INTERFACCIA DI INSERIMENTO ---
st.title("🩺 Registro Pressione e Ossigeno")
st.info("Nota: Lo script aggiunge solo nuove righe. Per modifiche o cancellazioni, agire direttamente sul Foglio Google.")

with st.form("form_inserimento", clear_on_submit=True):
    c1, c2 = st.columns(2)
    
    with c1:
        data_ins = st.date_input("Data misurazione", datetime.now())
        sat = salute_input("Saturazione %", "sat")
        max_p = salute_input("Pressione MAX", "max")
        bpm_p = salute_input("BPM (Misuratore Pressione)", "bpm_p")
        
    with c2:
        ora_ins = st.time_input("Ora misurazione", datetime.now().time())
        bpm_s = salute_input("BPM (Saturimetro)", "bpm_s")
        min_p = salute_input("Pressione MIN", "min")
        note = st.text_area("Note", value="", placeholder="Eventuali annotazioni...")

    submit = st.form_submit_button("💾 AGGIUNGI RIGA AL FOGLIO")

# --- LOGICA SALVATAGGIO (SOLO APPEND) ---
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
        # Il metodo .create aggiunge i dati in coda senza sovrascrivere l'esistente
        conn.create(data=nuovo_record)
        st.success("✅ Riga aggiunta correttamente in fondo al foglio!")
        time.sleep(1.5)
        st.rerun()
    except Exception as e:
        st.error(f"Errore nel salvataggio: {e}")

st.divider()

# --- ESPORTAZIONE PDF ---
st.subheader("🖨️ Esporta Report Stampabile")
cx, cy = st.columns(2)
d_start = cx.date_input("Data Inizio", datetime.now())
d_end = cy.date_input("Data Fine", datetime.now())

if st.button("📄 GENERA PDF"):
    try:
        # La lettura serve solo per generare il PDF locale, non scrive nulla
        df_raw = conn.read()
        
        # Conversione sicura per confronto date
        df_raw['tmp_dt'] = pd.to_datetime(df_raw['Data'], format="%d/%m/%Y", errors='coerce').dt.date
        df_clean = df_raw.dropna(subset=['tmp_dt'])
        
        # Filtro range
        mask = (df_clean['tmp_dt'] >= d_start) & (df_clean['tmp_dt'] <= d_end)
        df_final = df_clean.loc[mask].drop(columns=['tmp_dt']).astype(str)
        
        if df_final.empty:
            st.warning("Nessun dato trovato per il periodo selezionato.")
        else:
            pdf_name = "Report_Salute.pdf"
            doc = SimpleDocTemplate(pdf_name, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
            elements = []
            styles = getSampleStyleSheet()
            
            elements.append(Paragraph("DIARIO PARAMETRI SALUTE", styles['Title']))
            elements.append(Paragraph(f"Periodo: {d_start.strftime('%d/%m/%Y')} - {d_end.strftime('%d/%m/%Y')}", styles['Normal']))
            elements.append(Spacer(1, 12))
            
            # Tabella con bordi per PDF
            data_list = [df_final.columns.tolist()] + df_final.values.tolist()
            t = Table(data_list)
            t.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            
            elements.append(t)
            doc.build(elements)
            
            with open(pdf_name, "rb") as f:
                st.download_button("📥 Scarica il file PDF", f, file_name=f"Report_{d_start.strftime('%d_%m')}.pdf")
                
    except Exception as e:
        st.error(f"Errore generazione PDF: {e}")
