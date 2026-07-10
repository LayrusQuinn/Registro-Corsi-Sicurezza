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
    st.title("🔐 Accesso Riservato - Guasti Gino")
    with st.form("login_form_main"):
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        if st.form_submit_button("Accedi"):
            if user == "GuastiGino" and pwd == "Guasti2026!":
                st.session_state.authenticated = True
                st.query_params["logged_in"] = "true"
                st.rerun()
            else: st.error("Dati errati")
    st.stop() 

# --- 3. FIREBASE ---
DB_URL = "https://corsi-sicurezza-ggi-default-rtdb.europe-west1.firebasedatabase.app/"
if not firebase_admin._apps:
    key_dict = json.loads(st.secrets["firebase_json"])
    cred = credentials.Certificate(key_dict)
    firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})

# --- 4. FUNZIONI ---
def get_data(path): return db.reference(path, url=DB_URL).get() or {}
def push_data(path, data): db.reference(path, url=DB_URL).push(data)
def delete_data(path, cid): db.reference(f'{path}/{cid}', url=DB_URL).delete()
def update_data(path, cid, data): db.reference(f'{path}/{cid}', url=DB_URL).update(data)

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
    msg = MIMEMultipart(); msg['From'] = mt; msg['To'] = ", ".join(dest); msg['Subject'] = f"Scadenza: {cor}"
    msg.attach(MIMEText(f"Nominativo: {nom}<br>Scadenza: {sca}", 'html'))
    try:
        s = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        s.login(mt, ps); s.sendmail(mt, dest, msg.as_string()); s.quit()
    except: pass

@st.dialog("Conferma eliminazione")
def conferma_eliminazione(cid, path):
    st.write("Vuoi davvero eliminare questo record?")
    if st.button("Sì, elimina"): delete_data(path, cid); st.rerun()

# --- 5. SIDEBAR ---
with st.sidebar:
    if st.button("🚪 Logout"): st.session_state.authenticated = False; st.query_params.clear(); st.rerun()
    st.header("⚙️ Impostazioni")
    with st.expander("📧 Configurazione SMTP"):
        with st.form("smtp_form_side"):
            em = st.text_input("Mittente", value=get_data('/config').get('email_mittente', ''))
            pw = st.text_input("Password App", type="password", value=get_data('/config').get('password_mittente', ''))
            if st.form_submit_button("Salva Credenziali"): db.reference('/config', url=DB_URL).update({'email_mittente': em, 'password_mittente': pw}); st.rerun()
    with st.expander("👥 Destinatari"):
        for k, v in get_data('/destinatari').items():
            c1, c2 = st.columns([3, 1])
            c1.write(v['email'])
            if c2.button("🗑️", key=f"dest_{k}"): delete_data('/destinatari', k); st.rerun()
        nuova = st.text_input("Aggiungi email")
        if st.button("Aggiungi"): push_data('/destinatari', {"email": nuova}); st.rerun()
    st.divider()
    if st.button("🚀 Scansione Scadenze"):
        for k, v in get_data('/corsi').items():
            if datetime.strptime(v['data_scadenza'], "%Y-%m-%d").date() <= (datetime.today().date() + timedelta(30)):
                invia_email(v['nominativo'], v['corso'], v['data_scadenza'])
                db.reference(f'/corsi/{k}', url=DB_URL).update({'notifica_inviata': True})
    if st.button("🔄 Reset Mail Inviate"):
        for k in get_data('/corsi'): db.reference(f'/corsi/{k}', url=DB_URL).update({'notifica_inviata': False})
    st.divider()
    # Esportazione
    corsi = get_data('/corsi')
    if corsi: st.download_button("📥 Esporta Corsi Excel", data=esporta_excel(corsi, "Corsi"), file_name="Corsi.xlsx")
    cantieri = get_data('/cantieri')
    if cantieri: st.download_button("📥 Esporta Cantieri Excel", data=esporta_excel(cantieri, "Cantieri"), file_name="Cantieri.xlsx")

# --- 6. TAB PRINCIPALI ---
tabs = st.tabs(["📋 Registro Corsi", "➕ Aggiungi Corso", "🏗️ Cantieri", "➕ Aggiungi Cantiere"])
oggi = datetime.today().date()

with tabs[0]: # CORSI
    corsi = get_data('/corsi')
    with st.expander("✏️ Modifica o 🗑️ Elimina Corso"):
        if corsi:
            sel = st.selectbox("Seleziona corso:", ["Seleziona..."] + [f"{d.get('nominativo')} - {d.get('corso')}" for cid, d in corsi.items()])
            if sel != "Seleziona...":
                map_c = {f"{d.get('nominativo')} - {d.get('corso')}": cid for cid, d in corsi.items()}
                cid_m = map_c[sel]
                with st.form(f"mod_corso_{cid_m}"):
                    n = st.text_input("Dipendente", value=corsi[cid_m].get('nominativo'))
                    c = st.text_input("Corso", value=corsi[cid_m].get('corso'))
                    if st.form_submit_button("Salva"): update_data('/corsi', cid_m, {"nominativo": n, "corso": c}); st.rerun()
    for cid, d in corsi.items():
        try:
            d_s = datetime.strptime(d['data_scadenza'], "%Y-%m-%d").date()
            st_txt, lab = (("🔴 SCADUTO", "red") if d_s < oggi else ("⚠️ IN SCADENZA", "orange") if d_s <= (oggi+timedelta(30)) else ("🟢 OK", "blue"))
            with st.container(border=True):
                c = st.columns([2,2,1,1,0.5])
                c[0].markdown(f":{lab}[{d.get('nominativo')}]"); c[1].markdown(f":{lab}[{d.get('corso')}]")
                c[2].markdown(f":{lab}[{d.get('data_scadenza')}]"); c[3].markdown(f":{lab}[**{st_txt}**]")
                if c[4].button("🗑️", key=f"del_c_{cid}"): conferma_eliminazione(cid, '/corsi')
        except: pass

with tabs[1]:
    with st.form("form_add_corso_new"):
        n, c, d = st.text_input("Dipendente"), st.text_input("Corso"), st.date_input("Scadenza")
        if st.form_submit_button("Salva"): push_data('/corsi', {"nominativo": n, "corso": c, "data_scadenza": str(d)}); st.rerun()

with tabs[2]: # CANTIERI
    cantieri = get_data('/cantieri')
    with st.expander("✏️ Modifica o 🗑️ Elimina Cantiere"):
        if cantieri:
            sel = st.selectbox("Seleziona cantiere:", ["Seleziona..."] + [f"{d.get('nome_cantiere')}" for cid, d in cantieri.items()])
            if sel != "Seleziona...":
                map_can = {f"{d.get('nome_cantiere')}": cid for cid, d in cantieri.items()}
                cid_m = map_can[sel]
                with st.form(f"mod_cant_{cid_m}"):
                    nc = st.text_input("Nome", value=cantieri[cid_m].get('nome_cantiere'))
                    l = st.text_input("Luogo", value=cantieri[cid_m].get('luogo'))
                    if st.form_submit_button("Salva"): update_data('/cantieri', cid_m, {"nome_cantiere": nc, "luogo": l}); st.rerun()
    for cid, d in cantieri.items():
        try:
            d_f = datetime.strptime(d['data_fine'], "%Y-%m-%d").date()
            st_txt, lab = (("🔴 CHIUSO", "red") if d_f < oggi else ("⚠️ IN CHIUSURA", "orange") if d_f <= (oggi+timedelta(30)) else ("🟢 ATTIVO", "blue"))
            with st.container(border=True):
                c = st.columns([2,2,1,1,0.5])
                c[0].markdown(f":{lab}[{d.get('nome_cantiere')}]"); c[1].markdown(f":{lab}[{d.get('luogo')}]")
                c[2].markdown(f":{lab}[{d.get('data_fine')}]"); c[3].markdown(f":{lab}[**{st_txt}**]")
                if c[4].button("🗑️", key=f"del_cant_{cid}"): conferma_eliminazione(cid, '/cantieri')
        except: pass

with tabs[3]:
    with st.form("form_add_cant_new"):
        nc, l, df = st.text_input("Nome Cantiere"), st.text_input("Luogo"), st.date_input("Data Fine")
        if st.form_submit_button("Salva"): push_data('/cantieri', {"nome_cantiere": nc, "luogo": l, "data_fine": str(df)}); st.rerun()
