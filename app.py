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

# --- 2. SISTEMA DI LOGIN (PERSISTENTE VIA URL) --- 
if 'authenticated' not in st.session_state: 
    st.session_state.authenticated = False 

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

# --- 4. FUNZIONI DI DATABASE --- 
@st.cache_data(ttl=5) 
def get_data(path): 
    try: 
        dati = db.reference(path, url=DB_URL).get() 
        return dati if dati else {} 
    except: return {} 

def set_data(path, data): 
    db.reference(path, url=DB_URL).set(data) 

def push_data(path, data): 
    db.reference(path, url=DB_URL).push(data) 

def delete_data(path, item_id): 
    db.reference(f'{path}/{item_id}', url=DB_URL).delete() 

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
    config = get_data('/config') 
    mittente = config.get('email_mittente', '') 
    password = config.get('password_mittente', '') 
    destinatari_dict = get_data('/destinatari') 
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
    config = get_data('/config') 
    mittente = config.get('email_mittente', '') 
    password = config.get('password_mittente', '') 
    destinatari_dict = get_data('/destinatari') 
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
    col_si, col_no = st.columns(2) 
    if col_si.button("Sì, elimina corso"): 
        delete_data('/corsi', cid) 
        st.cache_data.clear()
        st.rerun() 
    if col_no.button("Annulla"): 
        st.rerun() 

@st.dialog("Conferma eliminazione scadenza")
def conferma_eliminazione_rapporto(rid):
    st.write("Vuoi davvero eliminare questa scadenza di cantiere?")
    col_si, col_no = st.columns(2)
    if col_si.button("Sì, elimina scadenza"):
        delete_data('/rapporti_cantiere', rid)
        st.cache_data.clear()
        st.rerun()
    if col_no.button("Annulla"):
        st.rerun()

# --- 8. INTERFACCIA UTENTE --- 
st.title("Guasti Gino Impianti S.r.l.") 

with st.sidebar: 
    st.header("🔄 Aggiornamento")
    auto_refresh = st.toggle("Abilita aggiornamento auto", value=True)
    if auto_refresh:
        st_autorefresh(interval=60000, key="datarefresh")
    st.divider()

    if st.button("🚪 Logout"): 
        st.session_state.authenticated = False 
        st.query_params.clear() 
        st.rerun() 
    st.header("⚙️ Impostazioni") 
    with st.expander("📧 Configurazione SMTP"): 
        with st.form("form_smtp"): 
            email_mit = st.text_input("Gmail Mittente", value=get_data('/config').get('email_mittente', '')) 
            pass_mit = st.text_input("Password App", value=get_data('/config').get('password_mittente', ''), type="password") 
            if st.form_submit_button("Salva Credenziali"): 
                set_data('/config/email_mittente', email_mit) 
                set_data('/config/password_mittente', pass_mit) 
                st.cache_data.clear()
                st.rerun() 
    with st.expander("👥 Destinatari"): 
        dest_attuali = get_data('/destinatari') 
        for d_id, d_dati in dest_attuali.items(): 
            col1, col2 = st.columns([3, 1]) 
            col1.write(d_dati.get('email', '')) 
            if col2.button("🗑️", key=f"del_{d_id}"): 
                delete_data('/destinatari', d_id) 
                st.cache_data.clear()
                st.rerun() 
        nuova_email = st.text_input("Aggiungi email:") 
        if st.button("Aggiungi"): 
            if "@" in nuova_email: 
                push_data('/destinatari', {"email": nuova_email}) 
                st.cache_data.clear()
                st.rerun() 
    st.divider() 
    
    # --- MODIFICA AGGIORNATA: Forzatura Refresh UI ---
    if st.button("🚀 Esegui Scansione", type="primary", use_container_width=True): 
        with st.spinner("Scansione in corso..."):
            oggi = datetime.today().date() 
            soglia = oggi + timedelta(days=30) 
            aggiornato = False
            
            # Scansione Corsi
            corsi = db.reference('/corsi', url=DB_URL).get() 
            if corsi: 
                for cid, dati in corsi.items(): 
                    try: 
                        d_scad = datetime.strptime(dati.get('data_scadenza', '2000-01-01'), "%Y-%m-%d").date() 
                        if d_scad <= soglia and not dati.get('notifica_inviata', False): 
                            esito = invia_email(dati.get('nominativo'), dati.get('corso'), dati.get('data_scadenza'))
                            if "Inviato" in esito:
                                db.reference(f'/corsi/{cid}', url=DB_URL).update({'notifica_inviata': True}) 
                                st.write(f"✅ Inviato: {dati.get('nominativo')}")
                                aggiornato = True
                    except Exception as e: st.error(f"Errore corso {cid}: {e}")
            
            # Scansione Rapporti
            rapporti = db.reference('/rapporti_cantiere', url=DB_URL).get()
            if rapporti:
                for rid, dati in rapporti.items():
                    try:
                        d_scad = datetime.strptime(dati.get('data_scadenza', '2000-01-01'), "%Y-%m-%d").date()
                        if d_scad <= soglia and not dati.get('notifica_inviata', False):
                            esito = invia_email_cantiere(dati.get('cantiere'), dati.get('parte'), dati.get('data_scadenza'))
                            if "Inviato" in esito:
                                db.reference(f'/rapporti_cantiere/{rid}', url=DB_URL).update({'notifica_inviata': True}) 
                                st.write(f"✅ Inviato: {dati.get('cantiere')}")
                                aggiornato = True
                    except Exception as e: st.error(f"Errore rapporto {rid}: {e}")
            
            if aggiornato:
                st.success("Operazione completata.")
                st.cache_data.clear() # Pulisce cache
                # TRUCCO: Forza un reload completo dell'URL per bypassare la cache browser/streamlit
                st.query_params["force_refresh"] = str(time.time())
                time.sleep(1)
                st.rerun() 
            else:
                st.info("Nessuna nuova scadenza trovata.")
         
    if st.button("🔄 Reset Mail Inviate"): 
        corsi = get_data('/corsi') 
        if corsi: 
            for cid, dati in corsi.items(): 
                db.reference(f'/corsi/{cid}', url=DB_URL).update({'notifica_inviata': False}) 
        rapporti = get_data('/rapporti_cantiere')
        if rapporti:
            for rid, dati in rapporti.items():
                db.reference(f'/rapporti_cantiere/{rid}', url=DB_URL).update({'notifica_inviata': False})
        st.cache_data.clear()
        st.rerun() 
    st.divider() 
    corsi_per_export = get_data('/corsi') 
    if corsi_per_export: 
        st.download_button("📥 Esporta Excel", 
                            data=esporta_excel(corsi_per_export), file_name="Registro.xlsx", 
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                            use_container_width=True) 

# --- MAIN --- 
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Registro Corsi",
    "📊 Tabella Corsi",
    "➕ Aggiungi Corso", 
    "⏳ Nuova Scadenza Cantiere",
    "🏗️ Scadenziario Cantieri"
]) 

opzioni_corsi = ["Preposto", "RLS", "Primo Soccorso", "Antincendio", 
"PLE", "Muletto", "Base 4H", "Specifica 12H", "DP13 Lavori in quota", 
"Altro"] 

with tab1: 
    corsi = get_data('/corsi') 
    c1, c2 = st.columns(2) 
    search = c1.text_input("🔍 Cerca") 
    filtro_stato = c2.selectbox("Filtra", ["Tutti", "🟢 IN CORSO", "⚠️ IN SCADENZA", "🔴 SCADUTO", "✅ Mail inviata"]) 
     
    with st.expander("✏️ Modifica o 🗑️ Elimina Corso"): 
        if corsi: 
            lista_corsi = ["Seleziona un corso..."] + [f"{d.get('nominativo')} - {d.get('corso')}" for cid, d in corsi.items()] 
            mappa_opzioni = {f"{d.get('nominativo')} - {d.get('corso')}": cid for cid, d in corsi.items()} 
            selezione = st.selectbox("Seleziona:", lista_corsi) 
            if selezione != "Seleziona un corso...": 
                cid_da_mod = mappa_opzioni[selezione] 
                dati_da_mod = corsi[cid_da_mod] 
                new_nom = st.text_input("Dipendente", value=dati_da_mod.get('nominativo', '')) 
                new_corso = st.text_input("Corso", value=dati_da_mod.get('corso', '')) 
                new_data = st.date_input("Data Svolgimento", value=datetime.strptime(dati_da_mod.get('data_svolto', datetime.today().strftime("%Y-%m-%d")), "%Y-%m-%d"), format="DD/MM/YYYY") 
                with st.form(f"form_modifica_{cid_da_mod}"): 
                    if st.form_submit_button("Salva Modifiche"): 
                        db.reference(f'/corsi/{cid_da_mod}', url=DB_URL).update({"nominativo": new_nom, "corso": new_corso, "data_svolto": str(new_data)}) 
                        st.cache_data.clear()
                        st.rerun() 

    st.divider() 
    oggi = datetime.today().date() 
    soglia = oggi + timedelta(days=30) 
    for cid, d in corsi.items(): 
        try: 
            d_scad = datetime.strptime(d['data_scadenza'], "%Y-%m-%d").date() 
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
    st.subheader("📊 Tabella dei Corsi Formativi")
    st.write("Visualizzazione in tempo reale dello stato di formazione di tutto il personale.")
    
    def colora_matrice(val):
        if val == "-" or pd.isna(val):
            return 'background-color: #f8f9fa; color: #adb5bd; text-align: center;'
        try:
            d_scad = datetime.strptime(val, "%d/%m/%Y").date()
            oggi_mat = datetime.today().date()
            soglia_mat = oggi_mat + timedelta(days=30)
            if d_scad < oggi_mat:
                return 'background-color: #f8d7da; color: #842029; font-weight: bold; text-align: center;'
            elif d_scad <= soglia_mat:
                return 'background-color: #fff3cd; color: #664d03; font-weight: bold; text-align: center;'
            else:
                return 'background-color: #d1e7dd; color: #0f5132; text-align: center;'
        except:
            return 'text-align: center;'

    corsi_matrice = get_data('/corsi')
    if corsi_matrice:
        dipendenti_unici = sorted(list(set(d.get('nominativo', '').strip() for d in corsi_matrice.values() if d.get('nominativo'))))
        corsi_base = [c for c in opzioni_corsi if c != "Altro"]
        corsi_db = list(set(d.get('corso', '').strip() for d in corsi_matrice.values() if d.get('corso')))
        colonne_corsi = sorted(list(set(corsi_base + corsi_db)))
        
        matrice_df = pd.DataFrame("-", index=dipendenti_unici, columns=colonne_corsi)
        
        for cid, d in corsi_matrice.items():
            dip = d.get('nominativo', '').strip()
            crs = d.get('corso', '').strip()
            scad_raw = d.get('data_scadenza', '')
            if dip and crs and scad_raw:
                try:
                    nuova_scad = datetime.strptime(scad_raw, "%Y-%m-%d").date()
                    nuova_scad_ita = nuova_scad.strftime("%d/%m/%Y")
                    valore_attuale = matrice_df.loc[dip, crs]
                    if valore_attuale == "-":
                        matrice_df.loc[dip, crs] = nuova_scad_ita
                    else:
                        scad_attuale = datetime.strptime(valore_attuale, "%d/%m/%Y").date()
                        if nuova_scad > scad_attuale:
                            matrice_df.loc[dip, crs] = nuova_scad_ita
                except:
                    continue
        
        col_l1, col_l2, col_l3, col_l4 = st.columns(4)
        col_l1.markdown("🟩 **Verde**: Corso Valido")
        col_l2.markdown("🟨 **Giallo**: In scadenza (30 gg)")
        col_l3.markdown("🟥 **Rosso**: Scaduto")
        col_l4.markdown("⬜ **Grigio**: Mai effettuato / Mancante")
        st.divider()
        
        try:
            matrice_stilizzata = matrice_df.style.map(colora_matrice)
        except AttributeError:
            matrice_stilizzata = matrice_df.style.applymap(colora_matrice)
            
        st.dataframe(
            matrice_stilizzata, 
            use_container_width=True,
            height=max(200, len(dipendenti_unici) * 40 + 50)
        )
    else:
        st.info("Nessun corso registrato nel database per poter generare la tabella.")

with tab3: 
    if 'nom_dipendente' not in st.session_state: st.session_state.nom_dipendente = "" 
    if 'form_key' not in st.session_state: st.session_state.form_key = 0 
    nom_input = st.text_input("Dipendente", value=st.session_state.nom_dipendente) 
    st.session_state.nom_dipendente = nom_input 

    with st.form(f"form_corso_{st.session_state.form_key}"): 
        scelta_add = st.selectbox("Corso", opzioni_corsi) 
        corso_add = st.text_input("Specifica nome corso") if scelta_add == "Altro" else scelta_add 
        data_s = st.date_input("Data Svolgimento", format="DD/MM/YYYY") 
        val = st.selectbox("Anni Validità", [1, 2, 3, 5, 10], index=3) 
        if st.form_submit_button("💾 Salva Corso"): 
            scadenza = data_s.replace(year=data_s.year + val) 
            push_data('/corsi', {"nominativo": st.session_state.nom_dipendente, "corso": corso_add, "data_svolto": str(data_s), "data_scadenza": str(scadenza), "notifica_inviata": False}) 
            st.session_state.form_key += 1 
            st.cache_data.clear()
            st.rerun() 

with tab4:
    st.subheader("⏳ Inserisci Nuova Scadenza Cantiere")
    with st.form("form_scadenza_cantiere"):
        nome_cantiere = st.text_input("Cantiere / Commessa")
        parte_cantiere = st.text_input("Parte di Cantiere / Opera da consegnare")
        data_scadenza = st.date_input("Data Scadenza Consegna", format="DD/MM/YYYY")
         
        if st.form_submit_button("💾 Salva Scadenza"):
            if nome_cantiere and parte_cantiere:
                nuova_scadenza = {
                    "cantiere": nome_cantiere,
                    "parte": parte_cantiere,
                    "data_scadenza": str(data_scadenza),
                    "notifica_inviata": False
                }
                push_data('/rapporti_cantiere', nuova_scadenza)
                st.success("Scadenza cantiere memorizzata correttamente!")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("Compila tutti i campi obbligatori (Cantiere e Parte di Cantiere)")

with tab5:
    st.subheader("🏗️ Scadenziario Consegne Cantieri")
    rapporti = get_data('/rapporti_cantiere')
     
    c3_1, c3_2 = st.columns(2)
    search_cantiere = c3_1.text_input("🔍 Cerca Cantiere o Componente", key="search_cantiere_input")
    filtro_stato_cant = c3_2.selectbox("Filtra Stato Consegna", ["Tutti", "🟢 IN CORSO", "⚠️ IN SCADENZA", "🔴 SCADUTO", "✅ Mail inviata"])
     
    st.divider()
    oggi = datetime.today().date()
    soglia = oggi + timedelta(days=30)
     
    if rapporti:
        for rid, d in rapporti.items():
            try:
                d_scad = datetime.strptime(d['data_scadenza'], "%Y-%m-%d").date()
                if d_scad < oggi: stato, colore = "🔴 SCADUTO", "red"
                elif d_scad <= soglia: stato, colore = "⚠️ IN SCADENZA", "orange"
                elif d.get('notifica_inviata', False): stato, colore = "✅ Mail inviata", "green"
                else: stato, colore = "🟢 IN CORSO", "blue"
                 
                match_ricerca = (search_cantiere.lower() in d.get('cantiere', '').lower()) or (search_cantiere.lower() in d.get('parte', '').lower())
                match_filtro = (filtro_stato_cant == "Tutti" or filtro_stato_cant == stato)
                 
                if match_ricerca and match_filtro:
                    with st.container(border=True):
                        cols = st.columns([2, 2, 2, 1, 0.5])
                        cols[0].markdown(f":{colore}[**Cantiere:** {d.get('cantiere')}]")
                        cols[1].markdown(f":{colore}[**Fase/Parte:** {d.get('parte')}]")
                        cols[2].markdown(f":{colore}[**Scadenza:** {d.get('data_scadenza')}]")
                        cols[3].markdown(f":{colore}[**{stato}**]")
                        if cols[4].button("🗑️", key=f"del_cantiere_{rid}"): 
                            conferma_eliminazione_rapporto(rid)
            except: continue
    else:
        st.info("Nessuna scadenza di cantiere presente nel database.")
