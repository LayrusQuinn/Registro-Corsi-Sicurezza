import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import json
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import PIL.Image
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

# --- 4. LOGICA EMAIL PROFESSIONALE ---
def invia_email(nominativo, corso, data_scadenza):
    config = get_data('/config')
    mittente = config.get('email_mittente', '')
    password = config.get('password_mittente', '')
    destinatari_dict = get_data('/destinatari')
    destinatari = [v['email'] for v in destinatari_dict.values()] if destinatari_dict else []

    if not destinatari or not password: return "Errore Config"

    try:
        d_scad_ita = datetime.strptime(data_scadenza, "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        d_scad_ita = data_scadenza
    
    msg = MIMEMultipart()
    msg['From'] = mittente
    msg['To'] = ", ".join(destinatari)
    msg['Subject'] = f"⚠️ Notifica Scadenza Formazione: {corso} - {nominativo}"
    
    corpo = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #2c3e50;">Notifica di Scadenza Formazione</h2>
            <p>Buongiorno,</p>
            <p>con la presente si comunica che il seguente corso di formazione è in fase di scadenza:</p>
            <ul style="list-style-type: none; padding: 0;">
                <li><strong>Dipendente:</strong> {nominativo}</li>
                <li><strong>Corso:</strong> {corso}</li>
                <li><strong>Data di scadenza:</strong> <span style="color: #c0392b;"><strong>{d_scad_ita}</strong></span></li>
            </ul>
            <p>Si prega di provvedere alle necessarie attività di rinnovo entro i termini previsti.</p>
            <hr style="border: 0; border-top: 1px solid #ccc;">
            <p style="font-size: 0.9em; color: #7f8c8d;">
                <em>Sistema di gestione sicurezza - Guasti Gino Impianti S.r.l.</em>
            </p>
        </body>
    </html>
    """
    msg.attach(MIMEText(corpo, 'html'))

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(mittente, password)
        server.sendmail(mittente, destinatari, msg.as_string())
        server.quit()
        return "Inviato ✅"
    except Exception as e:
        return f"Errore: {e}"

# --- 5. INTERFACCIA UTENTE ---
st.title("Guasti Gino Impianti S.r.l.")
st.subheader("Gestione Corsi Sicurezza")

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
                try:
                    d_scad = datetime.strptime(dati['data_scadenza'], "%Y-%m-%d").date()
                    if d_scad <= soglia and not dati.get('notifica_inviata', False):
                        esito = invia_email(dati.get('nominativo'), dati.get('corso'), dati.get('data_scadenza'))
                        if "Inviato" in esito:
                            db.reference(f'/corsi/{cid}', url=DB_URL).update({'notifica_inviata': True})
                            inviati += 1
                except: continue
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
            push_data('/corsi', {"nominativo": nom, "corso": corso, "data_svolto": str(data_s), "data_scadenza": str(scadenza), "notifica_inviata": False})
            st.success("Corso salvato!")
            st.rerun()

with tab1:
    with st.expander("✏️ Modifica"):
        corsi_tutti = get_data('/corsi')
        if corsi_tutti:
            opzioni = {f"{d.get('nominativo')} - {d.get('corso')}": cid for cid, d in corsi_tutti.items()}
            selezione = st.selectbox("Seleziona:", list(opzioni.keys()))
            cid_da_mod = opzioni[selezione]
            dati_da_mod = corsi_tutti[cid_da_mod]
            
            with st.form("form_modifica"):
                new_nom = st.text_input("Dipendente", value=dati_da_mod.get('nominativo', ''))
                new_corso = st.text_input("Corso", value=dati_da_mod.get('corso', ''))
                
                # CORREZIONE ERRORE DATA:
                data_svolto_raw = dati_da_mod.get('data_svolto')
                valore_default_data = datetime.strptime(data_svolto_raw, "%Y-%m-%d") if data_svolto_raw else datetime.today()
                
                new_data_s = st.date_input("Data Svolgimento", value=valore_default_data, format="DD/MM/YYYY")
                new_val = st.selectbox("Anni Validità", [1, 2, 3, 5, 10], index=3)
                if st.form_submit_button("Salva Modifiche"):
                    scadenza = new_data_s.replace(year=new_data_s.year + new_val)
                    db.reference(f'/corsi/{cid_da_mod}', url=DB_URL).update({"nominativo": new_nom, "corso": new_corso, "data_svolto": str(new_data_s), "data_scadenza": str(scadenza), "notifica_inviata": False})
                    st.success("Salvato!")
                    st.rerun()

    with st.expander("🗑️ Elimina"):
        corsi_da_eliminare = get_data('/corsi')
        if corsi_da_eliminare:
            opzioni_del = {f"{d.get('nominativo')} - {d.get('corso')}": cid for cid, d in corsi_da_eliminare.items()}
            selezione_del = st.selectbox("Seleziona corso:", list(opzioni_del.keys()))
            if st.button("Elimina Definitivamente", type="primary"):
                delete_data('/corsi', opzioni_del[selezione_del])
                st.rerun()

    # Visualizzazione Tabella
    st.divider()
    corsi = get_data('/corsi')
    if corsi:
        data_list = []
        oggi = datetime.today().date()
        soglia = oggi + timedelta(days=30)
        for cid, d in corsi.items():
            try:
                d_scad = datetime.strptime(d['data_scadenza'], "%Y-%m-%d").date()
                stato = "✅ Mail inviata" if d.get('notifica_inviata', False) else ("🔴 SCADUTO" if d_scad < oggi else ("⚠️ IN SCADENZA" if d_scad <= soglia else "🟢 IN CORSO"))
                data_list.append({"Stato": stato, "Nominativo": d.get('nominativo', ''), "Corso": d.get('corso', ''), "Data Scadenza": d_scad.strftime("%d/%m/%Y")})
            except: continue
        
        if data_list:
            df = pd.DataFrame(data_list)
            st.dataframe(df, use_container_width=True, hide_index=True)
