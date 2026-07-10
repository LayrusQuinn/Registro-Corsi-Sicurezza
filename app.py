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
            <p>con la presente si comunica che il seguente corso è in fase di scadenza:</p>
            <ul>
                <li><strong>Dipendente:</strong> {nominativo}</li>
                <li><strong>Corso:</strong> {corso}</li>
                <li><strong>Data di scadenza:</strong> <span style="color: #c0392b;"><strong>{d_scad_ita}</strong></span></li>
            </ul>
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
                        if "Inviato" in invia_email(dati.get('nominativo'), dati.get('corso'), dati.get('data_scadenza')):
                            db.reference(f'/corsi/{cid}', url=DB_URL).update({'notifica_inviata': True})
                            inviati += 1
                except: continue
        st.success(f"Scansione completata! Inviate {inviati} email.")

# --- MAIN ---
tab1, tab2 = st.tabs(["📋 Registro Corsi", "➕ Aggiungi Corso"])
opzioni_corsi = ["Preposto", "RLS", "Primo Soccorso", "Antincendio", "PLE", "Muletto", "Base 4H", "Specifica 12H", "DP13 Lavori in quota", "Altro"]

with tab2:
    with st.form("form_corso", clear_on_submit=True):
        nom = st.text_input("Dipendente")
        scelta_corso = st.selectbox("Corso", opzioni_corsi)
        if scelta_corso == "Altro":
            corso = st.text_input("Specifica nome corso")
        else:
            corso = scelta_corso
        data_s = st.date_input("Data Svolgimento", format="DD/MM/YYYY")
        val = st.selectbox("Anni Validità", [1, 2, 3, 5, 10], index=3)
        if st.form_submit_button("Salva Corso"):
            scadenza = data_s.replace(year=data_s.year + val)
            push_data('/corsi', {"nominativo": nom, "corso": corso, "data_svolto": str(data_s), "data_scadenza": str(scadenza), "notifica_inviata": False})
            st.rerun()

with tab1:
    st.subheader("Filtri")
    c1, c2 = st.columns(2)
    search = c1.text_input("🔍 Cerca dipendente o corso")
    filtro_stato = c2.selectbox("Filtra per stato", ["Tutti", "🟢 IN CORSO", "⚠️ IN SCADENZA", "🔴 SCADUTO", "✅ Mail inviata"])

    with st.expander("✏️ Modifica o 🗑️ Elimina Corso"):
        corsi_tutti = get_data('/corsi')
        if corsi_tutti:
            opzioni = {f"{d.get('nominativo')} - {d.get('corso')}": cid for cid, d in corsi_tutti.items()}
            selezione = st.selectbox("Seleziona:", list(opzioni.keys()))
            cid_da_mod = opzioni[selezione]
            dati_da_mod = corsi_tutti[cid_da_mod]
            
            with st.form("form_modifica"):
                new_nom = st.text_input("Dipendente", value=dati_da_mod.get('nominativo', ''))
                
                sel_idx = opzioni_corsi.index(dati_da_mod.get('corso', 'Altro')) if dati_da_mod.get('corso') in opzioni_corsi else 9
                new_scelta = st.selectbox("Corso", opzioni_corsi, index=sel_idx)
                if new_scelta == "Altro":
                    new_corso = st.text_input("Specifica nome corso", value=dati_da_mod.get('corso', ''))
                else:
                    new_corso = new_scelta
                
                data_svolto_raw = dati_da_mod.get('data_svolto')
                valore_default_data = datetime.strptime(data_svolto_raw, "%Y-%m-%d") if data_svolto_raw else datetime.today()
                new_data_s = st.date_input("Data Svolgimento", value=valore_default_data, format="DD/MM/YYYY")
                new_val = st.selectbox("Anni Validità", [1, 2, 3, 5, 10], index=3)
                
                col_mod, col_del = st.columns(2)
                if col_mod.form_submit_button("Salva Modifiche"):
                    scadenza = new_data_s.replace(year=new_data_s.year + new_val)
                    db.reference(f'/corsi/{cid_da_mod}', url=DB_URL).update({"nominativo": new_nom, "corso": new_corso, "data_svolto": str(new_data_s), "data_scadenza": str(scadenza), "notifica_inviata": False})
                    st.rerun()
                if col_del.form_submit_button("Elimina Definitivamente", type="primary"):
                    delete_data('/corsi', cid_da_mod)
                    st.rerun()

    st.divider()
    corsi = get_data('/corsi')
    oggi = datetime.today().date()
    soglia = oggi + timedelta(days=30)
    
    cols_header = st.columns([2, 2, 1.5, 1.5, 1, 1])
    cols_header[0].write("**Nominativo**")
    cols_header[1].write("**Corso**")
    cols_header[2].write("**Svolgimento**")
    cols_header[3].write("**Scadenza**")
    cols_header[4].write("**Stato**")
    cols_header[5].write("**Reset**")

    for cid, d in corsi.items():
        try:
            d_svolto = datetime.strptime(d['data_svolto'], "%Y-%m-%d").date()
            d_scad = datetime.strptime(d['data_scadenza'], "%Y-%m-%d").date()
            
            if d.get('notifica_inviata', False): stato = "✅ Mail inviata"
            elif d_scad < oggi: stato = "🔴 SCADUTO"
            elif d_scad <= soglia: stato = "⚠️ IN SCADENZA"
            else: stato = "🟢 IN CORSO"
            
            if (search.lower() in d.get('nominativo', '').lower() or search.lower() in d.get('corso', '').lower()):
                if filtro_stato == "Tutti" or filtro_stato == stato:
                    cols = st.columns([2, 2, 1.5, 1.5, 1, 1])
                    cols[0].write(d.get('nominativo', ''))
                    cols[1].write(d.get('corso', ''))
                    cols[2].write(d_svolto.strftime("%d/%m/%Y"))
                    cols[3].write(d_scad.strftime("%d/%m/%Y"))
                    cols[4].write(stato)
                    if cols[5].button("🔄", key=f"res_{cid}"):
                        reset_notifica(cid)
                        st.rerun()
        except: continue
