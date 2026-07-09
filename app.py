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
    with st.expander("✏️ Modifica un corso esistente"):
        corsi_tutti = get_data('/corsi')
        if corsi_tutti:
            opzioni = {f"{d.get('nominativo', 'N/A')} - {d.get('corso', 'N/A')}": cid for cid, d in corsi_tutti.items()}
            selezione = st.selectbox("Seleziona il corso da modificare:", list(opzioni.keys()))
            cid_da_mod = opzioni[selezione]
            dati_da_mod = corsi_tutti[cid_da_mod]

            with st.form("form_modifica"):
                new_nom = st.text_input("Dipendente", value=dati_da_mod.get('nominativo', ''))
                new_corso = st.text_input("Corso", value=dati_da_mod.get('corso', ''))
                d_svolto = datetime.strptime(dati_da_mod.get('data_svolto'), "%Y-%m-%d")
                new_data_s = st.date_input("Data Svolgimento", value=d_svolto, format="DD/MM/YYYY")
                new_val = st.selectbox("Anni Validità", [1, 2, 3, 5, 10], index=3)
                
                if st.form_submit_button("Salva Modifiche"):
                    scadenza = new_data_s.replace(year=new_data_s.year + new_val)
                    db.reference(f'/corsi/{cid_da_mod}', url=DB_URL).update({
                        "nominativo": new_nom, "corso": new_corso, 
                        "data_svolto": str(new_data_s), "data_scadenza": str(scadenza),
                        "notifica_inviata": False
                    })
                    st.success("Modifica salvata!")
                    st.rerun()

    with st.expander("🗑️ Gestione Archivi: Rimuovi un corso"):
        corsi_da_eliminare = get_data('/corsi')
        if corsi_da_eliminare:
            opzioni_del = {f"{d.get('nominativo', 'N/A')} - {d.get('corso', 'N/A')}": cid for cid, d in corsi_da_eliminare.items()}
            selezione_del = st.selectbox("Seleziona il corso da eliminare:", list(opzioni_del.keys()))
            conferma = st.checkbox("⚠️ Confermo di voler eliminare definitivamente questo corso")
            if st.button("🗑️ Elimina Definitivamente", type="primary", disabled=not conferma):
                delete_data('/corsi', opzioni_del[selezione_del])
                st.success("Corso eliminato!")
                st.rerun()

    st.divider()
    
    # --- RICERCA E TABELLA ---
    col_search, col_filter = st.columns([3, 1])
    query = col_search.text_input("🔍 Cerca nel registro...", placeholder="Nome, corso o data (DD/MM/YYYY)...")
    filtro_tipo = col_filter.selectbox("Filtra per:", ["Tutto", "Nominativo", "Corso", "In scadenza", "Scaduto"])
    
    corsi = get_data('/corsi')
    if corsi:
        data_list = []
        oggi = datetime.today().date()
        soglia = oggi + timedelta(days=30)
        
        for cid, d in corsi.items():
            data_svolto_ita = datetime.strptime(d['data_svolto'], "%Y-%m-%d").strftime("%d/%m/%Y")
            data_scad_ita = datetime.strptime(d['data_scadenza'], "%d/%m/%Y" if "/" in d['data_scadenza'] else "%Y-%m-%d").strftime("%d/%m/%Y")
            d_scad = datetime.strptime(data_scad_ita, "%d/%m/%Y").date()
            
            if d.get('notifica_inviata', False): stato = "✅ Mail inviata"
            elif d_scad < oggi: stato = "🔴 SCADUTO"
            elif d_scad <= soglia: stato = "⚠️ IN SCADENZA"
            else: stato = "🟢 IN CORSO"
            
            match = True
            if filtro_tipo == "In scadenza": match = (stato == "⚠️ IN SCADENZA")
            elif filtro_tipo == "Scaduto": match = (stato == "🔴 SCADUTO")
            elif query:
                if filtro_tipo == "Nominativo": match = query.lower() in d['nominativo'].lower()
                elif filtro_tipo == "Corso": match = query.lower() in d['corso'].lower()
                else: match = (query.lower() in d['nominativo'].lower() or query.lower() in d['corso'].lower() or query in data_scad_ita)
            
            if match:
                anni_val = (d_scad.year - datetime.strptime(d['data_svolto'], "%Y-%m-%d").year)
                data_list.append({
                    "Stato": stato, 
                    "Nominativo": d['nominativo'], 
                    "Corso": d['corso'],
                    "Validità (Anni)": anni_val,
                    "Data Svolto": data_svolto_ita, 
                    "Data Scadenza": data_scad_ita
                })
        
        if data_list:
            df = pd.DataFrame(data_list)
            priorita_stato = {"🔴 SCADUTO": 0, "⚠️ IN SCADENZA": 1, "🟢 IN CORSO": 2, "✅ Mail inviata": 3}
            df['priorita'] = df['Stato'].map(priorita_stato)
            df['Data_Temp'] = pd.to_datetime(df['Data Scadenza'], format='%d/%m/%Y')
            df = df.sort_values(by=['priorita', 'Nominativo', 'Data_Temp'], ascending=[True, True, True])
            df = df.drop(columns=['priorita', 'Data_Temp'])
            
            st.dataframe(
                df.style.set_properties(subset=['Validità (Anni)'], **{'text-align': 'center'}),
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.warning("Nessun risultato trovato.")
    else:
        st.info("Nessun corso presente nel registro.")
