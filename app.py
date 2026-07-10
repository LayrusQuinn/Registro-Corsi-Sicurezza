import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import json
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Sicurezza | Guasti Gino", layout="wide")

# --- 2. SISTEMA DI LOGIN ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 Accesso Riservato - Guasti Gino Impianti")
    with st.form("login_form"):
        user_input = st.text_input("Username")
        pass_input = st.text_input("Password", type="password")
        if st.form_submit_button("Accedi"):
            if user_input == "GuastiGino" and pass_input == "Guasti2026!":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Username o Password errati")
    st.stop()

# --- 3. CONNESSIONE A FIREBASE ---
DB_URL = "https://corsi-sicurezza-ggi-default-rtdb.europe-west1.firebasedatabase.app/"
if not firebase_admin._apps:
    try:
        key_dict = json.loads(st.secrets["firebase_json"])
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})
    except Exception as e:
        st.error(f"Errore connessione DB: {e}")

# --- 4. FUNZIONI DI SUPPORTO ---
def get_data(path): return db.reference(path, url=DB_URL).get() or {}
def set_data(path, data): db.reference(path, url=DB_URL).set(data)
def push_data(path, data): db.reference(path, url=DB_URL).push(data)
def delete_data(path, cid): db.reference(f'{path}/{cid}', url=DB_URL).delete()
def reset_notifica(cid): db.reference(f'/corsi/{cid}', url=DB_URL).update({'notifica_inviata': False})

def invia_email(nominativo, corso, data_scadenza):
    config = get_data('/config')
    mittente, password = config.get('email_mittente', ''), config.get('password_mittente', '')
    destinatari = [v['email'] for v in get_data('/destinatari').values()]
    if not destinatari or not password: return "Errore Config"
    try:
        msg = MIMEMultipart()
        msg['From'], msg['To'], msg['Subject'] = mittente, ", ".join(destinatari), f"⚠️ Scadenza: {corso} - {nominativo}"
        corpo = f"<html><body><h2>Notifica</h2><p>Dipendente: {nominativo}<br>Corso: {corso}<br>Scadenza: {data_scadenza}</p></body></html>"
        msg.attach(MIMEText(corpo, 'html'))
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(mittente, password)
        server.sendmail(mittente, destinatari, msg.as_string())
        server.quit()
        return "Inviato ✅"
    except Exception as e: return f"Errore: {e}"

# --- 5. INTERFACCIA UTENTE ---
st.title("Guasti Gino Impianti S.r.l.")

with st.sidebar:
    st.header("⚙️ Impostazioni")
    if st.button("🚪 Logout"): st.session_state.authenticated = False; st.rerun()
    with st.expander("📧 Configurazione SMTP"):
        with st.form("form_smtp"):
            em, pw = st.text_input("Mittente"), st.text_input("Password App", type="password")
            if st.form_submit_button("Salva"): set_data('/config', {'email_mittente': em, 'password_mittente': pw}); st.rerun()
    if st.button("🚀 Esegui Scansione"):
        for cid, d in get_data('/corsi').items():
            if datetime.strptime(d['data_scadenza'], "%Y-%m-%d").date() <= (datetime.today().date() + timedelta(days=30)) and not d.get('notifica_inviata'):
                if "Inviato" in invia_email(d['nominativo'], d['corso'], d['data_scadenza']): db.reference(f'/corsi/{cid}', url=DB_URL).update({'notifica_inviata': True})
        st.rerun()

tab1, tab2 = st.tabs(["📋 Registro Corsi", "➕ Aggiungi Corso"])
opzioni_corsi = ["Preposto", "RLS", "Primo Soccorso", "Antincendio", "PLE", "Muletto", "Base 4H", "Specifica 12H", "DP13 Lavori in quota", "Altro"]

with tab2:
    nom = st.text_input("Dipendente")
    scelta = st.selectbox("Corso", opzioni_corsi, key="add_sel")
    corso_spec = st.text_input("Specifica nome corso") if scelta == "Altro" else scelta
    with st.form("form_add", clear_on_submit=True):
        data_s = st.date_input("Data Svolgimento")
        val = st.selectbox("Anni Validità", [1, 2, 3, 5, 10], index=3)
        if st.form_submit_button("Salva"):
            scadenza = data_s.replace(year=data_s.year + val)
            push_data('/corsi', {"nominativo": nom, "corso": corso_spec, "data_svolto": str(data_s), "data_scadenza": str(scadenza), "notifica_inviata": False})
            st.rerun()

with tab1:
    search = st.text_input("🔍 Cerca")
    corsi = get_data('/corsi')
    with st.expander("✏️ Modifica o 🗑️ Elimina"):
        if corsi:
            sel = st.selectbox("Seleziona:", [f"{d['nominativo']} - {d['corso']} ({cid})" for cid, d in corsi.items()])
            cid_m = sel.split("(")[-1].replace(")", "")
            d_m = corsi[cid_m]
            new_nom = st.text_input("Dipendente", value=d_m['nominativo'])
            new_sel = st.selectbox("Corso", opzioni_corsi, index=opzioni_corsi.index(d_m['corso']) if d_m['corso'] in opzioni_corsi else 9)
            new_spec = st.text_input("Specifica", value=d_m['corso']) if new_sel == "Altro" else new_sel
            with st.form("form_mod"):
                new_data = st.date_input("Data", value=datetime.strptime(d_m['data_svolto'], "%Y-%m-%d"))
                val_mod = st.selectbox("Anni Validità", [1, 2, 3, 5, 10], index=3)
                if st.form_submit_button("Salva"):
                    scad = new_data.replace(year=new_data.year + val_mod)
                    db.reference(f'/corsi/{cid_m}', url=DB_URL).update({"nominativo": new_nom, "corso": new_spec, "data_svolto": str(new_data), "data_scadenza": str(scad), "notifica_inviata": False})
                    st.rerun()
                if st.form_submit_button("Elimina", type="primary"): delete_data('/corsi', cid_m); st.rerun()

    cols_h = st.columns([2, 2, 1.5, 1.5, 1])
    cols_h[0].write("**Nome**"); cols_h[1].write("**Corso**"); cols_h[2].write("**Data**"); cols_h[3].write("**Scadenza**"); cols_h[4].write("**Reset**")
    for cid, d in corsi.items():
        if search.lower() in d['nominativo'].lower():
            c = st.columns([2, 2, 1.5, 1.5, 1])
            c[0].write(d['nominativo']); c[1].write(d['corso']); c[2].write(d['data_svolto']); c[3].write(d['data_scadenza'])
            if c[4].button("🔄", key=f"res_{cid}"): reset_notifica(cid); st.rerun()
