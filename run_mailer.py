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
    except Exception as e:
        print(f"ERRORE durante inizializzazione Firebase: {e}")
        sys.exit(1)

def invia_email():
    print("Inizio scansione database...")
    # Puntiamo alla radice per leggere i nodi numerati 0, 1, ...
    ref = db.reference('/')
    dati = ref.get()
    
    if not dati:
        print("Database vuoto.")
        return

    # Filtriamo per assicurarci di leggere solo i dizionari dei corsi
    corsi = {k: v for k, v in dati.items() if isinstance(v, dict)}
    
    if not corsi:
        print("Nessun corso trovato nel database.")
        return

    oggi = datetime.now()
    soglia = oggi + timedelta(days=30)
    
    gmail_user = os.environ.get('GMAIL_USER')
    gmail_pass = os.environ.get('GMAIL_PASS')

    for corso_id, info in corsi.items():
        # Verifica campi necessari
        required_keys = ('data_scadenza', 'corso', 'email')
        if not all(k in info for k in required_keys):
            print(f"Record {corso_id} saltato: mancano dati necessari.")
            continue
            
        # Parsing data YYYY-MM-DD
        try:
            data_scadenza = datetime.strptime(info['data_scadenza'], '%Y-%m-%d')
        except ValueError:
            print(f"Data non valida per {info['corso']}: {info['data_scadenza']}")
            continue
            
        # Trigger: scadenza tra oggi e 30 giorni
        if oggi <= data_scadenza <= soglia:
            print(f"Invio avviso per: {info['corso']} (Scadenza: {info['data_scadenza']})")
            
            try:
                msg = EmailMessage()
                msg['Subject'] = f"Avviso scadenza corso: {info['corso']}"
                msg['From'] = gmail_user
                msg['To'] = info['email']
                msg.set_content(f"Attenzione, il corso '{info['corso']}' scade il {info['data_scadenza']}. Provvedere al rinnovo.")
                
                with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                    smtp.login(gmail_user, gmail_pass)
                    smtp.send_message(msg)
                print(f"Email inviata con successo a {info['email']}")
            except Exception as e:
                print(f"ERRORE invio email per {info['corso']}: {e}")

if __name__ == "__main__":
    initialize_firebase()
    invia_email()
