import streamlit as st 
from streamlit_autorefresh import st_autorefresh
import firebase_admin 
from firebase_admin import credentials, db 
import json 
import pandas as pd 
from datetime import datetime, timedelta 
import smtplib 
from email.mime.text import MIMEText 
from email.mime.multipart import MIMEMultipart 
import os 
import time 
import io 

# --- 1. CONFIGURAZIONE PAGINA --- 
st.set_page_config(page_title="Sicurezza & Cantieri | Guasti Gino", layout="wide") 

# --- 2. SISTEMA DI LOGIN --- 
if 'authenticated' not in st.session_state: 
    st.session_state.authenticated = False 
if 'db_version' not in st.session_state: 
    st.session_state.db_version = 0 # Variabile per il cache-busting

def force_refresh():
    """Incrementa la versione per forzare il ricaricamento dei dati"""
    st.session_state.db_version += 1

if st.query_params.get("logged_in") == "true": 
    st.session_state.authenticated = True 

if not st.session_state.authenticated: 
    st.title("🔐 Accesso Riservato - Guasti Gino Impianti") 
    with st.form("login_form"): 
        user_input = st.text_input("Username") 
        pass_input = st.text_input("Password", type="password") 
        if st.form_submit_button("Accedi"): 
            if user_input == "GuastiGino" and pass_input == "Guasti2026!": 
                st.session_state.authenticated = True 
                st.query_params["logged_in"] = "true" 
                st.rerun() 
            else: 
                st.error("Username o Password errati") 
    st.stop()  

# --- 3. CONNESSIONE A FIREBASE --- 
DB_URL = "https://corsi-sicurezza-ggi-default-rtdb.europe-west1.firebasedatabase.app/" 

if not firebase_admin._apps: 
    try: 
        key_dict = json.loads(st.secrets["firebase_json"]) 
        cred = credentials.Certificate(key_dict) 
        firebase_admin.initialize_app(cred, {'databaseURL': DB_URL}) 
    except Exception as e: 
        st.error(f"Errore connessione DB: {e}") 

# --- 4. FUNZIONI DI DATABASE (CON VERSIONAMENTO) --- 
@st.cache_data(ttl=60) 
def get_data(path, version): 
    try: 
        dati = db.reference(path, url=DB_URL).get() 
        return dati if dati else {} 
    except: return {} 

def set_data(path, data): 
    db.reference(path, url=DB_URL).set(data) 
    force_refresh()

def push_data(path, data): 
    db.reference(path, url=DB_URL).push(data) 
    force_refresh()

def delete_data(path, item_id): 
    db.reference(f'{path}/{item_id}', url=DB_URL).delete() 
    force_refresh()

# --- 5. LOGICA EXCEL --- 
def esporta_excel(dati): 
    lista_dati = [] 
    for cid, d in dati.items(): 
        lista_dati.append({ 
            "Nominativo": d.get('nominativo', ''), 
            "Corso": d.get('corso', ''), 
            "Data Svolgimento": d.get('data_svolto', ''), 
            "Data Scadenza": d.get('data_scadenza', '') 
        }) 
    df = pd.DataFrame(lista_dati) 
    df = df[["Nominativo", "Corso", "Data Svolgimento", "Data Scadenza"]] 
    output = io.BytesIO() 
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer: 
        df.to_excel(writer, index=False, sheet_name='Registro Corsi') 
        workbook  = writer.book 
        worksheet = writer.sheets['Registro Corsi'] 
        for i, col in enumerate(df.columns): 
            column_len = max(df[col].astype(str).map(len).max(), len(col)) + 2 
            worksheet.set_column(i, i, column_len) 
    return output.getvalue() 

# --- 6. LOGICA EMAIL --- 
def invia_email(nominativo, corso, data_scadenza): 
    config = get_data('/config', st.session_state.db_version) 
    mittente = config.get('email_mittente', '') 
    password = config.get('password_mittente', '') 
    destinatari_dict = get_data('/destinatari', st.session_state.db_version) 
    destinatari = [v['email'] for v in destinatari_dict.values()] if destinatari_dict else [] 
    if not destinatari or not password: return "Errore Config" 
    try: 
        d_scad_ita = datetime.strptime(data_scadenza, "%Y-%m-%d").strftime("%d/%m/%Y") 
    except: d_scad_ita = data_scadenza 
     
    msg = MIMEMultipart() 
    msg['From'] = mittente 
    msg['To'] = ", ".join(destinatari) 
    msg['Subject'] = f"⚠️ Notifica Scadenza Formazione: {corso} - {nominativo}" 

    corpo = f"<html><body><h2>Notifica Scadenza</h2><p>Dipendente: {nominativo}<br>Corso: {corso}<br>Scadenza: {d_scad_ita}</p></body></html>" 
    msg.attach(MIMEText(corpo, 'html')) 
    try: 
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465) 
        server.login(mittente, password) 
        server.sendmail(mittente, destinatari, msg.as_string()) 
        server.quit() 
        return "Inviato ✅" 
    except Exception as e: return f"Errore: {e}" 

def invia_email_cantiere(cantiere, parte, data_scadenza):
    config = get_data('/config', st.session_state.db_version) 
    mittente = config.get('email_mittente', '') 
    password = config.get('password_mittente', '') 
    destinatari_dict = get_data('/destinatari', st.session_state.db_version) 
    destinatari = [v['email'] for v in destinatari_dict.values()] if destinatari_dict else [] 
    if not destinatari or not password: return "Errore Config" 
    try: 
        d_scad_ita = datetime.strptime(data_scadenza, "%Y-%m-%d").strftime("%d/%m/%Y") 
    except: d_scad_ita = data_scadenza 
     
    msg = MIMEMultipart() 
    msg['From'] = mittente 
    msg['To'] = ", ".join(destinatari) 
    msg['Subject'] = f"⚠️ Notifica Scadenza Consegna Cantiere: {cantiere} - {parte}" 

    corpo = f"<html><body><h2>Scadenza Termini Consegna Cantiere</h2><p>Cantiere: {cantiere}<br>Parte/Fase in scadenza: {parte}<br>Data Scadenza: {d_scad_ita}</p></body></html>" 
    msg.attach(MIMEText(corpo, 'html')) 
    try: 
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465) 
        server.login(mittente, password) 
        server.sendmail(mittente, destinatari, msg.as_string()) 
        server.quit() 
        return "Inviato ✅" 
    except Exception as e: return f"Errore: {e}" 

# --- 7. DIALOG PER ELIMINAZIONE --- 
@st.dialog("Conferma eliminazione corso") 
def conferma_eliminazione(cid): 
    st.write("Vuoi davvero eliminare questo corso?") 
    if st.button("Sì, elimina corso"): 
        delete_data('/corsi', cid) 
        st.rerun() 
    if st.button("Annulla"): st.rerun() 

@st.dialog("Conferma eliminazione scadenza")
def conferma_eliminazione_rapporto(rid):
    st.write("Vuoi davvero eliminare questa scadenza di cantiere?")
    if st.button("Sì, elimina scadenza"):
        delete_data('/rapporti_cantiere', rid)
        st.rerun()
    if st.button("Annulla"): st.rerun()

# --- 8. INTERFACCIA UTENTE --- 
st.title("Guasti Gino Impianti S.r.l.") 

with st.sidebar: 
    st.header("🔄 Aggiornamento")
    auto_refresh = st.toggle("Abilita aggiornamento auto", value=True)
    if auto_refresh: st_autorefresh(interval=60000, key="datarefresh")
    st.divider()

    if st.button("🚪 Logout"): 
        st.session_state.authenticated = False 
        st.query_params.clear() 
        st.rerun() 
    
    st.header("⚙️ Impostazioni") 
    with st.expander("📧 Configurazione SMTP"): 
        with st.form("form_smtp"): 
            email_mit = st.text_input("Gmail Mittente", value=get_data('/config', st.session_state.db_version).get('email_mittente', '')) 
            pass_mit = st.text_input("Password App", value=get_data('/config', st.session_state.db_version).get('password_mittente', ''), type="password") 
            if st.form_submit_button("Salva Credenziali"): 
                set_data('/config/email_mittente', email_mit) 
                set_data('/config/password_mittente', pass_mit) 
                st.rerun() 
    with st.expander("👥 Destinatari"): 
        dest_attuali = get_data('/destinatari', st.session_state.db_version) 
        for d_id, d_dati in dest_attuali.items(): 
            col1, col2 = st.columns([3, 1]) 
            col1.write(d_dati.get('email', '')) 
            if col2.button("🗑️", key=f"del_{d_id}"): 
                delete_data('/destinatari', d_id) 
                st.rerun() 
        nuova_email = st.text_input("Aggiungi email:") 
        if st.button("Aggiungi"): 
            if "@" in nuova_email: 
                push_data('/destinatari', {"email": nuova_email}) 
                st.rerun() 
    st.divider() 
    
    if st.button("🚀 Esegui Scansione", type="primary", use_container_width=True): 
        with st.spinner("Scansione in corso..."):
            oggi = datetime.today().date() 
            soglia = oggi + timedelta(days=30) 
            aggiornato = False
            
            corsi = db.reference('/corsi', url=DB_URL).get() 
            if corsi: 
                for cid, dati in corsi.items(): 
                    try: 
                        d_scad = datetime.strptime(dati.get('data_scadenza', '2000-01-01'), "%Y-%m-%d").date() 
                        if d_scad <= soglia and not dati.get('notifica_inviata', False): 
                            esito = invia_email(dati.get('nominativo'), dati.get('corso'), dati.get('data_scadenza'))
                            if "Inviato" in esito:
                                db.reference(f'/corsi/{cid}', url=DB_URL).update({'notifica_inviata': True}) 
                                aggiornato = True
                    except: continue
            
            rapporti = db.reference('/rapporti_cantiere', url=DB_URL).get()
            if rapporti:
                for rid, dati in rapporti.items():
                    try:
                        d_scad = datetime.strptime(dati.get('data_scadenza', '2000-01-01'), "%Y-%m-%d").date()
                        if d_scad <= soglia and not dati.get('notifica_inviata', False):
                            esito = invia_email_cantiere(dati.get('cantiere'), dati.get('parte'), dati.get('data_scadenza'))
                            if "Inviato" in esito:
                                db.reference(f'/rapporti_cantiere/{rid}', url=DB_URL).update({'notifica_inviata': True}) 
                                aggiornato = True
                    except: continue
            
            if aggiornato:
                force_refresh()
                st.rerun() 
            else: st.info("Nessuna nuova scadenza trovata.")
         
    if st.button("🔄 Reset Mail Inviate"): 
        corsi = get_data('/corsi', st.session_state.db_version) 
        if corsi: 
            for cid in corsi: db.reference(f'/corsi/{cid}', url=DB_URL).update({'notifica_inviata': False}) 
        rapporti = get_data('/rapporti_cantiere', st.session_state.db_version)
        if rapporti:
            for rid in rapporti: db.reference(f'/rapporti_cantiere/{rid}', url=DB_URL).update({'notifica_inviata': False})
        force_refresh()
        st.rerun() 
    
    st.divider() 
    corsi_per_export = get_data('/corsi', st.session_state.db_version) 
    if corsi_per_export: 
        st.download_button("📥 Esporta Excel", data=esporta_excel(corsi_per_export), file_name="Registro.xlsx", use_container_width=True) 

# --- MAIN --- 
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Registro", "📊 Tabella", "➕ Corso", "⏳ Nuova Scadenza", "🏗️ Cantieri"]) 

with tab1: 
    corsi = get_data('/corsi', st.session_state.db_version) 
    c1, c2 = st.columns(2) 
    search = c1.text_input("🔍 Cerca") 
    filtro_stato = c2.selectbox("Filtra", ["Tutti", "🟢 IN CORSO", "⚠️ IN SCADENZA", "🔴 SCADUTO", "✅ Mail inviata"]) 
    
    if corsi:
        for cid, d in corsi.items(): 
            try: 
                d_scad = datetime.strptime(d['data_scadenza'], "%Y-%m-%d").date() 
                oggi = datetime.today().date()
                soglia = oggi + timedelta(days=30)
                if d_scad < oggi: stato, colore = "🔴 SCADUTO", "red" 
                elif d_scad <= soglia: stato, colore = "⚠️ IN SCADENZA", "orange" 
                elif d.get('notifica_inviata', False): stato, colore = "✅ Mail inviata", "green" 
                else: stato, colore = "🟢 IN CORSO", "blue" 
                
                if (search.lower() in d.get('nominativo', '').lower()) and (filtro_stato == "Tutti" or filtro_stato == stato): 
                    with st.container(border=True): 
                        cols = st.columns([2, 2, 1, 1, 1, 0.5]) 
                        cols[0].markdown(f":{colore}[{d.get('nominativo')}]") 
                        cols[1].markdown(f":{colore}[{d.get('corso')}]") 
                        cols[2].markdown(f":{colore}[{d.get('data_svolto')}]") 
                        cols[3].markdown(f":{colore}[{d.get('data_scadenza')}]") 
                        cols[4].markdown(f":{colore}[**{stato}**]") 
                        if cols[5].button("🗑️", key=f"del_{cid}"): conferma_eliminazione(cid) 
            except: continue

with tab2:
    corsi_matrice = get_data('/corsi', st.session_state.db_version)
    if corsi_matrice:
        # Logica tabella semplificata per brevità
        st.write("Visualizzazione tabella attiva.")
        st.dataframe(pd.DataFrame.from_dict(corsi_matrice, orient='index'), use_container_width=True)

with tab3: 
    nom_input = st.text_input("Dipendente")
    with st.form("form_corso_new"): 
        corso_add = st.selectbox("Corso", ["Preposto", "RLS", "Antincendio", "PLE", "Muletto", "Altro"]) 
        data_s = st.date_input("Data Svolgimento", format="DD/MM/YYYY") 
        val = st.selectbox("Anni Validità", [1, 2, 3, 5, 10], index=3) 
        if st.form_submit_button("💾 Salva"): 
            scadenza = data_s.replace(year=data_s.year + val) 
            push_data('/corsi', {"nominativo": nom_input, "corso": corso_add, "data_svolto": str(data_s), "data_scadenza": str(scadenza), "notifica_inviata": False}) 
            st.rerun() 

with tab4:
    with st.form("form_cantiere"):
        nome_cantiere = st.text_input("Cantiere")
        parte_cantiere = st.text_input("Parte")
        data_scadenza = st.date_input("Data Scadenza")
        if st.form_submit_button("💾 Salva"):
            push_data('/rapporti_cantiere', {"cantiere": nome_cantiere, "parte": parte_cantiere, "data_scadenza": str(data_scadenza), "notifica_inviata": False})
            st.rerun()

with tab5:
    rapporti = get_data('/rapporti_cantiere', st.session_state.db_version)
    if rapporti:
        for rid, d in rapporti.items():
            with st.container(border=True):
                st.write(f"{d.get('cantiere')} - {d.get('parte')} (Scadenza: {d.get('data_scadenza')})")
                if st.button("🗑️", key=f"del_c_{rid}"): conferma_eliminazione_rapporto(rid)
