import os
import json
import sys
import firebase_admin
from firebase_admin import credentials, db

def initialize_firebase():
    """
    Inizializza l'app Firebase usando le credenziali passate tramite
    variabile d'ambiente da GitHub Secrets.
    """
    # Il nome della variabile deve corrispondere a quello definito nello YAML
    raw_json = os.environ.get('FIREBASE_JSON_CONTENT')

    if not raw_json:
        print("ERRORE: Variabile d'ambiente 'FIREBASE_JSON_CONTENT' non trovata.")
        sys.exit(1)

    print(f"DEBUG: Lunghezza stringa ricevuta: {len(raw_json)}")

    try:
        # Carica il JSON dalla stringa
        cred_dict = json.loads(raw_json)
        
        # Inizializza Firebase
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {
            'databaseURL': "https://corsi-sicurezza-ggi-default-rtdb.europe-west1.firebasedatabase.app/"
        })
        print("Firebase inizializzato correttamente!")
        
    except json.JSONDecodeError as e:
        print(f"ERRORE di formato JSON: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERRORE durante l'inizializzazione di Firebase: {e}")
        sys.exit(1)

def invia_email():
    """
    Qui inserisci la tua logica per l'invio delle email.
    Esempio: recupero dati dal Realtime Database e invio.
    """
    print("Inizio procedura di invio email...")
    
    # Esempio di recupero dati (decommenta se serve):
    # ref = db.reference('/tuo_path')
    # dati = ref.get()
    
    print("Email inviate con successo.")

if __name__ == "__main__":
    # 1. Setup ambiente
    initialize_firebase()
    
    # 2. Esecuzione task
    try:
        invia_email()
    except Exception as e:
        print(f"Errore critico durante l'esecuzione: {e}")
        sys.exit(1)
