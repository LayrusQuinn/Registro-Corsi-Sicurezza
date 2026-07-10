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
st.set_page_config(page_title="Gestione Sicurezza e Cantieri | Guasti Gino", layout="wide")

# --- 2. LOGIN ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if st.query_params.get("logged_in") == "true": st.session_state.authenticated = True

if not st.session_state.authenticated:
    st.title("🔐 Accesso Riservato")
    with st.form("login_form"):
        u, p = st.text_input("Username"), st.text_input("Password", type="password")
        if st.form_submit_button("Accedi"):
            if u == "GuastiGino" and p == "Guasti2026!":
                st.session_state.authenticated = True; st.query_params["logged_in"] = "true"; st.rerun()
            else: st.error("Dati errati")
    st.stop()

# --- 3. FIREBASE E FUNZIONI ---
DB_URL = "https://corsi-sicurezza-ggi-default-rtdb.europe-west1.firebasedatabase.app/"
if not firebase_admin._apps:
    cred = credentials.Certificate(json.loads(st.secrets["firebase_json"]))
    firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})

def get_data(path): return db.reference(path, url=DB_URL).get() or {}
def update_data(path, cid, data): db.reference(f'{path}/{cid}', url=DB_URL).update(data)
def delete_data(path, cid): db.reference(f'{path}/{cid}', url=DB_URL).delete()
def push_data(path, data): db.reference(path, url=DB_URL).push(data)

def esporta_excel(dati, nome_foglio):
    df = pd.DataFrame(dati.values())
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer: df.to_excel(writer, index=False, sheet_name=nome_foglio)
    return output.getvalue()

def invia_email(nom, item, data):
    cfg = get_data('/config')
    mt, ps = cfg.get('email_mittente', ''), cfg.get('password_mittente', '')
    dest = [v['email'] for v in get_data('/destinatari').values()]
    if not dest or not ps: return
    msg = MIMEMultipart(); msg['From'] = mt; msg['To'] = ", ".join(dest); msg['Subject'] = f"Scadenza: {item}"
    msg.attach(MIMEText(f"Dipendente/Cantiere: {nom}<br>Attività: {item}<br>Data: {data}", 'html'))
    try:
        s = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        s.login(mt, ps); s.sendmail(mt, dest, msg.as_string()); s.quit()
    except: pass

@st.dialog("Conferma eliminazione")
def conferma_eliminazione(cid, path):
    if st.button("Sì, elimina"): delete_data(path, cid); st.rerun()

# --- 4. SIDEBAR ---
with st.sidebar:
    if st.button("🚪 Logout"): st.session_state.authenticated = False; st.query_params.clear(); st.rerun()
    st.header("⚙️ Impostazioni")
    with st.expander("📧 SMTP"):
        with st.form("smtp_form"):
            em = st.text_input("Mittente", value=get_data('/config').get('email_mittente', ''))
            pw = st.text_input("Password", type="password", value=get_data('/config').get('password_mittente', ''))
            if st.form_submit_button("Salva"): db.reference('/config', url=DB_URL).update({'email_mittente': em, 'password_mittente': pw}); st.rerun()
    with st.expander("🚀 Scansione e Dati"):
        if st.button("🚀 Scansione Mail"):
            for k, v in get_data('/corsi').items():
                if not v.get('notifica_inviata') and datetime.strptime(v['data_scadenza'], "%Y-%m-%d").date() <= (datetime.today().date() + timedelta(30)):
                    invia_email(v['nominativo'], v['corso'], v['data_scadenza']); update_data('/corsi', k, {'notifica_inviata': True})
            for k, v in get_data('/cantieri').items():
                if not v.get('notifica_inviata') and datetime.strptime(v['data_fine'], "%Y-%m-%d").date() <= (datetime.today().date() + timedelta(30)):
                    invia_email(v['nome_cantiere'], "Chiusura Cantiere", v['data_fine']); update_data('/cantieri', k, {'notifica_inviata': True})
        if st.button("🔄 Reset Notifiche"):
            for k in get_data('/corsi'): update_data('/corsi', k, {'notifica_inviata': False})
            for k in get_data('/cantieri'): update_data('/cantieri', k, {'notifica_inviata': False})
        
        c = get_data('/corsi')
        if c: st.download_button("📥 Export Corsi", data=esporta_excel(c, "Corsi"), file_name="Corsi.xlsx")

# --- 5. TAB E RICERCA ---
tabs = st.tabs(["📋 Corsi", "➕ Add Corso", "🏗️ Cantieri", "➕ Add Cantiere"])

with tabs[0]: # CORSI
    search = st.text_input("🔍 Cerca Corsi", key="search_c")
    with st.expander("Modifica Corso"):
        c_list = get_data('/corsi')
        sel = st.selectbox("Seleziona:", ["Seleziona..."] + [f"{d['nominativo']} - {d['corso']}" for cid, d in c_list.items()])
        if sel != "Seleziona...":
            map_c = {f"{d['nominativo']} - {d['corso']}": cid for cid, d in c_list.items()}
            cid = map_c[sel]
            with st.form("m_c"):
                n = st.text_input("Dipendente", value=c_list[cid]['nominativo'])
                c = st.text_input("Corso", value=c_list[cid]['corso'])
                if st.form_submit_button("Salva"): update_data('/corsi', cid, {"nominativo": n, "corso": c}); st.rerun()
    for cid, d in c_list.items():
        if search.lower() in (d.get('nominativo','').lower() + d.get('corso','').lower()):
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                col1.write(f"**{d.get('nominativo')}** - {d.get('corso')} (Scad: {d.get('data_scadenza')})")
                if col2.button("🗑️", key=f"del_c_{cid}"): conferma_eliminazione(cid, '/corsi')

with tabs[1]:
    with st.form("add_corso"):
        n, c, d = st.text_input("Dipendente"), st.text_input("Corso"), st.date_input("Scadenza")
        if st.form_submit_button("Salva"): push_data('/corsi', {"nominativo": n, "corso": c, "data_scadenza": str(d)}); st.rerun()

with tabs[2]: # CANTIERI
    search = st.text_input("🔍 Cerca Cantiere", key="search_can")
    with st.expander("Modifica Cantiere"):
        can_list = get_data('/cantieri')
        sel = st.selectbox("Seleziona:", ["Seleziona..."] + [d['nome_cantiere'] for cid, d in can_list.items()])
        if sel != "Seleziona...":
            map_can = {d['nome_cantiere']: cid for cid, d in can_list.items()}
            cid = map_can[sel]
            with st.form("m_can"):
                nc = st.text_input("Nome", value=can_list[cid]['nome_cantiere'])
                l = st.text_input("Luogo", value=can_list[cid]['luogo'])
                if st.form_submit_button("Salva"): update_data('/cantieri', cid, {"nome_cantiere": nc, "luogo": l}); st.rerun()
    for cid, d in can_list.items():
        if search.lower() in d.get('nome_cantiere', '').lower():
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                col1.write(f"**{d.get('nome_cantiere')}** - {d.get('luogo')} (Fine: {d.get('data_fine')})")
                if col2.button("🗑️", key=f"del_cant_{cid}"): conferma_eliminazione(cid, '/cantieri')

with tabs[3]:
    with st.form("add_cantiere"):
        nc, l, df = st.text_input("Nome"), st.text_input("Luogo"), st.date_input("Fine")
        if st.form_submit_button("Salva"): push_data('/cantieri', {"nome_cantiere": nc, "luogo": l, "data_fine": str(df)}); st.rerun()
