import os
import json
import sys
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
import firebase_admin
from firebase_admin import credentials, db

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

def invia_email():
    print("Inizio scansione database...")
    ref = db.reference('/corsi')
    corsi = ref.get()
    
    # DEBUG: Visualizza cosa viene letto
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
            
            # Verifica condizioni
            in_range = (oggi <= d_scad <= soglia)
            
            print(f"DEBUG: {info['corso']} | Scadenza: {d_scad.date()} | In range: {in_range} | Già inviata: {inviata}")
            
            if in_range and not inviata:
                print(f"AZIONE: Invio notifica per {info['corso']}...")
                invia_email_a_tutti(info['nominativo'], info['corso'], info['data_scadenza'])
                db.reference(f'/corsi/{cid}').update({'notifica_inviata': True})
            else:
                print(f"SALTO: {info['corso']} non necessita di notifica.")
        else:
            print(f"DEBUG: Il record {cid} non ha una data_scadenza valida.")

if __name__ == "__main__":
    initialize_firebase()
    invia_email()
