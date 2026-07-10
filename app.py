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

# --- 2. CONNESSIONE A FIREBASE ---
DB_URL = "https://corsi-sicurezza-ggi-default-rtdb.europe-west1.firebasedatabase.app/"

if not firebase_admin._apps:
    try:
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

def reset_notifica(item_id):
    db.reference(f'/corsi/{item_id}', url=DB_URL).update({'notifica_inviata': False})

# --- 4. LOGICA EMAIL ---
def invia_email(nominativo, corso, data_scadenza):
    config = get_data('/config')
    mittente = config.get('email_mittente', '')
    password = config.get('password_mittente', '')
    destinatari_dict = get_data('/destinatari')
    destinatari = [v['email'] for v in destinatari_dict.values()] if destinatari_dict else []
    if not destinatari or not password: return "Errore Config"

    try:
        d_scad_ita = datetime.strptime(data_scadenza, "%Y-%m-%d").strftime("%d/%m/%Y")
    except: d_scad_ita = data_scadenza
    
    msg = MIMEMultipart()
    msg['From'] = mittente
    msg['To'] = ", ".join(destinatari)
    msg['Subject'] = f"⚠️ Notifica Scadenza Formazione: {corso} - {nominativo}"
    corpo = f"Buongiorno, il corso {corso} per {nominativo} scade il {d_scad_ita}."
    msg.attach(MIMEText(corpo, 'plain'))

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(mittente, password)
        server.sendmail(mittente, destinatari, msg.as_string())
        server.quit()
        return "Inviato ✅"
    except Exception as e: return f"Errore: {e}"

# --- 5. INTERFACCIA UTENTE ---
st.title("Guasti Gino Impianti S.r.l.")

# --- SIDEBAR ---
with st.sidebar:
    if st.button("🚀 Esegui Scansione Generale", type="primary"):
        corsi = get_data('/corsi')
        oggi = datetime.today().date()
        soglia = oggi + timedelta(days=30)
        inviati = 0
        for cid, dati in corsi.items():
            if 'data_scadenza' in dati:
                try:
                    d_scad = datetime.strptime(dati['data_scadenza'], "%Y-%m-%d").date()
                    if d_scad <= soglia and not dati.get('notifica_inviata', False):
                        if "Inviato" in invia_email(dati.get('nominativo'), dati.get('corso'), dati.get('data_scadenza')):
                            db.reference(f'/corsi/{cid}', url=DB_URL).update({'notifica_inviata': True})
                            inviati += 1
                except: continue
        st.success(f"Inviate {inviati} email.")

# --- MAIN TAB ---
tab1, tab2 = st.tabs(["📋 Registro Corsi", "➕ Aggiungi Corso"])

with tab2:
    with st.form("form_corso", clear_on_submit=True):
        nom = st.text_input("Dipendente")
        corso = st.text_input("Corso")
        data_s = st.date_input("Data Svolgimento")
        val = st.selectbox("Anni Validità", [1, 2, 3, 5, 10], index=3)
        if st.form_submit_button("Salva"):
            scadenza = data_s.replace(year=data_s.year + val)
            push_data('/corsi', {"nominativo": nom, "corso": corso, "data_svolto": str(data_s), "data_scadenza": str(scadenza), "notifica_inviata": False})
            st.rerun()

with tab1:
    st.subheader("Filtri")
    c1, c2 = st.columns(2)
    search = c1.text_input("🔍 Cerca dipendente o corso")
    filtro_stato = c2.selectbox("Filtra per stato", ["Tutti", "🔴 SCADUTO", "⚠️ IN SCADENZA", "✅ Mail inviata"])

    corsi = get_data('/corsi')
    data_list = []
    oggi = datetime.today().date()
    soglia = oggi + timedelta(days=30)
    
    for cid, d in corsi.items():
        try:
            d_scad = datetime.strptime(d['data_scadenza'], "%Y-%m-%d").date()
            stato = "✅ Mail inviata" if d.get('notifica_inviata', False) else ("🔴 SCADUTO" if d_scad < oggi else ("⚠️ IN SCADENZA" if d_scad <= soglia else "🟢 IN CORSO"))
            
            # Filtri
            if (search.lower() in d.get('nominativo', '').lower() or search.lower() in d.get('corso', '').lower()):
                if filtro_stato == "Tutti" or filtro_stato == stato:
                    data_list.append({"id": cid, "Stato": stato, "Nominativo": d.get('nominativo', ''), "Corso": d.get('corso', ''), "Scadenza": d_scad.strftime("%d/%m/%Y")})
        except: continue
    
    # Tabella con pulsanti
    for item in data_list:
        cols = st.columns([1, 2, 2, 2, 1])
        cols[0].write(item["Stato"])
        cols[1].write(item["Nominativo"])
        cols[2].write(item["Corso"])
        cols[3].write(item["Scadenza"])
        if cols[4].button("🔄 Reset", key=f"res_{item['id']}"):
            reset_notifica(item['id'])
            st.rerun()
