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
        print("ERRORE CRITICO: FIREBASE_JSON_CONTENT non trovato nelle variabili d'ambiente.")
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

def invia_email():
    """Logica di controllo scadenze e invio email"""
    print("Inizio scansione database corsi...")
    ref = db.reference('/corsi')
    corsi = ref.get()
    
    if not corsi:
        print("Nessun corso trovato nel database.")
        return

    oggi = datetime.now()
    soglia = oggi + timedelta(days=30)
    
    gmail_user = os.environ.get('GMAIL_USER')
    gmail_pass = os.environ.get('GMAIL_PASS')

    # Iteriamo sui corsi
    for corso_id, info in corsi.items():
        # 1. Controllo esistenza chiavi (evita KeyError)
        if not all(k in info for k in ('scadenza', 'nome_corso', 'email_referente')):
            print(f"Record incompleto saltato (ID: {corso_id}).")
            continue
            
        # 2. Parsing data europea (DD/MM/YYYY)
        try:
            data_scadenza = datetime.strptime(info['scadenza'], '%d/%m/%Y')
        except ValueError:
            print(f"Data non valida per {info['nome_corso']}: {info['scadenza']}")
            continue
            
        # 3. Trigger: scadenza tra oggi e i prossimi 30 giorni
        if oggi <= data_scadenza <= soglia:
            print(f"Invio avviso per: {info['nome_corso']} (Scadenza: {info['scadenza']})")
            
            try:
                msg = EmailMessage()
                msg['Subject'] = f"Avviso scadenza corso: {info['nome_corso']}"
                msg['From'] = gmail_user
                msg['To'] = info['email_referente']
                msg.set_content(f"Attenzione, il corso '{info['nome_corso']}' scade il {info['scadenza']}. Provvedere al rinnovo.")
                
                with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                    smtp.login(gmail_user, gmail_pass)
                    smtp.send_message(msg)
                print(f"Email inviata con successo a {info['email_referente']}")
            except Exception as e:
                print(f"ERRORE invio email per {info['nome_corso']}: {e}")

if __name__ == "__main__":
    initialize_firebase()
    invia_email()
