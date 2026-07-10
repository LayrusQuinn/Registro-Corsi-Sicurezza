import os
import json
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, db

# 1. Recupero e Validazione del Secret
raw_json = os.environ.get('FIREBASE_JSON')

if not raw_json:
    print("ERRORE: Variabile FIREBASE_JSON non trovata.")
    sys.exit(1)

try:
    cred_dict = json.loads(raw_json)
except json.JSONDecodeError as e:
    print(f"ERRORE: Il contenuto non è un JSON valido. Dettagli: {e}")
    sys.exit(1)

# 2. Inizializzazione Firebase
try:
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred, {
        'databaseURL': "https://corsi-sicurezza-ggi-default-rtdb.europe-west1.firebasedatabase.app/"
    })
except Exception as e:
    print(f"ERRORE: Inizializzazione Firebase fallita: {e}")
    sys.exit(1)

# 3. Funzione invio email
def invia_email(nominativo, corso, data_scadenza):
    try:
        config = db.reference('/config').get()
        mittente = config.get('email_mittente')
        password = config.get('password_mittente')
        
        dest_data = db.reference('/destinatari').get()
        destinatari = [v['email'] for v in dest_data.values()] if dest_data else []
        
        if not mittente or not password or not destinatari:
            print("ERRORE: Configurazione email incompleta nel DB.")
            return

        msg = MIMEMultipart()
        msg['From'] = mittente
        msg['To'] = ", ".join(destinatari)
        msg['Subject'] = f"⚠️ Notifica Scadenza: {corso} - {nominativo}"
        
        corpo = f"Il corso {corso} relativo a {nominativo} scade il {data_scadenza}."
        msg.attach(MIMEText(corpo, 'plain'))
        
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(mittente, password)
        server.sendmail(mittente, destinatari, msg.as_string())
        server.quit()
        print(f"Email inviata per {nominativo}")
    except Exception as e:
        print(f"ERRORE durante invio email: {e}")

# 4. Logica di scansione
try:
    corsi = db.reference('/corsi').get()
    if corsi:
        oggi = datetime.today().date()
        soglia = oggi + timedelta(days=30)
        
        for cid, dati in corsi.items():
            if 'data_scadenza' in dati:
                d_scad = datetime.strptime(dati['data_scadenza'], "%Y-%m-%d").date()
                if d_scad <= soglia and not dati.get('notifica_inviata', False):
                    invia_email(dati.get('nominativo'), dati.get('corso'), dati.get('data_scadenza'))
                    db.reference(f'/corsi/{cid}').update({'notifica_inviata': True})
                    print(f"Aggiornato stato per {dati.get('nominativo')}")
    else:
        print("Nessun corso trovato nel database.")
except Exception as e:
    print(f"ERRORE durante la scansione: {e}")
    sys.exit(1)
