# --- 4. LOGICA EMAIL (VERSIONE PROFESSIONALE) ---
def invia_email(destinatario, nominativo, corso, data_scadenza):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from datetime import datetime

    # Configurazione credenziali (da personalizzare con i tuoi dati)
    mittente = "tua_email@esempio.com"
    password = "tua_password_app"
    
    # Formattazione data
    d_scad_ita = datetime.strptime(data_scadenza, "%Y-%m-%d").strftime("%d/%m/%Y")
    
    # Preparazione del messaggio
    msg = MIMEMultipart()
    msg['From'] = mittente
    msg['To'] = destinatario
    msg['Subject'] = f"⚠️ Notifica Scadenza Formazione: {corso} - {nominativo}"
    
    # Corpo HTML formale
    corpo = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #2c3e50;">Notifica di Scadenza Formazione</h2>
            <p>Buongiorno,</p>
            <p>con la presente si comunica che il seguente corso di formazione è in fase di scadenza:</p>
            <ul style="list-style-type: none; padding: 0;">
                <li><strong>Dipendente:</strong> {nominativo}</li>
                <li><strong>Corso:</strong> {corso}</li>
                <li><strong>Data di scadenza:</strong> <span style="color: #c0392b;"><strong>{d_scad_ita}</strong></span></li>
            </ul>
            <p>Si prega di provvedere alle necessarie attività di rinnovo o aggiornamento entro i termini previsti dalle normative vigenti.</p>
            <hr style="border: 0; border-top: 1px solid #ccc;">
            <p style="font-size: 0.9em; color: #7f8c8d;">
                <em>Comunicazione automatica generata dal sistema di gestione sicurezza.</em>
            </p>
        </body>
    </html>
    """
    
    msg.attach(MIMEText(corpo, 'html'))
    
    # Invio (Esempio per server Gmail)
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(mittente, password)
        server.send_message(msg)
        server.quit()
        print(f"Mail inviata con successo per {nominativo}")
    except Exception as e:
        print(f"Errore nell'invio della mail: {e}")
