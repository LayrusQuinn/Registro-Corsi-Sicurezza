import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import json
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Sicurezza | Guasti Gino", layout="wide")

# --- 2. SISTEMA DI LOGIN ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if not st.session_state.authenticated:
    st.title("🔐 Accesso Riservato - Guasti Gino Impianti")
    with st.form("login_form"):
        user_input = st.text_input("Username")
        pass_input = st.text_input("Password", type="password")
        if st.form_submit_button("Accedi"):
            if user_input == "GuastiGino" and pass_input == "Guasti2026!":
                st.session_state.authenticated = True
                st.rerun()
            else: st.error("Username o Password errati")
    st.stop()

# --- 3. CONNESSIONE A FIREBASE ---
DB_URL = "https://corsi-sicurezza-ggi-default-rtdb.europe-west1.firebasedatabase.app/"
if not firebase_admin._apps:
    try:
        key_dict = json.loads(st.secrets["firebase_json"])
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})
    except Exception as e: st.error(f"Errore connessione DB: {e}")

# --- 4. FUNZIONI DI DATABASE ---
def get_data(path): return db.reference(path, url=DB_URL).get() or {}
def set_data(path, data): db.reference(path, url=DB_URL).set(data)
def push_data(path, data): db.reference(path, url=DB_URL).push(data)
def delete_data(path, item_id): db.reference(f'{path}/{item_id}', url=DB_URL).delete()
def reset_notifica(item_id): db.reference(f'/corsi/{item_id}', url=DB_URL).update({'notifica_inviata': False})

# --- 5. LOGICA EMAIL ---
def invia_email(nominativo, corso, data_scadenza):
    config = get_data('/config')
    mittente = config.get('email_mittente', '')
    password = config.get('password_mittente', '')
    destinatari = [v['email'] for v in get_data('/destinatari').values()]
    if not destinatari or not password: return "Errore Config"
    try:
        msg = MIMEMultipart()
        msg['From'], msg['To'], msg['Subject'] = mittente, ", ".join(destinatari), f"⚠️ Notifica Scadenza: {corso} - {nominativo}"
        corpo = f"<html><body><p>Dipendente: {nominativo}<br>Corso: {corso}<br>Scadenza: {data_scadenza}</p></body></html>"
        msg.attach(MIMEText(corpo, 'html'))
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(mittente, password); server.sendmail(mittente, destinatari, msg.as_string()); server.quit()
        return "Inviato ✅"
    except Exception as e: return f"Errore: {e}"

# --- 6. INTERFACCIA ---
st.title("Guasti Gino Impianti S.r.l.")

with st.sidebar:
    if st.button("🚪 Logout"): st.session_state.authenticated = False; st.rerun()
    st.header("⚙️ Impostazioni")
    with st.expander("📧 Configurazione SMTP"):
        with st.form("form_smtp"):
            em = st.text_input("Mittente", value=get_data('/config').get('email_mittente', ''))
            pw = st.text_input("Password", value=get_data('/config').get('password_mittente', ''), type="password")
            if st.form_submit_button("Salva"): set_data('/config', {'email_mittente': em, 'password_mittente': pw}); st.rerun()
    with st.expander("👥 Destinatari"):
        for d_id, d in get_data('/destinatari').items():
            c1, c2 = st.columns([3, 1])
            c1.write(d.get('email', ''))
            if c2.button("🗑️", key=f"del_{d_id}"): delete_data('/destinatari', d_id); st.rerun()
        nuova = st.text_input("Aggiungi email:")
        if st.button("Aggiungi"): push_data('/destinatari', {"email": nuova}); st.rerun()
    
    if st.button("🚀 Esegui Scansione", type="primary"):
        inviati = 0
        for cid, d in get_data('/corsi').items():
            if datetime.strptime(d['data_scadenza'], "%Y-%m-%d").date() <= (datetime.today().date() + timedelta(30)) and not d.get('notifica_inviata'):
                if "Inviato" in invia_email(d['nominativo'], d['corso'], d['data_scadenza']):
                    db.reference(f'/corsi/{cid}', url=DB_URL).update({'notifica_inviata': True}); inviati += 1
        st.success(f"Scansione: {inviati} email.")

tab1, tab2 = st.tabs(["📋 Registro Corsi", "➕ Aggiungi Corso"])
opzioni_corsi = ["Preposto", "RLS", "Primo Soccorso", "Antincendio", "PLE", "Muletto", "Base 4H", "Specifica 12H", "DP13 Lavori in quota", "Altro"]

with tab2:
    st.subheader("Inserimento Multiplo")
    nom_add = st.text_input("Dipendente", value=st.session_state.get('last_name', ''), key="input_nom")
    scelta = st.selectbox("Corso", opzioni_corsi)
    spec = st.text_input("Specifica") if scelta == "Altro" else scelta
    data_s = st.date_input("Data Svolgimento", format="DD/MM/YYYY")
    val = st.selectbox("Anni Validità", [1, 2, 3, 5, 10], index=3)
    
    col1, col2 = st.columns(2)
    
    # LOGICA MULTIPLA
    def salva_record():
        scad = data_s.replace(year=data_s.year + val)
        push_data('/corsi', {"nominativo": nom_add, "corso": spec, "data_svolto": str(data_s), "data_scadenza": str(scad), "notifica_inviata": False})
        st.session_state.last_name = nom_add
        
    if col1.button("💾 Salva"):
        salva_record()
        st.session_state.last_name = "" # Resetta nome dopo salvataggio finale
        st.rerun()
    if col2.button("➕ Aggiungi altro corso"):
        salva_record()
        st.rerun() # Mantiene il nome in session_state

with tab1:
    search = st.text_input("🔍 Cerca")
    filtro = st.selectbox("Filtro", ["Tutti", "🟢 IN CORSO", "⚠️ IN SCADENZA", "🔴 SCADUTO"])
    corsi = get_data('/corsi')
    for cid, d in corsi.items():
        if search.lower() in d['nominativo'].lower():
            cols = st.columns([2, 2, 1, 1, 1, 1])
            cols[0].write(d['nominativo']); cols[1].write(d['corso']); cols[2].write(d['data_svolto']); cols[3].write(d['data_scadenza'])
            if cols[5].button("🔄", key=f"res_{cid}"): reset_notifica(cid); st.rerun()
