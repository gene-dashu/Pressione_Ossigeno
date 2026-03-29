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
        pwd = st.text_input("Inserisci la password", type="password")
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
        valore = st.text_input(label, value="", placeholder="Valore...", key=f"txt_{key}")
    with col_nd:
        st.write(" ") 
        nd = st.checkbox("N/D", key=f"chk_{key}")
    return "N/D" if nd else valore

# --- INTERFACCIA INSERIMENTO ---
st.title("🩺 Registro Pressione e Ossigeno")

with st.form("form_inserimento", clear_on_submit=True):
    c1, c2 = st.columns(2)
    with c1:
        data_ins = st.date_input("Data", datetime.now())
        sat = salute_input("Saturazione %", "sat")
        max_p = salute_input("Pressione MAX", "max")
        bpm_p = salute_input("BPM (Pressione)", "bpm_p")
    with c2:
        ora_ins = st.time_input("Ora", datetime.now().time())
        bpm_s = salute_input("BPM (Saturimetro)", "bpm_s")
        min_p = salute_input("Pressione MIN", "min")
        note = st.text_area("Note", value="")

    submit = st.form_submit_button("💾 SALVA NUOVA RIGA")

# --- LOGICA SALVATAGGIO ---
if submit:
    try:
        # Legge dati freschi
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
        
        df_finale = pd.concat([df_attuale, nuovo_record], ignore_index=True)
        conn.update(data=df_finale)
        
        st.success("✅ Riga aggiunta!")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Errore: {e}")

st.divider()

# --- ESPORTAZIONE PDF (LOGICA RINFORZATA) ---
st.subheader("🖨️ Esporta Report PDF")
cx, cy = st.columns(2)
d_start = cx.date_input("Dal", datetime.now())
d_end = cy.date_input("Al", datetime.now())

if st.button("📄 GENERA PDF"):
    try:
        df_raw = conn.read(ttl=0)
        
        # 1. Normalizzazione: Trasforma tutto in stringa e rimuovi spazi
        df_raw['Data'] = df_raw['Data'].astype(str).str.strip()
        
        # 2. Funzione di parsing multi-formato
        def robust_date_parser(date_str):
            for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    # Rimuove eventuali parti orarie se presenti
                    clean_str = date_str.split(' ')[0]
                    return datetime.strptime(clean_str, fmt).date()
                except (ValueError, IndexError):
                    continue
            return None

        # 3. Creazione colonna temporanea per il filtro
        df_raw['date_objects'] = df_raw['Data'].apply(robust_date_parser)
        
        # 4. Filtro
        df_filtrato = df_raw[
            (df_raw['date_objects'] >= d_start) & 
            (df_raw['date_objects'] <= d_end)
        ].copy()

        if df_filtrato.empty:
            st.warning(f"Nessun dato trovato tra il {d_start.strftime('%d/%m/%Y')} e il {d_end.strftime('%d/%m/%Y')}. Verifica il formato nel foglio.")
        else:
            # Rimuove la colonna tecnica e genera il PDF
            df_final_pdf = df_filtrato.drop(columns=['date_objects']).astype(str)
            
            pdf_path = "Report_Salute.pdf"
            doc = SimpleDocTemplate(pdf_path, pagesize=A4)
            elements = []
            styles = getSampleStyleSheet()
            
            elements.append(Paragraph("DIARIO PARAMETRI SALUTE", styles['Title']))
            elements.append(Spacer(1, 12))
            
            data_list = [df_final_pdf.columns.tolist()] + df_final_pdf.values.tolist()
            t = Table(data_list)
            t.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
            ]))
            elements.append(t)
            doc.build(elements)
            
            with open(pdf_path, "rb") as f:
                st.download_button("📥 Scarica PDF", f, file_name="Report_Salute.pdf")
                
    except Exception as e:
        st.error(f"Errore critico PDF: {e}")
