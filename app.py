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
import time
import io

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Sicurezza | Guasti Gino", layout="wide")

# --- 2. SISTEMA DI LOGIN (PERSISTENTE VIA URL) ---
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

# --- 3. CONNESSIONE A FIREBASE ---
DB_URL = "https://corsi-sicurezza-ggi-default-rtdb.europe-west1.firebasedatabase.app/"

if not firebase_admin._apps:
    try:
        key_dict = json.loads(st.secrets["firebase_json"])
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})
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

def push_data(path, data):
    db.reference(path, url=DB_URL).push(data)

def delete_data(path, item_id):
    db.reference(f'{path}/{item_id}', url=DB_URL).delete()

# --- 5. LOGICA EXCEL ---
def esporta_excel(dati):
    lista_dati = []
    for cid, d in dati.items():
        lista_dati.append({
            "Nominativo": d.get('nominativo', ''),
            "Corso": d.get('corso', ''),
            "Data Svolgimento": d.get('data_svolto', ''),
            "Data Scadenza": d.get('data_scadenza', '')
        })
    df = pd.DataFrame(lista_dati)
    df = df[["Nominativo", "Corso", "Data Svolgimento", "Data Scadenza"]]
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Registro Corsi')
        workbook  = writer.book
        worksheet = writer.sheets['Registro Corsi']
        for i, col in enumerate(df.columns):
            column_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.set_column(i, i, column_len)
    return output.getvalue()

# --- 6. LOGICA EMAIL ---
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
    corpo = f"<html><body><h2>Notifica Scadenza</h2><p>Dipendente: {nominativo}<br>Corso: {corso}<br>Scadenza: {d_scad_ita}</p></body></html>"
    msg.attach(MIMEText(corpo, 'html'))
    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(mittente, password)
        server.sendmail(mittente, destinatari, msg.as_string())
        server.quit()
        return "Inviato ✅"
    except Exception as e: return f"Errore: {e}"

# --- 7. DIALOG PER ELIMINAZIONE ---
@st.dialog("Conferma eliminazione")
def conferma_eliminazione(cid):
    st.write("Vuoi davvero eliminare questo corso?")
    if st.button("Sì, elimina"):
        delete_data('/corsi', cid)
        if 'corsi_cache' in st.session_state: del st.session_state.corsi_cache
        st.rerun()

# --- 8. INTERFACCIA UTENTE ---
st.title("Guasti Gino Impianti S.r.l.")

with st.sidebar:
    if st.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.query_params.clear()
        st.rerun()
    st.header("⚙️ Impostazioni")
    with st.expander("📧 Configurazione SMTP"):
        with st.form("form_smtp"):
            email_mit = st.text_input("Gmail Mittente", value=get_data('/config').get('email_mittente', ''))
            pass_mit = st.text_input("Password App", value=get_data('/config').get('password_mittente', ''), type="password")
            if st.form_submit_button("Salva Credenziali"):
                set_data('/config/email_mittente', email_mit)
                set_data('/config/password_mittente', pass_mit)
                st.rerun()
    with st.expander("👥 Destinatari"):
        dest_attuali = get_data('/destinatari')
        for d_id, d_dati in dest_attuali.items():
            col1, col2 = st.columns([3, 1])
            col1.write(d_dati.get('email', ''))
            if col2.button("🗑️", key=f"del_{d_id}"):
                delete_data('/destinatari', d_id)
                st.rerun()
        nuova_email = st.text_input("Aggiungi email:")
        if st.button("Aggiungi"):
            if "@" in nuova_email:
                push_data('/destinatari', {"email": nuova_email})
                st.rerun()
    st.divider()
    if st.button("🚀 Esegui Scansione", type="primary", use_container_width=True):
        corsi = get_data('/corsi')
        oggi = datetime.today().date()
        soglia = oggi + timedelta(days=30)
        if corsi:
            for cid, dati in corsi.items():
                try:
                    d_scad = datetime.strptime(dati.get('data_scadenza', '2000-01-01'), "%Y-%m-%d").date()
                    if d_scad <= soglia and not dati.get('notifica_inviata', False):
                        invia_email(dati.get('nominativo'), dati.get('corso'), dati.get('data_scadenza'))
                        db.reference(f'/corsi/{cid}', url=DB_URL).update({'notifica_inviata': True})
                except: continue
        st.rerun()
    if st.button("🔄 Reset Mail Inviate"):
        corsi = get_data('/corsi')
        if corsi:
            for cid, dati in corsi.items():
                db.reference(f'/corsi/{cid}', url=DB_URL).update({'notifica_inviata': False})
        st.rerun()
    st.divider()
    corsi_per_export = get_data('/corsi')
    if corsi_per_export:
        st.download_button("📥 Esporta Excel", data=esporta_excel(corsi_per_export), file_name="Registro.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

# --- MAIN ---
tab1, tab2 = st.tabs(["📋 Registro Corsi", "➕ Aggiungi Corso"])
opzioni_corsi = ["Preposto", "RLS", "Primo Soccorso", "Antincendio", "PLE", "Muletto", "Base 4H", "Specifica 12H", "DP13 Lavori in quota", "Altro"]

with tab2:
    nom_input = st.text_input("Dipendente")
    with st.form("form_corso_new"):
        scelta_add = st.selectbox("Corso", opzioni_corsi)
        corso_add = st.text_input("Specifica nome corso") if scelta_add == "Altro" else scelta_add
        data_s = st.date_input("Data Svolgimento", format="DD/MM/YYYY")
        val = st.selectbox("Anni Validità", [1, 2, 3, 5, 10], index=3)
        if st.form_submit_button("💾 Salva Corso"):
            scadenza = data_s.replace(year=data_s.year + val)
            push_data('/corsi', {"nominativo": nom_input, "corso": corso_add, "data_svolto": str(data_s), "data_scadenza": str(scadenza), "notifica_inviata": False})
            st.rerun()

with tab1:
    if 'corsi_cache' not in st.session_state: st.session_state.corsi_cache = get_data('/corsi')
    corsi = st.session_state.corsi_cache
    c1, c2 = st.columns(2)
    search = c1.text_input("🔍 Cerca")
    filtro_stato = c2.selectbox("Filtra", ["Tutti", "🟢 IN CORSO", "⚠️ IN SCADENZA", "🔴 SCADUTO", "✅ Mail inviata"])
    
    with st.expander("✏️ Modifica o 🗑️ Elimina Corso"):
        if corsi:
            lista = ["Seleziona..."] + [f"{d.get('nominativo')} - {d.get('corso')}" for cid, d in corsi.items()]
            sel = st.selectbox("Seleziona:", lista)
            if sel != "Seleziona...":
                mappa = {f"{d.get('nominativo')} - {d.get('corso')}": cid for cid, d in corsi.items()}
                cid_m = mappa[sel]
                dati = corsi[cid_m]
                new_nom = st.text_input("Nome", value=dati.get('nominativo'))
                new_c = st.text_input("Corso", value=dati.get('corso'))
                if st.button("Salva Modifiche"):
                    db.reference(f'/corsi/{cid_m}', url=DB_URL).update({"nominativo": new_nom, "corso": new_c})
                    st.rerun()

    oggi = datetime.today().date()
    soglia = oggi + timedelta(days=30)
    for cid, d in corsi.items():
        try:
            d_scad = datetime.strptime(d['data_scadenza'], "%Y-%m-%d").date()
            if d_scad < oggi: stato, colore = "🔴 SCADUTO", "red"
            elif d_scad <= soglia: stato, colore = "⚠️ IN SCADENZA", "orange"
            elif d.get('notifica_inviata', False): stato, colore = "✅ Mail inviata", "green"
            else: stato, colore = "🟢 IN CORSO", "blue"
            
            if (search.lower() in d.get('nominativo', '').lower()) and (filtro_stato == "Tutti" or filtro_stato == stato):
                with st.container(border=True):
                    cols = st.columns([2, 2, 1, 1, 1, 0.5])
                    cols[0].write(d.get('nominativo'))
                    cols[1].write(d.get('corso'))
                    cols[2].write(d.get('data_svolto'))
                    cols[3].write(d.get('data_scadenza'))
                    cols[4].markdown(f":{colore}[**{stato}**]")
                    if cols[5].button("🗑️", key=f"del_{cid}"): conferma_eliminazione(cid)
        except: continue
