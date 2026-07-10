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

# --- 4. FUNZIONI DI DATABASE E EMAIL ---
def get_data(path): return db.reference(path, url=DB_URL).get() or {}
def set_data(path, data): db.reference(path, url=DB_URL).set(data)
def push_data(path, data): db.reference(path, url=DB_URL).push(data)
def delete_data(path, item_id): db.reference(f'{path}/{item_id}', url=DB_URL).delete()
def reset_notifica(item_id): db.reference(f'/corsi/{item_id}', url=DB_URL).update({'notifica_inviata': False})

def invia_email(nominativo, corso, data_scadenza):
    config = get_data('/config')
    mittente = config.get('email_mittente', '')
    password = config.get('password_mittente', '')
    destinatari = [v['email'] for v in get_data('/destinatari').values()]
    if not destinatari or not password: return "Errore Config"
    try:
        d_scad_ita = datetime.strptime(data_scadenza, "%Y-%m-%d").strftime("%d/%m/%Y")
        msg = MIMEMultipart()
        msg['From'], msg['To'], msg['Subject'] = mittente, ", ".join(destinatari), f"⚠️ Notifica Scadenza: {corso} - {nominativo}"
        corpo = f"<html><body><h2 style='color: #2c3e50;'>Notifica Scadenza</h2><p>Dipendente: {nominativo}<br>Corso: {corso}<br>Scadenza: <b>{d_scad_ita}</b></p></body></html>"
        msg.attach(MIMEText(corpo, 'html'))
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(mittente, password)
        server.sendmail(mittente, destinatari, msg.as_string())
        server.quit()
        return "Inviato ✅"
    except Exception as e: return f"Errore: {e}"

# --- 5. INTERFACCIA E LOGICA ---
st.title("Guasti Gino Impianti S.r.l.")

with st.sidebar:
    if st.button("🚪 Logout"): st.session_state.authenticated = False; st.rerun()
    st.header("⚙️ Impostazioni Sistema")
    with st.expander("📧 Configurazione SMTP"):
        with st.form("form_smtp"):
            email_mit = st.text_input("Gmail Mittente", value=get_data('/config').get('email_mittente', ''))
            pass_mit = st.text_input("Password App", value=get_data('/config').get('password_mittente', ''), type="password")
            if st.form_submit_button("Salva"): set_data('/config', {'email_mittente': email_mit, 'password_mittente': pass_mit}); st.rerun()
    with st.expander("👥 Destinatari"):
        for d_id, d_dati in get_data('/destinatari').items():
            col1, col2 = st.columns([3, 1])
            col1.write(d_dati.get('email', ''))
            if col2.button("🗑️", key=f"del_{d_id}"): delete_data('/destinatari', d_id); st.rerun()
        nuova = st.text_input("Aggiungi email:")
        if st.button("Aggiungi"): push_data('/destinatari', {"email": nuova}); st.rerun()
    st.divider()
    if st.button("🚀 Esegui Scansione", type="primary"):
        inviati = 0
        for cid, dati in get_data('/corsi').items():
            try:
                if datetime.strptime(dati['data_scadenza'], "%Y-%m-%d").date() <= (datetime.today().date() + timedelta(days=30)) and not dati.get('notifica_inviata'):
                    if "Inviato" in invia_email(dati['nominativo'], dati['corso'], dati['data_scadenza']):
                        db.reference(f'/corsi/{cid}', url=DB_URL).update({'notifica_inviata': True}); inviati += 1
            except: continue
        st.success(f"Scansione: {inviati} email inviate.")

tab1, tab2 = st.tabs(["📋 Registro Corsi", "➕ Aggiungi Corso"])
opzioni_corsi = ["Preposto", "RLS", "Primo Soccorso", "Antincendio", "PLE", "Muletto", "Base 4H", "Specifica 12H", "DP13 Lavori in quota", "Altro"]

with tab2:
    st.subheader("Aggiungi nuovo corso")
    nom_add = st.text_input("Dipendente", value=st.session_state.get('last_nom', ''), key="add_nom")
    st.session_state.last_nom = nom_add
    scelta_add = st.selectbox("Corso", opzioni_corsi, key="add_sel")
    corso_add = st.text_input("Specifica nome corso", key="add_altro") if scelta_add == "Altro" else scelta_add
    with st.form("form_corso", clear_on_submit=True):
        data_s = st.date_input("Data Svolgimento", format="DD/MM/YYYY")
        val = st.selectbox("Anni Validità", [1, 2, 3, 5, 10], index=3)
        if st.form_submit_button("➕ Aggiungi Corso"):
            scadenza = data_s.replace(year=data_s.year + val)
            push_data('/corsi', {"nominativo": nom_add, "corso": corso_add, "data_svolto": str(data_s), "data_scadenza": str(scadenza), "notifica_inviata": False})
            st.rerun()

with tab1:
    c1, c2 = st.columns(2)
    search = c1.text_input("🔍 Cerca")
    filtro_stato = c2.selectbox("Filtro Stato", ["Tutti", "🟢 IN CORSO", "⚠️ IN SCADENZA", "🔴 SCADUTO", "✅ Mail inviata"])
    with st.expander("✏️ Modifica o 🗑️ Elimina"):
        corsi_t = get_data('/corsi')
        if corsi_t:
            opzioni = {f"{d['nominativo']} - {d['corso']}": cid for cid, d in corsi_t.items()}
            sel = st.selectbox("Seleziona:", list(opzioni.keys()))
            cid_m = opzioni[sel]; d_m = corsi_t[cid_m]
            new_nom = st.text_input("Dipendente", value=d_m['nominativo'])
            new_sel = st.selectbox("Corso", opzioni_corsi, index=opzioni_corsi.index(d_m['corso']) if d_m['corso'] in opzioni_corsi else 9)
            new_corso = st.text_input("Specifica", value=d_m['corso']) if new_sel == "Altro" else new_sel
            with st.form("form_mod"):
                new_d = st.date_input("Data", value=datetime.strptime(d_m['data_svolto'], "%Y-%m-%d"))
                if st.form_submit_button("Salva"):
                    db.reference(f'/corsi/{cid_m}', url=DB_URL).update({"nominativo": new_nom, "corso": new_corso, "data_svolto": str(new_d), "data_scadenza": str(new_d.replace(year=new_d.year+3))})
                    st.rerun()
                if st.form_submit_button("Elimina", type="primary"): delete_data('/corsi', cid_m); st.rerun()

    lista_corsi = [{"id": cid, **d} for cid, d in get_data('/corsi').items()]
    lista_corsi.sort(key=lambda x: x['nominativo'].lower())
    
    for d in lista_corsi:
        d_scad = datetime.strptime(d['data_scadenza'], "%Y-%m-%d").date()
        stato = "✅ Mail inviata" if d.get('notifica_inviata') else "🔴 SCADUTO" if d_scad < datetime.today().date() else "⚠️ IN SCADENZA" if d_scad <= (datetime.today().date() + timedelta(30)) else "🟢 IN CORSO"
        if (search.lower() in d['nominativo'].lower()) and (filtro_stato == "Tutti" or filtro_stato == stato):
            cols = st.columns([2, 2, 1, 1, 1, 1])
            cols[0].write(d['nominativo']); cols[1].write(d['corso']); cols[2].write(d['data_svolto']); cols[3].write(d['data_scadenza']); cols[4].write(stato)
            if cols[5].button("🔄", key=f"res_{d['id']}"): reset_notifica(d['id']); st.rerun()
