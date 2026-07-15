import os
import json
import sys
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
import firebase_admin
from firebase_admin import credentials, db
import streamlit as st

def initialize_firebase():
    """Inizializzazione sicura di Firebase"""
    raw_json = os.environ.get('FIREBASE_JSON_CONTENT')
    if not raw_json:
        print("ERRORE CRITICO: FIREBASE_JSON_CONTENT non trovato.")
        sys.exit(1)
    
    try:
        cred_dict = json.loads(raw_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {
            'databaseURL': "https://corsi-sicurezza-ggi-default-rtdb.europe-west1.firebasedatabase.app/"
        })
        print("Firebase inizializzato correttamente.")
    except Exception as e:
        print(f"ERRORE durante inizializzazione Firebase: {e}")
        sys.exit(1)

def invia_email_a_tutti(nominativo, corso, data_scadenza):
    """Invia notifica a tutti gli indirizzi salvati in /destinatari"""
    ref_dest = db.reference('/destinatari')
    dest_data = ref_dest.get()
    
    if not dest_data:
        print("Nessun destinatario trovato nel database.")
        return
    
    destinatari = [v['email'] for v in dest_data.values()]
    gmail_user = os.environ.get('GMAIL_USER')
    gmail_pass = os.environ.get('GMAIL_PASS')
    
    d_scad_obj = datetime.strptime(data_scadenza, '%Y-%m-%d')
    data_ita = d_scad_obj.strftime('%d/%m/%Y')
    
    msg = EmailMessage()
    msg['Subject'] = f"⚠️ Notifica Scadenza Formazione: {corso} - {nominativo}"
    msg['From'] = gmail_user
    msg['To'] = ", ".join(destinatari)
    msg.set_content(f"Buongiorno,\n\nSi comunica che il corso '{corso}' per il dipendente {nominativo} scade il {data_ita}.\nSi prega di provvedere alle necessarie attività di rinnovo.\n\nCordiali saluti.")
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(gmail_user, gmail_pass)
        smtp.send_message(msg)
    print(f"Email inviata con successo a: {', '.join(destinatari)}")

def aggiorna_corso(course_id, nuova_data_svolto, nuova_data_scadenza):
    """
    Aggiorna i dati di un corso specifico e resetta lo stato della notifica.
    course_id: La chiave univoca del record in Firebase (es. '-OL9y...')
    nuova_data_svolto: Stringa formato 'YYYY-MM-DD'
    nuova_data_scadenza: Stringa formato 'YYYY-MM-DD'
    """
    ref = db.reference(f'/corsi/{course_id}')
    ref.update({
        'data_svolto': nuova_data_svolto,
        'data_scadenza': nuova_data_scadenza,
        'notifica_inviata': False
    })
    print(f"Corso {course_id} aggiornato: Nuova scadenza {nuova_data_scadenza}")

def invia_email():
    print("Inizio scansione database...")
    ref = db.reference('/corsi')
    corsi = ref.get()
    
    print(f"DEBUG: Dati letti da /corsi: {corsi}")
    
    if not corsi:
        print("Nessun corso trovato sotto /corsi.")
        return

    oggi = datetime.today()
    soglia = oggi + timedelta(days=30)
    print(f"DEBUG: Scansione tra {oggi.date()} e {soglia.date()}")

    for cid, info in corsi.items():
        print(f"DEBUG: Analizzo record {cid} -> {info.get('corso', 'N/A')}")
        
        if isinstance(info, dict) and 'data_scadenza' in info:
            d_scad = datetime.strptime(info['data_scadenza'], '%Y-%m-%d')
            inviata = info.get('notifica_inviata', False)
            
            # Condizione aggiornata: notifica se scade entro i 30 giorni, inclusi i già scaduti
            in_range = (d_scad <= soglia)
            
            print(f"DEBUG: {info['corso']} | Scadenza: {d_scad.date()} | In range: {in_range} | Già inviata: {inviata}")
            
            if in_range and not inviata:
                print(f"AZIONE: Invio notifica per {info['corso']}...")
                invia_email_a_tutti(info['nominativo'], info['corso'], info['data_scadenza'])
                db.reference(f'/corsi/{cid}').update({'notifica_inviata': True})
            else:
                print(f"SALTO: {info['corso']} non necessita di notifica.")
        else:
            print(f"DEBUG: Il record {cid} non ha una data_scadenza valida.")

# --- PARTE UI STREAMLIT ---

@st.dialog("Modifica Corso")
def modifica_corso_dialog(cid, info):
    """Dialog per modificare i dati in sicurezza usando un form"""
    with st.form("form_modifica_corso"):
        st.write(f"Modifica dati per: **{info.get('nominativo')}**")
        
        nuova_data_svolto = st.date_input("Nuova Data Svolgimento", value=datetime.today())
        nuova_data_scadenza = st.date_input("Nuova Data Scadenza", value=datetime.today() + timedelta(days=365))
        
        submitted = st.form_submit_button("💾 Salva Modifiche")
        
        if submitted:
            aggiorna_corso(cid, str(nuova_data_svolto), str(nuova_data_scadenza))
            st.success("Corso aggiornato con successo!")
            st.rerun()

if __name__ == "__main__":
    # Inizializzazione Firebase
    initialize_firebase()
    
    # Esempio di avvio dello script (se lanciato da terminale)
    # invia_email()
    
    # Se invece stai costruendo l'app Streamlit, richiama qui la logica di visualizzazione
    # ad esempio:
    # if st.button("Modifica"):
    #     modifica_corso_dialog("-ID_CORSO", {...info...})
