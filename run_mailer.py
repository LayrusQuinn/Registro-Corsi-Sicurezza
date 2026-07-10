import firebase_admin
from firebase_admin import credentials, db
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import os

# Configurazione Firebase (usa le variabili d'ambiente di GitHub)
cred_json = json.loads(os.environ['FIREBASE_JSON'])
cred = credentials.Certificate(cred_json)
firebase_admin.initialize_app(cred, {'databaseURL': "https://corsi-sicurezza-ggi-default-rtdb.europe-west1.firebasedatabase.app/"})

def invia_email(nominativo, corso, data_scadenza):
    config = db.reference('/config').get()
    mittente = config.get('email_mittente')
    password = config.get('password_mittente')
    destinatari = [v['email'] for v in db.reference('/destinatari').get().values()]
    
    msg = MIMEMultipart()
    msg['From'] = mittente
    msg['To'] = ", ".join(destinatari)
    msg['Subject'] = f"⚠️ Notifica Scadenza: {corso} - {nominativo}"
    msg.attach(MIMEText(f"Il corso {corso} di {nominativo} scade il {data_scadenza}", 'html'))
    
    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    server.login(mittente, password)
    server.sendmail(mittente, destinatari, msg.as_string())
    server.quit()

# Logica di scansione
corsi = db.reference('/corsi').get()
oggi = datetime.today().date()
soglia = oggi + timedelta(days=30)

for cid, dati in corsi.items():
    d_scad = datetime.strptime(dati['data_scadenza'], "%Y-%m-%d").date()
    if d_scad <= soglia and not dati.get('notifica_inviata', False):
        invia_email(dati.get('nominativo'), dati.get('corso'), dati.get('data_scadenza'))
        db.reference(f'/corsi/{cid}').update({'notifica_inviata': True})