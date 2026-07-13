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

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Sicurezza | Guasti Gino", layout="wide")

# --- 2. SISTEMA DI LOGIN ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if st.query_params.get("logged_in") == "true": st.session_state.authenticated = True

if not st.session_state.authenticated:
    st.title("🔐 Accesso Riservato - Guasti Gino Impianti")
    with st.form("login_form"):
        user_input = st.text_input("Username")
        pass_input = st.text_input("Password", type="password")
        if st.form_submit_button("Accedi"):
            if user_input == "GuastiGino" and pass_input == "Guasti2026!":
                st.session_state.authenticated = True
                st.query_params["logged_in"] = "true"
                st.rerun()
            else: st.error("Username o Password errati")
    st.stop() 

# --- 3. CONNESSIONE FIREBASE ---
DB_URL = "https://corsi-sicurezza-ggi-default-rtdb.europe-west1.firebasedatabase.app/"
if not firebase_admin._apps:
    cred = credentials.Certificate(json.loads(st.secrets["firebase_json"]))
    firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})

# --- 4. FUNZIONI DB E EMAIL ---
@st.cache_data(ttl=10)
def get_data(path):
    dati = db.reference(path, url=DB_URL).get()
    return dati if dati else {}

def set_data(path, data): db.reference(path, url=DB_URL).set(data)
def push_data(path, data): db.reference(path, url=DB_URL).push(data)
def delete_data(path, cid): db.reference(f'{path}/{cid}', url=DB_URL).delete()

def invia_email(nominativo, corso, data_scadenza):
    config = get_data('/config')
    mt, ps = config.get('email_mittente', ''), config.get('password_mittente', '')
    dest_dict = get_data('/destinatari')
    dest = [v['email'] for v in dest_dict.values()] if dest_dict else []
    if not dest or not ps: return
    msg = MIMEMultipart(); msg['From'] = mt; msg['To'] = ", ".join(dest); msg['Subject'] = f"⚠️ Scadenza: {corso}"
    msg.attach(MIMEText(f"Dipendente: {nominativo}<br>Corso: {corso}<br>Scadenza: {data_scadenza}", 'html'))
    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    server.login(mt, ps); server.sendmail(mt, dest, msg.as_string()); server.quit()

# --- 5. SIDEBAR (CONFIGURAZIONI) ---
with st.sidebar:
    if st.button("🚪 Logout"): st.session_state.authenticated = False; st.query_params.clear(); st.rerun()
    st.header("⚙️ Impostazioni")
    with st.expander("📧 Configurazione SMTP"):
        with st.form("smtp"):
            email = st.text_input("Gmail Mittente", value=get_data('/config').get('email_mittente', ''))
            pasw = st.text_input("Password App", value=get_data('/config').get('password_mittente', ''), type="password")
            if st.form_submit_button("Salva SMTP"):
                set_data('/config/email_mittente', email)
                set_data('/config/password_mittente', pasw)
                st.rerun()
    with st.expander("👥 Destinatari"):
        for cid, d in get_data('/destinatari').items():
            c1, c2 = st.columns([3, 1])
            c1.text(d['email'])
            if c2.button("🗑️", key=f"del_{cid}"): delete_data('/destinatari', cid); st.rerun()
        nuova_mail = st.text_input("Nuova email:")
        if st.button("Aggiungi"): push_data('/destinatari', {"email": nuova_mail}); st.rerun()

# --- 6. INTERFACCIA PRINCIPALE ---
st.title("Guasti Gino Impianti S.r.l.")
tab1, tab2 = st.tabs(["📋 Registro Corsi", "➕ Aggiungi Corso"])

with tab2:
    with st.form("add_c"):
        nom = st.text_input("Dipendente")
        corso = st.selectbox("Corso", ["Preposto", "RLS", "Antincendio", "PLE", "Altro"])
        data_s = st.date_input("Data Svolgimento", format="DD/MM/YYYY")
        val = st.selectbox("Anni Validità", [1, 2, 3, 5, 10], index=3)
        if st.form_submit_button("💾 Salva"):
            scad = data_s.replace(year=data_s.year + val)
            push_data('/corsi', {"nominativo": nom, "corso": corso, "data_svolto": str(data_s), "data_scadenza": str(scad), "notifica_inviata": False})
            st.rerun()

with tab1:
    corsi = get_data('/corsi')
    search = st.text_input("🔍 Cerca Dipendente")
    for cid, d in corsi.items():
        if search.lower() in d.get('nominativo', '').lower():
            d_scad = datetime.strptime(d['data_scadenza'], "%Y-%m-%d").date()
            if d_scad < datetime.today().date(): stato, col = "🔴 SCADUTO", "red"
            elif d_scad <= (datetime.today().date()+timedelta(30)): stato, col = "⚠️ IN SCADENZA", "orange"
            elif d.get('notifica_inviata'): stato, col = "✅ Mail inviata", "green"
            else: stato, col = "🟢 IN CORSO", "blue"
            
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1, 0.5])
                c1.markdown(f":{col}[**{d['nominativo']}** | {d['corso']} | Scad: {d['data_scadenza']} | {stato}]")
                with c2.expander("✏️ Modifica"):
                    with st.form(f"m_{cid}"):
                        n = st.text_input("Nome", value=d['nominativo'])
                        ds = st.date_input("Data Svolgimento", value=datetime.strptime(d['data_svolto'], "%Y-%m-%d"))
                        if st.form_submit_button("Aggiorna"):
                            db.reference(f'/corsi/{cid}', url=DB_URL).update({"nominativo": n, "data_svolto": str(ds)})
                            st.rerun()
                if c3.button("🗑️", key=f"del_{cid}"): delete_data('/corsi', cid); st.rerun()
