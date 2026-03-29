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
# Impostiamo ttl a 0 per forzare la lettura di dati freschi ogni volta
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNZIONE INPUT (CAMPO VUOTO + CHECKBOX N/D) ---
def salute_input(label, key):
    col_text, col_nd = st.columns([3, 1])
    with col_text:
        valore = st.text_input(label, value="", placeholder="Inserisci valore...", key=f"txt_{key}")
    with col_nd:
        st.write(" ") 
        nd = st.checkbox("N/D", key=f"chk_{key}")
    return "N/D" if nd else valore

# --- INTERFACCIA DI INSERIMENTO ---
st.title("🩺 Registro Pressione e Ossigeno")

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
        note = st.text_area("Note", value="", placeholder="Annotazioni...")

    submit = st.form_submit_button("💾 AGGIUNGI NUOVA RIGA")

# --- LOGICA SALVATAGGIO (APPEND SICURO) ---
if submit:
    try:
        # Leggiamo i dati attuali per non perdere nulla
        df_attuale = conn.read(ttl=0)
        
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
        
        # Concateniamo i nuovi dati a quelli vecchi
        df_finale = pd.concat([df_attuale, nuovo_record], ignore_index=True)
        
        # Aggiorniamo il foglio
        conn.update(data=df_finale)
        
        st.success("✅ Riga aggiunta con successo!")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Errore nel salvataggio: {e}")

st.divider()

# --- ESPORTAZIONE PDF (RISOLUZIONE ERRORE DATE) ---
st.subheader("🖨️ Esporta Report Stampabile")
cx, cy = st.columns(2)
d_start = cx.date_input("Data Inizio", datetime.now())
d_end = cy.date_input("Data Fine", datetime.now())

if st.button("📄 GENERA PDF"):
    try:
        # Legge dati senza cache
        df_raw = conn.read(ttl=0)
        
        # Forza la colonna Data a stringa per evitare il problema del tipo datetime64[ns]
        df_raw['Data'] = df_raw['Data'].astype(str)
        
        # Funzione di conversione sicura per il filtro
        def parse_date(x):
            try:
                return datetime.strptime(x, "%d/%m/%Y").date()
            except:
                try:
                    # Tenta di gestire casi in cui Pandas ha già convertito parzialmente
                    return pd.to_datetime(x).date()
                except:
                    return None

        df_raw['tmp_dt'] = df_raw['Data'].apply(parse_date)
        df_clean = df_raw.dropna(subset=['tmp_dt'])
        
        # Filtro range (confronto tra oggetti .date() puri)
        mask = (df_clean['tmp_dt'] >= d_start) & (df_clean['tmp_dt'] <= d_end)
        df_pdf = df_clean.loc[mask].drop(columns=['tmp_dt']).astype(str)
        
        if df_pdf.empty:
            st.warning("Nessun dato trovato per questo range.")
        else:
            pdf_name = "Report_Salute.pdf"
            doc = SimpleDocTemplate(pdf_name, pagesize=A4)
            elements = []
            styles = getSampleStyleSheet()
            
            elements.append(Paragraph("DIARIO PARAMETRI SALUTE", styles['Title']))
            elements.append(Spacer(1, 12))
            
            # Creazione Tabella PDF
            data_list = [df_pdf.columns.tolist()] + df_pdf.values.tolist()
            t = Table(data_list)
            t.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
            ]))
            elements.append(t)
            doc.build(elements)
            
            with open(pdf_name, "rb") as f:
                st.download_button("📥 Scarica PDF", f, file_name="Report_Salute.pdf")
                
    except Exception as e:
        st.error(f"Errore generazione PDF: {e}")
