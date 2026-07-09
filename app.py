import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import json
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Sicurezza | Guasti Gino", page_icon="🛡️", layout="wide")

# --- 2. CONNESSIONE A FIREBASE ---
DB_URL = "https://corsi-sicurezza-ggi-default-rtdb.europe-west1.firebasedatabase.app/"

if not firebase_admin._apps:
    try:
        # Recupera le credenziali dai Secrets di Streamlit
        key_dict = json.loads(st.secrets["firebase_json"])
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})
    except Exception as e:
        st.error(f"Errore connessione DB: {e}")

# --- 3. FUNZIONI DI DATABASE ---
def get_data(path):
    try:
        dati = db.reference(path, url=DB_URL).get()
        return dati if dati else {}
    except: return {}

def set_data(path, data):
    db.reference(path, url=DB_URL).set(data)

def push_data(path, data):
    db.reference(path, url=DB_URL).push(data)

def delete_data(path, item_id):
    db.reference(f'{path}/{item_id}', url=DB_URL).delete()

# --- 4. LOGICA EMAIL ---
def invia_email(nominativo, corso, data_scadenza):
    config = get_data('/config')
    mittente = config.get('email_mittente', '')
    password = config.get('password_mittente', '')
    destinatari_dict = get_data('/destinatari')
    destinatari = [v['email'] for v in destinatari_dict.values()] if destinatari_dict else []

    if not destinatari: return "No destinatari"
    if not password: return "No credenziali SMTP"

    msg = MIMEMultipart()
    msg['From'] = mittente
    msg['To'] = ", ".join(destinatari)
    msg['Subject'] = f"Notifica Scadenza: {nominativo} - {corso}"
    
    d_scad_ita = datetime.strptime(data_scadenza, "%Y-%m-%d").strftime("%d/%m/%Y")
    corpo = f"Scadenza corso {corso} per {nominativo}. Scade il: {d_scad_ita}"
    msg.attach(MIMEText(corpo, 'plain'))

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(mittente, password)
        server.sendmail(mittente, destinatari, msg.as_string())
        server.quit()
        return "Inviato ✅"
    except Exception as e:
        st.error(f"Errore SMTP: {e}")
        return f"Errore: {e}"

# --- 5. INTERFACCIA UTENTE ---
st.title("🏢 Guasti Gino Impianti S.r.l.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Impostazioni Sistema")
    
    with st.expander("📧 Configurazione SMTP"):
        with st.form("form_smtp"):
            email_mit = st.text_input("Gmail Mittente", value=get_data('/config').get('email_mittente', ''))
            pass_mit = st.text_input("Password App", value=get_data('/config').get('password_mittente', ''), type="password")
            if st.form_submit_button("Salva Credenziali"):
                set_data('/config/email_mittente', email_mit)
                set_data('/config/password_mittente', pass_mit)
                st.success("Salvato!")
                st.rerun()

    with st.expander("👥 Destinatari"):
        dest_attuali = get_data('/destinatari')
        for d_id, d_dati in dest_attuali.items():
            col1, col2 = st.columns([3, 1])
            col1.write(d_dati.get('email', ''))
            if col2.button("🗑️", key=d_id):
                delete_data('/destinatari', d_id)
                st.rerun()
        nuova_email = st.text_input("Aggiungi email:")
        if st.button("Aggiungi"):
            if "@" in nuova_email:
                push_data('/destinatari', {"email": nuova_email})
                st.rerun()
    
    st.divider()
    
    if st.button("🚀 Esegui Scansione", type="primary"):
        corsi = get_data('/corsi')
        oggi = datetime.today().date()
        soglia = oggi + timedelta(days=30)
        inviati = 0
        
        for cid, dati in corsi.items():
            if 'data_scadenza' in dati:
                d_scad = datetime.strptime(dati['data_scadenza'], "%Y-%m-%d").date()
                if d_scad <= soglia:
                    esito = invia_email(dati.get('nominativo', 'N/D'), dati.get('corso', 'N/D'), dati.get('data_scadenza', 'N/D'))
                    if "Inviato" in esito:
                        db.reference(f'/corsi/{cid}', url=DB_URL).update({'notifica_inviata': True})
                        inviati += 1
        
        st.success(f"Scansione completata! Inviate {inviati} email.")

# --- MAIN ---
tab1, tab2 = st.tabs(["📋 Registro Corsi", "➕ Aggiungi Corso"])

with tab2:
    with st.form("form_corso", clear_on_submit=True):
        nom = st.text_input("Dipendente")
        corso = st.text_input("Corso")
        data_s = st.date_input("Data Svolgimento", format="DD/MM/YYYY")
        val = st.selectbox("Anni Validità", [1, 2, 3, 5, 10], index=3)
        if st.form_submit_button("Salva Corso"):
            scadenza = data_s.replace(year=data_s.year + val)
            push_data('/corsi', {
                "nominativo": nom, "corso": corso, 
                "data_svolto": str(data_s), "data_scadenza": str(scadenza), 
                "notifica_inviata": False
            })
            st.success("Corso salvato!")
            st.rerun()

with tab1:
    with st.expander("🗑️ Gestione Archivi: Rimuovi un corso"):
        corsi_da_eliminare = get_data('/corsi')
        if corsi_da_eliminare:
            opzioni = {f"{d.get('nominativo', 'N/A')} - {d.get('corso', 'N/A')}": cid for cid, d in corsi_da_eliminare.items()}
            selezione = st.selectbox("Seleziona il corso da eliminare:", list(opzioni.keys()))
            
            if st.button("⚠️ Elimina Definitivamente", type="primary"):
                delete_data('/corsi', opzioni[selezione])
                st.success("Corso eliminato correttamente!")
                st.rerun()
        else:
            st.write("Nessun corso presente da eliminare.")

    st.divider()
    
    corsi = get_data('/corsi')
    if corsi:
        data_list = []
        oggi = datetime.today().date()
        soglia = oggi + timedelta(days=30)
        for cid, d in corsi.items():
            if 'nominativo' in d and 'corso' in d:
                d_scad = datetime.strptime(d['data_scadenza'], "%Y-%m-%d").date()
                if d.get('notifica_inviata', False): stato = "✅ Mail inviata"
                elif d_scad < oggi: stato = "🔴 SCADUTO"
                elif d_scad <= soglia: stato = "⚠️ IN SCADENZA"
                else: stato = "🟢 IN CORSO"
                data_list.append({
                    "Stato": stato, "Nominativo": d['nominativo'], "Corso": d['corso'],
                    "Data Svolto": datetime.strptime(d['data_svolto'], "%Y-%m-%d").strftime("%d/%m/%Y"),
                    "Data Scadenza": datetime.strptime(d['data_scadenza'], "%Y-%m-%d").strftime("%d/%m/%Y")
                })
        st.dataframe(pd.DataFrame(data_list), use_container_width=True, hide_index=True)
    else:
        st.info("Nessun corso presente nel registro.")