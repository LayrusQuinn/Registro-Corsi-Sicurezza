import os
import json
import sys
import firebase_admin
from firebase_admin import credentials, db

# --- DEBUG DEFINITIVO ---
raw_json = os.environ.get('SECRET_KEY_FIREBASE')
print(f"DEBUG: Variabile trovata: {'SECRET_KEY_FIREBASE' in os.environ}")
print(f"DEBUG: Lunghezza stringa ricevuta: {len(str(raw_json))}")

if not raw_json or len(str(raw_json)) < 10:
    print("ERRORE CRITICO: Il secret non è stato passato o è vuoto.")
    sys.exit(1)

try:
    cred_dict = json.loads(raw_json)
    print("JSON caricato correttamente!")
except json.JSONDecodeError as e:
    print(f"ERRORE JSON: {e}")
    sys.exit(1)

# Inizializzazione Firebase
try:
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred, {
        'databaseURL': "https://corsi-sicurezza-ggi-default-rtdb.europe-west1.firebasedatabase.app/"
    })
    print("Firebase inizializzato!")
except Exception as e:
    print(f"ERRORE Firebase: {e}")
    sys.exit(1)

# ... resto del tuo codice (invia_email, ecc.) ...
