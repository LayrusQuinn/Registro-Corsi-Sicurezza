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
        sys.exit(1)
    cred_dict = json.loads(raw_json)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred, {
        'databaseURL': "https://corsi-sicurezza-ggi-default-rtdb.europe-west1.firebasedatabase.app/"
    })

def invia_email_a_tutti(nominativo, corso, data_scadenza):
    # Legge la lista destinatari dal database
    ref_dest = db.reference('/destinatari')
    dest_data = ref_dest.get()
    if not dest_data: return
    
    destinatari = [v['email'] for v in dest_data.values()]
    
    gmail_user = os.environ.get('GMAIL_USER')
    gmail_pass = os.environ.get('GMAIL_PASS')
    
    data_ita = datetime.strptime(data_scadenza, '%Y-%m-%d').strftime('%d/%m/%Y')
    
    msg = EmailMessage()
    msg['Subject'] = f"⚠️ Notifica Scadenza: {corso} - {nominativo}"
    msg['From'] = gmail_user
    msg['To'] = ", ".join(destinatari) # Invia a tutti
    msg.set_content(f"Attenzione, il corso '{corso}' per {nominativo} scade il {data_ita}. Provvedere al rinnovo.")
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(gmail_user, gmail_pass)
        smtp.send_message(msg)

def invia_email():
    ref = db.reference('/')
    dati = ref.get()
    if not dati: return

    # Logica per gestire lista o dizionario (come prima)
    corsi = {str(i): val for i, val in enumerate(dati)} if isinstance(dati, list) else dati
    
    oggi = datetime.today()
    soglia = oggi + timedelta(days=30)

    for cid, info in corsi.items():
        if isinstance(info, dict) and 'data_scadenza' in info and not info.get('notifica_inviata', False):
            d_scad = datetime.strptime(info['data_scadenza'], '%Y-%m-%d')
            if oggi <= d_scad <= soglia:
                invia_email_a_tutti(info['nominativo'], info['corso'], info['data_scadenza'])
                db.reference(f'/corsi/{cid}').update({'notifica_inviata': True})

if __name__ == "__main__":
    initialize_firebase()
    invia_email()
