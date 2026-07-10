import os
import json
import sys
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
import firebase_admin
from firebase_admin import credentials, db

def initialize_firebase():
    raw_json = os.environ.get('FIREBASE_JSON_CONTENT')
    if not raw_json:
        print("ERRORE: FIREBASE_JSON_CONTENT non trovato.")
        sys.exit(1)
    
    cred_dict = json.loads(raw_json)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred, {
        'databaseURL': "https://corsi-sicurezza-ggi-default-rtdb.europe-west1.firebasedatabase.app/"
    })

def invia_email():
    ref = db.reference('/corsi')
    corsi = ref.get()
    
    if not corsi:
        print("Nessun corso nel database.")
        return

    oggi = datetime.now()
    soglia = oggi + timedelta(days=30)
    
    gmail_user = os.environ.get('GMAIL_USER')
    gmail_pass = os.environ.get('GMAIL_PASS')

    for corso_id, info in corsi.items():
        try:
            # Parsing data europea DD/MM/YYYY
            data_scadenza = datetime.strptime(info['scadenza'], '%d/%m/%Y')
        except ValueError:
            print(f"Data non valida per {info.get('nome_corso')}: {info.get('scadenza')}")
            continue
            
        # Trigger: scadenza nei prossimi 30 giorni
        if oggi <= data_scadenza <= soglia:
            print(f"Invio avviso per: {info['nome_corso']}")
            
            msg = EmailMessage()
            msg['Subject'] = f"Avviso scadenza corso: {info['nome_corso']}"
            msg['From'] = gmail_user
            msg['To'] = info['email_referente']
            msg.set_content(f"Il corso '{info['nome_corso']}' scade il {info['scadenza']}. Provvedere al rinnovo.")
            
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(gmail_user, gmail_pass)
                smtp.send_message(msg)
            print(f"Email inviata a {info['email_referente']}")

if __name__ == "__main__":
    initialize_firebase()
    invia_email()
