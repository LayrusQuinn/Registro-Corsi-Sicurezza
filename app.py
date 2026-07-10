import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import json
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import io

# --- 1. CONFIGURAZIONE E CACHE ---
st.set_page_config(page_title="Gestione Tecnica - Guasti Gino", layout="wide")
DB_URL = "https://corsi-sicurezza-ggi-default-rtdb.europe-west1.firebasedatabase.app/"

if not firebase_admin._apps:
    cred = credentials.Certificate(json.loads(st.secrets["firebase_json"]))
    firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})

@st.cache_data(ttl=60)
def get_data_cached(path): return db.reference(path, url=DB_URL).get() or {}

def push_data(path, data): 
    db.reference(path, url=DB_URL).push(data)
    st.cache_data.clear()

def update_data(path, cid, data): 
    db.reference(f'{path}/{cid}', url=DB_URL).update(data)
    st.cache_data.clear()

def delete_data(path, cid): 
    db.reference(f'{path}/{cid}', url=DB_URL).delete()
    st.cache_data.clear()

# --- 2. LOGICA EMAIL E EXCEL ---
def to_excel(dati):
    df = pd.DataFrame(dati.values())
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer: df.to_excel(writer, index=False)
    return output.getvalue()

def invia_email(oggetto, corpo):
    cfg = get_data_cached('/config')
    mt, ps = cfg.get('email_mittente', ''), cfg.get('password_mittente', '')
    dest = [v['email'] for v in get_data_cached('/destinatari').values()]
    if not dest or not ps: return
    msg = MIMEMultipart(); msg['From'] = mt; msg['To'] = ", ".join(dest); msg['Subject'] = oggetto
    msg.attach(MIMEText(f"<html><body>{corpo}</body></html>", 'html'))
    try:
        s = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        s.login(mt, ps); s.sendmail(mt, dest, msg.as_string()); s.quit()
    except Exception as e: st.error(f"Errore Mail: {e}")

@st.dialog("Conferma eliminazione")
def conferma_eliminazione(cid, path):
    if st.button("SÌ, ELIMINA DEFINITIVAMENTE"): delete_data(path, cid); st.rerun()

# --- 3. SIDEBAR E OPERAZIONI ---
with st.sidebar:
    st.header("⚙️ Pannello Operativo")
    if st.button("🚀 AVVIA SCANSIONE TOTALE"):
        oggi = datetime.today().date()
        soglia = oggi + timedelta(days=30)
        # Processo Corsi
        for k, v in get_data_cached('/corsi').items():
            try:
                if not v.get('notifica_inviata') and datetime.strptime(v.get('data_scadenza','2000-01-01'), "%Y-%m-%d").date() <= soglia:
                    invia_email(f"⚠️ Scadenza: {v['corso']}", f"Dipendente: {v['nominativo']}<br>Scadenza: {v['data_scadenza']}")
                    update_data('/corsi', k, {'notifica_inviata': True})
            except: continue
        # Processo Cantieri
        for k, v in get_data_cached('/cantieri').items():
            try:
                if not v.get('notifica_inviata') and datetime.strptime(v.get('data_fine','2000-01-01'), "%Y-%m-%d").date() <= soglia:
                    invia_email(f"🏗️ Chiusura: {v['nome_cantiere']}", f"Cantiere: {v['nome_cantiere']}<br>Fine: {v['data_fine']}")
                    update_data('/cantieri', k, {'notifica_inviata': True})
            except: continue
        st.success("Scansione completata!")
    
    if st.button("🔄 Reset Totale Notifiche"):
        for p in ['/corsi', '/cantieri']:
            for k in get_data_cached(p): update_data(p, k, {'notifica_inviata': False})
    
    st.divider()
    st.download_button("📥 Esporta Corsi (Excel)", to_excel(get_data_cached('/corsi')), "Corsi.xlsx")
    st.download_button("📥 Esporta Cantieri (Excel)", to_excel(get_data_cached('/cantieri')), "Cantieri.xlsx")

# --- 4. INTERFACCIA TABS ---
tabs = st.tabs(["📋 Registro Corsi", "➕ Add Corso", "🏗️ Registro Cantieri", "➕ Add Cantiere"])

# LOGICA CORSI
with tabs[0]:
    search = st.text_input("🔍 Cerca Dipendente/Corso")
    for cid, d in get_data_cached('/corsi').items():
        if search.lower() in (d.get('nominativo', '').lower() + d.get('corso', '').lower()):
            scad = datetime.strptime(d.get('data_scadenza','2000-01-01'), "%Y-%m-%d").date()
            stato, col = ("🔴 SCADUTO", "red") if scad < datetime.today().date() else ("⚠️ IN SCADENZA", "orange") if scad <= (datetime.today().date()+timedelta(30)) else ("🟢 OK", "green")
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"**{d['nominativo']}** | {d['corso']} | Scad: {d['data_scadenza']} | :{col}[**{stato}**]")
                if c2.button("🗑️", key=f"del_c_{cid}"): conferma_eliminazione(cid, '/corsi')

with tabs[1]:
    with st.form("a_c"):
        n, c = st.text_input("Nominativo"), st.selectbox("Corso", ["Preposto", "RLS", "Antincendio", "Altro"])
        d = st.date_input("Scadenza")
        if st.form_submit_button("Salva"): push_data('/corsi', {"nominativo": n, "corso": c, "data_scadenza": str(d), "notifica_inviata": False}); st.rerun()

# LOGICA CANTIERI
with tabs[2]:
    search_can = st.text_input("🔍 Cerca Cantiere")
    for cid, d in get_data_cached('/cantieri').items():
        if search_can.lower() in d.get('nome_cantiere', '').lower():
            fine = datetime.strptime(d.get('data_fine','2000-01-01'), "%Y-%m-%d").date()
            stato, col = ("🔴 CHIUSO", "red") if fine < datetime.today().date() else ("🟢 IN CORSO", "green")
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"**{d['nome_cantiere']}** | {d['luogo']} | Fine: {d['data_fine']} | :{col}[**{stato}**]")
                if c2.button("🗑️", key=f"del_can_{cid}"): conferma_eliminazione(cid, '/cantieri')

with tabs[3]:
    with st.form("a_can"):
        nc, l = st.text_input("Nome Cantiere"), st.text_input("Luogo")
        df = st.date_input("Data Fine")
        if st.form_submit_button("Salva"): push_data('/cantieri', {"nome_cantiere": nc, "luogo": l, "data_fine": str(df), "notifica_inviata": False}); st.rerun()
