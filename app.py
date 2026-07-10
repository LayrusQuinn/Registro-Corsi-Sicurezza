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

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Gestione Sicurezza e Cantieri", layout="wide")

# --- LOGIN ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if st.query_params.get("logged_in") == "true": st.session_state.authenticated = True

if not st.session_state.authenticated:
    st.title("🔐 Accesso Riservato")
    with st.form("login_form"):
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        if st.form_submit_button("Accedi"):
            if user == "GuastiGino" and pwd == "Guasti2026!":
                st.session_state.authenticated = True
                st.query_params["logged_in"] = "true"
                st.rerun()
            else: st.error("Dati errati")
    st.stop()

# --- FIREBASE ---
DB_URL = "https://corsi-sicurezza-ggi-default-rtdb.europe-west1.firebasedatabase.app/"
if not firebase_admin._apps:
    key_dict = json.loads(st.secrets["firebase_json"])
    cred = credentials.Certificate(key_dict)
    firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})

# --- FUNZIONI ---
def get_data(path): return db.reference(path, url=DB_URL).get() or {}
def push_data(path, data): db.reference(path, url=DB_URL).push(data)
def delete_data(path, cid): db.reference(f'{path}/{cid}', url=DB_URL).delete()

def esporta_excel(dati, nome):
    df = pd.DataFrame(dati.values())
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer: df.to_excel(writer, index=False, sheet_name=nome)
    return output.getvalue()

def invia_email(nom, cor, sca):
    cfg = get_data('/config')
    mt, ps = cfg.get('email_mittente', ''), cfg.get('password_mittente', '')
    dest = [v['email'] for v in get_data('/destinatari').values()]
    if not dest or not ps: return
    msg = MIMEMultipart(); msg['From']=mt; msg['To']=", ".join(dest); msg['Subject']=f"Scadenza: {cor}"
    msg.attach(MIMEText(f"Dipendente: {nom}<br>Scadenza: {sca}", 'html'))
    try:
        s = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        s.login(mt, ps); s.sendmail(mt, dest, msg.as_string()); s.quit()
    except: pass

@st.dialog("Elimina")
def conferma_eliminazione(cid, path):
    st.write("Confermi?")
    if st.button("Sì"): delete_data(path, cid); st.rerun()

# --- SIDEBAR ---
with st.sidebar:
    if st.button("🚪 Logout"): st.session_state.authenticated=False; st.query_params.clear(); st.rerun()
    st.header("⚙️ Impostazioni")
    with st.expander("SMTP"):
        with st.form("smtp"):
            em = st.text_input("Email", value=get_data('/config').get('email_mittente',''))
            pw = st.text_input("Password", type="password", value=get_data('/config').get('password_mittente',''))
            if st.form_submit_button("Salva"): db.reference('/config', url=DB_URL).update({'email_mittente':em, 'password_mittente':pw}); st.rerun()
    with st.expander("Destinatari"):
        for k, v in get_data('/destinatari').items():
            c1, c2 = st.columns([3,1])
            c1.write(v['email'])
            if c2.button("🗑️", key=k): delete_data('/destinatari', k); st.rerun()
        nuova = st.text_input("Aggiungi");
        if st.button("Aggiungi"): push_data('/destinatari', {"email": nuova}); st.rerun()
    st.divider()
    if st.button("🚀 Scansione"):
        for k, v in get_data('/corsi').items():
            if datetime.strptime(v['data_scadenza'], "%Y-%m-%d").date() <= (datetime.today().date()+timedelta(30)):
                invia_email(v['nominativo'], v['corso'], v['data_scadenza'])
                db.reference(f'/corsi/{k}', url=DB_URL).update({'notifica_inviata': True})
    if st.button("🔄 Reset Mail"):
        for k in get_data('/corsi'): db.reference(f'/corsi/{k}', url=DB_URL).update({'notifica_inviata': False})
    
    corsi = get_data('/corsi')
    if corsi: st.download_button("📥 Esporta Excel", data=esporta_excel(corsi, "Corsi"), file_name="Registro.xlsx")

# --- MAIN ---
tabs = st.tabs(["📋 Corsi", "➕ Add Corso", "🏗️ Cantieri", "➕ Add Cantiere"])
oggi = datetime.today().date()

with tabs[0]: # CORSI
    for cid, d in get_data('/corsi').items():
        try:
            d_s = datetime.strptime(d['data_scadenza'], "%Y-%m-%d").date()
            col = "red" if d_s < oggi else "orange" if d_s <= (oggi+timedelta(30)) else "blue"
            st, lab = (("🔴 SCADUTO", "red") if d_s < oggi else ("⚠️ IN SCADENZA", "orange") if d_s <= (oggi+timedelta(30)) else ("🟢 OK", "blue"))
            with st.container(border=True):
                c = st.columns([2,2,1,1,0.5])
                c[0].markdown(f":{lab}[{d['nominativo']}]"); c[1].markdown(f":{lab}[{d['corso']}]")
                c[2].markdown(f":{lab}[{d['data_scadenza']}]"); c[3].markdown(f":{lab}[**{st}**]")
                if c[4].button("🗑️", key=f"d1{cid}"): conferma_eliminazione(cid, '/corsi')
        except: pass

with tabs[1]:
    with st.form("new_c"):
        n, c, d = st.text_input("Dipendente"), st.text_input("Corso"), st.date_input("Scadenza")
        if st.form_submit_button("Salva"): push_data('/corsi', {"nominativo": n, "corso": c, "data_scadenza": str(d)}); st.rerun()

with tabs[2]: # CANTIERI
    for cid, d in get_data('/cantieri').items():
        try:
            d_f = datetime.strptime(d['data_fine'], "%Y-%m-%d").date()
            st, lab = (("🔴 CHIUSO", "red") if d_f < oggi else ("⚠️ IN CHIUSURA", "orange") if d_f <= (oggi+timedelta(30)) else ("🟢 ATTIVO", "blue"))
            with st.container(border=True):
                c = st.columns([2,2,1,1,0.5])
                c[0].markdown(f":{lab}[{d['nome_cantiere']}]"); c[1].markdown(f":{lab}[{d['luogo']}]")
                c[2].markdown(f":{lab}[{d['data_fine']}]"); c[3].markdown(f":{lab}[**{st}**]")
                if c[4].button("🗑️", key=f"d2{cid}"): conferma_eliminazione(cid, '/cantieri')
        except: pass

with tabs[3]:
    with st.form("new_cant"):
        nc, l, df = st.text_input("Nome"), st.text_input("Luogo"), st.date_input("Fine")
        if st.form_submit_button("Salva"): push_data('/cantieri', {"nome_cantiere": nc, "luogo": l, "data_fine": str(df)}); st.rerun()
