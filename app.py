import streamlit as st
from streamlit_autorefresh import st_autorefresh
import firebase_admin
from firebase_admin import credentials, db
import json
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import io
import time

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Sicurezza & Cantieri | Guasti Gino", layout="wide")
st_autorefresh(interval=2000, key="datarefresh")

# --- Utility Data ---
def to_ita(date_str):
    """Converte YYYY-MM-DD in DD/MM/YYYY"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        return date_str

# --- 2. SISTEMA DI LOGIN ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if st.query_params.get("logged_in") == "true":
    st.session_state.authenticated = True

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
            else:
                st.error("Username o Password errati")
    st.stop()

# --- 2.5 FORZA RERUN OGNI 2 SECONDI ---
if "last_manual_rerun" not in st.session_state:
    st.session_state.last_manual_rerun = time.time()

current_time = time.time()
if current_time - st.session_state.last_manual_rerun > 2:
    st.session_state.last_manual_rerun = current_time
    st.rerun()

# --- 3. CONNESSIONE A FIREBASE ---
DB_URL = "https://corsi-sicurezza-ggi-default-rtdb.europe-west1.firebasedatabase.app/"

if not firebase_admin._apps:
    try:
        if "firebase_json" in st.secrets:
            key_dict = json.loads(st.secrets["firebase_json"])
            cred = credentials.Certificate(key_dict)
            firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})
        else:
            st.error("Errore: Credenziali Firebase non trovate nei Secrets.")
            st.stop()
    except Exception as e:
        st.error(f"Errore connessione DB: {e}")

# --- 4. FUNZIONI DI DATABASE ---
def get_data(path):
    try:
        dati = db.reference(path, url=DB_URL).get()
        return dati if dati else {}
    except: return {}

def set_data(path, data):
    db.reference(path, url=DB_URL).set(data)
    st.rerun()

def push_data(path, data):
    db.reference(path, url=DB_URL).push(data)
    st.rerun()

def delete_data(path, item_id):
    db.reference(f'{path}/{item_id}', url=DB_URL).delete()
    st.rerun()

def update_data(path, item_id, data):
    db.reference(f'{path}/{item_id}', url=DB_URL).update(data)
    st.rerun()

# --- 5. LOGICA EXCEL ---
def esporta_excel(dati):
    lista_dati = []
    for cid, d in dati.items():
        lista_dati.append({
            "Nominativo": d.get('nominativo', ''),
            "Corso": d.get('corso', ''),
            "Data Svolgimento": to_ita(d.get('data_svolto', '')),
            "Data Scadenza": to_ita(d.get('data_scadenza', ''))
        })
    df = pd.DataFrame(lista_dati)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Registro Corsi')
        worksheet = writer.sheets['Registro Corsi']
        for i, col in enumerate(df.columns):
            worksheet.set_column(i, i, 15)
    return output.getvalue()

# --- 6. LOGICA EMAIL ---
def invia_email(nominativo, corso, data_scadenza):
    config = get_data('/config')
    mittente = config.get('email_mittente', '')
    password = config.get('password_mittente', '')
    destinatari_dict = get_data('/destinatari')
    destinatari = [v['email'] for v in destinatari_dict.values()] if destinatari_dict else []
    if not destinatari or not password: return "Errore Config"
    msg = MIMEMultipart()
    msg['From'] = mittente
    msg['To'] = ", ".join(destinatari)
    msg['Subject'] = f"⚠️ Notifica Scadenza: {corso} - {nominativo}"
    corpo = f"<html><body><h2>Notifica Scadenza</h2><p>Dipendente: {nominativo}<br>Corso: {corso}<br>Scadenza: {to_ita(data_scadenza)}</p></body></html>"
    msg.attach(MIMEText(corpo, 'html'))
    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(mittente, password)
        server.sendmail(mittente, destinatari, msg.as_string())
        server.quit()
        return "Inviato ✅"
    except Exception as e: return f"Errore: {e}"

def invia_email_cantiere(cantiere, parte, data_scadenza):
    config = get_data('/config')
    mittente = config.get('email_mittente', '')
    password = config.get('password_mittente', '')
    destinatari_dict = get_data('/destinatari')
    destinatari = [v['email'] for v in destinatari_dict.values()] if destinatari_dict else []
    if not destinatari or not password: return "Errore Config"
    msg = MIMEMultipart()
    msg['From'] = mittente
    msg['To'] = ", ".join(destinatari)
    msg['Subject'] = f"⚠️ Notifica Cantiere: {cantiere}"
    corpo = f"<html><body><h2>Scadenza Cantiere</h2><p>Cantiere: {cantiere}<br>Parte: {parte}<br>Scadenza: {to_ita(data_scadenza)}</p></body></html>"
    msg.attach(MIMEText(corpo, 'html'))
    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(mittente, password)
        server.sendmail(mittente, destinatari, msg.as_string())
        server.quit()
        return "Inviato ✅"
    except Exception as e: return f"Errore: {e}"

# --- 7. DIALOG E UI ---
@st.dialog("Conferma eliminazione")
def conferma_eliminazione(cid, path):
    st.write("Vuoi davvero eliminare questo record?")
    if st.button("Sì"):
        delete_data(path, cid)
        st.rerun()

@st.dialog("📝 Modifica Corso")
def modifica_corso_dialog(cid, dati_corso):
    st.write(f"**{dati_corso.get('nominativo')}** - {dati_corso.get('corso')}")
    
    # Input date con formato europeo
    dt_svolto = datetime.strptime(dati_corso.get('data_svolto'), "%Y-%m-%d")
    dt_scad = datetime.strptime(dati_corso.get('data_scadenza'), "%Y-%m-%d")
    
    new_svolto = st.date_input("Data Svolgimento", value=dt_svolto, format="DD/MM/YYYY")
    new_scad = st.date_input("Data Scadenza", value=dt_scad, format="DD/MM/YYYY")
    reset_notifica = st.checkbox("🔄 Reset notifica inviata")
    
    if st.button("💾 Salva Modifiche"):
        update_data('/corsi', cid, {
            'data_svolto': str(new_svolto),
            'data_scadenza': str(new_scad),
            'notifica_inviata': False if reset_notifica else dati_corso.get('notifica_inviata', False)
        })
        st.success("Aggiornato!")
        st.rerun()

def render_registro():
    corsi = get_data('/corsi')
    
    st.subheader("📝 Modifica Corsi")
    if corsi:
        opzioni = {cid: f"{d.get('nominativo')} - {d.get('corso')} (Scade: {to_ita(d.get('data_scadenza'))})" for cid, d in corsi.items()}
        sel = st.selectbox("Seleziona da modificare:", options=list(opzioni.keys()))
        if st.button("✏️ Modifica"):
            modifica_corso_dialog([k for k, v in opzioni.items() if v == sel][0], corsi[[k for k, v in opzioni.items() if v == sel][0]])

    st.divider()
    c1, c2 = st.columns(2)
    search = c1.text_input("🔍 Cerca")
    
    if corsi:
        for cid, d in corsi.items():
            d_scad = datetime.strptime(d['data_scadenza'], "%Y-%m-%d").date()
            if (search.lower() in d.get('nominativo', '').lower()):
                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
                    col1.write(d.get('nominativo'))
                    col2.write(d.get('corso'))
                    col3.write(to_ita(d.get('data_scadenza')))
                    if col4.button("🗑️", key=f"del_{cid}"): conferma_eliminazione(cid, '/corsi')

# --- 8. MAIN E SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Impostazioni")
    if st.button("🚀 Esegui Scansione"):
        corsi = get_data('/corsi')
        oggi = datetime.today().date()
        for cid, dati in corsi.items():
            d_scad = datetime.strptime(dati.get('data_scadenza', '2000-01-01'), "%Y-%m-%d").date()
            if d_scad <= (oggi + timedelta(days=30)) and not dati.get('notifica_inviata', False):
                invia_email(dati.get('nominativo'), dati.get('corso'), dati.get('data_scadenza'))
                db.reference(f'/corsi/{cid}', url=DB_URL).update({'notifica_inviata': True})
        st.rerun()

st.title("Guasti Gino Impianti S.r.l.")
tab1, tab2, tab3 = st.tabs(["📋 Registro", "➕ Nuovo Corso", "🏗️ Cantieri"])
with tab1: render_registro()
with tab2:
    with st.form("new_corso"):
        nom = st.text_input("Dipendente")
        c_name = st.selectbox("Corso", ["Preposto", "RLS", "Antincendio", "PLE", "Muletto", "Altro"])
        d_svolto = st.date_input("Data Svolgimento", format="DD/MM/YYYY")
        val = st.selectbox("Anni Validità", [1, 2, 3, 5, 10], index=3)
        if st.form_submit_button("Salva"):
            scad = d_svolto.replace(year=d_svolto.year + val)
            push_data('/corsi', {"nominativo": nom, "corso": c_name, "data_svolto": str(d_svolto), "data_scadenza": str(scad), "notifica_inviata": False})
with tab3:
    st.write("Gestione Cantieri (Logica analoghe a Registro)")
